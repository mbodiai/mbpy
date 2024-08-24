import pytest
import sys
from unittest.mock import patch, call
from mbpy.create import create_project, extract_docstrings, setup_documentation


@pytest.fixture
def mock_cwd(tmp_path):
    with patch("mbpy.create.getcwd", return_value=str(tmp_path)):
        yield tmp_path


def test_create_project(mock_cwd):
    project_name = "test_project"
    author = "Test Author"
    description = "Test Description"
    deps = ["pytest", "numpy"]

    with (
        patch("mbpy.create.Path.mkdir") as mock_mkdir,
        patch("mbpy.create.Path.write_text") as mock_write_text,
        patch("mbpy.create.Path.touch") as mock_touch,
        patch(
            "mbpy.create.create_pyproject_toml",
            return_value="mock_pyproject_content",
        ) as mock_create_pyproject,
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
        patch("mbpy.create.getcwd", return_value=str(mock_cwd)),
    ):
        create_project(project_name, author, description, deps)

        # Check if directories were created
        assert mock_mkdir.call_count == 16  # Confirm 16 mkdir calls
        assert mock_touch.call_count == 4  # Confirm 4 touch calls for .gitkeep files
        expected_call = call(exist_ok=True, parents=True)
        assert all(call == expected_call for call in mock_mkdir.call_args_list), \
            f"Not all mkdir calls used both exist_ok=True and parents=True. Actual calls: {mock_mkdir.call_args_list}"

        # Check if files were created with correct content
        assert mock_write_text.call_count == 9  # LICENSE, README.md, pyproject.toml, __about__.py, __init__.py, main.py, and possibly additional files
        # Check for specific file contents
        mock_write_text.assert_has_calls(
            [
                call(""),  # LICENSE
                call(f"# {project_name}\n\n{description}\n\n## Installation\n\n```bash\npip install {project_name}\n```\n"),  # README.md
                call("mock_pyproject_content"),  # pyproject.toml
                call('__version__ = "0.0.1"'),  # __about__.py
                call("from .main import cli\n\n__all__ = ['cli']"),  # __init__.py
                call("from click import command\n\n@command()\ndef cli() -> None:\n    pass\n\nif __name__ == '__main__':\n    cli()"),  # main.py
            ],
            any_order=True,
        )
        # Note: There might be additional files created that we're not explicitly checking here

        # Check if .gitkeep files were touched
        assert mock_touch.call_count == 4

        # Check if create_pyproject_toml was called with correct arguments
        mock_create_pyproject.assert_called_once_with(project_name, author, description, deps, python_version="3.11", add_cli=True)

        # Check if setup_documentation was called
        mock_setup_docs.assert_called_once_with((mock_cwd / project_name).absolute(), project_name, author, description, 'sphinx', {})

def test_create_project_with_mkdocs(mock_cwd):
    project_name = "mkdocs_project"
    author = "MkDocs Author"
    description = "MkDocs Description"
    deps = ["pytest"]

    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
    ):
        create_project(project_name, author, description, deps, doc_type='mkdocs')

        # Check if setup_documentation was called with mkdocs
        mock_setup_docs.assert_called_once_with(mock_cwd / project_name, project_name, author, description, 'mkdocs')

def test_create_project_without_cli(mock_cwd):
    project_name = "no_cli_project"
    author = "No CLI Author"
    description = "No CLI Description"
    deps = ["pytest"]

    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text") as mock_write_text,
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation"),
    ):
        create_project(project_name, author, description, deps, add_cli=False)

        # Check if __init__.py was created without cli import
        mock_write_text.assert_any_call("")  # Empty __init__.py

def test_create_project_custom_python_version(mock_cwd):
    project_name = "custom_py_project"
    author = "Custom Py Author"
    description = "Custom Py Description"
    deps = ["pytest"]
    python_version = "3.9"

    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml") as mock_create_pyproject,
        patch("mbpy.create.setup_documentation"),
    ):
        create_project(project_name, author, description, deps, python_version=python_version)

        # Check if create_pyproject_toml was called with correct python version
        mock_create_pyproject.assert_called_once_with(project_name, author, description, deps, python_version=python_version, add_cli=True)


def test_create_project_with_local_deps(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml") as mock_create_pyproject,
    ):
        create_project(
            "local_project",
            "Local Author",
            "local",
            None,
            python_version="3.11",
            add_cli=False,
        )
        mock_create_pyproject.assert_called_once_with("local_project", "Local Author", "local", [], python_version='3.11', add_cli=False)


def test_create_project_no_deps(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml") as mock_create_pyproject,
    ):
        create_project("no_deps_project", "No Deps Author")
        mock_create_pyproject.assert_called_once_with(
            "no_deps_project",
            "No Deps Author",
            "",
            [],
            python_version="3.11",
            add_cli=True,
        )


def test_create_project_existing_directory(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir") as mock_mkdir,
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
    ):
        create_project("existing_project", "Existing Author")

        # All mkdir calls should have exist_ok=True
        for call in mock_mkdir.call_args_list:
            assert call[1].get("exist_ok", False) is True

def test_create_project_with_documentation(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
    ):
        create_project("doc_project", "Doc Author", doc_type="sphinx")
        mock_setup_docs.assert_called_once_with((mock_cwd / "doc_project").absolute(), "doc_project", "Doc Author", "", "sphinx", {})

def test_create_project_with_mkdocs(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
        patch("mbpy.create.getcwd", return_value=str(mock_cwd)),
    ):
        create_project("mkdocs_project", "MkDocs Author", doc_type="mkdocs")
        mock_setup_docs.assert_called_once_with((mock_cwd / "mkdocs_project").absolute(), "mkdocs_project", "MkDocs Author", "", "mkdocs", {})

def test_create_project_with_custom_python_version(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml") as mock_create_pyproject,
    ):
        create_project("custom_py_project", "Custom Py Author", python_version="3.9")
        mock_create_pyproject.assert_called_once_with(
            "custom_py_project",
            "Custom Py Author",
            "",
            [],
            python_version="3.9",
            add_cli=True,
        )

def test_extract_docstrings(tmp_path):
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    (project_path / "test_module.py").write_text('''
def test_function():
    """This is a test function docstring."""
    pass

class TestClass:
    """This is a test class docstring."""
    pass
''')
    
    with patch("mbpy.create.importlib.import_module") as mock_import:
        mock_module = mock_import.return_value
        mock_module.test_function.__doc__ = "This is a test function docstring."
        mock_module.TestClass.__doc__ = "This is a test class docstring."
        
        docstrings = extract_docstrings(project_path)
        
        assert docstrings == {
            "test_module.test_function": "This is a test function docstring.",
            "test_module.TestClass": "This is a test class docstring.",
        }

import pytest
import subprocess
import time
import requests
from requests.exceptions import RequestException
import socket
import signal
from pathlib import Path
from mbpy.create import create_project

@pytest.mark.network
def test_mpip_create_and_mkdocs_serve(tmp_path):
    # Function to find an available port
    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    # Create a new package using mpip create
    project_name = "test_project"
    author = "Test Author"
    description = "Test Description"
    
    create_project(project_name, author, description, doc_type='mkdocs')
    
    project_path = tmp_path / project_name
    
    # Find an available port
    port = find_free_port()

    # Start MkDocs server
    process = subprocess.Popen(
        ["mkdocs", "serve", "-a", f"localhost:{port}"],
        cwd=str(project_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for the server to start and retry connection
        max_retries = 15
        for _ in range(max_retries):
            time.sleep(1)
            try:
                response = requests.get(f"http://localhost:{port}")
                if response.status_code == 200:
                    # Test the response
                    assert project_name in response.text, "Project name not found in response"
                    assert description in response.text, "Project description not found in response"
                    assert "def test_function():" in response.text, "Function definition not found in response"
                    assert "This is a test docstring." in response.text, "Docstring not found in response"
                    break
            except requests.ConnectionError:
                continue
        else:
            raise TimeoutError("MkDocs server did not start successfully")

        # Check if the process ended without errors
        stdout, stderr = process.communicate()
        if process.returncode not in [0, -2, -15]:
            raise AssertionError(f"MkDocs serve failed with unexpected return code: {process.returncode}\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}")

    except Exception as e:
        # Log error information
        stdout, stderr = process.communicate()
        print(f"Error: {str(e)}")
        print(f"STDOUT: {stdout.decode()}")
        print(f"STDERR: {stderr.decode()}")
        raise

    finally:
        # Terminate the server gracefully
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

def test_setup_documentation(tmp_path):
    project_name = "test_docs"
    author = "Test Author"
    description = "Test Description"
    doc_type = "sphinx"
    
    with patch("mbpy.create.setup_sphinx_docs") as mock_setup_sphinx:
        setup_documentation(tmp_path, project_name, author, description, doc_type)
        
        mock_setup_sphinx.assert_called_once_with(
            tmp_path / "docs",
            project_name,
            author,
            description,
            None  # docstrings parameter
        )
    
    # Test with MkDocs
    doc_type = "mkdocs"
    with patch("mbpy.create.setup_mkdocs") as mock_setup_mkdocs:
        setup_documentation(tmp_path, project_name, author, description, doc_type)
        
        mock_setup_mkdocs.assert_called_once_with(
            tmp_path / "docs",
            project_name,
            author,
            description,
            None  # docstrings parameter
        )
    
    # Test with invalid doc_type
    with pytest.raises(ValueError, match="Invalid doc_type. Choose 'sphinx' or 'mkdocs'."):
        setup_documentation(tmp_path, project_name, author, description, "invalid_type")
