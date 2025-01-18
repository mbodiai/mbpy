# Git Cliff +  Changelong generator
# Blogpost generator
# git commit fetcher as context for llm
# MYPY extensions for arg kwargs?
# https://blog.ganssle.io/articles/2021/10/setup-py-deprecated.html#summary
# long functions break into steps
import ast
from pathlib import Path


def read_description(pkg_file: Path, search_key:str| None =None) -> str:
    """Return the first sentence of the docstring."""
    mod = ast.parse(pkg_file.read_text(), pkg_file)
    from pydoc import apropos
    if ast.get_docstring(mod):
      desc = ast.get_docstring(mod)
    if desc:
        return desc
    if search_key and (desc := apropos(search_key)):
        return desc
    return "No description found"
    