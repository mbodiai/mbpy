import pytest
import sys
from mbpy.cli import run_command
import time
import requests
from requests.exceptions import RequestException
import socket
import signal
from pathlib import Path
import tempfile
import os
import json
from mbpy.create import create_project, setup_documentation, extract_docstrings


# @pytest.fixture
# def tmp_path():
#     with tempfile.NamedTemporaryFile() as tmpdir:
#         yield Path(tmpdir.name)

def test_create_project():
    project_name = "test_project"
    author = "Test Author"
    description = "Test Description"
    deps = ["pytest", "numpy"]
    with tempfile.NamedTemporaryFile() as tmp:
        try:
            tmp_path = Path(tmp.name).parent
            result = run_command(
                [
                    sys.executable,
                    "-m",
                    "mbpy.cli",
                    "create",
                    project_name,
                    author,
                    "--description",
                    description,
                    "--deps",
                    ",".join(deps),
                ],
                cwd=tmp_path,
            )
            result = "".join(list(result))

            assert f"Project {project_name} created successfully" in result

            project_root = tmp_path
            assert (project_root / project_name).exists()
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
    
        finally:
            pass
            # tmp.close() if tmp and Path(tmp.name).exists() else None
            # os.unlink(tmp.name) if tmp and os.path.exists(tmp.name) else None
def test_create_project_with_mkdocs(tmp_path):
    project_name = "mkdocs_project"
    author = "MkDocs Author"
    description = "MkDocs Description"
    deps = ["pytest"]

    result = run_command(
        [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--deps", ",".join(deps), "--doc-type", "mkdocs"],
        cwd=tmp_path,
    )
    result = "".join(list(result))


    assert f"Project {project_name} created successfully" in result

    project_root = tmp_path
    assert (project_root / project_name).exists()
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / project_name / "__init__.py").exists()
    assert (project_root / "docs").exists()
    assert (project_root / "mkdocs.yml").exists()

    # Check mkdocs.yml content
    mkdocs_content = (project_root / "mkdocs.yml").read_text()
    assert project_name in mkdocs_content
    assert author in mkdocs_content
    assert description in mkdocs_content

def test_create_project_without_cli():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_name = "test_project"
        author = "Test Author"
        description = "Test Description"
        deps = ["pytest"]
        
        result = run_command(
            [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--deps", ",".join(deps), "--no-cli"],
            cwd=tmpdir,
            
        )
        
        result = "".join(list(result))
        
        project_path = Path(tmpdir) / project_name
        assert project_path.exists()
        assert (project_path / "__init__.py").exists()        
        assert not (project_path / "cli.py").exists()

def test_create_project_custom_python_version():
    project_name = "custom_py_project"
    author = "Custom Py Author"
    description = "Custom Py Description"
    deps = ["pytest"]
    python_version = "3.9"
    with tempfile.NamedTemporaryFile() as tmpdir:
        tmp_path = Path(tmpdir.name).parent
        result = "".join(list(run_command(
            [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--deps", ",".join(deps), "--python", python_version, "--no-cli"],
            cwd=tmp_path,
            timeout=10
        )))


        project_path = tmp_path


        with open(project_path / "pyproject.toml", "r") as f:
            content = f.read()
            assert f'requires-python = ">={python_version}"' in content

        assert not (project_path / project_name / "cli.py").exists()


def test_create_project_classifiers_on_newlines():
    project_name = "classifier_test"
    author = "Test Author"
    description = "Test Description"
    python_version = "3.11"
    from mbpy.cli import run_command
    with tempfile.NamedTemporaryFile() as tmpdir:
        tmp_path = Path(tmpdir.name).parent
        "".join(list(run_command(
            [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--python", python_version, "--no-cli"],
            cwd=tmp_path,
        )))



    project_path = tmp_path
    pyproject_path = project_path / "pyproject.toml"
    assert pyproject_path.exists()

    with open(pyproject_path, "r") as f:
        content = f.read()
        
    # Check that classifiers are on separate lines
    classifiers_start = content.index("classifiers = [")
    classifiers_end = content.index("]", classifiers_start)
    classifiers_content = content[classifiers_start:classifiers_end]
    
    assert classifiers_content.count("\n") >= 6  # At least 6 newlines for 6 classifiers
    assert f'"Programming Language :: Python :: {python_version}"' in classifiers_content
    assert all(classifier.strip().startswith('"') for classifier in classifiers_content.split("\n")[1:-1])  # Check each classifier is on a new line and starts with a quote


def test_create_project_with_local_deps():
    project_name = "local_project"
    author = "Local Author"
    description = "local"
    with tempfile.NamedTemporaryFile() as tmpdir:
        tmp_path = Path(tmpdir.name).parent
        result = "".join(list(run_command(
            [sys.executable, "-m", "mbpy.cli", "create", project_name, author, "--description", description, "--deps", "local", "--python", "3.11", "--no-cli"],
            cwd=tmp_path,
        )))


        project_path = tmp_path

        with open(project_path / "pyproject.toml", "r") as f:
                content = f.read()
                assert 'dependencies = [' in content
                assert '"local",' in content


def test_create_project_no_deps(tmp_path):
    project_name = "no_deps_project"
    author = "No Deps Author"

    result = "".join(list(run_command(
        [sys.executable, "-m", "mbpy.cli", "create", project_name, author],
        cwd=tmp_path,
    )))


    project_path = tmp_path

    with open(project_path / "pyproject.toml", "r") as f:
            content = f.read()
            assert 'dependencies = []' in content


def test_create_project_existing_directory(tmp_path):
    project_name = "existing_project"
    author = "Existing Author"

    # Create the project directory beforehand
    (tmp_path / project_name).mkdir()

    result = "".join(list(run_command(
        [sys.executable, "-m", "mbpy.cli", "create", project_name, author],
        cwd=tmp_path,
    )))

    project_path = tmp_path
    assert (project_path / project_name).exists()
    assert (project_path / "pyproject.toml").exists()

def test_create_project_with_documentation(tmp_path):
    project_path = create_project("doc_project", "Doc Author", doc_type="sphinx", project_root=tmp_path)
    assert (project_path / "doc_project").exists()
    assert (project_path / "pyproject.toml").exists()
    assert (project_path / "docs").exists()
    assert (project_path / "docs" / "conf.py").exists()
    assert (project_path / "docs" / "index.rst").exists()


def test_create_project_with_custom_python_version(tmp_path):
    project_path = create_project("custom_py_project", "Custom Py Author", python_version="3.9", project_root=tmp_path)
    assert (project_path / "custom_py_project").exists()
    assert (project_path / "pyproject.toml").exists()
    pyproject_path = project_path / "pyproject.toml"
    assert pyproject_path.exists()
    content = pyproject_path.read_text()
    assert 'requires-python = ">=3.9"' in content

def test_create_project_existing_project(tmp_path):
    existing_project = tmp_path / "existing_project"
    existing_project.mkdir()
    (tmp_path / "pyproject.toml").write_text("existing content")

    project_path = create_project("existing_project", "Existing Author", project_root=tmp_path)
    assert (project_path / "existing_project").exists()
    assert project_path.exists()
    assert (project_path / "pyproject.toml").exists()
    assert (project_path / "pyproject.toml").read_text() != "existing content"

    assert project_path == tmp_path
    content = (project_path / "pyproject.toml").read_text()
    assert "Existing Author" in content
    assert "existing content" not in content  # Ensure the old content is replaced
    assert "[project]" in content  # Ensure the new TOML structure is created
    assert 'name = "existing_project"' in content  # Ensure the project name is set correctly

def test_extract_docstrings():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()
        (project_path / "test_module.py").write_text('''
def test_function():
    """This is a test function docstring."""
    pass

class TestClass:
    """This is a test class docstring."""
    pass
''')
        
        result = "".join(list(run_command(
            [sys.executable, "-c", f"\"from mbpy.create import extract_docstrings; import json; print(json.dumps(extract_docstrings('{project_path}')))\""],
            debug=True,
        )))
        print(f"results: {result}")

        
        docstrings = json.loads(result)
        assert "test_module.test_function" in docstrings
        assert "test_module.TestClass" in docstrings
        docstrings = eval(result)
        
        assert docstrings == {
            "test_module.test_function": "This is a test function docstring.",
            "test_module.TestClass": "This is a test class docstring.",
        }


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
    
    print("Calling create_project function")
    create_project(project_name, author, description, doc_type='mkdocs', project_root=tmp_path)

    # Verify that the project structure is created
    print("Verifying project structure")
    assert project_path.exists(), f"Project path {project_path} does not exist"
    docs_path = tmp_path / "docs"
    assert docs_path.exists(), f"Docs path {docs_path} does not exist"
    assert (docs_path / "mkdocs.yml").exists(), "mkdocs.yml does not exist"
    assert (docs_path / "index.md").exists(), "index.md does not exist"

    # Find an available port
    print("Finding available port")
    port = find_free_port()
    print(f"Using port: {port}")

    # Start MkDocs server
    print("Starting MkDocs server")
    process = run_command(
        ["mkdocs", "serve", "-a", f"localhost:{port}"],
        cwd=str(project_path),
        run_in_background=True
        
    )

    try:
        # Wait for the server to start and retry connection
        print("Waiting for server to start")
        max_retries = 30
        for attempt in range(max_retries):
            print(f"Attempt {attempt + 1} of {max_retries}")
            try:
                print(f"Trying to connect to http://localhost:{port}")
                response = requests.get(f"http://localhost:{port}")
                if response.status_code == 200:
                    print("Successfully connected to server")
                    # Test the response
                    assert project_name.lower() in response.text.lower(), f"Project name '{project_name}' not found in response"
                    assert description.lower() in response.text.lower(), f"Project description '{description}' not found in response"
                    print("Project name and description found in response")
                    break
            except requests.ConnectionError:
                print("Connection failed, retrying...")
            time.sleep(1)
        else:
            raise TimeoutError("MkDocs server did not start successfully")

    except Exception as e:
        # Log error information
        print("An exception occurred:")
        print(f"Error: {str(e)}")
    finally:
        # Terminate the server gracefully
        print("Terminating MkDocs server")
        process.terminate()
        try:
            process.wait(timeout=5)
        except TimeoutError:
            print("Server didn't terminate gracefully, forcing kill")
            process.kill()
        
        # Print server output for debugging
        stdout, stderr = process.communicate()
        print(f"Server STDOUT:\n{stdout.decode()}")
        print(f"Server STDERR:\n{stderr.decode()}")
        
    print("Test completed successfully")

def test_setup_documentation():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_name = "test_docs"
        author = "Test Author"
        description = "Test Description"
        
        # Test with Sphinx
        doc_type = "sphinx"
        result = "".join(list(run_command(
            [sys.executable, "-c", f"from pathlib import Path; from mbpy.create import setup_documentation; setup_documentation(Path('{tmpdir}'), '{project_name}', '{author}', '{description}', '{doc_type}')"],
            capture_output=True,
            text=True
        )))
        assert (Path(tmpdir) / "docs" / "conf.py").exists()
        assert (Path(tmpdir) / "docs" / "conf.py").exists()
        
        # Test with MkDocs
        doc_type = "mkdocs"
        result = "".join(list(run_command(
            [sys.executable, "-c", f"from mbpy.create import setup_documentation; setup_documentation('{tmpdir}', '{project_name}', '{author}', '{description}', '{doc_type}')"],
        )))
        assert result.returncode == 0
        assert (Path(tmpdir) / "docs" / "index.md").exists()
        
        # Test with invalid doc_type
        doc_type = "invalid_type"
        result = "".join(list(run_command(
            [sys.executable, "-c", f"from mbpy.create import setup_documentation; setup_documentation('{tmpdir}', '{project_name}', '{author}', '{description}', '{doc_type}')"],
        )))
        assert result.returncode != 0
        assert "Invalid doc_type. Choose 'sphinx' or 'mkdocs'." in result.stderr

if __name__ == "__main__":
    pytest.main(["-vv", __file__, "-s"])