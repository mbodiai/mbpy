#-----------------------------------------------------------------
# Benchmarking utility for internal use.
#
# Use with Python 3.6+
#
# Eli Bendersky [https://eli.thegreenplace.net/]
# License: BSD
#-----------------------------------------------------------------
import os
import sys
import time

sys.path.extend(['.', '..'])

from pycparser import c_ast, c_parser


def measure_parse(text, n, progress_cb):
    """Measure the parsing of text with pycparser.

    text should represent a full file. n is the number of iterations to measure.
    progress_cb will be called with the iteration number each time one is done.

    Returns a list of elapsed times, one per iteration.
    """
    times = []
    for i in range(n):
        parser = c_parser.CParser()
        t1 = time.time()
        ast = parser.parse(text, '')
        elapsed = time.time() - t1
        assert isinstance(ast, c_ast.FileAST)
        times.append(elapsed)
        progress_cb(i)
    return times


def measure_file(filename, n) -> None:
    progress_cb = lambda i: print('.', sep='', end='', flush=True)
    with open(filename) as f:
        text = f.read()
        measure_parse(text, n, progress_cb)


NUM_RUNS = 5


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
    for filename in os.listdir(sys.argv[1]):
        filename = os.path.join(sys.argv[1], filename)
        measure_file(filename, NUM_RUNS)
