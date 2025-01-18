
# conf.py
# Configuration file for the Sphinx documentation builder.
import os
import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------

project = "mb"
author = "mbodiai"
copyright = "2024, mbodiai"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",  # Core Sphinx extension for auto-generating documentation from docstrings
    "sphinx.ext.viewcode",  # Adds links to highlighted source code
    "sphinx.ext.napoleon",  # Supports Google and NumPy style docstrings
    "sphinx.ext.githubpages",  # Creates .nojekyll file for publishing on GitHub Pages
    "sphinx.ext.autosummary",  # Added autosummary extension
    
]

source_suffix = {
    ".rst": "restructuredtext",
    
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

html_theme = "furo"
html_static_path = ["_static"]

# -- Theme Options ----------------------------------------------------------

# Custom Color Scheme
mbodi_color = {
    "c50": "#fde8e8",
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
    "sidebar_width": "300px",
    "light_css_variables": {
        "color-sidebar-background": mbodi_color["c50"],
        "color-sidebar-border": mbodi_color["c700"],
        "color-brand-primary": "#ed3d5d",
        "color-brand-content": "#ed3d5d",
    },
    "dark_css_variables": {
        "color-sidebar-background": mbodi_color["c800"],
        "color-sidebar-border": mbodi_color["c700"],
        "color-brand-primary": "#f15c5c",
        "color-brand-content": "#f15c5c",
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

# -- Extensions configuration -----------------------------------------------
autosummary_generate = True  # Generate stub pages for autosummary
autosummary_imported_members = True

# -- Custom Static and Template Paths -----------------------------------------

