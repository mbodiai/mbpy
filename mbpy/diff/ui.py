from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from mbpy.diff.core import DiffBlock

class DiffRenderer:
    @staticmethod
    def render_block(block: DiffBlock, is_current: bool = False) -> list[Text]:
        style = "bold cyan" if is_current else ""
        prefix = "→ " if is_current else "  "
        header = Text(f"{prefix}[{block.is_selected and 'x' or ' '}] {block.description}")
        header.stylize(style)
        
        if block.is_folded:
            header.append(" [folded]")
            return [header]
        
        result = [header]
        if not block.is_folded:
            for line in block.changes:
                style = "green" if line.startswith('+') else "red" if line.startswith('-') else ""
                result.append(Text(f"    {line}", style=style))
        
        return result

class DiffDisplay:
    def __init__(self, console: Console):
        self.console = console
        self.layout = Layout()

        # Create sub-layouts with initial content
        header = Layout(name="header")
        header.update(Panel("Diff Selector"))
        header.size = 3

        # Create main content area first
        main = Layout(name="main")
        main.update(Panel("Loading..."))
        main.ratio = 2

        help_view = Layout(name="help")
        help_view.update(Panel("Press ? for help"))
        help_view.visible = False

        # Create body layout and split it
        body = Layout(name="body")
        body.split_row(
            main,
            help_view
        )

        footer = Layout(name="footer")
        footer.update(Panel("j/k: Navigate | Space: Select | z: Fold | ?: Help | q: Quit"))
        footer.size = 3

        # Split root layout last
        self.layout.split_column(
            header,
            body,
            footer
        )

    def update(self, blocks: list[DiffBlock], current_idx: int, status: str = ""):
        """Update the display with current state."""
        header = self.layout.get("header")
        body = self.layout.get("body")
        main = body.get("main") if body else None
        help_section = body.get("help") if body else None

        if not all([header, body, main]):
            raise ValueError("Layout structure is invalid")

        # Create header text first
        header_text = Text(f"Block {current_idx + 1}/{len(blocks)} | {status}", style="bold cyan")
        header.update(Panel(header_text, title="Header"))

        # Create content group
        block_content = Group(*[
            DiffRenderer.render_block(block, i == current_idx)
            for i, block in enumerate(blocks)
        ])
        
        # Update main panel with content
        main.update(Panel(
            block_content,
            title=f"[bold cyan]Diff View ({len(blocks)} blocks)[/bold cyan]",
            border_style="cyan"
        ))

        # Update help if visible
        if help_section and help_section.visible:
            help_section.update(Panel(
                Markdown(HELP_TEXT)
            ))