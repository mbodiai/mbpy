
from pathlib import Path
import importlib
import click
import tomlkit
from typing import Literal

getcwd = Path.cwd
WORKFLOW_UBUNTU = """name: "Ubuntu"

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  ubuntu:
    name: ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-20.04, ubuntu-latest]

    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v3
        with:
          python-version: 3.11

      - name: Run install script
        run: |
            python -m pip install --upgrade pip
            python -m pip install hatch

      - name: Cache packages
        uses: actions/cache@v3
        env:
          cache-name: cache-packages
        with:
          path: ~/.local/bin ~/.local/lib .mbodied/envs/mbodied
          key: ${{ runner.os }}-${{ env.cache-name }}-${{ hashFiles('install.bash') }}
          restore-keys: |
            ${{ runner.os }}-${{ env.cache-name }}-

      - name: Check disk usage
        run: df -h

      - name: Clean up before running tests
        run: |
          # Add commands to clean up unnecessary files
          sudo apt-get clean
          sudo rm -rf /usr/share/dotnet /etc/mysql /etc/php /etc/apt/sources.list.d
          # Add more cleanup commands as needed

      - name: Check disk usage after cleanup
        run: df -h

      - name: Run tests
        run: |
          hatch run pip install '.'
          hatch run test"""

WORKFLOW_MAC = """name: "MacOS | Python 3.12|3.11|3.10"

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write

jobs:
  test:
    name: Python ${{ matrix.python-version }}
    runs-on: macos-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.11", "3.10"]

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v3
        with:
          python-version: ${{ matrix.python-version }}

      - name: Run install script
        run: |
            python -m pip install --upgrade pip
            python -m pip install hatch

      - name: Cache packages
        uses: actions/cache@v3
        env:
          cache-name: cache-packages
        with:
          path: ~/Library/Caches/Homebrew
          key: ${{ runner.os }}-${{ env.cache-name }}-${{ hashFiles('install.bash') }}
          restore-keys: |
            ${{ runner.os }}-${{ env.cache-name }}-
      - name: Run tests
        run: |
          hatch run pip install '.'
          hatch run test"""


import os
import subprocess
import ast

def create_project(
    project_name,
    author,
    description="",
    deps: list[str] | Literal["local"] | None = None,
    python_version="3.10",
    add_cli=True,
    doc_type='sphinx',
    docstrings: dict = None,
) -> Path:
    # Set project root directory
    root = Path.cwd()
    project_root = root / project_name

    # ... (rest of the function remains the same)

    print(f"Project {project_name} created successfully with {doc_type} documentation.")
    return project_root  # Return the project root directory



def setup_documentation(project_root, project_name, author, description, doc_type='sphinx', docstrings=None):
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True, parents=True)

    if doc_type == 'sphinx':
        setup_sphinx_docs(docs_dir, project_name, author, description, docstrings)
    elif doc_type == 'mkdocs':
        setup_mkdocs(docs_dir, project_name, author, description, docstrings)
    else:
        raise ValueError("Invalid doc_type. Choose 'sphinx' or 'mkdocs'.")

def setup_sphinx_docs(docs_dir, project_name, author, description, docstrings):
    # Create conf.py
    conf_content = f"""
# Configuration file for the Sphinx documentation builder.

project = '{project_name}'
copyright = '2024, {author}'
author = '{author}'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'alabaster'
html_static_path = ['_static']
"""
    (docs_dir / "conf.py").write_text(conf_content)

    # Create index.rst
    index_content = f"""
Welcome to {project_name}'s documentation!
==========================================

{description}

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
"""
    (docs_dir / "index.rst").write_text(index_content)

    # Create api.rst
    api_content = """
API Reference
=============

.. automodule:: {project_name}
   :members:
   :undoc-members:
   :show-inheritance:
"""
    (docs_dir / "api.rst").write_text(api_content)

    # Create Makefile
    makefile_content = """
# Minimal makefile for Sphinx documentation

SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
"""
    (docs_dir / "Makefile").write_text(makefile_content)

def extract_docstrings(project_path):
    docstrings = {}
    for py_file in project_path.glob('**/*.py'):
        module_name = '.'.join(py_file.relative_to(project_path).with_suffix('').parts)
        try:
            with open(py_file, 'r') as file:
                tree = ast.parse(file.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        docstrings[f"{module_name}.{node.name}"] = docstring.strip()
        except Exception as e:
            print(f"Warning: Unable to parse {py_file}: {e}")
    return docstrings

def setup_mkdocs(docs_dir: Path, project_name: str, author, description, docstrings):
    # Create mkdocs.yml
    mkdocs_content = f"""
site_name: {project_name}
site_description: {description}
site_author: {author}

theme:
  name: material

nav:
  - Home: index.md
  - API: api.md

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences

plugins:
  - search
  - mkdocstrings:
      default_handler: python
      handlers:
        python:
          rendering:
            show_source: true
"""
    (docs_dir.parent / "mkdocs.yml").write_text(mkdocs_content)

    # Create index.md
    index_content = f"""
# Welcome to {project_name}

{description}

## Installation

```bash
pip install {project_name}
```

## Usage

[Add usage information here]

## API Documentation

For detailed API documentation, please see the [API](api.md) page.
"""
    (docs_dir / "index.md").write_text(index_content)

    # Create api.md with extracted docstrings
    api_content = f"""
# API Reference

This page contains the API reference for {project_name}.

"""
    for full_name, docstring in docstrings.items():
        module_name, obj_name = full_name.rsplit('.', 1)
        api_content += f"""
## {obj_name}

```python
from {module_name} import {obj_name}
```

{docstring}

---

"""

    (docs_dir / "api.md").write_text(api_content)

def create_pyproject_toml(
    project_name,
    author,
    desc="",
    deps=None,
    python_version="3.10",
    add_cli=True,
    existing_content=None,
    overwrite=True,
    **kwargs
) -> str:
    """Create a pyproject.toml file for a Hatch project."""
    pyproject_path = Path(project_name) / "pyproject.toml"
    pyproject_path.parent.mkdir(parents=True, exist_ok=True)
    if pyproject_path.exists() and not overwrite:
        print("Skipping pyproject.toml creation.")
        return ""

    pyproject = tomlkit.parse(existing_content) if existing_content else tomlkit.document()

    # ... (rest of the function remains the same)

    from mbpy.mpip import write_pyproject
    if not existing_content:
      Path(pyproject_path).touch(exist_ok=True)
    write_pyproject(pyproject, pyproject_path)
    return tomlkit.dumps(pyproject)  # Convert TOMLDocument to string

