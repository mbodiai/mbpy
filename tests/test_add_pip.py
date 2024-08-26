import pytest
import subprocess
import sys
import tempfile
import os
from pathlib import Path
import tomlkit
from mbpy.create import create_project, setup_documentation, extract_docstrings, create_pyproject_toml

def test_add_dependencies_to_pyproject(tmp_path):
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
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(initial_pyproject)

    new_dependencies = ["pytest==7.3.1", "requests>=2.26.0"]
    
    # Run mbpy install command to add new dependencies
    for dep in new_dependencies:
        result = subprocess.run(
            [sys.executable, "-m", "mbpy.cli", "install", dep],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )
        print(f"Install output for {dep}:")
        print(result.stdout)
        print(result.stderr)
        assert result.returncode == 0, f"Failed to install {dep}"

    # Read and parse the updated pyproject.toml
    updated_content = pyproject_file.read_text()
    parsed_toml = tomlkit.parse(updated_content)

    # Check if the new dependencies were added correctly
    project_dependencies = parsed_toml["project"]["dependencies"]
    assert "pytest==7.3.1" in project_dependencies
    assert "requests>=2.26.0" in project_dependencies

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
    assert "dependencies = [" in updated_content
    assert "]" in updated_content.split("dependencies = [")[1]

    # Test that installing "einops==0.8.0" equals the current string in the test
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "einops==0.8.0"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

    installed_version = subprocess.run(
        [sys.executable, "-m", "pip", "show", "einops"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert "Version: 0.8.0" in installed_version.stdout
    assert "einops==0.8.0" in parsed_toml["project"]["optional-dependencies"]["all"]
