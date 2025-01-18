import pytest
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.layout import Layout
from mbpy.diff.ui import DiffDisplay, DiffRenderer
from mbpy.diff.core import DiffBlock, DiffContext

@pytest.fixture
def console():
    return Console()

@pytest.fixture
def diff_block():
    return DiffBlock(
        header="@@ -1,3 +1,4 @@",
        changes=[
            "-    print('hello')",
            "+    print('hello world')"
        ],
        context=DiffContext(
            before=[" def hello():"],
            after=[" "]
        )
    )

@pytest.fixture
def simple_layout():
    """Create a simple test layout without full initialization"""
    layout = Layout()
    layout.split_column(
        Layout(Panel("Header"), name="header", size=3),
        Layout(Panel("Body"), name="body"),
        Layout(Panel("Footer"), name="footer", size=3)
    )
    return layout

class TestLayoutStructure:
    """Test suite for complex layout behavior"""
    
    def test_layout_initialization(self, console):
        """Test complete layout tree initialization"""
        display = DiffDisplay(console)
        layout = display.layout
        
        # Test main structure
        assert layout.get("header") is not None
        assert layout.get("body") is not None
        assert layout.get("footer") is not None
        
        # Test body split
        body = layout.get("body")
        assert body.get("main") is not None
        assert body.get("help") is not None
        
        # Test help panel visibility
        assert not body.get("help").visible
    
    def test_layout_content_update(self, console, diff_block):
        """Test layout content updates properly"""
        display = DiffDisplay(console)
        
        # Update with single block
        display.update([diff_block], 0, "Test status")
        
        # Get panel content string
        header_panel = display.layout.get("header").renderable
        header_content = str(header_panel.renderable)  # Access Panel's renderable property
        
        assert "Block 1/1" in header_content
        assert "Test status" in header_content

class TestRendererBehavior:
    """Test suite for renderer edge cases"""
    
    def test_empty_changes(self, diff_block):
        """Test renderer handles empty changes"""
        diff_block.changes = []
        rendered = DiffRenderer.render_block(diff_block)
        assert len(rendered) == 1  # Should still have header
    
    def test_mixed_changes(self, diff_block):
        """Test renderer handles mixed additions and deletions"""
        diff_block.changes = [
            "-line1",
            "+line2",
            " unchanged",
            "-line3",
            "+line4"
        ]
        rendered = DiffRenderer.render_block(diff_block)
        assert len(rendered) == 6  # Header + 5 lines
        
        # Verify styling
        text = rendered[1]
        assert text.style == "red"  # First change is deletion
        
        text = rendered[2]
        assert text.style == "green"  # Second change is addition

class TestInteractionStates:
    """Test suite for interaction states"""
    
    def test_folded_selected_current(self, diff_block):
        """Test block showing all states simultaneously"""
        diff_block.is_folded = True
        diff_block.is_selected = True
        rendered = DiffRenderer.render_block(diff_block, is_current=True)
        
        text = rendered[0].plain
        assert "→" in text  # Current indicator
        assert "[x]" in text  # Selected indicator
        assert "[folded]" in text  # Folded indicator
    
    @pytest.mark.parametrize("num_blocks", [1, 5, 10])
    def test_multiple_blocks_rendering(self, console, diff_block, num_blocks):
        """Test handling different numbers of blocks"""
        blocks = [diff_block] * num_blocks
        display = DiffDisplay(console)
        display.update(blocks, 0, "")
        
        # Check panel title for block count
        main_panel = display.layout.get("body").get("main").renderable
        panel_title = main_panel.title
        assert str(num_blocks) in panel_title

def test_layout_creation(console):
    """Test basic layout structure creation"""
    display = DiffDisplay(console)
    
    # First verify root layout exists
    assert isinstance(display.layout, Layout)
    
    # Try accessing each section directly from root
    header = display.layout.get("header")
    body = display.layout.get("body")
    footer = display.layout.get("footer")
    
    assert all([header, body, footer]), "All main sections should exist"
    
    # Check sizes are correct
    assert header.size == 3
    assert footer.size == 3
    assert body.size is None  # Body should be flexible

def test_renderer_handles_folded_block(diff_block):
    """Test renderer handles folded blocks correctly"""
    diff_block.is_folded = True
    rendered = DiffRenderer.render_block(diff_block)
    assert len(rendered) == 1
    assert "[folded]" in rendered[0].plain

def test_renderer_shows_selected_block(diff_block):
    """Test renderer shows selection state correctly"""
    diff_block.is_selected = True
    rendered = DiffRenderer.render_block(diff_block)
    assert "[x]" in rendered[0].plain

def test_renderer_shows_current_block(diff_block):
    """Test renderer shows current block indicator"""
    rendered = DiffRenderer.render_block(diff_block, is_current=True)
    assert "→" in rendered[0].plain