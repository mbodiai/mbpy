from importlib.resources import files
from typing import List
import click
import difflib
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.syntax import Syntax
from rich.prompt import Confirm
from rich.table import Table
from rich import print as rprint
import rich_click as click
from rich.live import Live
from rich.layout import Layout
from rich.markdown import Markdown
from rich.console import Group
from rich.padding import Padding
from rich.box import HEAVY
from rich.style import Style
from rich.text import Text
from dataclasses import dataclass
import collections

console = Console()

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "yellow italic"
click.rich_click.STYLE_OPTION = "green"
click.rich_click.STYLE_SWITCH = "bold cyan"

HELP_TEXT = "j/k: Move | Space: Select | z: Toggle fold | ?: Help | q: Quit"

def create_backup(file_path):
    """Create a backup of the given file."""
    backup_path = f"{file_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    shutil.copy2(file_path, backup_path)
    return backup_path

def escape_markup(text):
    """Escape square brackets in text to prevent markup parsing errors."""
    return text.replace('[', '\\[').replace(']', '\\]').replace('\\\\', '\\')

def display_tree_view(blocks):
    """Display diff blocks in a tree structure with proper markup escaping."""
    tree = Tree("[bold cyan]Diff Overview[/bold cyan]")
    
    for i, block in enumerate(blocks, 1):
        block_tree = tree.add(f"[bold yellow]Block {i}[/bold yellow]")
        
        # Show header/location
        block_tree.add(f"[dim]{escape_markup(block.header.strip())}[/dim]")
        
        # Changes
        changes = block_tree.add("[bold green]Changes[/bold green]")
        for line in block.changes:
            if line.startswith('+'):
                changes.add(f"[green]{escape_markup(line.strip())}[/green]")
            elif line.startswith('-'):
                changes.add(f"[red]{escape_markup(line.strip())}[/red]")
            else:
                changes.add(f"[dim]{escape_markup(line.strip())}[/dim]")
        
        # Context
        if block.context.before:
            context = block_tree.add("[dim]Context[/dim]")
            for line in block.context.before[:2]:
                context.add(f"[dim]{escape_markup(line.strip())}[/dim]")
    
    return tree

@dataclass
class DiffContext:
    before: List[str]
    after: List[str]

@dataclass
class DiffBlock:
    header: str
    changes: List[str]
    context: DiffContext
    is_folded: bool = False
    is_selected: bool = False
    
    def toggle_fold(self) -> None:
        """Toggle the folded state of the block."""
        self.is_folded = not self.is_folded
    
    @property 
    def description(self) -> str:
        """Generate a meaningful description from the changes."""
        for change in self.changes:
            if change.startswith('+'):
                line = change[1:].strip()
                if line and not line.isspace():
                    return line[:57] + ('...' if len(line) > 57 else '')
        return self.header.strip()

class DiffParser:
    @staticmethod
    def parse_blocks(diff: List[str]) -> List[DiffBlock]:
        """Parse unified diff into structured diff blocks."""
        blocks = []
        current_block = None
        context_before = []
        context_after = []
        changes = []
        header = ""
        
        for line in diff:
            if line.startswith("@@"):
                if current_block:
                    blocks.append(DiffBlock(header, changes, DiffContext(context_before, context_after)))
                header = line
                changes = []
                context_before = []
                context_after = []
                current_block = True
            elif current_block:
                if line.startswith(" "):
                    if changes:
                        context_after.append(line)
                    else:
                        context_before.append(line)
                else:
                    changes.append(line)
        
        if current_block:
            blocks.append(DiffBlock(header, changes, DiffContext(context_before, context_after)))
        
        return blocks

class DiffViewer:
    def __init__(self, blocks):
        self.blocks = blocks
        self.current_index = 0
        self.show_help = True  # Always show help at first
        self.status_message = ""
        self.tree_view = display_tree_view(blocks)
        self.layout = self._create_layout()

    def _create_layout(self):
        """Create a split layout with main view"""
        layout = Layout()
        
        # Simpler layout - just header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
        )

        # Split body into tree and diffs only
        layout["body"].split_row(
            Layout(name="tree", ratio=1, minimum_size=30),
            Layout(name="diffs", ratio=3, minimum_size=50),
        )
        
        # Initialize content
        layout["header"].update(Panel(
            HELP_TEXT, 
            style="white",
            border_style="white"
        ))
        
        layout["body"]["tree"].update(Panel(
            self.tree_view,
            title="[bold white]Overview[/bold white]",
            border_style="white"
        ))
        
        return layout

    def update_display(self):
        """Update the display with current content"""
        # Update header with status and help
        status = f"{HELP_TEXT} | Block {self.current_index + 1}/{len(self.blocks)}"
        if self.status_message:
            status += f" | {self.status_message}"
            
        self.layout["header"].update(Panel(
            status,
            style="white",
            border_style="white"
        ))
        
        # Update tree view
        self.layout["body"]["tree"].update(Panel(
            self.tree_view,
            title="[bold white]Overview[/bold white]",
            border_style="white"
        ))
        
        # Update main diff view
        visible_blocks = self._get_visible_blocks()
        self.layout["body"]["diffs"].update(Panel(
            Group(*visible_blocks),
            title="[bold white]Changes[/bold white]",
            border_style="white"
        ))

    def _get_visible_blocks(self):
        """Get renderable blocks around current selection"""
        context_size = 2  # Number of blocks to show above/below current
        start = max(0, self.current_index - context_size)
        end = min(len(self.blocks), self.current_index + context_size + 1)
        
        rendered_blocks = []
        for idx in range(start, end):
            block = self.blocks[idx]
            rendered = self.render_block(block, idx, idx == self.current_index)
            rendered_blocks.append(rendered)
            
        return rendered_blocks

    def render_block(self, block, index, is_current):
        """Render a single block with proper styling"""
        style = "bold cyan" if is_current else ""
        prefix = "→ " if is_current else "  "
        
        header = Text()
        header.append(prefix)
        header.append(f"[{block.is_selected and 'x' or ' '}] ", style=style)
        header.append(block.description, style=style)
        
        if block.is_folded:
            header.append(" [folded]", style="dim")
            return header
            
        result = [header]
        for line in block.changes:
            if line.startswith('+'):
                result.append(Text(f"    {line}", style="green"))
            elif line.startswith('-'):
                result.append(Text(f"    {line}", style="red"))
            else:
                result.append(Text(f"    {line}", style="dim"))
        
        return Group(*result)

    def handle_input(self, key):
        """Handle input with proper folding"""
        self.status_message = ""
        
        if key.name in ["k", "up"]:
            self.current_index = max(0, self.current_index - 1)
        elif key.name in ["j", "down"]:
            self.current_index = min(self.current_index + 1, len(self.blocks) - 1)
        elif key.name == "z":
            block = self.blocks[self.current_index]
            block.is_folded = not block.is_folded
            self.status_message = f"Block {self.current_index + 1} {'folded' if block.is_folded else 'unfolded'}"
        elif key.name == "space":
            block = self.blocks[self.current_index]
            block.is_selected = not block.is_selected
            self.status_message = f"Block {self.current_index + 1} {'selected' if block.is_selected else 'unselected'}"

@click.command()
@click.argument("file1", type=click.Path(exists=True, dir_okay=False, readable=True, allow_dash=False))
@click.argument("file2", type=click.Path(exists=True, dir_okay=False, readable=True, allow_dash=False))
@click.argument("output", type=click.Path(writable=True), required=False)
@click.option('--context-lines', '-c', default=3, help='Number of context lines to show')
def diff_selector(file1, file2, output="diff_output.py", context_lines=3):
    """
    Interactive diff selection with tree view and context awareness.
    
    Shows structured view of changes with context and supports multi-select.
    """
    print(f"Starting diff_selector with file1: {file1}, file2: {file2}, output: {output}, context_lines: {context_lines}")
    console.print(Panel.fit("=== Advanced Diff Selector ===", style="cyan bold"))
    console.print(f"[cyan]Comparing files:[/cyan]\n- {file1} (Older)\n- {file2} (Newer)")
    
    if output:
        console.print(f"[cyan]Output file:[/cyan] {output}\n")
    else:
        output = "diff_output.py"
        console.print(f"[yellow][INFO] No output file provided. Defaulting to {output}[/yellow]\n")

    # Create backups
    with console.status("[cyan]Creating backups...[/cyan]"):
        backup1 = create_backup(file1)
        backup2 = create_backup(file2)
    console.print(f"[green]Backups created:[/green]\n- {backup1}\n- {backup2}")
    print(f"Backups created: {backup1}, {backup2}")

    try:
        with open(file1, "r") as f1, open(file2, "r") as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()
        console.print("[green][INFO] Files successfully read.[/green]")
        print("Files successfully read.")
    except (FileNotFoundError, IOError) as e:
        console.print(f"[red][ERROR] {str(e)}[/red]")
        print(f"Error reading files: {e}")
        return

    with console.status("[cyan]Generating unified diff...[/cyan]"):
        diff = list(
            difflib.unified_diff(lines1, lines2, fromfile=f"Older File: {file1}", tofile=f"Newer File: {file2}", n=context_lines)
        )
    print("Generating unified diff...")

    blocks = DiffParser.parse_blocks(diff)
    print(f"Parsed {len(blocks)} diff blocks.")

    if not blocks:
        console.print("[yellow]No differences found.[/yellow]")
        print("No differences found.")
        return

    viewer = DiffViewer(blocks)
    print("Initialized DiffViewer.")
    
    with Live(viewer.layout, refresh_per_second=4, screen=True, auto_refresh=False) as live:
        while True:
            viewer.update_display()
            live.refresh()
            try:
                # Fix console input handling
                key = click.getchar()  # Use click.getchar() instead of console.input()
                if key == "q":
                    if click.confirm("\nSave selections and quit?"):
                        selected_blocks = [b for b in viewer.blocks if b.is_selected]
                        print(f"Selected blocks: {len(selected_blocks)}")
                        break
                else:
                    # Create a simple key object that mimics the behavior expected by handle_input
                    class KeyPress:
                        def __init__(self, name):
                            self.name = name
                    
                    key_map = {
                        "\x1b[A": "up",
                        "\x1b[B": "down",
                        "\x1b": "escape",
                        "k": "up",
                        "j": "down",
                        " ": "space",
                        "z": "z",
                        "?": "?",
                    }
                    
                    key_name = key_map.get(key, key)
                    viewer.handle_input(KeyPress(key_name))
                    
            except KeyboardInterrupt:
                if click.confirm("\nQuit without saving?"):
                    print("User chose to quit without saving.")
                    return

    # Process selected blocks
    if not selected_blocks:
        console.print("[yellow][INFO] No blocks selected. Exiting.[/yellow]")
        print("No blocks selected. Exiting.")
        return

    # Create selection table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Block #", style="cyan")
    table.add_column("Changes", style="green")
    table.add_column("Context", style="dim")
    
    for i, block in enumerate(blocks, 1):
        changes = len([l for l in block['changes'] if l.startswith(('+', '-'))])
        context = len(block['context']['before']) + len(block['context']['after'])
        table.add_row(str(i), f"{changes} lines", f"{context} lines")
    
    console.print("\n[bold]Available Blocks:[/bold]")
    console.print(table)
    print(f"Creating selection table for {len(selected_blocks)} blocks.")

    # Multi-select interface
    selected_blocks = []
    while True:
        choice = click.prompt(
            "\nOptions (block numbers, comma-separated, 'v' to view, 'd' done)",
            default='d'
        )
        
        if choice.lower() == 'd':
            break
        elif choice.lower() == 'v':
            block_num = click.prompt("Enter block number to view", type=int) - 1
            if 0 <= block_num < len(blocks):
                console.print("\n[bold]Detailed View:[/bold]")
                syntax = Syntax("".join(blocks[block_num]['changes']), "python", theme="monokai")
                console.print(syntax)
                print(f"Viewing block {block_num + 1}")
            continue
        
        try:
            selections = [int(x.strip()) for x in choice.split(',')]
            for sel in selections:
                if 1 <= sel <= len(blocks):
                    selected_blocks.append(blocks[sel-1])
                    console.print(f"[green]Added block {sel}[/green]")
                    print(f"Added block {sel}")
        except ValueError:
            console.print("[red]Invalid input. Use numbers separated by commas.[/red]")
            print("Invalid input for block selection.")

    if not selected_blocks:
        console.print("[yellow][INFO] No blocks selected. Exiting.[/yellow]")
        print("No blocks selected after multi-select. Exiting.")
        return

    combined_output = "\n".join("".join(block['changes']) for block in selected_blocks)
    try:
        with open(output, "w") as out_file:
            out_file.write(combined_output)
        console.print(f"[green bold][SUCCESS] Combined output saved to {output}[/green bold]")
        print(f"Combined output saved to {output}")

        with console.status("[cyan]Linting the output file with black...[/cyan]"):
            subprocess.run(["black", output], check=True, capture_output=True)
        console.print("[green][SUCCESS] Linting completed.[/green]")
        print("Linting completed successfully.")
    except subprocess.CalledProcessError as e:
        console.print(f"[red][ERROR] Linting failed: {e}[/red]")
        print(f"Linting failed: {e}")
    except IOError as e:
        console.print(f"[red][ERROR] Unable to write to output file: {e}[/red]")
        print(f"Unable to write to output file: {e}")

    console.print("\n[green bold][INFO] Diff Selector process completed.[/green bold]")
    print("Diff Selector process completed.")

if __name__ == "__main__":
    example = """

# 1) Consolidate repeated calls to flatten by caching references.
# 2) Remove redundant dictionary lookups for fields by storing a direct reference.
# 3) Use in-place updates instead of returning new structures in flatten/pack methods.
# 4) Eliminate extra copying in dict() and dump() methods.
# 5) Combine flatten() and model_dump() logic to avoid duplication.
# 6) Prefetch field descriptors to skip overhead in __setitem__ and __getitem__.
# 7) Cache resolved references during unflatten to skip repeated resolution.
# 8) Reuse arrays in tolist()/numpy()/torch() conversions for zero-copy behavior.
# 9) Pre-allocate attribute containers in __call__ to prevent repeated expansions.
# 10) Remove ephemeral Sample creation in update()/pop().
# 11) Permit pass-through on read() for already-loaded objects.
# 12) Merge space() and space_for() calls to skip double checks.
# 13) Combine infer_features_dict() and features() for direct pass of memoized results.
# 14) Streamline cast() to avoid deep recursion in dispatch().
# 15) Centralize internal iteration logic to remove multiple for-loops.

class Sample(metaclass=SampleMeta):
    content: Any | None = NoInitField()
    __idx__: Any = NoInitField()
    type: TagType | None = NoInitField()

    def __init__(self, content: Any | None = None, **kwargs) -> None:
        self._fields_ref = self.__dataclass_fields__  # direct reference
        self._cached_flat = None
        self._cached_np = None
        self._cached_list = None
        if content is not None:
            kwargs["content"] = content
        super().__init__(**kwargs)

    def fields(self) -> dict[str, _Field[Any]]:
        return self._fields_ref

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return getattr(self, list(self._fields_ref.keys())[key])
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key.startswith("_"):
            raise ValueError(f"Attribute name cannot start with an underscore: {key}")
        # Use the cached reference to skip dictionary lookups
        setattr(self, key, value)

    def flatten(self, to="list", **kwargs):
        if self._cached_flat and to == "list" and not kwargs:
            return self._cached_flat
        # Minimal duplication across flatten calls
        # ...
        flattened = []  # in-place fill
        # (example) collect all leaf values referencing them directly
        for k in self._fields_ref:
            val = getattr(self, k)
            # zero-copy aggregator logic
            if isinstance(val, Sample):
                flattened.extend(val.flatten(to=to, **kwargs))
            else:
                flattened.append(val)
        if to == "list":
            self._cached_flat = flattened
            return flattened
        if to == "dict":
            return {f"{k}": getattr(self, k) for k in self._fields_ref}
        # Additional zero-copy paths for "np", "torch", etc.
        # ...
        return flattened

    def model_dump(self, **kwargs) -> dict[str, Any]:
        # Use flatten with to="dict" for internal representation
        return self.flatten(to="dict", **kwargs)

    def update(self, arg: dict[str, Any] | "Sample", **kwargs: Any) -> Self:
        # Direct in-place update
        if isinstance(arg, Sample):
            for k, v in arg._fields_ref.items():
                self[k] = getattr(arg, k)
        else:
            for k, v in arg.items():
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v
        return self

    def copy(self) -> "Sample":
        # Zero-copy approach: clone references, skip deep copies
        # If mutation is needed, consider partial copy or fresh instance
        new_s = type(self)()
        new_s.__dict__.update(self.__dict__)
        return new_s

    # Similar changes for unflatten, pack, unpack, etc., ensuring references
    # are reused and memory is not duplicated.

    # ... more revised methods with zero-copy usage and caching ...
    
// ...existing code..."""
    import sys
    if not sys.argv[1:]:
        diffs = difflib.HtmlDiff().make_table(
            example.splitlines(), Path(files("mbodied.types.sample") / "sample.py").read_text().splitlines(), "Before", "After", context=True, numlines=3
        )
        Path("diff.html").write_text(diffs)
