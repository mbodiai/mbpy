import pytest
from rich.console import Console
from mbpy.diff.core import DiffBlock, DiffContext  # Absolute import

@pytest.fixture
def console():
    return Console(force_terminal=True)

@pytest.fixture
def sample_diff():
    return [
        "@@ -1,3 +1,4 @@",
        " def hello():",
        "-    print('hello')",
        "+    print('hello world')",
        "+    return True",
        " ",
    ]

@pytest.fixture
def diff_block():
    return DiffBlock(
        header="@@ -1,3 +1,4 @@",
        changes=[
            "-    print('hello')",
            "+    print('hello world')",
            "+    return True"
        ],
        context=DiffContext(
            before=[" def hello():"],
            after=[" "]
        )
    )