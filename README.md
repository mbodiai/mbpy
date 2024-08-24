# mbpy (WIP)

[![PyPI - Version](https://img.shields.io/pypi/v/mbpy.svg)](https://pypi.org/project/mbpy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mbpy.svg)](https://pypi.org/project/mbpy)

-----

Install and manage pyproject.toml with pip commands.

See usage:

```
mpypip --help
```


## Table of Contents

- [mbpy (WIP)](#mbpy-wip)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Documentation](#documentation)
  - [License](#license)

## Installation

```console
pip install mbpy
```

## Usage

For detailed usage instructions, please refer to the [documentation](#documentation).

```console
mpip --help
```

```
Usage: mpip [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --hatch-env TEXT  Specify the Hatch environment to use
  --help                Show this message and exit.

Commands:
  find       Find a package on PyPI and optionally sort the results.
  info       Get information about a package from PyPI.
  install    Install packages and update requirements.txt and...
  show       Show the dependencies from the pyproject.toml file.
  uninstall  Uninstall packages and update requirements.txt and...
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

`mbpy` is distributed under the terms of the [apache-2.0](https://spdx.org/licenses/apache-2.0.html) license.
