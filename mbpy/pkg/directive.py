# Ensure the tmp/mbpy directory is correctly referenced
import os
from pathlib import Path

def add_auto_cpdef_to_package(package_path, outdir):
    """Add the `# cython: auto_cpdef=True` directive to the top of all `.py` files in the given package.

    :param package_path: Path to the package directory.
    """
    package_path = Path(package_path)
    directive = "# cython: auto_cpdef=True\n"
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    outpkg = outdir / package_path.name
    for f in package_path.glob("**/*.py"):
        if "venv" in str(f.resolve()) or "site-packages" in str(f.resolve()):
            continue
        if f.name in ("__init__.py", "__main__.py", "setup.py","conf.py"):
            continue
        out_file_path = outpkg / f.relative_to(package_path)
        out_file_path = out_file_path.with_suffix(".pyx")
        out_file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lines = f.read_text(encoding='utf-8').splitlines(True)
            with out_file_path.open("w", encoding='utf-8') as out:
                out.write(directive)
                out.writelines(lines)
        except Exception as e:
            print(f"Error processing {f}: {e}")
            continue

