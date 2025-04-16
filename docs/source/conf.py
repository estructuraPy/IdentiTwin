# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:

import os
import sys

sys.path.insert(0, os.path.abspath('../../src'))
# -- Project information -----------------------------------------------------

project = 'IdentiTwin'
copyright = '2025, Instituto Tecnológico de Costa Rica'
authors = ['Angel Navarro-Mora', 'Alvaro Perez-Mora']
author = ', '.join(authors)
release = '0.0.1'

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.autosummary'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# Add autodoc settings
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

# Add intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/', None),
}

# Add autosummary
autosummary_generate = True

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Ensure that the module documentation can be found
html_extra_path = ['modules']
