# setup.py
from setuptools import Extension, setup

from Cython.Build import cythonize

extensions: list[Extension] = [
    Extension("mod", ["mbpy/testcmd/mod.pyx"],include_dirs=[]),
]

setup(ext_modules=cythonize(extensions, language_level=3))
