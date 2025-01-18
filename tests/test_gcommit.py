import subprocess
import pytest
from unittest import mock
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import ast

# Import from parent directory
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mbpy.helpers.gcommit import (
    run_cmd,
    get_staged_files,
    parse_changes,
    analyze_diff,
    generate_commit_message,
    create_project_item,
    CodeChange
)


@pytest.fixture
def mock_subprocess():
  with patch('subprocess.check_output') as mock_check_output:
    yield mock_check_output


def test_run_cmd_success(mock_subprocess):
  mock_subprocess.return_value = b'success output\n'
  result = run_cmd('echo "test"')
  assert result == 'success output\n'
  mock_subprocess.assert_called_with('echo "test"', shell=True)


def test_run_cmd_failure(mock_subprocess):
  mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'cmd')
  result = run_cmd('fail_cmd')
  assert result == ''


def test_get_staged_files(mock_subprocess):
  mock_subprocess.return_value = b'file1.py\nfile2.txt\n'
  files = get_staged_files()
  assert files == ['file1.py', 'file2.txt']
  mock_subprocess.assert_called_with('git diff --cached --name-only', shell=True)


def test_parse_changes_valid():
  code = """
def foo():
  pass

class Bar:
  pass

"""
  ast_nodes = parse_changes(code)
  assert len(ast_nodes) > 0
  assert any(isinstance(node, ast.FunctionDef) for node in ast_nodes)
  assert any(isinstance(node, ast.ClassDef) for node in ast_nodes)
  assert any(isinstance(node, ast.Import) for node in ast_nodes)


def test_parse_changes_invalid():
  code = "def foo(:"
  ast_nodes = parse_changes(code)
  assert ast_nodes == []


def test_parse_changes_respects_max_lines():
    code = """
def foo():
    pass

def bar():
    pass

def baz():
    pass
"""
    nodes = parse_changes(code, max_lines=5)
    fns = [n for n in nodes if isinstance(n, ast.FunctionDef)]
    assert len(fns) <= 2  # Should only include foo and bar


@patch('mbpy.helpers.gcommit.run_cmd')
@patch('pathlib.Path.read_text')
def test_analyze_diff_add_function(mock_read_text, mock_run_cmd):
  mock_run_cmd.side_effect = ['diff content', 'old code']
  mock_read_text.return_value = 'def new_func(): pass'
  
  change = analyze_diff('test.py')
  assert change is not None
  assert change.change_type == 'modify'
  assert 'Added function new_func' in change.ast_changes


@patch('mbpy.helpers.gcommit.run_cmd')
def test_analyze_diff_with_repo_root(mock_run_cmd):
    mock_run_cmd.side_effect = [
        'diff content',
        'old code',
        '/repo/root'
    ]
    with patch('pathlib.Path.read_text') as mock_read:
        mock_read.return_value = 'def new_func(): pass'
        change = analyze_diff('src/test.py', '/repo/root')
        assert 'src/test.py#L1' in change.ast_changes[0]


def test_generate_commit_message_empty():
  message = generate_commit_message([])
  assert message == "Update files"


def test_generate_commit_message_additions():
  changes = [
    CodeChange(
      file='test.py',
      old_code='',
      new_code='def foo(): pass',
      change_type='modify',
      line_no=0,
      ast_changes=['Added function foo']
    )
  ]
  message = generate_commit_message(changes)
  assert message == "Add Added function foo"


def test_generate_commit_message_additions_and_updates():
  changes = [
    CodeChange(
      file='test.py',
      old_code='def foo(): pass',
      new_code='def foo(): pass\ndef bar(): pass',
      change_type='modify',
      line_no=0,
      ast_changes=['Added function bar']
    ),
    CodeChange(
      file='utils.py',
      old_code='import os',
      new_code='import os\nimport sys',
      change_type='modify',
      line_no=0,
      ast_changes=['Added import sys']
    )
  ]
  message = generate_commit_message(changes)
  assert message == "Add Added function bar, Added import sys"


def test_generate_commit_message_with_refs():
    changes = [
        CodeChange(
            file='src/test.py',
            old_code='',
            new_code='def foo(): pass',
            change_type='modify', 
            line_no=0,
            ast_changes=['Added function foo() at src/test.py#L1']
        )
    ]
    msg = generate_commit_message(changes)
    assert 'src/test.py#L1' in msg


@patch('mbpy.helpers.gcommit.run_cmd')
def test_create_project_item(mock_run_cmd):
  mock_run_cmd.return_value = 'item created'
  title = "Commit Title"
  body = '{"file": "test.py", "changes": ["Added function foo"]}'
  result = create_project_item(title, body)
  assert result == 'item created'
  mock_run_cmd.assert_called_with(
    'gh project item-create --owner="$GITHUB_OWNER" --project="$GITHUB_PROJECT" --title="Commit Title" --body="{\\"file\\": \\"test.py\\", \\"changes\\": [\\"Added function foo\\"]}"'
  )

if __name__ == '__main__':
  pytest.main([__file__,"-v", "-s"])