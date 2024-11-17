import unittest
import networkx as nx
from mbpy.g2 import build_dependency_graph, get_stats
from mbpy.graph import effective_size
import logging

logging.basicConfig(level=logging.DEBUG)


def test_effective_size():
    G = nx.Graph()
    G.add_edges_from([("A", "B"), ("A", "C"), ("B", "C"), ("C", "D"), ("D", "E")])

    expected = {
        "A": 2 - (2 * 1) / 2,  # 2 - 1 = 1.0
        "B": 2 - (2 * 1) / 2,  # 2 - 1 = 1.0
        "C": 3 - (2 * 2) / 3,  # 3 - 1.3333 ≈ 1.6667
        "D": 2 - (2 * 0) / 2,  # 2 - 0 = 2.0
        "E": 1 - (2 * 0) / 1,  # 1 - 0 = 1.0
    }

    esize = effective_size(G)
    for node in expected:
        print(f"Node: {node}, Expected: {expected[node]:.4f}, Computed: {esize.get(node, 'N/A'):.4f}")


# Test for requests
# Test cases for dependency graph analysis
class TestDependencyGraph(unittest.TestCase):
    def setUp(self):
        self.requests_path = Path(__import__("requests").__file__).resolve().parent
        self.result = build_dependency_graph(self.requests_path, include_site_packages=True)
        self.module_nodes = self.result["module_nodes"]
        self.adjacency_list = self.result["adjacency_list"]
        self.reverse_adjacency_list = self.result["reverse_adjacency_list"]
        self.stats = get_stats(self.module_nodes, self.adjacency_list, self.reverse_adjacency_list)

    def test_num_modules(self):
        self.assertGreaterEqual(self.stats["num_modules"], 1, "Expected at least 1 module in requests")

    def test_avg_degree(self):
        self.assertGreater(self.stats["avg_degree"], 0, "Average degree should be greater than 0")

    def test_effective_size(self):
        for node, size_data in self.stats["size_importance"]:
            self.assertIn("effective_size", size_data)
            self.assertIn("pagerank", size_data)
            self.assertIn("neighbors", size_data)


# Run the tests
unittest.main(argv=[""], exit=False)
