# setup.py
try:
    from setuptools import Extension, setup, find_packages
    from Cython.Build import cythonize
    from pathlib import Path
    import os
    import toml

    def get_package_name():
        """Dynamically retrieve the package name from pyproject.toml or directory."""
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            pyproject = toml.load(pyproject_path)
            pkg_name = pyproject.get("project", {}).get("name", os.path.basename(os.path.dirname(__file__)))
            print(f"Package name from pyproject.toml: {pkg_name}")
            return pkg_name
        else:
            pkg_name = Path(__file__).parent.name
            print(f"Package name from directory: {pkg_name}")
            return pkg_name

    def find_pyx_modules():
        """Dynamically find all .pyx files in the discovered packages."""
        package_name = get_package_name()
        package_dir = Path("tmp") / package_name
        extensions = []
        
        if package_dir.exists():
            print(f"Searching for .pyx files in {package_dir}")
            for pyx_file in package_dir.rglob("*.pyx"):
                print(f"Found .pyx file: {pyx_file}")
                if pyx_file.stem == "__init__":
                    continue
                module_name = f"{package_name}.{'.'.join(pyx_file.relative_to(package_dir.parent).with_suffix('').parts)}"
                print(f"Adding extension module: {module_name}")
                extensions.append(
                    Extension(module_name, [str(pyx_file)])
                )
        else:
            print(f"Package directory {package_dir} does not exist.")
        return extensions

    extensions = cythonize(
        find_pyx_modules(),
        language_level=3,
    )

    setup(
        name=get_package_name(),
        version="0.0.5",
        package_dir={get_package_name(): f"tmp/{get_package_name()}"},
        packages=[get_package_name()],
        ext_modules=extensions,
    )
except ImportError as e:
    print(f"ImportError: {e}")
    pass