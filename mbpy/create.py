
from pathlib import Path
from typing import Literal

import tomlkit

DEFAULT_PYTHON = "3.11"
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


import ast


def create_project(
    project_name,
    author,
    description="",
    deps: list[str] | Literal["local"] | None = None,
    python_version=DEFAULT_PYTHON,
    add_cli=True,
    doc_type='sphinx',
    docstrings: dict = None,
    project_root: Path = None,
) -> Path:
    # Set project root directory
    if project_root is None:
        project_root = Path.cwd()
    project_path = project_root

    # Create project structure
    src_dir = project_path / project_name.replace("-", "_")
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("")
    
    # Always create or update __about__.py
    about_file = src_dir / "__about__.py"
    about_file.write_text('__version__ = "0.1.0"')

    # Create pyproject.toml
    pyproject_path = project_path / "pyproject.toml"
    existing_content = None
    if pyproject_path.exists():
        with pyproject_path.open() as f:
            existing_content = f.read()
    
    pyproject_content = create_pyproject_toml(
        project_name,
        author,
        description,
        deps if deps is not None else [],
        python_version=python_version,
        add_cli=add_cli,
        existing_content=existing_content
    )
    pyproject_path.write_text(pyproject_content)

    # Setup documentation
    setup_documentation(project_path, project_name, author, description, doc_type, docstrings or {})

    if add_cli:
        cli_content = f"""
import click

@click.command()
def main():
    click.echo("Hello from {project_name}!")

if __name__ == "__main__":
    main()
"""
        (src_dir / "cli.py").write_text(cli_content)

    return project_path  # Return the project path



def setup_documentation(project_root, project_name, author, description, doc_type='sphinx', docstrings=None) -> None:
    project_root = Path(project_root)  # Convert to Path object if it's a string
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True, parents=True)

    if doc_type == 'sphinx':
        setup_sphinx_docs(docs_dir, project_name, author, description, docstrings or {})
    elif doc_type == 'mkdocs':
        setup_mkdocs(project_root, project_name, author, description, docstrings or {})
    else:
        raise ValueError("Invalid doc_type. Choose 'sphinx' or 'mkdocs'.")

def setup_sphinx_docs(docs_dir, project_name, author, description, docstrings=None) -> None:
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

def extract_docstrings(project_path) -> dict[str, str]:
    docstrings = {}
    project_path = Path(project_path)  # Convert to Path object if it's a string
    for py_file in project_path.glob('**/*.py'):
        module_name = '.'.join(py_file.relative_to(project_path).with_suffix('').parts)
        try:
            with py_file.open() as file:
                tree = ast.parse(file.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.ClassDef):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        docstrings[f"{module_name}.{node.name}"] = docstring.strip()
        except Exception:
            pass
    return docstrings

def setup_mkdocs(project_root: Path, project_name: str, author, description, docstrings) -> None:
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True)

    # Create mkdocs.yml in the project root
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
    (project_root / "mkdocs.yml").write_text(mkdocs_content)

    # Create index.md
    index_content = f"""
# Welcome to {project_name}

{description}

## Installation

```bash
pip install {project_name}
```

## Usage

Here's a simple example:

```python
def test_function():
    \"\"\"This is a test docstring.\"\"\"
    pass

# Use the function
test_function()
```

## API Documentation

For detailed API documentation, please see the [API](api.md) page.
"""
    (docs_dir / "index.md").write_text(index_content)

    # Create api.md with extracted docstrings
    api_content = f"""
# API Reference

This page contains the API reference for {project_name}.

## test_function

```python
def test_function():
    \"\"\"This is a test docstring.\"\"\"
    pass
```

This is a test docstring.

---

"""
    if docstrings:
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
    existing_content=None
) -> str:
    """Create a pyproject.toml file for a Hatch project."""
    try:
        pyproject = tomlkit.parse(existing_content) if existing_content else tomlkit.document()
    except tomlkit.exceptions.ParseError:
        pyproject = tomlkit.document()

    # Build system
    pyproject.setdefault("build-system", {
        "requires": ["hatchling"],
        "build-backend": "hatchling.build"
    })

    # Project metadata
    project = pyproject.setdefault("project", tomlkit.table())
    project["name"] = project_name
    project["version"] = "0.0.1"
    project["description"] = desc
    project["readme"] = "README.md"
    project["requires-python"] = f">={python_version}"
    project["license"] = "MIT"
    project["authors"] = [{"name": author}]

    # Classifiers
    classifiers = tomlkit.array()
    classifiers.multiline(True)  # Ensure each classifier is on a new line
    classifiers.extend([
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        f"Programming Language :: Python :: {python_version}",
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ])
    project["classifiers"] = classifiers

    # Dependencies
    existing_deps = project.get("dependencies", tomlkit.array())
    new_deps = tomlkit.array()
    new_deps.multiline(True)  # Ensure each dependency is on a new line
    
    # Add existing dependencies
    for dep in existing_deps:
        new_deps.append(dep)
    
    # Add new dependencies
    if deps:
        deps_to_add = deps if isinstance(deps, list) else [deps]
        for dep in deps_to_add:
            if dep not in new_deps:
                new_deps.append(dep)
    
    project["dependencies"] = new_deps

    if add_cli:
        scripts = project.setdefault("scripts", tomlkit.table())
        scripts[project_name] = f"{project_name}.cli:main"

    # Tool configurations
    tool = pyproject.setdefault("tool", tomlkit.table())
    
    # Hatch configuration
    hatch = tool.setdefault("hatch", tomlkit.table())
    hatch["version"] = {"path": f"{project_name}/__about__.py"}
    hatch["envs"] = {
        "default": {
            "dependencies": [
                "pytest",
                "pytest-cov"
            ]
        }
    }

    # Ruff configuration
    ruff = tool.setdefault("ruff", tomlkit.table())
    ruff["line-length"] = 120
    ruff["select"] = [
        "A", "COM812", "C4", "D", "E", "F", "UP", "B", "SIM", "N", "ANN",
        "ASYNC", "S", "T20", "RET", "SIM", "ARG", "PTH", "ERA", "PD", "I", "PLW"
    ]
    ruff["ignore"] = [
        "D105", "PGH004", "D100", "D101", "D104", "D106", "ANN101", "ANN102",
        "ANN003", "ANN204", "UP009", "B026", "ANN001", "ANN401", "ANN202",
        "D107", "D102", "D103", "E731", "UP006", "UP035", "ANN002"
    ]
    ruff["fixable"] = ["ALL"]
    ruff["unfixable"] = []

    ruff_format = ruff.setdefault("format", tomlkit.table())
    ruff_format["docstring-code-format"] = True
    ruff_format["quote-style"] = "double"
    ruff_format["indent-style"] = "space"
    ruff_format["skip-magic-trailing-comma"] = False
    ruff_format["line-ending"] = "auto"

    ruff_lint = ruff.setdefault("lint", tomlkit.table())
    ruff_lint_pydocstyle = ruff_lint.setdefault("pydocstyle", tomlkit.table())
    ruff_lint_pydocstyle["convention"] = "google"

    ruff_lint_per_file_ignores = ruff_lint.setdefault("per-file-ignores", tomlkit.table())
    ruff_lint_per_file_ignores["**/{tests,docs}/*"] = ["ALL"]
    ruff_lint_per_file_ignores["**__init__.py"] = ["F401"]

    tool["codeflash"] = {
        "module-root": project_name,
        "tests-root": "tests",
        "test-framework": "pytest",
        "ignore-paths": [],
        "formatter-cmds": [
            "hatch run ruff check --exit-zero --fix $file",
            "hatch run ruff format $file"
        ]
    }

    tool["pytest"] = {
        "ini_options": {
            "addopts": "-m 'not network'",
            "markers": "network: marks tests that make network calls (deselect with '-m \"not network\"')"
        }
    }
    
    # Add additional Ruff configurations from the current pyproject.toml
    current_ruff = pyproject.get("tool", {}).get("ruff", {})
    for key, value in current_ruff.items():
        if key not in ruff:
            ruff[key] = value
        elif isinstance(value, list):
            ruff[key].extend([item for item in value if item not in ruff[key]])

    # Pytest configuration
    tool["pytest"] = {
        "ini_options": {
            "addopts": "--cov=src --cov-report=term-missing",
            "testpaths": ["tests"],
            "markers": [
                "network: marks tests that require network access (deselect with '-m \"not network\"')",
            ]
        }
    }

    return tomlkit.dumps(pyproject)

