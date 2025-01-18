
# Configuration file for Sphinx
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = "mbpy"
author = "mbodiai"
copyright = "2024, mbodiai"

# Add extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
    "sphinx.ext.autosummary",
    "sphinx_design"
]

# Source settings
source_suffix = {
    '.rst: 'restructuredtext''
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
    "light_css_variables": {
        "color-foreground-primary": "var(--color-content-foreground)",
        "color-background-primary": "#ffffff",
        "color-background-secondary": "#f8f9fb",
        "color-brand-primary": "#ed3d5d",
        "color-brand-content": "#ed3d5d",
        "color-api-background": "var(--color-background-secondary)",
    },
    "dark_css_variables": {
        "color-foreground-primary": "var(--color-content-foreground)",
        "color-background-primary": "#131416",
        "color-background-secondary": "#1a1c1e",
        "color-brand-primary": "#f15c5c",
        "color-brand-content": "#f15c5c",
        "color-api-background": "var(--color-background-secondary)",
    },
    "announcement": "⚡ Currently in beta!",
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
autosummary_generate = True
autosummary_imported_members = True
autosummary_ignore_module_all = False

# -- Custom Static and Template Paths -----------------------------------------

