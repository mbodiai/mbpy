import sys

sys.path.insert(0, '../..')

from pycparser import c_ast, parse_file


class MyVisitor(c_ast.NodeVisitor):
    def visit_Typedef(self, node) -> None:
        pass



def generate_fake_typedefs(filename) -> None:
    ast = parse_file(filename, use_cpp=True, cpp_path="../cpp.exe")
    v = MyVisitor()
    v.visit(ast)


if __name__ == "__main__":
    generate_fake_typedefs('example_c_file_pp.c')

