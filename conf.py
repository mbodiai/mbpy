
# Configuration file for the Sphinx documentation builder.
import os
import sys

sys.path.insert(0, os.path.abspath('..'))
project = 'mbpy'
copyright = '2024, mbodiai'
author = 'mbodiai'

# Example taken from https://github.com/sphinx-extensions2/sphinx-autodoc2/issues/33#issuecomment-2196309585 
extensions = [
    'sphinx.ext.autodoc2',
    'sphinx.ext.napoleon',
    "sphinx-tippy",
    "myst_parser",
]
autodoc2_docstring_parser_regexes = [
    (
        ".*",
        "projects/mbpy/docutils/docs_parser",
    ),
]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'furo'
html_static_path = ['_static']
