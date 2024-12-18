
import asyncio
import logging
import re
from contextlib import chdir
from inspect import cleandoc
from inspect import getdoc as inspect_getdoc
from pydoc import getdoc as pydoc_getdoc
from pydoc import locate, splitdoc, synopsis
from typing import Any, Dict, Tuple

from typing_extensions import Final

from mbpy.commands import run
from mbpy.utils.collect import PathLike
from mbpy.utils.static import SPHINX_API, SPHINX_CONF, SPHINX_INDEX, SPHINX_MAKEFILE

visit: set = set()


CONTROL_ESCAPE: Final = {
    7: "\\a",
    8: "\\b",
    11: "\\v",
    12: "\\f",
    13: "\\r",
}
def escape_control_codes(
    text: str,
    _translate_table: Dict[int, str] = CONTROL_ESCAPE,
) -> str:
    r"""Replace control codes with their "escaped" equivalent in the given text.
    
    (e.g. "\b" becomes "\\b")

    Args:
        text (str): A string possibly containing control codes.

    Returns:
        str: String with control codes replaced with their escaped version.
    """
    return text.translate(_translate_table)     



visit: set = set()


def first_paragraph(doc: str) -> Tuple[str, str, str]:
    """Splits the docstring into the first paragraph and the rest."""
    return doc.partition("\n\n") 



async def get_formatted_doc(obj: Any, verbose: bool = False) -> None | str:
    """Extract the docstring of an object, process it, and return it.
    
    The processing consists of cleaning up the docstring's indentation,
    taking only its first paragraph if `verbose` is False,
    and escaping its control codes.

    Args:
        obj (Any): The object to get the docstring from.
        verbose (bool): Whether to include the full docstring.

    Returns:
        Optional[str]: The processed docstring, or None if no docstring was found.
    """
    docs = pydoc_getdoc(obj)
    if docs is None:
        docs = inspect_getdoc(obj) or ""
    if not docs:
        return None

    docs = cleandoc(docs).strip()
    if not verbose:
        docs, _, _ = first_paragraph(docs)
    return escape_control_codes(docs)


async def brief_summary(obj: object) -> Tuple[str, str]:
    """Extracts the first sentence (brief) and returns the.

    Args:
        obj (object): The object from which to extract the docstring.

    Returns:
        Tuple[str, str]: A tuple containing the summary and the remaining documentation.
                         Both elements are empty strings if no docstring is found.
    """
    doc = pydoc_getdoc(obj)
    if not doc:
        doc = inspect_getdoc(obj) or ""

    if not doc:
        # Attempt to locate the object and get a synopsis
        full_name = f"{getattr(obj, '__module__', '')}.{getattr(obj, '__qualname__', '')}"
        try:
            located = locate(full_name, forceload=True)
            if located:
                if hasattr(located, "__file__"):
                    doc = synopsis(located.__file__)
                elif hasattr(obj, "__file__"):
                    doc = synopsis(obj.__file__)
        except Exception as e:
            logging.debug(f"Failed to locate synopsis for {full_name}: {e}")
            doc = ""

    if not doc:
        # Fallback to get_formatted_doc with verbose=True
        formatted_doc = await get_formatted_doc(obj, verbose=True)
        if formatted_doc:
            doc = formatted_doc

    # If doc is still empty, set to empty string to avoid None
    if not doc:
        doc = ""

    # Split the docstring into summary and remaining parts
    summary, remaining = splitdoc(doc)
    if not summary or not remaining:
        # Attempt to split manually using first_paragraph
        summary, sep, remaining = first_paragraph(doc)
        summary = summary.strip()
        remaining = remaining.strip()

    # Ensure both summary and remaining are strings
    summary = summary if summary else ""
    remaining = remaining if remaining else ""

    return summary, remaining

async def setup_sphinx_docs(
    *, docs_dir: PathLike, project_name: str, author: str, description: str, source_dir: PathLike,
) -> None:
    """Set up Sphinx documentation."""
    docs_path = PathLike(docs_dir).resolve()
    source_path = PathLike(source_dir)
    modules = [f.stem for f in source_path.glob("*.py") if f.stem != "__init__"]

    # Generate index.rst
    rst_content = SPHINX_INDEX.format(
        project_name=project_name,
        author=author,
        description=description,
        modules=modules,
    )
    output_path = PathLike(docs_dir) / "index.rst"
    output_path.write_text(rst_content)
    logging.info(f"Generated {output_path}")

    await generate_sphinx_docs(project_dir=source_dir, docs_dir=docs_dir)
    # Add subdirectories to the TOC

    conf_content = SPHINX_CONF.format(
        project_name=project_name, author=author, path=source_dir,
    )
    (docs_path / "conf.py").write_text(conf_content)
    logging.info(f"Generated {docs_path / 'conf.py'}")

    # Create Makefile
    (docs_path / "Makefile").write_text(SPHINX_MAKEFILE)
    logging.info(f"Generated {docs_path / 'Makefile'}")

    # Create api.rst
    api_content = SPHINX_API.format(
        project_name=project_name,
        module_name=project_name,
    )
    (docs_path / "api.rst").write_text(api_content)
    logging.info(f"Generated {docs_path / 'api.rst'}")

    # Build the HTML documentation
    with chdir(docs_path):
        run("make html")


async def generate_sphinx_docs(project_dir: PathLike, docs_dir: PathLike) -> None:
    """Generate Sphinx-compatible `.rst` files for all directories and Python modules.

    Args:
        project_dir (PathLike): The base directory of the repository.
        docs_dir (PathLike): The output directory for the Sphinx `.rst` files.
    """
    rel_path = PathLike(project_dir).relative_to(project_dir)
    rst_path = PathLike(docs_dir) / rel_path
    rst_path.mkdir(parents=True, exist_ok=True)

    # Create index.rst for the current directory
    index_rst = rst_path / "index.rst"
    children = [
        f
        for f in project_dir.iterdir()
        if f.is_dir() or (f.is_file() and f.suffix == ".py")
    ]
    with index_rst.open("w") as f:
        # Write the title and TOC configuration
        title = (
            f"{rel_path} Documentation" if rel_path != "." else "Project Documentation"
        )
        f.write(f"{title}\n")
        f.write("=" * len(title) + "\n\n")
        f.write(".. toctree::\n")
        f.write("   :maxdepth: 2\n")
        f.write("   :caption: Contents:\n\n")
        f.write("   api\n")
        f.write("   recipes\n\n")
        for child in children:
            f.write(f"   {child.stem}\n")

        # Add autosummary for package levels
        f.write("\n.. autosummary::\n")
        f.write("   :toctree: _autosummary\n\n")
        for child in children:
            if child.is_dir() or (child.is_file() and child.suffix == ".py"):
                f.write(f"   {child.stem}\n")

    for file in children:
        if file.is_dir() and not any(
            f.name.endswith(".md") or f.name.endswith(".py") for f in file.iterdir()
        ):
            continue
        if file.is_dir():
            package_name = file.name
            package_file = file / "__init__.py"
            if not package_file.exists():
                package_file.touch()
            if package_file.read_text().strip() == "":
                package_file.write_text(f"""{await one_liner(package_name, openai=True)}
                                            
{await summary(package_name)}

{await outline(package_name)}""")
            await generate_sphinx_docs(project_dir=file, docs_dir=docs_dir)

        elif file.is_file() and file.suffix == ".py":
            module_name = file.stem
            rst_file = rst_path / f"{module_name}.rst"
            with rst_file.open("w") as f:
                f.write(f"{module_name.capitalize()} Module\n")
                f.write("=" * len(f"{module_name.capitalize()} Module") + "\n\n")
                f.write(".. code-block:: python\n\n")
                f.write(
                    f"    from {rel_path.replace('/', '.')}.{module_name} import *\n\n",
                )
                f.write(f"    {one_liner(module_name)}\n\n")
                f.write(f"    {summary(module_name)}\n\n")
                f.write(f"    {outline(module_name)}\n\n")

            with index_rst.open("a") as f:
                f.write(f"   {module_name}\n")


async def one_liner(package_name: str, openai: bool = False):
    """Generate a one-liner description for the package."""
    return await get_formatted_doc(locate(package_name), verbose=False)


async def summary(package_name: str):
    """Generate a summary for the package."""
    return await one_liner(package_name)


async def outline(package_name: str):
    """Generate an outline for the package."""
    return await one_liner(package_name)


async def clean_code(code: str) -> str:
    """Cleans the test code by removing pytest imports, fixtures, mocks, and assert statements."""
    code = re.sub(r"^import pytest.*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"^from pytest.*\n?", "", code, flags=re.MULTILINE)

    # Remove mock imports if any
    code = re.sub(r"^from unittest.mock import .*", "", code, flags=re.MULTILINE)
    code = re.sub(r"^import mock.*\n?", "", code, flags=re.MULTILINE)

    # Remove fixtures (decorators like @pytest.fixture), mock.patch
    code = re.sub(r"@pytest\.fixture.*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"@mock\.patch\(.*\)\n?", "", code, flags=re.MULTILINE)

    # Remove test_ prefixes from function names
    code = re.sub(r"def test_(\w+)\(", r"def \1(", code)

    # Remove assert statements
    code = re.sub(r"^\s*assert .*\n?", "", code, flags=re.MULTILINE)

    # Remove any remaining blank lines
    code = re.sub(r"\n{2,}", "\n\n", code)

    return code.strip()


async def generate_recipe_docs(test_dir: PathLike, output_dir: PathLike) -> None:
    """Generate Sphinx-compatible `.rst` files for each test module, converting them into recipes.

    Args:
        test_dir (PathLike): The directory containing the test files.
        output_dir (PathLike): The base directory for Sphinx documentation output.
    """
    recipes_dir = output_dir / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)

    # Create a main Recipes index file
    recipes_index = recipes_dir / "index.rst"
    with recipes_index.open("w") as index_file:
        index_file.write("Recipes\n")
        index_file.write("=" * len("Recipes") + "\n\n")
        index_file.write(".. autosummary::\n")
        index_file.write("   :toctree: .\n\n")

        # Process each test file
        for test_file in test_dir.rglob("test_*.py"):
            module_name = test_file.stem.replace("test_", "")

            # Add module to the autosummary
            index_file.write(f"   {module_name}\n")

            # Generate an individual recipe file
            recipe_rst = recipes_dir / f"{module_name}.rst"
            with recipe_rst.open("w") as recipe_file:
                title = f"{module_name.capitalize()} Recipes"
                recipe_file.write(f"{title}\n")
                recipe_file.write("=" * len(title) + "\n\n")
                recipe_file.write(".. code-block:: python\n\n")

                # Read and clean the test file
                with test_file.open("r") as tf:
                    code = tf.read()
                    cleaned_code = await clean_code(code)

                    # Add cleaned code to the recipe file with proper indentation
                    for line in cleaned_code.splitlines():
                        recipe_file.write(f"    {line}\n")


if __name__ == "__main__":
    test_dir = PathLike("../../tests")
    output_dir = PathLike("docs")

    asyncio.run(generate_recipe_docs(test_dir, output_dir))

