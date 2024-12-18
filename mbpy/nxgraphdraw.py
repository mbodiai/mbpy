import os
from typing import List, Tuple, TypedDict

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.offsetbox import AnnotationBbox, OffsetImage


# Define the NodeAttributes TypedDict
class NodeAttributes(TypedDict, total=False):
    label: str
    size: int
    color: str
    shape: str
    icon: str | None

# Define the GraphBuilder class
class GraphBuilder:
    def __init__(self):
        self.node_array: List[List[List[NodeAttributes]]] = []
        self.edge_list: List[Tuple[str, str]] = []
        self._current_column: List[List[NodeAttributes]] = []
        self._current_row: List[NodeAttributes] = []

    def column(self):
        return self.ColumnContext(self)

    def row(self):
        return self.RowContext(self)

    def add_node(self, node: NodeAttributes) -> None:
        if not self._current_row:
            self._current_row = []
        self._current_row.append(node)

    def add_nodes(self, nodes: List[NodeAttributes]) -> None:
        if not self._current_row:
            self._current_row = []
        self._current_row.extend(nodes)

    class ColumnContext:
        def __init__(self, builder: 'GraphBuilder'):
            self.builder = builder

        def __enter__(self):
            self.builder._current_column = []
            return self.builder

        def __exit__(self, exc_type, exc_value, traceback):
            self.builder.node_array.append(self.builder._current_column)
            self.builder._current_column = []

    class RowContext:
        def __init__(self, builder: 'GraphBuilder'):
            self.builder = builder

        def __enter__(self):
            self.builder._current_row = []
            return self.builder

        def __exit__(self, exc_type, exc_value, traceback):
            self.builder._current_column.append(self.builder._current_row)
            self.builder._current_row = []

# Adjusted draw_graph function to handle the new node_array structure
# Now, using the GraphBuilder to construct your graph
graph = GraphBuilder()

with graph.column():
    # Wrap in a row context
    with graph.row():
        graph.add_nodes(
            [
                {
                    "label": "Consumer Goods Manufacturers",
                    "shape": "o",
                    "color": "yellow",
                    "size": 3000,
                },
            ],
        )

with graph.column():
    with graph.row():
        graph.add_nodes(
            [
                {
                    "label": "Foundation Models",
                    "shape": "s",
                    "color": "orange",
                    "size": 3000,
                },
                {
                    "label": "Networking and AI Infrastructure",
                    "shape": "^",
                    "color": "lightcoral",
                    "size": 3000,
                },
            ],
        )
    with graph.row():
        graph.add_nodes(
            [
                {
                    "label": "SDKs",
                    "shape": "D",
                    "color": "violet",
                    "size": 3000,
                    "icon": "icons/sdk.png",
                },
                {
                    "label": "Integrators",
                    "shape": "o",
                    "color": "lightblue",
                    "size": 5000,
                },
            ],
        )

with graph.column(), graph.row():  # Ensure this is wrapped in a row
    graph.add_nodes(
        [
            {
                "label": "Humanoid Robotic Hardware Manufacturers",
                "shape": "o",
                "color": "lightgreen",
                "size": 3000,
            },
            {
                "label": "Industrial Robotic Hardware Manufacturers",
                "shape": "o",
                "color": "green",
                "size": 3000,
            },
        ],
    )

# Edge list
edge_list = [
    ("Foundation Models", "Networking and AI Infrastructure"),
    ("Foundation Models", "SDKs"),
    ("Networking and AI Infrastructure", "Integrators"),
    ("SDKs", "Integrators"),
    ("Humanoid Robotic Hardware Manufacturers", "Consumer Goods Manufacturers"),
    ("Industrial Robotic Hardware Manufacturers", "Consumer Goods Manufacturers"),
]
def draw_graph(
    node_array: List[List[List[NodeAttributes]]], edge_list: List[Tuple[str, str]],
) -> None:
    G = nx.DiGraph()
    pos = {}
    # Assign positions based on the structure of node_array
    for x_idx, column in enumerate(node_array):
        for y_idx, row in enumerate(column):
            for node_attr in row:
                label = node_attr["label"]
                G.add_node(label)
                # Position nodes: x position is column index, y position is row index
                pos[label] = (x_idx * 2, -y_idx)
                # Update node attributes
                G.nodes[label].update(node_attr)

    # Add edges to the graph
    G.add_edges_from(edge_list)

    # Drawing code
    plt.figure(figsize=(14, 10))
    ax = plt.gca()

    # Extract shapes
    node_shapes = set(nx.get_node_attributes(G, "shape").values())
    for shape in node_shapes:
        shape_nodes = [
            node for node, data in G.nodes(data=True) if data.get("shape", "o") == shape
        ]
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=shape_nodes,
            node_color=[
                G.nodes[node].get("color", "lightblue") for node in shape_nodes
            ],
            node_size=[G.nodes[node].get("size", 3000) for node in shape_nodes],
            node_shape=shape,
            alpha=0.9,
            edgecolors="black",
            linewidths=2,
            ax=ax,
        )

    # Draw edges
    nx.draw_networkx_edges(
        G,
        pos,
        edge_color="black",
        arrowsize=30,
        width=3,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0",
        min_source_margin=20,
        min_target_margin=30,
        ax=ax,
    )

    # Add labels
    nx.draw_networkx_labels(
        G,
        pos,
        labels={node: node for node in G.nodes()},
        font_size=12,
        font_weight="bold",
        bbox={'facecolor': "white", 'edgecolor': "black", 'boxstyle': "round,pad=0.5"},
        ax=ax,
    )

    # Add icons if specified
    for node in G.nodes():
        icon_path = G.nodes[node].get("icon")
        if icon_path and os.path.exists(icon_path):
            image = plt.imread(icon_path)
            imagebox = OffsetImage(image, zoom=0.15)
            ab = AnnotationBbox(
                imagebox, pos[node], frameon=False, box_alignment=(0.5, 0.5),
            )
            ax.add_artist(ab)

    plt.title("Custom Graph with Shapes and Icons", fontsize=18, fontweight="bold")
    plt.axis("off")
    plt.show()
# Draw the graph
draw_graph(graph.node_array, edge_list)