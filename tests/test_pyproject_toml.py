import pytest
import subprocess
import sys
from pathlib import Path
import tomlkit

def test_mpip_install_requirements(tmp_path):
    # Create a temporary requirements.txt file
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("click==8.1.7\nrequests==2.31.0\n")

    # Create a temporary pyproject.toml file
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = []
""")

    # Run the mpip install command
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "-r", str(requirements_file)],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )

    # Check the output
    assert result.returncode == 0
    assert "Installing packages from" in result.stdout
    assert "Running command: " in result.stdout
    assert "-m pip install -r" in result.stdout
    assert "Successfully installed" in result.stdout or "Requirement already satisfied" in result.stdout

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    updated_toml = tomlkit.parse(updated_content)
    
    assert "click" in [dep.split("==")[0] for dep in updated_toml["project"]["dependencies"]]
    assert "requests" in [dep.split("==")[0] for dep in updated_toml["project"]["dependencies"]]

def test_mpip_install_upgrade(tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_file = tmp_path / "pyproject.toml"
    initial_content = """
[project]
name = "test-project"
version = "0.1.0"
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
    assert "Successfully installed sphinx" in result.stdout or "Requirement already satisfied" in result.stdout

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    updated_toml = tomlkit.parse(updated_content)
    
    assert 'sphinx==7.0.0' not in updated_toml["project"]["dependencies"]
    assert any(dep.startswith("sphinx==") for dep in updated_toml["project"]["dependencies"])

    # Check if requirements.txt was created and updated
    requirements_file = tmp_path / "requirements.txt"
    assert requirements_file.exists()
    requirements_content = requirements_file.read_text()
    assert any(line.startswith("sphinx==") for line in requirements_content.splitlines())

def test_mpip_install_new_dependency(tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_file = tmp_path / "pyproject.toml"
    initial_content = """
[project]
name = "test-project"
version = "0.1.0"
dependencies = []
"""
    pyproject_file.write_text(initial_content)

    # Run the mbpy install command to add a new dependency
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "requests"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Successfully installed requests" in result.stdout or "Requirement already satisfied" in result.stdout

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    updated_toml = tomlkit.parse(updated_content)
    
    assert any(dep.startswith("requests") for dep in updated_toml["project"]["dependencies"])

    # Check if requirements.txt was created and updated
    requirements_file = tmp_path / "requirements.txt"
    assert requirements_file.exists()
    requirements_content = requirements_file.read_text()
    assert any(line.startswith("requests") for line in requirements_content.splitlines())

@pytest.mark.parametrize("args", [
    ["-r", "requirements.txt"],
    ["--requirements", "requirements.txt"],
])
def test_mpip_install_requirements_variations(tmp_path, args):
    # Create a temporary requirements.txt file
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("click==8.1.7\n")

    # Create a temporary pyproject.toml file
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = []
""")

    # Run the mbpy install command with different argument variations
    full_args = [sys.executable, "-m", "mbpy.cli", "install"] + args
    result = subprocess.run(
        full_args,
        cwd=tmp_path,
        capture_output=True,
        text=True
    )

    # Check the output
    assert result.returncode == 0
    assert "Installing packages from" in result.stdout
    assert "Successfully installed" in result.stdout or "Requirement already satisfied" in result.stdout

    # Check if pyproject.toml was updated correctly
    updated_content = pyproject_file.read_text()
    updated_toml = tomlkit.parse(updated_content)
    
    assert "click" in [dep.split("==")[0] for dep in updated_toml["project"]["dependencies"]]
