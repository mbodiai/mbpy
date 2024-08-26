import pytest
import subprocess
import sys
from unittest.mock import patch
from mbpy.create import create_pyproject_toml
import tomlkit
import click
from click.testing import CliRunner

def test_add_dependencies_to_pyproject():
    initial_pyproject = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "embdata"
dynamic = ["version"]
description = 'Data, types, pipes, manipulation for embodied learning.'
readme = "README.md"
requires-python = ">=3.10"
license = "apache-2.0"
keywords = []
authors = [
    { name = "mbodi ai team", email = "info@mbodi.ai" },
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
]

dependencies = [
    "gymnasium==0.29.1",
    "importlib-resources==6.4.0",
    "lager",
    "methodtools==0.4.7",
    "numpy==1.26.4",
    "pydantic==2.7.4",
    "requires",
    "rich==13.7.1",
    "funkify",
    "datasets",
    "pillow",
    "opencv-python",
]

[project.optional-dependencies]
audio = [
    "pyaudio"
]
stream = [
    "opencv-python"
]
plot = [
    "plotext==5.2.8",
]
mpl = [
    "matplotlib",
]
all = [
    "ffpyplayer",
    "opencv-python",
    "datasets==2.20.0",
    "plotext==5.2.8",
    "pyaudio",
    "scikit-learn",
    "shapely==2.0.4",
    "torch==2.3.1",
    "torchvision==0.18.1",
    "transformers>=4.42.4",
    "einops==0.8.0",
    "rerun-sdk==0.17.0",
    "matplotlib",
]
"""

    new_dependencies = ["new_package1==1.0.0", "new_package2>=2.0.0"]
    
    # Create a new pyproject.toml content with added dependencies
    updated_pyproject = create_pyproject_toml(
        project_name="embdata",
        author="mbodi ai team",
        description="Data, types, pipes, manipulation for embodied learning.",
        deps=new_dependencies,
        python_version="3.10",
        add_cli=False,
        existing_content=initial_pyproject
    )

    # Parse the updated pyproject.toml content
    parsed_toml = tomlkit.parse(updated_pyproject)

    # Check if the new dependencies were added correctly
    project_dependencies = parsed_toml["project"]["dependencies"]
    assert "new_package1==1.0.0" in project_dependencies
    assert "new_package2>=2.0.0" in project_dependencies

    # Check if the original dependencies are still present
    assert "gymnasium==0.29.1" in project_dependencies
    assert "importlib-resources==6.4.0" in project_dependencies
    assert "lager" in project_dependencies

    # Check if the structure and other sections are preserved
    assert "build-system" in parsed_toml
    assert "project" in parsed_toml
    assert "optional-dependencies" in parsed_toml["project"]
    assert parsed_toml["project"]["name"] == "embdata"
    assert parsed_toml["project"]["description"] == "Data, types, pipes, manipulation for embodied learning."

    # Verify that the formatting is preserved (this is a basic check, might need refinement)
    assert "dependencies = [" in updated_pyproject
    assert "]" in updated_pyproject.split("dependencies = [")[1]

    # Test that installing "einops==0.8.0" equals the current string in the test
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "einops==0.8.0"],
            capture_output=True,
            text=True,
            check=True
        )
        installed_version = subprocess.run(
            [sys.executable, "-m", "pip", "show", "einops"],
            capture_output=True,
            text=True,
            check=True
        )
        assert "Version: 0.8.0" in installed_version.stdout
        assert "einops==0.8.0" in parsed_toml["project"]["optional-dependencies"]["all"]
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to install or check einops: {e.stdout}\n{e.stderr}")

def test_pip_upgrade_notice(monkeypatch, capsys):
    def mock_subprocess_popen(*args, **kwargs):
        class MockProcess:
            def communicate(self, timeout=None):
                return (
                    "Requirement already satisfied: markdown2==2.5.0 in /path/to/site-packages (2.5.0)\n"
                    "[notice] A new release of pip is available: 24.1 -> 24.2\n"
                    "[notice] To update, run: pip install --upgrade pip\n",
                    ""
                )
            
            @property
            def returncode(self):
                return 0

        return MockProcess()

    monkeypatch.setattr(subprocess, "Popen", mock_subprocess_popen)
    
    from mbpy.cli import install_command
    runner = click.testing.CliRunner()
    result = runner.invoke(install_command, ["-r", "requirements.txt"])
    
    assert result.exit_code == 0
    assert "Installing packages from requirements.txt..." in result.output
    assert "Running command:" in result.output
    assert "/python" in result.output and "-m pip install -r requirements.txt" in result.output
    assert "Requirement already satisfied: markdown2==2.5.0 in /path/to/site-packages (2.5.0)" in result.output
    assert "[notice] A new release of pip is available: 24.1 -> 24.2" in result.output
    assert "[notice] To update, run: pip install --upgrade pip" in result.output

    # Test that the function returns after processing requirements file
    assert "Successfully installed" not in result.output
    assert "HINT: You are attempting to install a package literally named 'requirements.txt'" not in result.output
    assert "ERROR: Could not find a version that satisfies the requirement requirements.txt" not in result.output
    assert "ERROR: No matching distribution found for requirements.txt" not in result.output

def test_install_requirements_txt_error(monkeypatch, tmp_path):
    # Create a temporary requirements.txt file
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("requirements.txt\n")  # This line simulates the error condition

    def mock_subprocess_popen(*args, **kwargs):
        class MockProcess:
            def communicate(self, timeout=None):
                return (
                    "HINT: You are attempting to install a package literally named \"requirements.txt\" (which cannot exist). Consider using the '-r' flag to install the packages listed in requirements.txt\n"
                    "\n"
                    "ERROR: Could not find a version that satisfies the requirement requirements.txt (from versions: none)\n"
                    "ERROR: No matching distribution found for requirements.txt\n",
                    ""
                )
            
            @property
            def returncode(self):
                return 1

        return MockProcess()

    monkeypatch.setattr(subprocess, "Popen", mock_subprocess_popen)
    
    from mbpy.cli import install_command
    runner = click.testing.CliRunner()
    result = runner.invoke(install_command, ["-r", str(requirements_file)])
    
    assert result.exit_code != 0
    assert "Installing packages from" in result.output
    assert "Running command:" in result.output
    assert "-m pip install -r" in result.output
    assert "Error: The requirements.txt file contains an invalid entry 'requirements.txt'." in result.output
    assert "Please remove this line from your requirements.txt file and try again." in result.output
    output_lines = result.output.strip().split("\n")
    assert 6 <= len(output_lines) <= 15  # Allow for more flexibility in the number of lines
    non_empty_lines = [line for line in output_lines if line.strip()]
    assert len(non_empty_lines) >= 6  # Ensure at least 6 non-empty lines
    assert all(expected in result.output for expected in [
        "Installing packages from requirements.txt...",
        "Running command:",
        "/python",
        "-m pip install -r requirements.txt",
        "Requirement already satisfied: markdown2==2.5.0 in /path/to/site-packages (2.5.0)",
        "[notice] A new release of pip is available: 24.1 -> 24.2",
        "[notice] To update, run: pip install --upgrade pip"
    ])

def test_mpip_install_requirements_subprocess(tmp_path):
    # Create a temporary requirements.txt file
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("click==8.1.7\nrequests==2.31.0\n")

    # Run the mpip install command
    result = subprocess.run(
        ["python", "-m", "mbpy.cli", "install", "-r", str(requirements_file)],
        capture_output=True,
        text=True
    )

    # Check the output
    assert result.returncode == 0
    assert "Installing packages from" in result.stdout
    assert "Running command:" in result.stdout
    assert "-m pip install -r" in result.stdout
    assert "Successfully installed" in result.stdout or "Requirement already satisfied" in result.stdout

def test_install_requirements_txt_error(monkeypatch, tmp_path):
    # ... (keep the existing test)

def test_mpip_install_upgrade(monkeypatch, tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_file = tmp_path / "pyproject.toml"
    initial_content = """
[project]
dependencies = [
    "sphinx==7.0.0"
]
"""
    pyproject_file.write_text(initial_content)

    def mock_subprocess_popen(*args, **kwargs):
        class MockProcess:
            def communicate(self, timeout=None):
                return (
                    "Successfully installed sphinx-8.0.2\n",
                    ""
                )
            
            @property
            def returncode(self):
                return 0

        return MockProcess()

    monkeypatch.setattr(subprocess, "Popen", mock_subprocess_popen)
    monkeypatch.setattr("mbpy.cli.Path.cwd", lambda: tmp_path)
    
    from mbpy.cli import install_command
    runner = click.testing.CliRunner()
    result = runner.invoke(install_command, ["-U", "sphinx"])
    
    assert result.exit_code == 0
    assert "Successfully installed sphinx-8.0.2" in result.output

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    assert 'sphinx==8.0.2' in updated_content
    assert 'sphinx==7.0.0' not in updated_content
[project]
dependencies = [
    "sphinx==7.0.0"
]
"""
    pyproject_file.write_text(initial_content)

    def mock_subprocess_popen(*args, **kwargs):
        class MockProcess:
            def communicate(self, timeout=None):
                return (
                    "Successfully installed sphinx-8.0.2\n",
                    ""
                )
            
            @property
            def returncode(self):
                return 0

        return MockProcess()

    monkeypatch.setattr(subprocess, "Popen", mock_subprocess_popen)
    monkeypatch.setattr("mbpy.cli.Path.cwd", lambda: tmp_path)
    
    from mbpy.cli import install_command
    runner = click.testing.CliRunner()
    result = runner.invoke(install_command, ["-U", "sphinx"])
    
    assert result.exit_code == 0
    assert "Successfully installed sphinx-8.0.2" in result.output

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    assert 'sphinx==8.0.2' in updated_content
    assert 'sphinx==7.0.0' not in updated_content

def test_install_command_none_requirements(monkeypatch):
    def mock_subprocess_popen(*args, **kwargs):
        class MockProcess:
            def communicate(self, timeout=None):
                return (
                    "[notice] A new release of pip is available: 24.1 -> 24.2\n"
                    "[notice] To update, run: pip install --upgrade pip\n",
                    ""
                )
            
            @property
            def returncode(self):
                return 0

        return MockProcess()

    monkeypatch.setattr(subprocess, "Popen", mock_subprocess_popen)
    
    from mbpy.cli import install_command
    runner = click.testing.CliRunner()
    result = runner.invoke(install_command, ["-r", None])
    
    assert result.exit_code == 0
    assert "No packages specified for installation." in result.output
    assert "[notice] A new release of pip is available: 24.1 -> 24.2" not in result.output
    assert "[notice] To update, run: pip install --upgrade pip" not in result.output

import subprocess
import sys
import tomlkit
from pathlib import Path

import subprocess
import sys
import tomlkit
from pathlib import Path

def test_create_pyproject_toml_existing_directory(tmp_path, monkeypatch):
    project_name = "test_project"
    author = "Test Author"
    project_dir = tmp_path
    src_dir = project_dir / project_name

    initial_pyproject = """
[project]
dependencies = [
"altair==5.3.0",
"coloredlogs==15.0.1",
"gradio==4.36.1",
"idna==3.7",
"importlib-resources==6.4.0",
"jsonschema-specifications==2023.12.1",
"pycparser==2.22",
"rich==13.7.1",
"soundfile==0.12.1",
"starlette==0.37.2",
"uvloop==0.19.0"
]
"""
    (project_dir / "pyproject.toml").write_text(initial_pyproject)

    # Simulate user input for overwriting existing directory
    monkeypatch.setattr('builtins.input', lambda _: 'y')

    # Run mbpy create command
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "create", project_name, "--author", author],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=True
    )

    assert result.returncode == 0
    assert f"Project '{project_name}' created successfully" in result.stdout

    # Check that the project structure is created correctly
    assert (project_dir / "__about__.py").exists()
    assert (project_dir / "__about__.py").read_text() == '__version__ = "0.1.0"'
    
    # Read and parse the updated pyproject.toml
    new_pyproject = tomlkit.parse((project_dir / "pyproject.toml").read_text())
    
    # Check that the original dependencies are preserved
    assert "project" in new_pyproject
    assert "dependencies" in new_pyproject["project"]
    assert "altair==5.3.0" in new_pyproject["project"]["dependencies"]
    assert len(new_pyproject["project"]["dependencies"]) == 11
    assert "uvloop==0.19.0" in new_pyproject["project"]["dependencies"]
    
    # Check that new sections are added
    assert "build-system" in new_pyproject
    assert new_pyproject["build-system"]["requires"] == ["hatchling"]
    assert new_pyproject["build-system"]["build-backend"] == "hatchling.build"
    
    assert "tool" in new_pyproject
    assert "hatch" in new_pyproject["tool"]
    assert new_pyproject["tool"]["hatch"]["version"]["path"] == f"{project_name}/__about__.py"
    assert "pytest" in new_pyproject["tool"]["hatch"]["envs"]["default"]["dependencies"]
    
    assert "ruff" in new_pyproject["tool"]
    assert new_pyproject["tool"]["ruff"]["line-length"] == 120
    assert "E" in new_pyproject["tool"]["ruff"]["select"]
    
    assert "pytest" in new_pyproject["tool"]
    assert "--cov=src" in new_pyproject["tool"]["pytest"]["ini_options"]["addopts"]
