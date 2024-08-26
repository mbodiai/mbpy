import pytest
import sys
import subprocess
from pathlib import Path

def test_create_project(tmp_path):
    project_name = "test_project"
    author = "Test Author"
    description = "Test Description"
    deps = ["pytest", "numpy"]

    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--deps", ",".join(deps)],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert f"Project {project_name} created successfully" in result.stdout

    project_root = tmp_path / project_name
    assert project_root.exists()
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / project_name / "__about__.py").exists()
    assert (project_root / project_name / "__init__.py").exists()
    assert (project_root / "docs").exists()

    # Check pyproject.toml content
    pyproject_content = (project_root / "pyproject.toml").read_text()
    assert project_name in pyproject_content
    assert author in pyproject_content
    assert description in pyproject_content
    for dep in deps:
        assert dep in pyproject_content

    # Check __about__.py content
    about_content = (project_root / project_name / "__about__.py").read_text()
    assert '__version__ = "0.1.0"' in about_content

    # Check if documentation was set up
    assert (project_root / "docs" / "conf.py").exists()

def test_create_project_with_mkdocs(tmp_path):
    project_name = "mkdocs_project"
    author = "MkDocs Author"
    description = "MkDocs Description"
    deps = ["pytest"]

    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--deps", ",".join(deps), "--doc-type", "mkdocs"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert f"Project {project_name} created successfully" in result.stdout

    project_root = tmp_path / project_name
    assert project_root.exists()
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / project_name / "__about__.py").exists()
    assert (project_root / project_name / "__init__.py").exists()
    assert (project_root / "docs").exists()
    assert (project_root / "mkdocs.yml").exists()

    # Check mkdocs.yml content
    mkdocs_content = (project_root / "mkdocs.yml").read_text()
    assert project_name in mkdocs_content
    assert author in mkdocs_content
    assert description in mkdocs_content

def test_create_project_without_cli(mock_cwd):
    project_name = "no_cli_project"
    author = "No CLI Author"
    description = "No CLI Description"
    deps = ["pytest"]

    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text") as mock_write_text,
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation"),
    ):
        create_project(project_name, author, description, deps, add_cli=False)

        # Check if __init__.py was created without cli import
        mock_write_text.assert_any_call("")  # Empty __init__.py
        mock_write_text.assert_any_call('__version__ = "0.1.0"')  # __about__.py content

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
        create_project(project_name, author, description, deps, python_version=python_version, add_cli=False)

        # Check if create_pyproject_toml was called with correct python version and without CLI
        mock_create_pyproject.assert_called_once_with(
            project_name, 
            author, 
            description, 
            deps, 
            python_version=python_version, 
            add_cli=False, 
            existing_content=None
        )

        # Check if CLI file was not created
        assert not (mock_cwd / project_name / project_name / "cli.py").exists()


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
        mock_create_pyproject.assert_called_once_with(
            "local_project", 
            "Local Author", 
            "local", 
            [], 
            python_version='3.11', 
            add_cli=False, 
            existing_content=None
        )


def test_create_project_no_deps(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
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
            existing_content=None
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
            assert call[1].get("exist_ok", True) is True

def test_create_project_with_documentation(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
        patch("mbpy.create.getcwd", return_value=str(mock_cwd)),
    ):
        project_path = create_project("doc_project", "Doc Author", doc_type="sphinx")
        mock_setup_docs.assert_called_once_with(project_path, "doc_project", "Doc Author", "", "sphinx", {})


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
            existing_content=None
        )

def test_create_project_existing_project(mock_cwd):
    existing_project = mock_cwd / "existing_project"
    existing_project.mkdir()
    (existing_project / "pyproject.toml").write_text("existing content")

    with (
        patch("mbpy.create.Path.mkdir", side_effect=lambda *args, **kwargs: None),
        patch("mbpy.create.Path.write_text"),
        patch("builtins.input", return_value="y"),  # Simulate user input to overwrite
        patch("mbpy.create.create_pyproject_toml") as mock_create_pyproject,
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
        patch("mbpy.create.getcwd", return_value=mock_cwd),
        patch("builtins.open", mock_open(read_data="existing content")),
        patch("mbpy.create.DEFAULT_PYTHON", "3.11"),
    ):
        project_path = create_project("existing_project", "Existing Author")
    
        assert project_path == existing_project
        mock_create_pyproject.assert_called_once()
        mock_setup_docs.assert_called_once()
        mock_create_pyproject.assert_called_once_with(
            "existing_project",
            "Existing Author",
            "",
            [],
            python_version="3.11",
            add_cli=True,
            existing_content="existing content"
        )
        mock_setup_docs.assert_called_once()

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
from unittest.mock import patch, mock_open
from mbpy.create import create_project, setup_documentation, extract_docstrings

@pytest.mark.network
def test_mpip_create_and_mkdocs_serve(tmp_path):
    print("Starting test_mpip_create_and_mkdocs_serve")
    
    # Function to find an available port
    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    # Create a new package using mpip create
    project_name = "test_project"
    author = "Test Author"
    description = "Test Description"
    
    print(f"Creating project: {project_name}")
    project_path = tmp_path / project_name
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "mkdocs.yml").write_text("site_name: Test Project")
    docs_path = project_path / "docs"
    docs_path.mkdir(exist_ok=True)
    (docs_path / "index.md").write_text("# Welcome to Test Project")

    print("Calling create_project function")
    create_project(project_name, author, description, doc_type='mkdocs', project_root=tmp_path)

    # Verify that the project structure is created
    print("Verifying project structure")
    assert project_path.exists(), f"Project path {project_path} does not exist"
    assert (project_path / "mkdocs.yml").exists(), "mkdocs.yml does not exist"
    assert docs_path.exists(), f"Docs path {docs_path} does not exist"
    assert (docs_path / "index.md").exists(), "index.md does not exist"

    # Find an available port
    print("Finding available port")
    port = find_free_port()
    print(f"Using port: {port}")

    # Start MkDocs server
    print("Starting MkDocs server")
    process = subprocess.Popen(
        ["mkdocs", "serve", "-a", f"localhost:{port}"],
        cwd=str(project_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for the server to start and retry connection
        print("Waiting for server to start")
        max_retries = 15
        for attempt in range(max_retries):
            print(f"Attempt {attempt + 1} of {max_retries}")
            time.sleep(1)
            try:
                print(f"Trying to connect to http://localhost:{port}")
                response = requests.get(f"http://localhost:{port}")
                if response.status_code == 200:
                    print("Successfully connected to server")
                    # Test the response
                    assert project_name in response.text, "Project name not found in response"
                    assert description in response.text, "Project description not found in response"
                    assert "def test_function():" in response.text, "Function definition not found in response"
                    assert "This is a test docstring." in response.text, "Docstring not found in response"
                    print("All assertions passed")
                    break
            except requests.ConnectionError:
                print("Connection failed, retrying...")
        else:
            raise TimeoutError("MkDocs server did not start successfully")

        # Check if the process ended without errors
        print("Checking process status")
        stdout, stderr = process.communicate(timeout=5)
        if process.returncode not in [0, -2, -15]:
            raise AssertionError(f"MkDocs serve failed with unexpected return code: {process.returncode}\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}")

    except Exception as e:
        # Log error information
        print("An exception occurred:")
        print(f"Error: {str(e)}")
        stdout, stderr = process.communicate(timeout=5)
        print(f"STDOUT: {stdout.decode()}")
        print(f"STDERR: {stderr.decode()}")
        raise

    finally:
        print("Terminating MkDocs server")
        # Terminate the server gracefully
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Server didn't terminate gracefully, forcing kill")
            process.kill()
        
    print("Test completed successfully")

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
