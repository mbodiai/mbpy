#-----------------------------------------------------------------
# pycparser: rewrite_ast.py
#
# Tiny example of rewriting a AST node
#
# Eli Bendersky [https://eli.thegreenplace.net/]
# License: BSD
#-----------------------------------------------------------------
import sys

sys.path.extend(['.', '..'])
from pycparser import c_parser

text = r"""
void func(void)
{
  x = 1;
}
"""

if __name__ == '__main__':
    parser = c_parser.CParser()
    ast = parser.parse(text)
    ast.show(offset=2)

    assign = ast.ext[0].body.block_items[0]
    assign.lvalue.name = "y"
    assign.rvalue.value = 2

    ast.show(offset=2)
