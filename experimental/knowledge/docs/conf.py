
# Configuration file for the Sphinx documentation builder.
import os
import sys
sys.path.insert(0, os.path.abspath('knowledge'))

project = 'knowledge'
copyright = '2024, mbodiai'
author = 'mbodiai'

extensions = [
 'autodoc2',
 'sphinx.ext.napoleon',
]

autodoc2_packages = [
 {
     'path': 'knowledge',
     'auto_mode': True,
 },
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'furo'
html_static_path = ['_static']
