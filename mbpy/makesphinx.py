# create.py

import contextlib
from pathlib import Path
import ast

# Import the Sphinx templates from static.py
from mbpy.commands import run
from mbpy.static import SPHINX_API, SPHINX_CONF_TEMPLATE, SPHINX_MAKEFILE, SPHINX_INDEX


# create.py or makesphinx.py


def generate_custom_css(docs_dir):
    custom_css = """
    /* custom.css */

    /* Sidebar Background */
    .wy-side-scroll {
        background-color: #ed3d5d; /* mbodi_color.c500 */
    }

    /* Sidebar Border */
    .wy-side-scroll:after {
        border-color: #852333; /* mbodi_color.c700 */
    }

    /* Additional Custom Styles */
    body {
        background-color: #fde8e8; /* mbodi_color.c50 */
    }

    /* Add more styles as needed */
    """
    static_path = Path(docs_dir) / "_static"
    static_path.mkdir(parents=True, exist_ok=True)
    (static_path / "custom.css").write_text(custom_css)
    print(f"Generated {static_path / 'custom.css'}")


def SPHINX_CONF(project_name, author, path):
    path = str(Path(str(path).replace("\\", "/")).resolve())
    return f"""
# Configuration file for the Sphinx documentation builder.
import os
import sys

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath('{path}'))

project = '{project_name}'
author = '{author}'

extensions = [
    'autodoc2',
    'sphinx.ext.napoleon',
]

autodoc2_packages = [
    {{
        'path': '{project_name}',
        'auto_mode': True,
    }},
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'furo'
html_static_path = ['_static']

# Add custom CSS
html_css_files = [
    'custom.css',
]
"""



def setup_sphinx_docs(docs_dir, project_name, author, description, source_dir) -> None:
    """Set up Sphinx documentation."""

    docs_path = Path(docs_dir) if docs_dir else Path("docs")
    docs_path.mkdir(parents=True, exist_ok=True)

    # Generate index.rst
    generate_index_rst(docs_path, project_name, author, description)

    # Generate RST files for each module
    generate_rst_for_project(source_dir, docs_path, package_name=project_name)

    # Generate custom.css
    generate_custom_css(docs_path)
    # Create conf.py
    conf_content = SPHINX_CONF(project_name=project_name, author=author, path=source_dir)
    (docs_path / "conf.py").write_text(conf_content)
    print(f"Generated conf.py")

    # Create Makefile
    (docs_path / "Makefile").write_text(SPHINX_MAKEFILE)
    print(f"Generated Makefile")

    # Create api.rst
    api_content = SPHINX_API.format(
        project_name=project_name,
        module_name=project_name,  # Ensure this is the correct module name
    )
    (docs_path / "api.rst").write_text(api_content)
    print(f"Generated api.rst")

    # Build the HTML documentation
    with contextlib.chdir(docs_path):
        run("make html")
        print(f"Generated HTML documentation in {docs_path / '_build/html'}")

def generate_rst_for_project(source_dir, docs_dir, package_name):
    """Generate RST files for each module in the project."""
    
    source_path = Path(source_dir)
    modules = [f.stem for f in source_path.glob("*.py") if f.stem != "__init__"]
    for module in modules:
        rst_content = f"""
{module.capitalize()}
{'=' * len(module.capitalize())}

.. automodule:: {package_name}.{module}
    :members:
    :undoc-members:
    :show-inheritance:
""" + ""
        output_path = Path(docs_dir) / f"{module}.rst"
        output_path.write_text(rst_content)
        print(f"Generated {output_path}")


def generate_index_rst(docs_dir, project_name, author,description=""):
    """Generate the index.rst file."""
    index_content = SPHINX_INDEX.format(project_name=project_name,author=author,module_name=project_name,description=description)
    (Path(docs_dir) / "index.rst").write_text(index_content)
    print(f"Generated index.rst")


def get_function_signature(node):
    """Construct a function signature from an AST FunctionDef node."""
    args = []
    defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + node.args.defaults

    for arg, default in zip(node.args.args, defaults, strict=False):
        arg_name = arg.arg
        if arg.annotation:
            arg_type = ast.unparse(arg.annotation)
            arg_str = f"{arg_name}: {arg_type}"
        else:
            arg_str = arg_name

        if default:
            default_value = ast.unparse(default)
            arg_str += f" = {default_value}"

        args.append(arg_str)

    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")

    for kwarg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=False):
        kwarg_name = kwarg.arg
        if kwarg.annotation:
            kwarg_type = ast.unparse(kwarg.annotation)
            kwarg_str = f"{kwarg_name}: {kwarg_type}"
        else:
            kwarg_str = kwarg_name

        if default:
            default_value = ast.unparse(default)
            kwarg_str += f" = {default_value}"

        args.append(kwarg_str)

    return f"({', '.join(args)})"
