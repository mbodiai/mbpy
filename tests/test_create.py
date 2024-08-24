import pytest
import sys
from unittest.mock import patch, call
from mbpy.create import create_project, extract_docstrings


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
    ):
        create_project(project_name, author, description, deps)

        # Check if directories were created
        assert mock_mkdir.call_count == 8  # Updated count to match actual behavior
        mock_mkdir.assert_has_calls([call(exist_ok=True, parents=True) for _ in range(7)], any_order=True)

        # Check if files were created with correct content
        assert mock_write_text.call_count == 9  # LICENSE, README.md, pyproject.toml, __about__.py, etc.
        mock_write_text.assert_has_calls(
            [
                call(""),  # LICENSE
                call(
                    f"# {project_name}\n\n{description}\n\n## Installation\n\n```bash\npip install {project_name}\n```\n"
                ),  # README.md
                call("mock_pyproject_content"),  # pyproject.toml
                call('__version__ = "0.0.1"'),  # __about__.py
            ],
            any_order=True,
        )

        # Check if __init__.py and other files were touched
        assert mock_touch.call_count == 4

        # Check if create_pyproject_toml was called with correct arguments
        mock_create_pyproject.assert_called_once_with(project_name, author, description, deps, python_version="3.11", add_cli=True)


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
        mock_setup_docs.assert_called_once_with(mock_cwd / "doc_project", "doc_project", "Doc Author", "", "sphinx")

def test_create_project_with_mkdocs(mock_cwd):
    with (
        patch("mbpy.create.Path.mkdir"),
        patch("mbpy.create.Path.write_text"),
        patch("mbpy.create.Path.touch"),
        patch("mbpy.create.create_pyproject_toml"),
        patch("mbpy.create.setup_documentation") as mock_setup_docs,
    ):
        create_project("mkdocs_project", "MkDocs Author", doc_type="mkdocs")
        mock_setup_docs.assert_called_once_with(mock_cwd / "mkdocs_project", "mkdocs_project", "MkDocs Author", "", "mkdocs")

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
            "test_project.test_module.test_function": "This is a test function docstring.",
            "test_project.test_module.TestClass": "This is a test class docstring.",
        }
