import subprocess
import ast
from typing import List, Dict, Any, Optional
import rich_click as click
from dataclasses import dataclass
from pathlib import Path
import json
import os

@dataclass
class CodeChange:
    file: str
    old_code: str
    new_code: str
    change_type: str  # 'add', 'modify', 'delete'
    line_no: int
    ast_changes: List[str]

def run_cmd(cmd: str) -> str:
    """Run shell command and return output."""
    try:
        return subprocess.check_output(cmd, shell=True).decode('utf-8')
    except subprocess.CalledProcessError:
        return ""

def get_staged_files() -> List[str]:
    """Get list of staged files for commit."""
    return run_cmd("git diff --cached --name-only").splitlines()

def parse_changes(content: str, max_lines: int = 5) -> List[ast.AST]:
    """Parse Python code and return AST nodes."""
    try:
        tree = ast.parse(content)
        nodes = []
        for node in ast.walk(tree):
            # Skip nodes beyond max lines
            if hasattr(node, 'lineno') and node.lineno > max_lines:
                continue
            nodes.append(node)
        return nodes
    except:
        return []

def analyze_diff(file: str, repo_root: Optional[str] = None) -> Optional[CodeChange]:
    """Analyze git diff for a file and return structured changes."""
    if not file.endswith('.py'):
        return None
        
    diff = run_cmd(f"git diff --cached {file}")
    if not diff:
        return None
    
    try:
        old_content = run_cmd(f"git show HEAD:{file}")
    except:
        old_content = ""
    
    try:
        new_content = Path(file).read_text()
    except:
        return None
    
    old_ast = parse_changes(old_content)
    new_ast = parse_changes(new_content)
    
    changes = []
    repo_root = repo_root or run_cmd("git rev-parse --show-toplevel").strip()
    
    def get_object_ref(node: ast.AST) -> str:
        """Get reference link for an object"""
        try:
            rel_path = os.path.relpath(file, repo_root)
            return f"{rel_path}#L{node.lineno}"
        except:
            return file

    def get_node_changes(new_node: ast.AST) -> List[str]:
        """Get detailed changes for a node"""
        if isinstance(new_node, ast.FunctionDef):
            args = [a.arg for a in new_node.args.args]
            return [f"Added function {new_node.name}({', '.join(args)}) at {get_object_ref(new_node)}"]
        elif isinstance(new_node, ast.ClassDef):
            bases = [b.id for b in new_node.bases if isinstance(b, ast.Name)]
            return [f"Added class {new_node.name}({', '.join(bases)}) at {get_object_ref(new_node)}"]
        elif isinstance(new_node, ast.Import):
            return [f"Added import {n.name} at {get_object_ref(new_node)}" for n in new_node.names]
        return []

    for node in new_ast:
        if not any(type(old) == type(node) for old in old_ast):
            changes.extend(get_node_changes(node))
    
    return CodeChange(
        file=file,
        old_code=old_content[:500],  # Limit code size
        new_code=new_content[:500],  # Limit code size
        change_type='modify',
        line_no=0,
        ast_changes=changes[:10]  # Limit number of changes
    )

def generate_commit_message(changes: List[CodeChange]) -> str:
    """Generate commit message from code changes."""
    if not changes:
        return "Update files"
        
    # Categorize changes
    additions = []
    modifications = []
    
    for change in changes:
        for ast_change in change.ast_changes:
            if ast_change.startswith("Added"):
                additions.append(ast_change)
            else:
                modifications.append(ast_change)
    
    msg_parts = []
    if additions:
        msg_parts.append("Add " + ", ".join(additions))
    if modifications:
        msg_parts.append("Update " + ", ".join(modifications))
        
    return "; ".join(msg_parts) or "Update files"

def create_project_item(title: str, body: str) -> str:
    """Create GitHub project item using gh CLI."""
    cmd = f'gh project item-create --owner="$GITHUB_OWNER" --project="$GITHUB_PROJECT" --title="{title}" --body="{body}"'
    return run_cmd(cmd)

@click.command()
@click.option('--analyze-only', is_flag=True, help='Only analyze changes without committing')
@click.option('--create-item', is_flag=True, help='Create GitHub project item')
@click.option('--repo-path', type=str, help='Path to git repository')
def main(analyze_only: bool, create_item: bool, repo_path: Optional[str] = None):
    """Analyze changes and generate commit message."""
    if repo_path:
        os.chdir(repo_path)
        
    files = get_staged_files()
    changes = [c for c in (analyze_diff(f, repo_path) for f in files) if c]
    
    if not changes:
        print("No Python file changes detected")
        return
        
    message = generate_commit_message(changes)
    
    if analyze_only:
        print(f"Generated message: {message}")
        return
        
    # Create commit
    commit_cmd = f'git commit -m "{message}"'
    result = run_cmd(commit_cmd)
    print(result)
    
    if create_item and result:
        # Create project item with detailed analysis
        body = json.dumps([{
            'file': c.file,
            'changes': c.ast_changes
        } for c in changes], indent=2)
        
        item_result = create_project_item(message, body)
        print(f"Created project item: {item_result}")

if __name__ == '__main__':
    main()
