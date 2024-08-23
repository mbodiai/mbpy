# Configuration file for the Sphinx documentation builder.
import os
import sys

sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------
project = 'mpip'
copyright = '2024, Sebastian Peralta'
author = 'Sebastian Peralta'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_click',
    'myst_parser',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# -- Extension configuration -------------------------------------------------
autodoc_typehints = 'description'
autodoc_member_order = 'bysource'
