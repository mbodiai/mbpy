import logging
import os
import platform
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which
from typing import Dict, List, Optional

from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn
import contextlib

logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(rich_tracebacks=True)])
log = logging.getLogger("build")


@dataclass
class SystemCSpecs:
    compiler_path: str
    compiler_version: str
    include_paths: List[str]
    system_type: str
    supports_c17: bool

    @classmethod
    def detect(cls) -> "SystemCSpecs":
        cc = os.getenv("CC") or which("cc") or which("gcc")
        if not cc:
            raise RuntimeError("No C compiler found")

        version_info = subprocess.check_output(
            [cc, "-x", "c", "-v", "-E", "/dev/null"], stderr=subprocess.STDOUT, text=True
        )

        includes = []
        capture = False
        for line in version_info.splitlines():
            if line.startswith("#include <...>"):
                capture = True
            elif line.startswith("End of search list"):
                capture = False
            elif capture and line.strip():
                includes.append(line.strip())

        return cls(
            compiler_path=cc,
            compiler_version=version_info.splitlines()[0],
            include_paths=includes,
            system_type=sys.platform,
            supports_c17="clang" in version_info.lower(),
        )


@dataclass
class ProjectCSpecs:
    abi_version: int = 14
    c_standard: int = 11
    shared_libs: bool = True
    build_parallel: bool = True
    source_paths: List[str] = field(default_factory=list)

    @classmethod
    def from_cmake(cls, cmake_path: Path) -> "ProjectCSpecs":
        if not cmake_path.exists():
            return cls()

        content = cmake_path.read_text()
        specs = cls()

        for line in content.splitlines():
            if "TREE_SITTER_ABI_VERSION" in line and "set(" in line.lower():
                with contextlib.suppress(ValueError):
                    specs.abi_version = int(line.split()[-1].rstrip(")"))

        return specs


@dataclass
class BuildConfig:
    system: SystemCSpecs
    project: ProjectCSpecs

    def get_cflags(self) -> str:
        std = "-std=c17" if self.system.supports_c17 else "-std=c11"
        return f"{std} -O3 -fPIC"

    def get_env(self) -> Dict[str, str]:
        return {
            "CC": self.system.compiler_path,
            "CFLAGS": self.get_cflags(),
        }



class SystemPackageManager:
    mode_check = "check"  # Check if installed, fail if not
    mode_install = "install"
    mode_report = "report"  # Only report what would be installed, no check (can run in any system)
    mode_report_installed = "report-installed"  # report installed and missing packages
    tool_name = None
    install_command = ""
    update_command = ""
    check_command = ""
    accepted_install_codes = [0]
    accepted_update_codes = [0]
    accepted_check_codes = [0, 1]

    def __init__(self, buildconfig):
        self._buildconfig = buildconfig
        self._active_tool = self._buildconfig.conf.get(
            "tools.system.package_manager:tool", default=self.get_default_tool()
        )
        self._sudo = self._buildconfig.conf.get("tools.system.package_manager:sudo", default=False, check_type=bool)
        self._sudo_askpass = self._buildconfig.conf.get(
            "tools.system.package_manager:sudo_askpass", default=False, check_type=bool
        )
        self._mode = self._buildconfig.conf.get("tools.system.package_manager:mode", default=self.mode_check)
        self._arch = (
            self._buildconfig.settings_build.get_safe("arch")

        )
        self._arch_names = {}
        self._arch_separator = ""

    def get_default_tool(self):
        os_name = platform.system()
        if os_name in ["Linux", "FreeBSD"]:
            import distro

            os_name = distro.id() or os_name
        elif os_name == "Windows" and self._buildconfig.settings.get_safe("os.subsystem") == "msys2":
            os_name = "msys2"
        manager_mapping = {
            "apt-get": ["Linux", "ubuntu", "debian", "raspbian", "linuxmint", "astra", "elbrus", "altlinux", "pop"],
            "apk": ["alpine"],
            "yum": ["pidora", "scientific", "xenserver", "amazon", "oracle", "amzn", "almalinux", "rocky"],
            "dnf": ["fedora", "rhel", "centos", "mageia", "nobara"],
            "brew": ["Darwin"],
            "pacman": ["arch", "manjaro", "msys2", "endeavouros"],
            "choco": ["Windows"],
            "zypper": ["opensuse", "sles"],
            "pkg": ["freebsd"],
            "pkgutil": ["Solaris"],
        }
        # first check exact match of name
        for tool, distros in manager_mapping.items():
            if os_name in distros:
                return tool
        # in case we did not detect any exact match, check
        # if the name is contained inside the returned distro name
        # like for opensuse, that can have opensuse-version names
        for tool, distros in manager_mapping.items():
            for d in distros:
                if d in os_name:
                    return tool

        # No default package manager was found for the system,
        # so notify the user
        self._buildconfig.output.info(
            f"A default system package manager couldn't be found for {os_name}, "
            "system packages will not be installed."
        )
        return None

    def get_package_name(self, package, host_package=True):
        # Only if the package is for building, for example a library,
        # we should add the host arch when cross building.
        # If the package is a tool that should be installed on the current build
        # machine we should not add the arch.
        if self._arch in self._arch_names:
            return f"{package}{self._arch_separator}{self._arch_names.get(self._arch)}"
        return package

    @property
    def sudo_str(self):
        sudo = "sudo " if self._sudo else ""
        askpass = "-A " if self._sudo and self._sudo_askpass else ""
        return f"{sudo}{askpass}"

    def run(self, method, *args, **kwargs):
        if self._active_tool == self.__class__.tool_name:
            return method(*args, **kwargs)
        return None

    def _buildconfig_run(self, command, accepted_returns):
        # When checking multiple packages, this is too noisy
        ret = self._buildconfig.run(command, ignore_errors=True, quiet=True)
        if ret not in accepted_returns:
            raise RuntimeError(f"Command '{command}' failed")
        return ret

    def install_substitutes(self, *args, **kwargs):
        """Will try to call the install() method with  several lists of packages passed as a variable number of parameters.
        
        This is useful if, for example, the names of the
        packages are different from one distro or distro version to another. For example,
        ``libxcb`` for ``Apt`` is named ``libxcb-util-dev`` in Ubuntu >= 15.0 and ``libxcb-util0-dev``
        for other versions. You can call to:

           .. code-block:: python

            # will install the first list of packages that succeeds in the installation
            Apt.install_substitutes(["libxcb-util-dev"], ["libxcb-util0-dev"])

        :param packages_alternatives: try to install the list of packages passed as a parameter.
        :param update: try to update the package manager database before checking and installing.
        :param check: check if the packages are already installed before installing them.
        :return: the return code of the executed package manager command.
        """
        return self.run(self._install_substitutes, *args, **kwargs)

    def install(self, *args, **kwargs):
        """Will try to install the list of packages passed as a parameter.
        
        Its behaviour is affected by the value of ``tools.system.package_manager:mode``
        :ref:`configuration<conan_tools_system_package_manager_config>`.

        :param packages: try to install the list of packages passed as a parameter.
        :param update: try to update the package manager database before checking and installing.
        :param check: check if the packages are already installed before installing them.
        :return: the return code of the executed package manager command.
        """
        return self.run(self._install, *args, **kwargs)

    def update(self, *args, **kwargs):
        """Update the system package manager database.
        
        Its behaviour is affected by
        the value of ``tools.system.package_manager:mode``
        :ref:`configuration<conan_tools_system_package_manager_config>`.

        :return: the return code of the executed package manager update command.
        """
        return self.run(self._update, *args, **kwargs)

    def check(self, *args, **kwargs):
        """Check if the list of packages passed as parameter are already installed.

        :param packages: list of packages to check.
        :return: list of packages from the packages argument that are not installed in the system.
        """
        return self.run(self._check, *args, **kwargs)

    def _install_substitutes(self, *packages_substitutes, update=False, check=True, **kwargs):
        errors = []
        for packages in packages_substitutes:
            try:
                return self.install(packages, update, check, **kwargs)
            except RuntimeError as e:
                errors.append(e)

        for error in errors:
            self._buildconfig.output.warning(str(error))
        raise RuntimeError("None of the installs for the package substitutes succeeded.")

    def _install(self, packages, update=False, check=True, host_package=True, **kwargs):
        pkgs = self._buildconfig.system_requires.setdefault(self._active_tool, {})
        install_pkgs = pkgs.setdefault("install", [])
        install_pkgs.extend(p for p in packages if p not in install_pkgs)
        if self._mode == self.mode_report:
            return

        if check or self._mode in (self.mode_check, self.mode_report_installed):
            packages = self.check(packages, host_package=host_package)
            missing_pkgs = pkgs.setdefault("missing", [])
            missing_pkgs.extend(p for p in packages if p not in missing_pkgs)

        if self._mode == self.mode_report_installed:
            return

        if self._mode == self.mode_check and packages:
            raise RuntimeError(
                "System requirements: '{0}' are missing but can't install "  # noqa: S608
                "because tools.system.package_manager:mode is '{1}'."
                "Please update packages manually or set "
                "'tools.system.package_manager:mode' "
                "to '{2}' in the [conf] section of the profile, "
                "or in the command line using "
                "'-c tools.system.package_manager:mode={2}'".format(
                    ", ".join(packages), self.mode_check, self.mode_install
                )
            )
        if packages:
            if update:
                self.update()

            packages_arch = [self.get_package_name(package, host_package=host_package) for package in packages]
            if packages_arch:
                command = self.install_command.format(
                    sudo=self.sudo_str, tool=self.tool_name, packages=" ".join(packages_arch), **kwargs
                )
                return self._buildconfig_run(command, self.accepted_install_codes)
            return None

        self._buildconfig.output.info("System requirements: {} already " "installed".format(" ".join(packages)))
        return None

    def _update(self):
        # we just update the package manager database in case we are in 'install mode'
        # in case we are in check mode just ignore
        if self._mode == self.mode_install:
            command = self.update_command.format(sudo=self.sudo_str, tool=self.tool_name)
            return self._buildconfig_run(command, self.accepted_update_codes)
        return None

    def _check(self, packages, host_package=True):
        missing = [
            pkg for pkg in packages if self.check_package(self.get_package_name(pkg, host_package=host_package)) != 0
        ]
        return missing

    def check_package(self, package):
        command = self.check_command.format(tool=self.tool_name, package=package)
        return self._buildconfig_run(command, self.accepted_check_codes)


class Apt(SystemPackageManager):
    tool_name = "apt-get"
    install_command = "{sudo}{tool} install -y {recommends}{packages}"
    update_command = "{sudo}{tool} update"
    check_command = "dpkg-query -W -f='${{Status}}' {package} | grep -q \"ok installed\""

    def __init__(self, buildconfig, arch_names=None):
        """Apt package manager tool.
        
        :param buildconfig: The current recipe object. Always use ``self``.
        :param arch_names: This argument maps the Conan architecture setting with the package manager
                           tool architecture names. It is ``None`` by default, which means that it will use a
                           default mapping for the most common architectures. For example, if you are using
                           ``x86_64`` Conan architecture setting, it will map this value to ``amd64`` for *Apt* and
                           try to install the ``<package_name>:amd64`` package.
        """
        super(Apt, self).__init__(buildconfig)
        self._arch_names = (
            {
                "x86_64": "amd64",
                "x86": "i386",
                "ppc32": "powerpc",
                "ppc64le": "ppc64el",
                "armv7": "arm",
                "armv7hf": "armhf",
                "armv8": "arm64",
                "s390x": "s390x",
            }
            if arch_names is None
            else arch_names
        )

        self._arch_separator = ":"

    def install(self, packages, update=False, check=True, recommends=False, host_package=True):
        """Manage the Apt package manager.
        
        Will try to install the list of packages passed as a parameter. Its
        behaviour is affected by the value of ``tools.system.package_manager:mode``
        :ref:`configuration<conan_tools_system_package_manager_config>`.

        :param packages: try to install the list of packages passed as a parameter.
        :param update: try to update the package manager database before checking and installing.
        :param check: check if the packages are already installed before installing them.
        :param host_package: install the packages for the host machine architecture (the machine
               that will run the software), it has an effect when cross building.
        :param recommends: if the parameter ``recommends`` is ``False`` it will add the
               ``'--no-install-recommends'`` argument to the *apt-get* command call.
        :return: the return code of the executed apt command.
        """
        recommends_str = "" if recommends else "--no-install-recommends "
        return super().install(
            packages, update=update, check=check, host_package=host_package, recommends=recommends_str
        )


class Yum(SystemPackageManager):
    tool_name = "yum"
    install_command = "{sudo}{tool} install -y {packages}"
    update_command = "{sudo}{tool} check-update -y"
    check_command = "rpm -q {package}"
    accepted_update_codes = [0, 100]

    def __init__(self, buildconfig, arch_names=None):
        """Manage the Yum package manager.
        
        :param buildconfig: the current recipe object. Always use ``self``.
        :param arch_names: this argument maps the Conan architecture setting with the package manager
                           tool architecture names. It is ``None`` by default, which means that it will use a
                           default mapping for the most common architectures. For example, if you are using
                           ``x86`` Conan architecture setting, it will map this value to ``i?86`` for *Yum* and
                           try to install the ``<package_name>.i?86`` package.
        """
        super(Yum, self).__init__(buildconfig)
        self._arch_names = (
            {
                "x86_64": "x86_64",
                "x86": "i?86",
                "ppc32": "powerpc",
                "ppc64le": "ppc64le",
                "armv7": "armv7",
                "armv7hf": "armv7hl",
                "armv8": "aarch64",
                "s390x": "s390x",
            }
            if arch_names is None
            else arch_names
        )
        self._arch_separator = "."


class Dnf(Yum):
    tool_name = "dnf"


class Brew(SystemPackageManager):
    tool_name = "brew"
    install_command = "{sudo}{tool} install {packages}"
    update_command = "{sudo}{tool} update"
    check_command = 'test -n "$({tool} ls --versions {package})"'


class Pkg(SystemPackageManager):
    tool_name = "pkg"
    install_command = "{sudo}{tool} install -y {packages}"
    update_command = "{sudo}{tool} update"
    check_command = "{tool} info {package}"


class PkgUtil(SystemPackageManager):
    tool_name = "pkgutil"
    install_command = "{sudo}{tool} --install --yes {packages}"
    update_command = "{sudo}{tool} --catalog"
    check_command = 'test -n "`{tool} --list {package}`"'


class Chocolatey(SystemPackageManager):
    tool_name = "choco"
    install_command = "{tool} install --yes {packages}"
    update_command = "{tool} outdated"
    check_command = "{tool} search --local-only --exact {package} | " 'findstr /c:"1 packages installed."'


if __name__ == "__main__":

    def build_languages(config: BuildConfig):
        with Progress() as progress:
            task = progress.add_task("Building...", total=100)

            os.environ.update(config.get_env())
            progress.advance(task, 20)

            out_lib = Path("tree_sitter_languages")
            out_lib = out_lib / ("languages.dll" if sys.platform == "win32" else "languages.so")

            try:
                from tree_sitter import Language

                Language.build_library(str(out_lib), config.project.source_paths)
                progress.advance(task, 80)
                log.info(f"Successfully built {out_lib}")
            except Exception as e:
                log.error(f"Build failed: {e}")
                raise


    try:
        system_specs = SystemCSpecs.detect()
        project_specs = ProjectCSpecs.from_cmake(Path("CMakeLists.txt"))
        config = BuildConfig(system_specs, project_specs)
        build_languages(config)
    except Exception as e:
        log.error("Build failed", exc_info=True)
        sys.exit(1)