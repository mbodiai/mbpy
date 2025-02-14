import asyncio
from datetime import datetime, timedelta
import ast
from typing import TYPE_CHECKING, Dict, List
import collections
import os
from typing_extensions import TypedDict
import rich_click as click
import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from mbpy.import_utils import smart_import
from mbpy.cli import base_args
from mbpy.helpers._cache import acache

_repo_root = None

if TYPE_CHECKING:
    class ModuleChanges(TypedDict):
        classes: list[str]
        functions: list[str] 
        module: str
else:
    ModuleChanges = dict

class Granularity(Enum):
    MODULE = "module"
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"

@dataclass
class ChangeMetric:
    name: str
    lines_changed: int
    type: Granularity
    module: str
    children: Optional[Set[str]] = None

    def __hash__(self):
        return hash((self.name, self.type, self.module))

@acache
async def is_git_repo(path: str | None = None) -> bool:
    """Check if the current directory is a git repository."""
    try:
        process = await asyncio.create_subprocess_exec(
            'git', 'rev-parse', '--is-inside-work-tree',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path
        )
        _, _ = await process.communicate()
        return process.returncode == 0
    except:
        return False

async def get_repo_root() -> str:
    """Get and cache the Git repository root."""
    global _repo_root
    if not _repo_root:
        result = await arun(['git', 'rev-parse', '--show-toplevel'])
        _repo_root = result.strip()
    return _repo_root

async def arun(cmd_args: List[str], cwd: str | None = None, debug: bool = False,console=None) -> str:
    """Run a command asynchronously and return its output."""

    if not TYPE_CHECKING:
        SPINNER = smart_import("mbpy.helpers._display.SPINNER")
        console = console or smart_import("mbpy.helpers._display.getconsole")()
    else:
        from mbpy.helpers._display import SPINNER
        from mbpy.helpers._display import getconsole
        console = getconsole()
        
    if not await is_git_repo(cwd):
        raise ValueError("Not a git repository")
    try:
        if debug:
            console.print(f"[dim]$ {' '.join(cmd_args)}[/dim]")
        
        # Handle path validation
        if cwd and not os.path.exists(cwd):
            raise FileNotFoundError(f"Directory not found: {cwd}")
            
        # Clean up command arguments to handle malformed strings
        cleaned_args = [arg.strip() for arg in cmd_args if isinstance(arg, str)]
        
        process = await asyncio.create_subprocess_exec(
            *cleaned_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            if debug:
                console.print(f"[yellow]stderr:[/yellow] {stderr.decode().strip()}")
            # Enhanced error message for common git issues
            error_msg = stderr.decode().strip()
            if "not a git repository" in error_msg.lower():
                raise ValueError("Not a git repository. Please check your working directory.")
            elif "no such file or directory" in error_msg.lower():
                raise FileNotFoundError(f"File or directory not found in command: {' '.join(cmd_args)}")
            raise RuntimeError(f"Command failed: {error_msg}")
        
        SPINNER().stop()
        output = stdout.decode().strip()
        if debug and len(output) > 0:
            console.print(f"[dim]{len(output)} bytes[/dim]")
        return output
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return ""

def categorize_commit(message: str) -> tuple[str, str]:
    """Categorize a commit message and improve its formatting."""
    categories = {
        'feat': '🚀 Features',
        'fix': '🐛 Bug Fixes', 
        'docs': '📚 Documentation',
        'test': '🧪 Tests',
        'refactor': '♻️ Refactoring',
        'style': '💎 Style',
        'chore': '🔧 Maintenance',
        'perf': '⚡️ Performance'
    }
    
    # Extract type and description
    parts = message.split(':', 1)
    if len(parts) == 2:
        type_str = parts[0].lower()
        description = parts[1].strip()
    else:
        type_str = 'other'
        description = message.strip()
        
    # Improve message formatting
    if description:
        description = description[0].upper() + description[1:]
        if not description.endswith('.'):
            description += '.'
            
    return categories.get(type_str, '🔍 Other Changes'), description

async def get_diff_stats(commit_hash: str = None, include_unstaged: bool = False) -> Dict[str, int]:
    """Get number of changed lines per file."""
    if commit_hash:
        # Use a more specific git show command to get stats
        cmd = [
            'git', 'show',
            '--format=',  # Skip commit message
            '--stat',     # Get statistics
            '--numstat',  # Numeric statistics
            commit_hash
        ]
    else:
        if include_unstaged:
            # Include both staged and unstaged changes
            cmd = ['git', 'diff', '--numstat']
        else:
            # Only staged changes
            cmd = ['git', 'diff', '--cached', '--numstat']
    
    output = await arun(cmd)
    changes = {}
    
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith('/'): # Skip empty lines and file paths
            continue
            
        try:
            parts = line.split('\t')
            if len(parts) == 3:  # Only process lines with additions, deletions, and filepath
                additions, deletions, filepath = parts
                if additions != '-' and deletions != '-':  # Skip binary files
                    changes[filepath] = int(additions) + int(deletions)
        except (ValueError, IndexError):
            continue
            
    return changes

async def analyze_scope_changes(filepath: str, commit_hash: str = None) -> str:
    """Analyze whether changes affect module, class or function level."""
    if commit_hash:
        cmd = ['git', 'show', f'{commit_hash}:{filepath}']
    else:
        cmd = ['git', 'show', f':{filepath}']
    
    try:
        content = await arun(cmd)
        tree = ast.parse(content)
        changed_classes = []
        changed_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                changed_classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                changed_functions.append(node.name)
        
        if changed_classes:
            return f"class:{','.join(changed_classes)}"
        elif changed_functions:
            return f"function:{','.join(changed_functions)}"
        return "module"
    except:
        return "module"

def categorize_by_size(filepath: str, lines: int, scope: str) -> str:
    """Categorize changes based on line count thresholds."""
    if lines > 1000:
        return f"Major overhaul to {os.path.basename(filepath)} module"
    elif lines >= 100:
        scope_name = scope.split(':')[-1] if ':' in scope else os.path.basename(filepath)
        return f"Improvements to {scope_name}"
    return "Minor fixes"

async def amend_commit_message(commit_hash: str, new_message: str) -> bool:
    """Amend a commit message using git filter-branch."""
    try:
        # Create a temporary script for filter-branch
        script = f'''
if [ "$GIT_COMMIT" = "{commit_hash}" ]; then
    echo "{new_message}"
else
    cat
fi
'''
        script_path = '/tmp/filter-msg'
        with open(script_path, 'w') as f:
            f.write(script)
        os.chmod(script_path, 0o755)

        # Run filter-branch to rewrite the commit message
        cmd = [
            'git', 'filter-branch', '-f', '--msg-filter', 
            f'/bin/bash {script_path}', f'{commit_hash}^..{commit_hash}'
        ]
        await arun(cmd)
        os.remove(script_path)
        return True
    except Exception as e:
        console = smart_import("mbpy.helpers._display.getconsole")()
        console.print(f"[red]Failed to amend commit message: {str(e)}[/red]")
        return False

def clean_commit_message(msg: str) -> str:
    """Clean up commit messages by removing unwanted patterns."""
    patterns = [
        r'┏[━┃┗]+┓[\s\S]*?┛',  # Box drawings with content
        r'┏[━┃┗]+┓',           # Box headers
        r'┗[━┃┗]+┛',           # Box footers
        r'━+',                 # Horizontal lines
        r'#\s*Changelog.*?(?=\n|$)',  # Changelog headers
        r'Generated on:.*?(?=\n|$)',   # Generated timestamps
        r'\s+$',              # Trailing whitespace
        r'^\s+',              # Leading whitespace
        r'\n+',               # Multiple newlines
        r'\[.*?\]',           # Square bracket content
        r'┃.*?┃',             # Vertical box lines with content
    ]
    
    cleaned = msg
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)
    
    # Additional cleanup
    cleaned = cleaned.strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Collapse multiple spaces
    
    return cleaned if cleaned else "No message"

async def analyze_module_changes(filepath: str, commit_hash: str |None = None) -> ModuleChanges:
    """Analyze module changes using AST."""
    try:
        if commit_hash:
            cmd = ['git', 'show', f'{commit_hash}:{filepath}']
        else:
            cmd = ['git', 'show', f':{filepath}']
        
        content = await arun(cmd)
        tree = ast.parse(content)
        


        changes: ModuleChanges = {
            'classes': [],
            'functions': [], 
            'module': os.path.basename(filepath)
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                changes['classes'].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                changes['functions'].append(node.name)       
        return changes
    except Exception:
        return {'module': os.path.basename(filepath), 'classes': [], 'functions': []}
async def generate_change_message(changes: ModuleChanges, lines: int, granularity: Granularity = Granularity.MODULE) -> tuple[str, List[ChangeMetric]]:
            """Generate a structured change message and return metrics."""
            module = changes['module']
            metrics = []
            
            # Determine change magnitude
            if lines > 1000:
                header = "Major Changes"
            elif lines >= 100:
                header = "Significant Changes"
            else:
                header = "Minor Changes"
            
            msg_parts = []
            
            if granularity == Granularity.FILE:
                msg_parts.append(f"{header}")
                msg_parts.append(f"- Module: {module}")
                metrics.append(ChangeMetric(module, lines, Granularity.FILE, module))
            
            elif granularity == Granularity.CLASS and changes['classes']:
                classes = changes['classes']
                msg_parts.append(f"{header}")
                msg_parts.append(f"- Module: {module}")
                msg_parts.extend([f"  - Class: {c}" for c in classes])
                metrics.extend([ChangeMetric(c, lines // len(classes), Granularity.CLASS, module) for c in classes])
            
            elif granularity == Granularity.FUNCTION and changes['functions']:
                functions = changes['functions']
                msg_parts.append(f"{header}")
                msg_parts.append(f"- Module: {module}")
                msg_parts.extend([f"  - Function: {f}" for f in functions])
                metrics.extend([ChangeMetric(f, lines // len(functions), Granularity.FUNCTION, module) for f in functions])
            
            else:  # Default MODULE
                msg_parts.append(f"{header}")
                msg_parts.append(f"- Module: {module}")
                if changes['classes']:
                    msg_parts.append("  - Classes:")
                    msg_parts.extend([f"    * {c}" for c in changes['classes']])
                if changes['functions']:
                    msg_parts.append("  - Functions:")
                    msg_parts.extend([f"    * {f}" for f in changes['functions']])
                
                metric = ChangeMetric(
                    module, 
                    lines, 
                    Granularity.MODULE, 
                    module,
                    children=set(changes['classes'] + changes['functions'])
                )
                metrics.append(metric)
            
            return "\n".join(msg_parts), metrics

async def get_log_date(days: int) -> str:
    """Get the correct date format for git log."""
    date = datetime.now() - timedelta(days=days)
    return date.strftime('%Y-%m-%d')

async def get_commit_history(
        days: int | None = None,
        branch: str | None = None, 
        overwrite: bool = False, 
        dry_run: bool = False,
        granularity: Granularity = Granularity.MODULE,
        max_changes: int|None = None,
        commit_filters: Dict[str, str] = None,  # Added configurable filters
        min_lines: int = 1,  # Added minimum lines threshold
        file_patterns: List[str] = None  # Added file pattern filter
    ) -> tuple[List[dict], List[ChangeMetric]]:
        """Get commit history and change metrics.
        
        Args:
            days: Number of days to look back (-1 for last change)
            branch: Branch to analyze
            overwrite: Whether to overwrite commit messages
            dry_run: Whether to perform a dry run
            granularity: Level of change analysis
            max_changes: Maximum number of changes to process
            commit_filters: Filters for commit selection
            min_lines: Minimum number of changed lines to include
            file_patterns: List of file patterns to analyze (e.g. ['*.py'])
        """
        debug = smart_import("mbpy.log.debug")
        console = smart_import("mbpy.helpers._display.getconsole")()

        console.print("\n[blue]Git Repository Info[/blue]")
        console.print(f"[dim]Working directory:[/dim] {os.getcwd()}")
        from mbpy.log import debug
        debug = bool(debug())
        try:
            repo_root = await get_repo_root()
            console.print(f"[dim]Git root:[/dim] {repo_root}")
        except Exception as e:
            console.print(f"[yellow]Could not get repo root: {e}[/yellow]")

        # Build git log command with configurable parameters
        cmd = ['git', 'log']
        
        if days is not None:
            cmd.extend([f'--since={days}.days.ago'])
        
        cmd.extend([
            '--all',
            '--full-history',
            '--no-merges',
            '--date=format:%Y-%m-%d',
            '--pretty=format:%H|%ad|%s|%ae'
        ])

        if branch:
            cmd.append(branch)
            
        if file_patterns:
            cmd.extend(['--'] + file_patterns)

        console.print("\n[blue]Commit History[/blue]")
        output = await arun(cmd,debug=debug)
        
        if not output:
            console.print("[yellow]No commits found in the specified time period[/yellow]")
            return [], []

        commits = []
        all_metrics: List[ChangeMetric] = []
        lines = output.splitlines()
        
        if max_changes:
            lines = lines[:max_changes]
        if debug:
            console.print(f"\n[blue]Found {len(lines)} commits to analyze[/blue]")
        
        for line in lines:
            try:
                hash_val, date, msg, author = line.split('|')
                
                # Apply commit filters if specified
                if commit_filters:
                    skip = False
                    for key, pattern in commit_filters.items():
                        if key == 'author' and not re.search(pattern, author):
                            skip = True
                            break
                        elif key == 'message' and not re.search(pattern, msg):
                            skip = True
                            break
                    if skip:
                        continue
                if debug:
                    console.print(f"\n[blue]Analyzing commit[/blue] {hash_val[:7]} from {date}")
                
                changes = await get_diff_stats(hash_val)
                if not changes:
                    console.print("[yellow]No file changes found[/yellow]")
                    continue

                # Filter changes by minimum lines
                changes = {k: v for k, v in changes.items() if v >= min_lines}
                
                messages = []
                commit_metrics = []
                
                for filepath, lines_changed in changes.items():
                    if filepath.endswith('.py'):  # This could be made configurable too
                        if debug:
                            console.print(f"[blue]Analyzing Python file:[/blue] {filepath} ({lines_changed} lines)")
                        module_changes = await analyze_module_changes(filepath, hash_val)
                        message, metrics = await generate_change_message(module_changes, lines_changed, granularity)
                        messages.append(message)
                        commit_metrics.extend(metrics)

                if commit_metrics:
                    all_metrics.extend(commit_metrics)

                final_message = ' && \n'.join(filter(None, messages)) if messages else "minor fixes"

                console.print("\n[yellow]Commit Message Change:[/yellow]")
                # console.print(f"[red]- Old:[/red] {msg}")
                if debug:
                    console.print(f"[green]+ New:[/green] {final_message}")
                
                if commit_metrics:
                    console.print("\n[blue]Change Metrics:[/blue]")
                    for metric in commit_metrics:
                        console.print(f"  - {metric.type.value}: {metric.name} ({metric.lines_changed} lines)")
                
                if overwrite and not dry_run:
                    if await amend_commit_message(hash_val, final_message):
                        console.print(f"[green]✓ Successfully rewrote commit {hash_val[:7]}[/green]")
                    else:
                        console.print(f"[red]✗ Failed to rewrite commit {hash_val[:7]}[/red]")
                
                commits.append({
                    'hash': hash_val,
                    'date': date,
                    'message': final_message,
                    'author': author,
                    'category': '🔄 Changes',
                    'metrics': commit_metrics
                })
            except ValueError as e:
                console.print(f"[red]Error processing commit {hash_val[:7]}: {str(e)}[/red]")
                continue
        
        if max_changes:
            filtered_metrics = sorted(all_metrics, key=lambda m: m.lines_changed, reverse=True)[:max_changes]
            filtered_hashes = {commit['hash'] for commit in commits 
                             if any(m in filtered_metrics for m in commit['metrics'])}
            commits = [c for c in commits if c['hash'] in filtered_hashes]
        
        console.print(f"\n[blue]Processed {len(commits)} commits total[/blue]")
        return commits, all_metrics

async def extract_code_changes(commit_hash: str) -> Dict[str, List[str]]:
    """Extract meaningful code changes from a commit."""
    cmd = ['git', 'show', '--format=', '--unified=3', commit_hash, '--', '*.py']
    diff = await arun(cmd)
    
    changes = collections.defaultdict(list)
    current_file = None
    current_block = []
    
    for line in diff.splitlines():
        if line.startswith('diff --git'):
            if current_file and current_block:
                code = '\n'.join(current_block)
                try:
                    ast.parse(code)  # Validate Python syntax
                    changes[current_file].append(code)
                except SyntaxError:
                    pass
            current_file = line.split(' b/')[-1]
            current_block = []
        elif line.startswith('+') and not line.startswith('+++'):
            current_block.append(line[1:])
    
    return dict(changes)

async def generate_changelog(
    days: int=-1,
    branch: str|None = None, 
    show_code: bool = False, 
    overwrite: bool = False,
    dry_run: bool = False, 
    granularity: Granularity = Granularity.MODULE,
    max_changes: int|None = None,
    commit_filters: Dict[str, str] | None = None,  # Add missing kwargs
    min_lines: int = 1,
    file_patterns: List[str] |  None = None
) -> str:
    console = smart_import("mbpy.helpers._display.getconsole")()
    cmd = ['git', 'rev-parse', 'HEAD'] if days == -1 else None
    if days == -1:
        commit_hash = await arun(cmd)
        if commit_hash:
            commits, metrics = await get_commit_history(
                1, commit_hash, overwrite, dry_run, granularity, max_changes,
                commit_filters=commit_filters,
                min_lines=min_lines,
                file_patterns=file_patterns
            )
        else:
            commits, metrics = [], []
    else:
        commits, metrics = await get_commit_history(
            days, branch, overwrite, dry_run, granularity, max_changes,
            commit_filters=commit_filters,
            min_lines=min_lines,
            file_patterns=file_patterns
        )
        
    repo_url = await arun(['git', 'config', '--get', 'remote.origin.url'])
    if repo_url and repo_url.endswith('.git'):
        repo_url = repo_url[:-4]
    
    # Generate changelog content
    lines = [
        "# Changelog",
        "",
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ]
    
    # Group commits by category
    grouped_commits = collections.defaultdict(list)
    for commit in commits:
        if commit['message'].strip():  # Only include commits with messages
            grouped_commits[commit['category']].append(commit)
    
    # Helper function to format file links
    def format_file_link(filepath: str) -> str:
        """Create both GitHub and local file links."""
        filename = os.path.basename(filepath)
        if repo_url:
            return f"[{filename}]({repo_url}/blob/main/{filepath}) ([local](file://{filepath}))"
        return f"[{filename}](file://{filepath})"

    # Helper function to format changes
    def format_changes(message: str) -> str:
        """Format change messages more cleanly."""
        parts = message.split(" && ")
        formatted = []
        
        for part in parts:
            # Extract file and changes
            if "affecting classes:" in part or "with function changes in:" in part:
                # Split into file changes and details
                file_part, *details = part.split(" affecting classes:" if "affecting classes:" in part 
                                                else "with function changes in:")
                
                # Format file change
                file_name = file_part.split("for ")[-1].strip()
                change_type = "major overhaul to" if "major overhaul" in file_part else \
                            "modified" if "modified" in file_part else "minor fixes for"
                
                formatted.append(f"- **{change_type}** {format_file_link(file_name)}")
                
                # Format details if any
                if details:
                    detail_text = details[0].strip()
                    if "with function changes in:" in detail_text:
                        functions = detail_text.split("with function changes in:")[-1].strip()
                        formatted.append(f"  - 🔧 Functions: `{functions}`")
                    else:
                        classes = detail_text.strip()
                        formatted.append(f"  - 📦 Classes: `{classes}`")
            else:
                formatted.append(f"- {part.strip()}")
                
        return "\n".join(formatted)

    # Single consolidated loop for commit formatting
    for category, commits in grouped_commits.items():
        if not commits:
            continue
            
        lines.append(f"## {category}")
        lines.append("")
        
        for commit in commits:
            date = datetime.strptime(commit['date'], '%Y-%m-%d').strftime('%b %d')
            commit_link = f"{repo_url}/commit/{commit['hash']}" if repo_url else commit['hash']
            
            # Format the commit header and changes
            lines.append(f"### [{date}] Commit {commit['hash'][:7]}")
            formatted_message = format_changes(commit['message'])
            lines.extend(formatted_message.splitlines())
            
            if show_code:
                changes = await extract_code_changes(commit['hash'])
                for file_path, snippets in changes.items():
                    if snippets:  # Only show files with actual changes
                        lines.append(f"\n  Changes in `{file_path}`:")
                        for snippet in snippets:
                            lines.append("  ```python")
                            lines.extend("  " + line for line in snippet.splitlines())
                            lines.append("  ```")
                        lines.append("")  # Add spacing between files
            
            lines.append("")  # Add spacing between commits
        
        lines.append("")  # Add spacing between categories
    
    # Add metrics summary with improved formatting
    if metrics:
        lines.append("\n## Change Metrics Summary\n")
        
        # Group by type and sort by lines changed
        metrics_by_type = collections.defaultdict(list)
        for m in metrics:
            metrics_by_type[m.type].append(m)
            
        for type_, type_metrics in metrics_by_type.items():
            lines.append(f"### {type_.value.title()} Changes")
            sorted_metrics = sorted(type_metrics, key=lambda m: m.lines_changed, reverse=True)
            
            # Only show top changes with significant impact
            significant_changes = [m for m in sorted_metrics if m.lines_changed > 10][:5]
            
            for metric in significant_changes:
                lines.append(f"- {metric.name}")
                lines.append(f"  Lines changed: {metric.lines_changed}")
                if metric.children:
                    # Split long lists of affected items into multiple lines
                    affected = list(metric.children)
                    if len(affected) > 3:
                        lines.append("  Affects:")
                        for item in affected:
                            lines.append(f"    - {item}")
                    else:
                        lines.append(f"  Affects: {', '.join(affected)}")
                lines.append("")  # Add spacing between entries
            
            lines.append("")  # Add spacing between types
    
    try:
        return "\n".join(lines).strip()
    except Exception as e:
        console.print(f"[red]Error generating changelog: {str(e)}[/red]")
        return ""

async def undo_last_commit() -> bool:
    """Undo the last commit but keep the changes staged."""
    console = smart_import("mbpy.helpers._display.getconsole")()
    try:
        # Get the last commit hash first
        last_hash = await arun(['git', 'rev-parse', 'HEAD'])
        if not last_hash:
            console.print("[yellow]No commits to undo[/yellow]")
            return False
            
        # Reset to the previous commit, keeping changes staged
        await arun(['git', 'reset', '--soft', 'HEAD~1'])
        console.print(f"[green]Successfully undid last commit ({last_hash[:7]})[/green]")
        console.print("[dim]Changes are still staged in your working directory[/dim]")
        return True
    except Exception as e:
        console.print(f"[red]Failed to undo last commit: {str(e)}[/red]")
        return False

async def add_untracked(branch: str = None, dry_run: bool = False) -> Dict[str, str]:
    """Add untracked files and return a dict of {filepath: status}."""
    try:
        if dry_run:
            cmd = ['git', 'add', '--dry-run', '.']
        else:
            cmd = ['git', 'add', '.']
        output = await arun(cmd)
        console = smart_import("mbpy.helpers._display.getconsole")()
        console.print(output)

        file_status = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith(("add '", "remove '", "rename ")):
                if line.startswith("add '"):
                    filepath = line.split("add '", 1)[-1].rstrip("'")
                    file_status[filepath] = 'add'
                elif line.startswith("remove '"):
                    filepath = line.split("remove '", 1)[-1].rstrip("'")
                    file_status[filepath] = 'remove'
                elif line.startswith("rename "):
                    _, paths = line.split(" ", 1)
                    old_path, new_path = paths.split(" -> ")
                    file_status[new_path.strip("'")] = 'rename'
        return file_status
    except Exception as e:
        console = smart_import("mbpy.helpers._display.getconsole")()
        console.print(f"[red]Failed to add untracked files: {str(e)}[/red]")
        return {}

async def get_status_summary(file_status: Dict[str, str]) -> Dict[str, List[str]]:
    """Convert file status dict into a summary by operation."""
    summary = collections.defaultdict(list)
    for file, status in file_status.items():
        summary[status].append(os.path.basename(file))
    return summary

async def generate_short_commit_message(*, dry_run: bool = False) -> str:
    """Generate a brief, meaningful commit message based on current changes."""
    try:
        file_status = await add_untracked(dry_run=dry_run)
        if not file_status:
            return "No changes to commit"

        # Group changes by type
        replacements = []  # setup.py -> gen_setup.py type changes
        package_changes = []  # pyproject.toml, setup.py etc
        code_changes = []  # python files
        other_changes = []  # everything else
        
        # First pass - identify replacements
        files = list(file_status.items())
        for i, (filepath, status) in enumerate(files):
            base = os.path.basename(filepath)
            if status == 'remove':
                # Look for a corresponding add of a similar file
                for other_path, other_status in files[i+1:]:
                    if other_status == 'add' and other_path.endswith(filepath.split('.')[-1]):
                        replacements.append(f"Replace {base} with {os.path.basename(other_path)}")
                        # Mark both files as handled
                        file_status[filepath] = 'handled'
                        file_status[other_path] = 'handled'
                        break

        # Second pass - categorize remaining files
        for filepath, status in file_status.items():
            if status == 'handled':
                continue
                
            base = os.path.basename(filepath)
            if filepath.endswith(('pyproject.toml', 'setup.py', 'setup.cfg')):
                package_changes.append(f"{status} {base}")
            elif filepath.endswith('.py'):
                try:
                    if status != 'remove':  # Can't analyze removed files
                        module_changes = await analyze_module_changes(filepath)
                        if module_changes['classes'] or module_changes['functions']:
                            msg = base
                            if module_changes['classes']:
                                msg += f" (classes: {', '.join(module_changes['classes'])})"
                            if module_changes['functions']:
                                changed_funcs = module_changes['functions']
                                if len(changed_funcs) <= 3:
                                    msg += f" (functions: {', '.join(changed_funcs)})"
                                else:
                                    msg += f" ({len(changed_funcs)} function changes)"
                            code_changes.append(f"{status} {msg}")
                        else:
                            code_changes.append(f"{status} {base}")
                    else:
                        code_changes.append(f"{status} {base}")
                except Exception:
                    code_changes.append(f"{status} {base}")
            else:
                other_changes.append(f"{status} {base}")

        # Build message prioritizing the changes
        parts = []
        if replacements:
            parts.extend(replacements)
        if package_changes:
            parts.append(f"Update package configuration: {', '.join(package_changes)}")
        if code_changes:
            parts.append(f"Code changes: {'; '.join(code_changes)}")
        if other_changes:
            parts.append(f"Other changes: {'; '.join(other_changes)}")

        return " && ".join(parts) if parts else "Update project files"

    except Exception as e:
        return f"Update project files ({str(e)})"

async def check_diverging_changes(branch: str = None) -> tuple[bool, str]:
    try:
        has_commits = await arun(['git', 'rev-parse', '--verify', 'HEAD'], debug=False)
        if not has_commits:
            return False, ""

        if not branch:
            branch = await arun(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        
        remote_exists = await arun(['git', 'ls-remote', '--heads', 'origin', branch])
        if not remote_exists:
            return False, ""
            
        await arun(['git', 'fetch', 'origin', branch])
        diff = await arun(['git', 'diff', f'origin/{branch}...'])
        
        return bool(diff.strip()), diff
        
    except Exception as e:
        if "does not have any commits yet" in str(e):
            return False, ""
        console = smart_import("mbpy.helpers._display.getconsole")()
        console.print(f"[red]Error checking diverging changes: {str(e)}[/red]")
        return False, ""

async def git_pull(branch: str = None) -> bool:
    """Pull latest changes from remote."""
    try:
        # Check if we have any commits first
        has_commits = await arun(['git', 'rev-parse', '--verify', 'HEAD'], debug=False)
        if not has_commits:
            return True  # Nothing to pull in new repo
            
        current = await arun(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        if branch:
            try:
                await arun(['git', 'branch', '--set-upstream-to', f'origin/{branch}', current])
            except Exception:
                pass  # Ignore if remote branch doesn't exist yet
        
        cmd = ['git', 'pull']
        if branch:
            cmd.extend(['origin', branch])
        output = await arun(cmd)
        return True
    except Exception as e:
        if "does not have any commits yet" in str(e):
            return True
        console = smart_import("mbpy.helpers._display.getconsole")()
        console.print(f"[red]Failed to pull changes: {str(e)}[/red]")
        return False

async def git_add_commit_push(branch: str = None, dry_run: bool = False) -> bool:
    try:
        # Check for diverging changes first
        console = smart_import("mbpy.helpers._display.getconsole")()
        has_diverged, diff = await check_diverging_changes(branch)
        if has_diverged:
            console.print("[yellow]Warning: Your branch has diverged from origin[/yellow]")
            console.print("\n[blue]Diverging changes:[/blue]")
            console.print(diff)
            if not dry_run:
                if not click.confirm("Do you want to pull changes first?"):
                    if not click.confirm("Continue with push anyway? This may fail"):
                        return
                else:
                    if not await git_pull(branch):
                        console.print("[red]Pull failed. Please resolve conflicts manually[/red]")
                        return

        # Add untracked files
        file_status = await add_untracked(branch, dry_run=dry_run)

        if dry_run:
            console.print("[yellow]Dry run enabled. No changes were pushed.[/yellow]")
            if file_status:
                by_status = collections.defaultdict(list)
                for file, status in file_status.items():
                    by_status[status].append(file)
                
                for status, files in by_status.items():
                    console.print(f"[blue]Files that would be {status}ed:[/blue]")
                    for f in files:
                        console.print(f"  - {f}")
                        
            cl = await generate_short_commit_message(dry_run=True)
            console.print(f"[blue]Dry run commit message:[/blue] {cl}")
            return True
        else:
            # Commit with a temporary message
            commit_cmd = ['git', 'commit', '-m', 'updates']
            out = await arun(commit_cmd)

            # Generate the commit message after the commit
            cl = await generate_short_commit_message()
            console.print(f"\n[blue]Commit Message:[/blue] \n{cl}")

            # Amend the commit with the generated message
            amend_success = await amend_commit_message(out.strip(), cl)
            if amend_success:
                console.print(f"[green]✓ Successfully amended commit with new message[/green]")
            else:
                console.print(f"[red]✗ Failed to amend commit message[/red]")

            # Push the changes
            push_cmd = ['git', 'push']
            if branch:
                push_cmd.extend(['origin', branch])
            
            out = await arun(push_cmd)
            
            if "error" in out.lower() or "fail" in out.lower():
                console.print(f"[red]Failed to push changes: {out}[/red]")
            elif "everything up-to-date" in out.lower():
                console.print("[yellow]No changes to push[/yellow]")
            else:
                console.print("[green]Successfully pushed changes[/green]")
        if dry_run:
            console.print("[yellow]Dry run enabled. No changes were pushed.[/yellow]")
    except Exception as e:
            console.print(f"[red]Push failed: {str(e)})")
            console.print("[yellow]Hint: Try pulling changes first with 'git pull'[/yellow]")
            return True
@click.command("git",no_args_is_help=True)
@click.option('-cl','--change-log',is_flag=True,help='Generate changelog')
@click.option('--days', type=int, default=30, help='Number of days to look back')
@click.option('--branch', '-b', type=str, help='Branch to analyze or push to')
@click.option('--output', type=click.Path(), help='Output file path')
@click.option('--show-code', is_flag=True, help='Include code changes in changelog')
@click.option('--overwrite', is_flag=True, help='DANGER: Rewrites commit messages - use with caution')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying them')
@click.option('--undo', is_flag=True, help='Undo the last commit')
@click.option('--push', '-p', is_flag=True, help='Push changes after generating changelog')
@click.option('--max-changes', type=int, help='Maximum number of commits to process')
@click.option('--granularity', 
              type=click.Choice([g.value for g in Granularity], case_sensitive=False),
              default=Granularity.MODULE.value,
              help='Level of detail for change messages')
@base_args()
async def main(change_log: bool,
    days: int, branch: str, output: str, show_code: bool, 
               overwrite: bool, dry_run: bool, max_changes: int,
               undo: bool, push: bool, granularity: str):
    """Git operations including changelog generation and pushing changes."""
    if TYPE_CHECKING:
            from mbpy.helpers._display import SPINNER
            from mbpy.helpers._display import getconsole
            from rich.markdown import Markdown
    else:
        console = smart_import("mbpy.helpers._display.getconsole")()
        Markdown = smart_import("rich.markdown.Markdown")
        SPINNER = smart_import("mbpy.helpers._display.SPINNER")
    try:
        # Validate working directory
        if not os.path.exists(os.getcwd()):
            console.print("[red]Error: Current working directory does not exist[/red]")
            return
            
        if not await is_git_repo():
            console.print("[red]Error: Not a git repository[/red]")
            return

        if undo:
            await undo_last_commit()
            return

        if dry_run:
            SPINNER().stop()
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")
            SPINNER().start()
            await asyncio.sleep(1)
            
            
        # Only push if explicitly requested
        if push:
           return await git_add_commit_push(branch, dry_run)
        changelog = await generate_changelog(
            days, branch, show_code, overwrite, dry_run,
            granularity=Granularity(granularity),
            max_changes=max_changes
        )
        
        if not changelog.strip():
            console.print("[yellow]No changes found in the specified time period[/yellow]")
            return
        if change_log:
            output = output or 'CHANGELOG.md'
        if output:
            with open(output, 'w') as f:
                f.write(changelog)
            console.print(f"[green]Changelog written to {output}[/green]")
        else:
            console.print(Markdown(changelog))
    except Exception as e:
        console.print(f"[red]Error generating changelog: {str(e)}[/red]")

if __name__ == '__main__':
    from mbpy.cli import cli
    cli.add_command(main)
    cli()