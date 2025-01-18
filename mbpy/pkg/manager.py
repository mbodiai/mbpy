# # Copyright 2024 Marimo. All rights reserved.
# from __future__ import annotations

# import abc
# import json
# import logging
# import subprocess
# import sys
# from typing import List, Optional

# from mbpy.helpers._env import split_packages
# from mbpy.pkg.dependency import DependencyManager

# PY_EXE = sys.executable


# LOGGER = logging.getLogger(__name__)


# @dataclass
# class PackageDescription:
#     name: str
#     version: str


# class PackageManager(abc.ABC):
#     """Interface for a package manager that can install packages."""

#     name: str
#     docs_url: str

#     def __init__(self) -> None:
#         self._attempted_packages: set[str] = set()

#     @abc.abstractmethod
#     def module_to_package(self, module_name: str) -> str:
#         """Canonicalizes a module name to a package name."""
#         ...

#     @abc.abstractmethod
#     def package_to_module(self, package_name: str) -> str:
#         """Canonicalizes a package name to a module name."""
#         ...

#     def is_manager_installed(self) -> bool:
#         """Is the package manager is installed on the user machine?"""
#         if DependencyManager.which(self.name):
#             return True
#         LOGGER.error(
#             f"{self.name} is not available. " f"Check out the docs for installation instructions: {self.docs_url}"  # noqa: E501
#         )
#         return False

#     @abc.abstractmethod
#     async def _install(self, package: str) -> bool:
#         """Installation logic."""
#         ...

#     async def install(self, package: str, version: Optional[str]) -> bool:
#         """Attempt to install a package that makes this module available.

#         Returns True if installation succeeded, else False.
#         """
#         self._attempted_packages.add(package)
#         return await self._install(append_version(package, version))

#     @abc.abstractmethod
#     async def uninstall(self, package: str) -> bool:
#         """Attempt to uninstall a package.

#         Returns True if the package was uninstalled, else False.
#         """
#         ...

#     def attempted_to_install(self, package: str) -> bool:
#         """True iff package installation was previously attempted."""
#         return package in self._attempted_packages

#     def should_auto_install(self) -> bool:
#         """Should this package manager auto-install packages."""
#         return False

#     def run(self, command: list[str]) -> bool:
#         if not self.is_manager_installed():
#             return False
#         proc = subprocess.run(command)  # noqa: ASYNC101
#         return proc.returncode == 0

#     def update_notebook_script_metadata(
#         self,
#         filepath: str,
#         *,
#         packages_to_add: Optional[List[str]] = None,
#         packages_to_remove: Optional[List[str]] = None,
#         import_namespaces_to_add: Optional[List[str]] = None,
#         import_namespaces_to_remove: Optional[List[str]] = None,
#     ) -> None:
#         del (
#             filepath,
#             packages_to_add,
#             packages_to_remove,
#             import_namespaces_to_add,
#             import_namespaces_to_remove,
#         )
#         """
#         Add or remove inline script metadata metadata
#         in the marimo notebook.

#         For packages_to_add, packages_to_remove, we use the package name as-is.
#         For import_namespaces_to_add, import_namespaces_to_remove, we canonicalize
#         to the module name based on popular packages on PyPI.

#         This follows PEP 723 https://peps.python.org/pep-0723/
#         """
#         return

#     @abc.abstractmethod
#     def list_packages(self) -> List[PackageDescription]:
#         """List installed packages."""
#         ...

#     def alert_not_installed(self) -> None:
#         """Alert the user that the package manager is not installed."""
#         Alert(
#             title="Package manager not installed",
#             description=(f"{self.name} is not available on your machine."),
#             variant="danger",
#         ).broadcast()


# class CanonicalizingPackageManager(PackageManager):
#     """Base class for package managers.

#     Has a heuristic for mapping from package names to module names and back,
#     using a registry of well-known packages and basic rules for package
#     names.

#     Subclasses needs to implement _construct_module_name_mapping.
#     """

#     def __init__(self) -> None:
#         # Initialized lazily
#         self._module_name_to_repo_name: dict[str, str] | None = None
#         self._repo_name_to_module_name: dict[str, str] | None = None
#         super().__init__()

#     @abc.abstractmethod
#     def _construct_module_name_mapping(self) -> dict[str, str]: ...

#     def _initialize_mappings(self) -> None:
#         if self._module_name_to_repo_name is None:
#             self._module_name_to_repo_name = self._construct_module_name_mapping()

#         if self._repo_name_to_module_name is None:
#             self._repo_name_to_module_name = {v: k for k, v in self._module_name_to_repo_name.items()}

#     def module_to_package(self, module_name: str) -> str:
#         """Canonicalizes a module name to a package name on PyPI."""
#         if self._module_name_to_repo_name is None:
#             self._initialize_mappings()
#         assert self._module_name_to_repo_name is not None

#         if module_name in self._module_name_to_repo_name:
#             return self._module_name_to_repo_name[module_name]
#         else:
#             return module_name.replace("_", "-")

#     def package_to_module(self, package_name: str) -> str:
#         """Canonicalizes a package name to a module name."""
#         if self._repo_name_to_module_name is None:
#             self._initialize_mappings()
#         assert self._repo_name_to_module_name is not None

#         return (
#             self._repo_name_to_module_name[package_name]
#             if package_name in self._repo_name_to_module_name
#             else package_name.replace("-", "_")
#         )


# class PypiPackageManager(CanonicalizingPackageManager):
#     def _construct_module_name_mapping(self) -> dict[str, str]:
#         return module_name_to_pypi_name()

#     def _list_packages_from_cmd(
#         self, cmd: List[str]
#     ) -> List[PackageDescription]:
#         if not self.is_manager_installed():
#             return []
#         proc = subprocess.run(cmd, capture_output=True, text=True)
#         if proc.returncode != 0:
#             return []
#         try:
#             packages = json.loads(proc.stdout)
#             return [
#                 PackageDescription(name=pkg["name"], version=pkg["version"])
#                 for pkg in packages
#             ]
#         except json.JSONDecodeError:
#             return []


# class PipPackageManager(PypiPackageManager):
#     name = "pip"
#     docs_url = "https://pip.pypa.io/"

#     async def _install(self, package: str) -> bool:
#         return self.run(
#             ["pip", "--python", PY_EXE, "install", *split_packages(package)]
#         )

#     async def uninstall(self, package: str) -> bool:
#         return self.run(
#             [
#                 "pip",
#                 "--python",
#                 PY_EXE,
#                 "uninstall",
#                 "-y",
#                 *split_packages(package),
#             ]
#         )

#     def list_packages(self) -> List[PackageDescription]:
#         cmd = ["pip", "--python", PY_EXE, "list", "--format=json"]
#         return self._list_packages_from_cmd(cmd)


# class UvPackageManager(PypiPackageManager):
#     name = "uv"
#     docs_url = "https://docs.astral.sh/uv/"

#     async def _install(self, package: str) -> bool:
#         return self.run(
#             ["uv", "pip", "install", *split_packages(package), "-p", PY_EXE]
#         )

#     def update_notebook_script_metadata(
#         self,
#         filepath: str,
#         *,
#         packages_to_add: Optional[List[str]] = None,
#         packages_to_remove: Optional[List[str]] = None,
#         import_namespaces_to_add: Optional[List[str]] = None,
#         import_namespaces_to_remove: Optional[List[str]] = None,
#     ) -> None:
#         packages_to_add = packages_to_add or []
#         packages_to_remove = packages_to_remove or []
#         import_namespaces_to_add = import_namespaces_to_add or []
#         import_namespaces_to_remove = import_namespaces_to_remove or []

#         packages_to_add = packages_to_add + [
#             self.module_to_package(im) for im in import_namespaces_to_add
#         ]
#         packages_to_remove = packages_to_remove + [
#             self.module_to_package(im) for im in import_namespaces_to_remove
#         ]

#         if not packages_to_add and not packages_to_remove:
#             return

#         version_map = self._get_version_map()

#         def _is_installed(package: str) -> bool:
#             without_brackets = package.split("[")[0]
#             return without_brackets.lower() in version_map

#         def _maybe_add_version(package: str) -> str:
#             # Skip marimo
#             if package == "marimo":
#                 return package
#             without_brackets = package.split("[")[0]
#             version = version_map.get(without_brackets.lower())
#             if version:
#                 return f"{package}=={version}"
#             return package

#         # Filter to packages that are found in "uv pip list"
#         packages_to_add = [
#             _maybe_add_version(im)
#             for im in packages_to_add
#             if _is_installed(im)
#         ]

#         if packages_to_add:
#             self.run(
#                 ["uv", "--quiet", "add", "--script", filepath]
#                 + packages_to_add
#             )
#         if packages_to_remove:
#             self.run(
#                 ["uv", "--quiet", "remove", "--script", filepath]
#                 + packages_to_remove
#             )

#     def _get_version_map(self) -> dict[str, str]:
#         packages = self.list_packages()
#         return {pkg.name: pkg.version for pkg in packages}

#     async def uninstall(self, package: str) -> bool:
#         return self.run(
#             ["uv", "pip", "uninstall", *split_packages(package), "-p", PY_EXE]
#         )

#     def list_packages(self) -> List[PackageDescription]:
#         cmd = ["uv", "pip", "list", "--format=json", "-p", PY_EXE]
#         return self._list_packages_from_cmd(cmd)


# class RyePackageManager(PypiPackageManager):
#     name = "rye"
#     docs_url = "https://rye.astral.sh/"

#     async def _install(self, package: str) -> bool:
#         return self.run(["rye", "add", *split_packages(package)])

#     async def uninstall(self, package: str) -> bool:
#         return self.run(["rye", "remove", *split_packages(package)])

#     def list_packages(self) -> List[PackageDescription]:
#         cmd = ["rye", "list", "--format=json"]
#         return self._list_packages_from_cmd(cmd)


# class PoetryPackageManager(PypiPackageManager):
#     name = "poetry"
#     docs_url = "https://python-poetry.org/docs/"

#     async def _install(self, package: str) -> bool:
#         return self.run(
#             ["poetry", "add", "--no-interaction", *split_packages(package)]
#         )

#     async def uninstall(self, package: str) -> bool:
#         return self.run(
#             ["poetry", "remove", "--no-interaction", *split_packages(package)]
#         )

#     def _list_packages_from_cmd(
#         self, cmd: List[str]
#     ) -> List[PackageDescription]:
#         if not self.is_manager_installed():
#             return []
#         proc = subprocess.run(cmd, capture_output=True, text=True)
#         if proc.returncode != 0:
#             return []

#         # Each line in package_lines is of the form
#         # package_name    version_string      some more arbitrary text
#         #
#         # For each line, extract the package_name and version_string, ignoring
#         # the rest of the text.
#         package_lines = proc.stdout.splitlines()
#         packages = []
#         for line in package_lines:
#             parts = line.split()
#             if len(parts) < 2:
#                 continue
#             packages.append(
#                 PackageDescription(name=parts[0], version=parts[1])
#             )
#         return packages

#     def list_packages(self) -> List[PackageDescription]:
#         cmd = ["poetry", "show", "--no-dev"]
#         return self._list_packages_from_cmd(cmd)
