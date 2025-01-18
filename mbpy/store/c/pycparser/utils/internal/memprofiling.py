from pycparser import parse_file
from pycparser.c_ast import *


def expand_decl(decl):
    """Converts the declaration into a nested list."""
    typ = type(decl)

    if typ == TypeDecl:
        return ['TypeDecl', expand_decl(decl.type)]
    if typ == IdentifierType:
        return ['IdentifierType', decl.names]
    if typ == ID:
        return ['ID', decl.name]
    if typ in [Struct, Union]:
        decls = [expand_decl(d) for d in decl.decls or []]
        return [typ.__name__, decl.name, decls]
    nested = expand_decl(decl.type)

    if typ == Decl:
        if decl.quals:
            return ['Decl', decl.quals, decl.name, nested]
        return ['Decl', decl.name, nested]
    if typ == Typename: # for function parameters
        if decl.quals:
            return ['Typename', decl.quals, nested]
        return ['Typename', nested]
    if typ == ArrayDecl:
        dimval = decl.dim.value if decl.dim else ''
        return ['ArrayDecl', dimval, nested]
    if typ == PtrDecl:
        return ['PtrDecl', nested]
    if typ == Typedef:
        return ['Typedef', decl.name, nested]
    if typ == FuncDecl:
        params = [expand_decl(param) for param in decl.args.params] if decl.args else []
        return ['FuncDecl', params, nested]
    return None

#-----------------------------------------------------------------
class NodeVisitor:
    def __init__(self):
        self.current_parent = None

    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def visit_FuncCall(self, node) -> None:
        pass

    def generic_visit(self, node) -> None:
        """Called if no explicit visitor function exists for a
        node. Implements preorder visiting of the node.
        """
        oldparent = self.current_parent
        self.current_parent = node
        for c in node.children():
            self.visit(c)
        self.current_parent = oldparent


def heapyprofile() -> None:
    # pip install guppy
    # [works on python 2.7, AFAIK]
    import gc

    from guppy import hpy

    hp = hpy()
    parse_file('/tmp/197.c')
    gc.collect()
    hp.heap()


def memprofile() -> None:
    import tracemalloc

    tracemalloc.start()

    parse_file('/tmp/197.c')


    snapshot = tracemalloc.take_snapshot()
    for _stat in snapshot.statistics('lineno')[:20]:
        pass


if __name__ == "__main__":
    source_code = r'''void foo() {
    L"hi" L"there";
}
    '''

    memprofile()
    #heapyprofile()

    #parser = CParser()
    #ast = parser.parse(source_code, filename='zz')
    #ast.show(showcoord=True, attrnames=True, nodenames=True)


