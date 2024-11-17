
SPHINX_CONF="""""
# conf.py
# Configuration file for the Sphinx documentation builder.
import os
import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------

project = "{project_name}"
author = "{author}"
copyright = "2024, {author}"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",  # Core Sphinx extension for auto-generating documentation from docstrings
    "sphinx.ext.viewcode",  # Adds links to highlighted source code
    "sphinx.ext.napoleon",  # Supports Google and NumPy style docstrings
    "sphinx.ext.githubpages",  # Creates .nojekyll file for publishing on GitHub Pages
    "myst_parser",  # Enables Markdown support
]

# Enable both reStructuredText and Markdown file extensions
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Paths that contain templates, relative to this directory.
templates_path = ["_templates"]

# List of patterns to exclude from the documentation build.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "docs",
    "**/*.c",
    "**/*.so",
    "**/*.dylib",
    "**/*.dll",
    "**/*prover**/*",
    "nltk/prover/",
    "*.h",
    "**/*/docs*.py",
    "**/*test*",
]

# -- Options for HTML output -------------------------------------------------

html_theme = "furo"  # You can change this to another theme if desired
html_static_path = ["_static"]

# -- Theme Options ----------------------------------------------------------

# Custom Color Scheme
mbodi_color = {
    "c50": "#fde8e8",
    "c100": "#f9b9b9",
    "c200": "#f58b8b",
    "c300": "#f15c5c",
    "c400": "#ee2e2e",
    "c500": "#ed3d5d",  # Main theme color
    "c600": "#b93048",
    "c700": "#852333",
    "c800": "#51171f",
    "c900": "#1e0a0a",
    "c950": "#0a0303",
    "name": "mbodi",
}

html_theme_options = {
    "sidebar_hide_name": True,
    "sidebar_width": "300px",
    "light_css_variables": {
        "color-brand-primary": mbodi_color["c500"],
        "color-sidebar-background": mbodi_color["c50"],
        "color-sidebar-border": mbodi_color["c700"],
    },
    "dark_css_variables": {
        "color-brand-primary": mbodi_color["c500"],
        "color-sidebar-background": mbodi_color["c800"],
        "color-sidebar-border": mbodi_color["c700"],
    },
    "navigation_depth": 3,
    "sidebar_items": ["page-toc", "search"],
}

# -- Napoleon Settings -------------------------------------------------------

# Enable Google style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True  # Disable NumPy style if not used
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_param = True
napoleon_use_rtype = True

# -- Autodoc Settings --------------------------------------------------------

autodoc_typehints = "description"  # Show type hints in description
autodoc_member_order = "bysource"  # Order members by source code order

# -- MyST Parser Settings -----------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_admonition",
    "html_image",
    "linkify",
]

# -- Custom Static and Template Paths -----------------------------------------

# Optionally, add custom CSS files
# html_css_files = [
#     "custom.css",
# ]

# Optionally, add custom JavaScript files
# html_js_files = [
#     "custom.js",
# ]
"""

SPHINX_INDEX = """
Welcome to {project_name}'s Documentation by {author}!
======================================================

{description}

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   getting_started

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`"""

SPHINX_API = """
{project_name} API Reference
============================

.. toctree::
   :maxdepth: 2
   :caption: Modules:

   {module_name}

.. automodule:: {module_name}
   :members:
   :undoc-members:
   :show-inheritance:
""" 


SPHINX_MAKEFILE = """
# Makefile for Sphinx documentation

# You can set these variables from the command line.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without a target is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Catch-all target: route all other targets to Sphinx using the new
# "make mode" option.  See documentation for Sphinx Makefile.
.PHONY: help Makefile
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
"""