import asyncio
import logging
from pathlib import Path
import re
from contextlib import chdir
from inspect import cleandoc
from inspect import getdoc as inspect_getdoc
from pydoc import getdoc as pydoc_getdoc
from pydoc import splitdoc, synopsis
from mbpy.import_utils import locate
from typing import Any, Dict, Tuple

from typing_extensions import Final

from mbpy.cmd import arun
from mbpy.collect import PathLike
from mbpy.helpers._static import SPHINX_API, SPHINX_CONF, SPHINX_INDEX, SPHINX_MAKEFILE

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
    """Split the docstring into the first paragraph and the rest."""
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
    """Extract the first sentence (brief) and returns the.

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
    *, docs_dir: PathLike, project_name: str, author: str, description: str, source_dir: PathLike, theme: str = "furo"
) -> None:
    """Set up Sphinx documentation."""
    docs_path = Path(docs_dir).resolve()
    source_path = Path(source_dir)
    
    # Create directories
    docs_path.mkdir(parents=True, exist_ok=True)
    templates_dir = docs_path / "_templates"
    templates_dir.mkdir(exist_ok=True)
    api_dir = docs_path / "api"
    api_dir.mkdir(exist_ok=True)
    autosummary_dir = api_dir / "_autosummary"
    autosummary_dir.mkdir(exist_ok=True)
    static_dir = docs_path / "_static"
    static_dir.mkdir(exist_ok=True)

    # Create custom templates with fixed syntax
    template_files = {
        "module.rst": """
{%- if show_headings %}
{{- basename | heading }}
{% endif -%}
.. automodule:: {{ qualname }}
   :members:
   :undoc-members:
   :show-inheritance:
""",
        "class.rst": """
{%- if show_headings %}
{{- basename | heading }}
{% endif -%}
.. autoclass:: {{ qualname }}
   :members:
   :undoc-members:
   :show-inheritance:
""",
    }

    for name, content in template_files.items():
        template_path = templates_dir / name
        template_path.write_text(content)

    # Create API index with fixed syntax
    with (api_dir / "index.rst").open("w") as f:
        f.write(f"""
API Reference
============

.. toctree::
   :maxdepth: 2
   :caption: API Documentation

   {project_name}

.. currentmodule:: {project_name}

.. autosummary::
   :toctree: _autosummary
   :template: module.rst
   :recursive:

   {project_name}
""")

    # Create conf.py with proper settings
    conf_content = SPHINX_CONF(
        project_name=project_name,
        author=author,
        theme=theme,
        description=description,
        myst_parser=False  # Disable myst_parser by default
    )
    (docs_path / "conf.py").write_text(conf_content)

    # Build documentation with error handling
    with chdir(docs_path):
        try:
            build_dir = docs_path / "_build"
            if build_dir.exists():
                import shutil
                shutil.rmtree(build_dir)
            # Clean build with -W to treat warnings as errors
            await arun("sphinx-build -W -E -a -b html . _build/html", show=True)
        except Exception as e:
            logging.error(f"Failed to build documentation: {e}")
            raise

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
        title = f"{rel_path} Documentation" if rel_path != "." else "Project Documentation"
        f.write(f"{title}\n")
        f.write("=" * len(title) + "\n\n")
        
        # Write toctree with only existing files
        f.write(".. toctree::\n")
        f.write("   :maxdepth: 2\n")
        f.write("   :caption: Contents:\n\n")
        
        # Only include files that exist
        if (docs_dir / "api.rst").exists():
            f.write("   api\n")
        if (docs_dir / "recipes").exists():
            f.write("   recipes/index\n")
        
        # Add valid Python modules
        for child in children:
            if child.suffix == ".py" and child.stem != "__init__":
                f.write(f"   {child.stem}\n")
        f.write("\n")

        # Properly format autosummary
        f.write("API Reference\n")
        f.write("============\n\n")
        f.write(".. autosummary::\n")
        f.write("   :toctree: _autosummary\n")
        f.write("   :recursive:\n\n")
        
        # Only include Python modules in autosummary
        for child in children:
            if child.is_file() and child.suffix == ".py" and not child.stem.startswith("_"):
                f.write(f"   {str(rel_path).replace('/', '.')}.{child.stem}\n")

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
                    f"    from {str(rel_path).replace('/', '.')}.{module_name} import *\n\n",
                )
                f.write(f"    {await one_liner(module_name)}\n\n")
                f.write(f"    {await summary(module_name)}\n\n")
                f.write(f"    {await outline(module_name)}\n\n")

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
        """Clean the test code by removing pytest imports, fixtures, mocks, and assert statements."""
        if not code.strip():
            return "No content found"
            
        # Remove pytest and mock imports
        code = re.sub(r"(^import pytest.*\n|^from pytest.*\n|^from unittest.mock.*\n|^import mock.*\n)", "", code, flags=re.MULTILINE)

        # Remove pytest decorators and mocks 
        code = re.sub(r"(@pytest\.fixture.*\n|@mock\.patch.*\n|@patch.*\n)", "", code, flags=re.MULTILINE)

        # Remove commented sections
        code = re.sub(r"^\s*#.*\n", "", code, flags=re.MULTILINE)

        # Remove unused imports
        code = re.sub(r"(^from .*?\n|^import .*?\n)", "", code, flags=re.MULTILINE)

        # Improved function name cleaning
        code = re.sub(r"def test_(\w+)\(.*?\):", lambda m: m.group(1).replace('_', ' '), code, flags=re.MULTILINE)
        code = re.sub(r"@.*\nmock\s+(\w+)", r"\1", code, flags=re.MULTILINE)  # Clean mock fixtures
        code = re.sub(r"^\s*mock\s+(\w+)\s*=", r"\1 =", code, flags=re.MULTILINE)  # Clean mock variables

        # Extract clean functions
        functions = {}
        current_fn = None
        current_body = []

        for line in code.splitlines():
            if line.strip() in ['if __name__ == "__main__":', 'pytest.main([', ']):']:
                continue
            if line.strip() and not line.strip().startswith(('assert', 'pytest', 'mock')):
                if line.strip() in functions.keys():
                    current_fn = line.strip()
                    current_body = []
                elif line[0].isupper() and line[-1] == '=':
                    current_fn = line.strip('=').strip()
                    current_body = []
                elif re.match(r'^[a-zA-Z][\w\s]+$', line.strip()):  # Match cleaned function names
                    current_fn = line.strip()
                    current_body = []
                else:
                    if current_fn:
                        current_body.append(line)
                        functions[current_fn] = '\n'.join(current_body).strip()

        # Format recipes
        recipe = []
        if not functions:
            return "No recipes found in this test file"
            
        for fn_name, fn_body in functions.items():
            if fn_body.strip():
                recipe.append(fn_name)
                recipe.append("=" * len(fn_name))
                recipe.append(fn_body.strip())
                recipe.append("")
                
        return "\n".join(recipe) if recipe else "No valid recipes extracted"

async def generate_recipe_docs(test_dir: PathLike, output_dir: PathLike, show: bool = False) -> None:
        """Generate recipe documentation from test files.

        Args:
            test_dir: Test files directory
            output_dir: Output documentation directory
            show: Whether to print processing information
        """
        if show:
            print(f"\nGenerating recipes from {test_dir} to {output_dir}")
            
        recipes_dir = output_dir / "recipes"
        recipes_dir.mkdir(parents=True, exist_ok=True)

        recipes_index = recipes_dir / "index.rst"
        with recipes_index.open("w") as index_file:
            index_file.write("Recipes\n=======\n\n")
            index_file.write(".. toctree::\n   :maxdepth: 2\n\n")

            for test_file in test_dir.rglob("test_*.py"):
                if show:
                    print(f"\nProcessing test file: {test_file}")
                    print(f"File size: {test_file.stat().st_size} bytes")
                
                module_name = test_file.stem.replace("test_", "")
                index_file.write(f"   {module_name}\n")

                recipe_rst = recipes_dir / f"{module_name}.rst"
                with recipe_rst.open("w") as recipe_file:
                    title = f"{module_name.capitalize()} Recipes"
                    recipe_file.write(f"{title}\n{'=' * len(title)}\n")
                    recipe_file.write(".. code-block:: python\n\n")

                    with test_file.open() as tf:
                        content = tf.read()
                        if show:
                            print(f"Raw content length: {len(content)} characters")
                        cleaned = await clean_code(content)
                        if show:
                            print(f"\nCleaned content for {module_name}:")
                            print(cleaned)
                            print("-" * 80)
                        for line in cleaned.splitlines():
                            recipe_file.write(f"    {line}\n")

if __name__ == "__main__":
    from mbpy.helpers.traverse import search_children_for_file
    test_dir = search_children_for_file("tests", cwd=Path.cwd().parent)
    output_dir = PathLike("docs")

    asyncio.run(generate_recipe_docs(test_dir, output_dir,show=True))

