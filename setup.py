# setup.py
try:
    from setuptools import Extension, setup, find_packages  # Added find_packages
    from Cython.Build import cythonize
    import glob
    from pathlib import Path
    import os
    import toml  # Added import for reading pyproject.toml

    def get_package_name():
        """Dynamically retrieve the package name from pyproject.toml or directory."""
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            pyproject = toml.load(pyproject_path)
            return pyproject.get("project", {}).get("name", os.path.basename(os.path.dirname(__file__))) 
        else:
            return Path(__file__).parent.name 

    def find_pyx_modules():
        """Dynamically find all .pyx files in the discovered packages."""
        packages = find_packages()  # Dynamically find all packages
        extensions = []
        for package in packages:
            package_dir = package.replace('.', '/')
            for pyx_file in Path(package_dir).rglob("*.pyx"):
                module_name = f"{package}.{pyx_file.stem}"
                extensions.append(
                    Extension(
                        module_name,
                        [str(pyx_file)],
                    )
                )
        return extensions

    extensions = cythonize(
        find_pyx_modules(), 
        language_level=3,
    )

    setup(
        name=get_package_name(),
        version="0.1.0",
        packages=find_packages(),
        ext_modules=extensions,
    )
except ImportError:
    pass
