# mbpy - Manage Python Projects with Ease

[![PyPI - Version](https://img.shields.io/pypi/v/mbpy.svg)](https://pypi.org/project/mbpy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mbpy.svg)](https://pypi.org/project/mbpy)

-----

`mbpy` is a powerful tool for creating, managing, and documenting Python projects. It simplifies the process of setting up project structures, managing dependencies, and generating documentation.

## Features

- Create new Python projects with customizable structures
- Manage project dependencies using pyproject.toml
- Set up documentation using Sphinx or MkDocs
- Generate GitHub Actions workflows for CI/CD
- Simplify package installation and management with pip-like commands

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Documentation](#documentation)
- [License](#license)

## Installation

```console
pip install mbpy
```

## Usage

To create a new project:

```console
mbpy create <project_name> --author "<Your Name>" --description "<Project Description>"
```

To manage dependencies:

```console
mpip install <package_name>
mpip uninstall <package_name>
mpip show
```

For more detailed usage instructions, run:

```console
mbpy --help
```

or

```console
mpip --help
```

## Documentation

To view the full documentation, you have two options:

### Sphinx

1. Build the docs:
   ```
   hatch run docs
   ```
2. Open `docs/_build/html/index.html` in your web browser.

### MkDocs

1. Install MkDocs if you haven't already:
   ```
   pip install mkdocs
   ```
2. Build and serve the docs:
   ```
   mkdocs serve
   ```
3. Open your web browser and go to `http://127.0.0.1:8000/`

## License

`mbpy` is distributed under the terms of the [MIT License](LICENSE).
