import pytest
import subprocess
import sys
from pathlib import Path
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


def test_install_requirements_txt_error(tmp_path):
    # Create a temporary requirements.txt file
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("requirements.txt\n")  # This line simulates the error condition

    # Run the mbpy install command
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "-r", str(requirements_file)],
        capture_output=True,
        text=True
    )

    assert result.returncode != 0
    assert "Error: The requirements.txt file contains an invalid entry 'requirements.txt'." in result.stderr
    assert "Please remove this line from your requirements.txt file and try again." in result.stderr

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
    # Test that install -r requirements.txt works for all argument cases.
    assert False

def test_mpip_install_upgrade(tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_file = tmp_path / "pyproject.toml"
    initial_content = """
[project]
dependencies = [
    "sphinx==7.0.0"
]
"""
    pyproject_file.write_text(initial_content)

    # Run the mbpy install command
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "-U", "sphinx"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Successfully installed sphinx" in result.stdout

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    assert 'sphinx==7.0.0' not in updated_content
    assert 'sphinx==' in updated_content  # The version might vary, so we just check for an updated version
