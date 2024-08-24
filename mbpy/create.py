
from pathlib import Path
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
) -> None:
    print(f"Creating project: {project_name}")
    print(f"Author: {author}")
    print(f"Description: {description}")
    print(f"Dependencies: {deps}")
    print(f"Python version: {python_version}")
    print(f"Add CLI: {add_cli}")

    if deps is None or deps == "local":
        deps = []
    
    # Set project root directory
    root = Path(getcwd())
    project_root = root / project_name

    # Check if project directory already exists
    if project_root.exists():
        overwrite = input(f"Project directory {project_root} already exists. Overwrite? (y/n): ").lower() == 'y'
        if not overwrite:
            print("Project creation cancelled.")
            return

    print(f"Creating project root directory: {project_root}")
    project_root.mkdir(exist_ok=True, parents=True)
    
    # Create main directories
    dirs = ["assets", "docs", "tests", project_name, "resources"]
    for dir in dirs:
        dir_path = project_root / dir
        print(f"Creating directory: {dir_path}")
        dir_path.mkdir(exist_ok=True, parents=True)
        if dir != project_name:
            (dir_path / ".gitkeep").touch(exist_ok=True)
    
    # Create workflows directory
    workflows = project_root / ".github" / "workflows"
    workflows.mkdir(exist_ok=True, parents=True)
    
    # Create __about__.py in project directory
    about_file = project_root / project_name / "__about__.py"
    about_content = '__version__ = "0.0.1"'
    about_file.write_text(about_content)

    # Create __init__.py and main.py in project directory if add_cli is True
    if add_cli:
        init_content = "from .main import cli\n\n__all__ = ['cli']"
        main_content = "from click import command\n\n@command()\ndef cli() -> None:\n    pass\n\nif __name__ == '__main__':\n    cli()"
        (project_root / project_name / "__init__.py").write_text(init_content)
        (project_root / project_name / "main.py").write_text(main_content)
    else:
        (project_root / project_name / "__init__.py").touch()

    # Create pyproject.toml content
    print("Calling create_pyproject_toml...")
    pyproject_content = create_pyproject_toml(project_name, author, description, deps, python_version=python_version, add_cli=add_cli)
    print("create_pyproject_toml called successfully")

    # Create files in root
    files = [
        ("LICENSE", ""),
        (
            "README.md",
            f"# {project_name}\n\n{description}\n\n## Installation\n\n```bash\npip install {project_name}\n```\n",
        ),
        ("pyproject.toml", pyproject_content),
        ("requirements.txt", "click" if add_cli else ""),
    ]
    for file, content in files:
        file_path = project_root / file
        if file_path.exists():
            overwrite = input(f"{file} already exists. Overwrite? (y/n): ").lower() == 'y'
            if not overwrite:
                print(f"Skipping {file}")
                continue
        file_path.write_text(content)

    # Create workflow files
    (workflows / "macos.yml").write_text(WORKFLOW_MAC)
    (workflows / "ubuntu.yml").write_text(WORKFLOW_UBUNTU)

    # Extract docstrings if not provided
    if docstrings is None:
        docstrings = extract_docstrings(project_root / project_name)

    # Set up documentation
    setup_documentation(project_root.absolute(), project_name, author, description, doc_type, docstrings or {})

    # Check for import errors
    import_errors = []
    for module in ['__about__', '__init__', 'main']:
        try:
            __import__(f"{project_name}.{module}")
        except ImportError as e:
            import_errors.append(f"Warning: Unable to import {project_name}.{module}: {str(e)}")

    for error in import_errors:
        print(error)

    print(f"Project {project_name} created successfully with {doc_type} documentation.")

import ast
import importlib
import inspect

def setup_documentation(project_dir, project_name, author, description, doc_type='sphinx', docstrings=None):
    docs_dir = project_dir / "docs"
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

def setup_mkdocs(docs_dir, project_name, author, description, docstrings):
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

def create_project(
    project_name,
    author,
    description="",
    deps: list[str] | Literal["local"] | None = None,
    python_version="3.11",
    add_cli=True,
    doc_type='sphinx',
    docstrings: dict = None,
    project_root: Path = None,
) -> None:
    print(f"Creating project: {project_name}")
    print(f"Author: {author}")
    print(f"Description: {description}")
    print(f"Dependencies: {deps}")
    print(f"Python version: {python_version}")
    print(f"Add CLI: {add_cli}")

    if deps is None or deps == "local":
        deps = []
    
    # Set project root directory
    if project_root is None:
        project_root = Path(getcwd())
    project_path = project_root / project_name
    if project_path.exists():
        overwrite = input(f"Project directory {project_path.absolute()} already exists. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Project creation aborted.")
            return
    print(f"Creating project root directory: {project_path}")
    project_path.mkdir(exist_ok=True, parents=True)
    
    # Create all necessary directories
    dirs = [
        "assets",
        "docs",
        "tests",
        "resources",
        project_name,
        ".github/workflows",
        f"{project_name}/resources",
        f"{project_name}/tests",
        "docs/api",
        f"{project_name}/src"
    ]
    for dir in dirs:
        dir_path = project_path / dir
        dir_path.mkdir(exist_ok=True, parents=True)
        if dir not in [project_name, ".github/workflows", f"{project_name}/resources", f"{project_name}/tests", "docs/api", f"{project_name}/src"]:
            gitkeep_path = dir_path / ".gitkeep"
            gitkeep_path.parent.mkdir(exist_ok=True, parents=True)
            gitkeep_path.touch(exist_ok=True)
    
    # Create __about__.py in project directory
    about_file = project_root / project_name / "__about__.py"
    about_content = '__version__ = "0.0.1"'
    about_file.write_text(about_content)

    # Create __init__.py and main.py in project directory if add_cli is True
    if add_cli:
        init_content = "from .main import cli\n\n__all__ = ['cli']"
        main_content = "from click import command\n\n@command()\ndef cli() -> None:\n    pass\n\nif __name__ == '__main__':\n    cli()"
        (project_root / project_name / "__init__.py").write_text(init_content)
        (project_root / project_name / "main.py").write_text(main_content)
    else:
        (project_root / project_name / "__init__.py").touch(exist_ok=True, parents=True)

    # Create pyproject.toml content
    print("Calling create_pyproject_toml...")
    pyproject_content = create_pyproject_toml(project_name, author, description, deps, python_version=python_version, add_cli=add_cli)
    print("create_pyproject_toml called successfully")

    # Create files in root
    files = [
        ("LICENSE", ""),
        (
            "README.md",
            f"# {project_name}\n\n{description}\n\n## Installation\n\n```bash\npip install {project_name}\n```\n",
        ),
        ("pyproject.toml", pyproject_content),
        ("requirements.txt", "click" if add_cli else ""),
    ]
    for file, content in files:
        file_path = project_root / file
        file_path.write_text(content)

    # Create workflow files
    (project_root / ".github" / "workflows" / "macos.yml").write_text(WORKFLOW_MAC)
    (project_root / ".github" / "workflows" / "ubuntu.yml").write_text(WORKFLOW_UBUNTU)

    # Set up documentation
    docs_dir = project_path / "docs"
    docs_dir.mkdir(exist_ok=True, parents=True)
    setup_documentation(project_path, project_name, author, description, doc_type, docstrings or {})


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
    if pyproject_path.exists() and not overwrite:
        print("Skipping pyproject.toml creation.")
        return ""

    if existing_content:
        pyproject = tomlkit.parse(existing_content)
    else:
        pyproject = tomlkit.document()

    # Update build-system
    build_system = pyproject.setdefault("build-system", {})
    build_system["requires"] = ["hatchling"]
    build_system["build-backend"] = "hatchling.build"

    # Update project
    project = pyproject.setdefault("project", {})
    project["name"] = project_name
    project["dynamic"] = ["version"]
    project["description"] = desc if desc else project.get("description", "")
    project["readme"] = "README.md"
    project["requires-python"] = f">={python_version}"
    project["license"] = "apache-2.0"
    project["keywords"] = []
    project["authors"] = [{"name": a.strip()} for a in author.split(",")]

    # Update classifiers
    classifiers = [
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
    ]
    classifiers.extend([f"Programming Language :: Python :: 3.{v}" for v in range(int(python_version.split('.')[1]), 13)])
    classifiers.extend([
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ])
    project["classifiers"] = classifiers

    # Update dependencies
    existing_deps = project.get("dependencies", [])
    new_deps = deps or []
    all_deps = list(set(existing_deps + new_deps))
    all_deps.sort(key=lambda x: x.lower())
    project["dependencies"] = all_deps

    # Update optional dependencies
    optional_deps = project.setdefault("optional-dependencies", {})

    # Update project URLs
    project["urls"] = {
        "Documentation": f"https://github.com/{author}/{project_name}#readme",
        "Issues": f"https://github.com/{author}/{project_name}/issues",
        "Source": f"https://github.com/{author}/{project_name}",
    }

    # Update project scripts
    if add_cli:
        project["scripts"] = {project_name: f"{project_name}:cli"}

    # Update tool configurations
    tool = pyproject.setdefault("tool", {})
    
    # Hatch configuration
    hatch = tool.setdefault("hatch", {})
    hatch["version"] = {"path": f"{project_name}/__about__.py"}
    hatch["metadata"] = {"allow-direct-references": True}
    hatch["build"] = {"targets": {"wheel": {"force-include": {"resources": f"{project_name}/resources"}}}}
    
    hatch_envs = hatch.setdefault("envs", {})
    default_env = hatch_envs.setdefault("default", {})
    default_env["python"] = python_version
    default_env["path"] = f".envs/{project_name}"
    default_env["dependencies"] = ["pytest", "pytest-mock", "pytest-asyncio", "requests", "sphinx"]
    default_env["scripts"] = {
        "test": f"pytest -vv -m 'not network' --ignore third_party {{args:tests}}",
        "test-all": f"pytest -vv --ignore third_party {{args:tests}}",
        "test-cov": "coverage run -m pytest -m 'not network' {{args:tests}}",
        "test-cov-all": "coverage run -m pytest {{args:tests}}",
        "cov-report": ["- coverage combine", "coverage report"],
        "cov": ["test-cov", "cov-report"],
        "cov-all": ["test-cov-all", "cov-report"],
    }

    conda_env = hatch_envs.setdefault("conda", {})
    conda_env["type"] = "conda"
    conda_env["python"] = python_version
    conda_env["command"] = "conda"
    conda_env["conda-forge"] = False
    conda_env["environment-file"] = "environment.yml"
    conda_env["prefix"] = ".venv/"

    hatch_envs["all"] = {"matrix": [{"python": ["3.10", "3.11", "3.12"]}]}

    types_env = hatch_envs.setdefault("types", {})
    types_env["dependencies"] = ["mypy>=1.0.0"]
    types_env["scripts"] = {"check": f"mypy --install-types --non-interactive {{args:{project_name}/ tests}}"}

    # Coverage configuration
    coverage = tool.setdefault("coverage", {})
    coverage["run"] = {
        "source_pkgs": [project_name, "tests"],
        "branch": True,
        "parallel": True,
        "omit": [f"{project_name}/__about__.py"],
    }
    coverage["paths"] = {
        project_name: [f"{project_name}/"],
        "tests": ["tests"],
    }
    coverage["report"] = {
        "exclude_lines": ["no cov", "if __name__ == .__main__.:", "if TYPE_CHECKING:"],
    }

    # Ruff configuration
    ruff = tool.setdefault("ruff", {})
    ruff["line-length"] = 120
    ruff["indent-width"] = 4
    ruff["target-version"] = f"py{python_version.replace('.', '')}"

    ruff_lint = ruff.setdefault("lint", {})
    ruff_lint["extend-unsafe-fixes"] = ["ALL"]
    ruff_lint["select"] = [
        "A", "C4", "D", "E", "F", "UP", "B", "SIM", "N", "ANN", "ASYNC",
        "S", "T20", "RET", "SIM", "ARG", "PTH", "ERA", "PD", "I", "PLW",
    ]
    ruff_lint["ignore"] = [
        "D100", "D101", "D104", "D106", "ANN101", "ANN102", "ANN003", "UP009", "ANN204",
        "B026", "ANN001", "ANN401", "ANN202", "D107", "D102", "D103", "E731", "UP006",
        "UP035", "ANN002", "PLW2901", "UP035", "UP006",
    ]
    ruff_lint["fixable"] = ["ALL"]
    ruff_lint["unfixable"] = []

    ruff["format"] = {
        "docstring-code-format": True,
        "quote-style": "double",
        "indent-style": "space",
        "skip-magic-trailing-comma": False,
        "line-ending": "auto",
    }

    ruff_lint["pydocstyle"] = {"convention": "google"}

    ruff_lint["per-file-ignores"] = {
        "**/{tests,docs}/*": ["ALL"],
        "**__init__.py": ["F401"],
    }

    return tomlkit.dumps(pyproject)


