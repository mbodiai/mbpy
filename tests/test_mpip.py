import pytest
import subprocess
import sys
from pathlib import Path

import tomlkit

def test_upgrade_from_requirements_file(tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_path = tmp_path / "pyproject.toml"
    initial_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "0.1.0"
description = "A test project"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
dependencies = [
    "click==8.0.3",
    "requests==2.26.0",
    "toml==0.10.2",
]

[tool.hatch.version]
path = "test_project/__about__.py"

[tool.hatch.envs.default]
dependencies = [
    "pytest",
    "pytest-cov"
]

[tool.ruff]
line-length = 120
select = ["E", "F", "W", "I", "N", "D", "UP", "S", "B", "A"]
ignore = ["E501", "D100", "D104"]
"""
    pyproject_path.write_text(initial_content)

    # Create a requirements.txt file with upgraded versions
    requirements_path = tmp_path / "requirements.txt"
    requirements_content = """
click==8.1.7
requests==2.32.3
toml==0.10.2
packaging==24.1
"""
    requirements_path.write_text(requirements_content)

    # Run the upgrade command
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "-r", str(requirements_path), "-U"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Upgrade failed: {result.stderr}"

    # Read and parse the updated pyproject.toml
    updated_content = pyproject_path.read_text()
    updated_pyproject = tomlkit.parse(updated_content)

    # Check if the dependencies were updated correctly
    dependencies = updated_pyproject["project"]["dependencies"]
    assert any(dep.startswith("click==8.1.7") for dep in dependencies), f"click not updated in {dependencies}"
    assert any(dep.startswith("requests==2.32.3") for dep in dependencies), f"requests not updated in {dependencies}"
    assert any(dep.startswith("toml==0.10.2") for dep in dependencies), f"toml not updated in {dependencies}"
    assert any(dep.startswith("packaging==24.1") for dep in dependencies), f"packaging not added in {dependencies}"
    assert any(dep.startswith("requests==2.32.3") for dep in dependencies), f"requests not updated in {dependencies}"
    assert any(dep.startswith("toml==0.10.2") for dep in dependencies), f"toml not updated in {dependencies}"
    assert any(dep.startswith("packaging==24.1") for dep in dependencies), f"packaging not added in {dependencies}"

    # Check if dependencies are on separate lines
    dependencies_str = tomlkit.dumps(updated_pyproject["project"]["dependencies"])
    assert "\n" in dependencies_str, "Dependencies are not on separate lines"

    # Ensure the rest of the pyproject.toml content remains unchanged
    assert updated_pyproject["build-system"]["requires"] == ["hatchling"]
    assert updated_pyproject["build-system"]["build-backend"] == "hatchling.build"
    assert updated_pyproject["project"]["name"] == "test-project"
    assert updated_pyproject["project"]["version"] == "0.1.0"
    assert updated_pyproject["project"]["description"] == "A test project"
    assert updated_pyproject["project"]["readme"] == "README.md"
    assert updated_pyproject["project"]["requires-python"] == ">=3.10"
    assert updated_pyproject["project"]["license"] == "MIT"
    assert updated_pyproject["tool"]["hatch"]["version"]["path"] == "test_project/__about__.py"
    assert "pytest" in updated_pyproject["tool"]["hatch"]["envs"]["default"]["dependencies"]
    assert "pytest-cov" in updated_pyproject["tool"]["hatch"]["envs"]["default"]["dependencies"]
    assert updated_pyproject["tool"]["ruff"]["line-length"] == 120
    assert set(updated_pyproject["tool"]["ruff"]["select"]) == {"E", "F", "W", "I", "N", "D", "UP", "S", "B", "A"}
    assert set(updated_pyproject["tool"]["ruff"]["ignore"]) == {"E501", "D100", "D104"}

    # Check if the requirements.txt file was updated
    updated_requirements = requirements_path.read_text()
    assert "click==8.1.7" in updated_requirements
    assert "requests==2.32.3" in updated_requirements
    assert "toml==0.10.2" in updated_requirements
    assert "packaging==24.1" in updated_requirements

def test_modify_dependencies(tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_path = tmp_path / "pyproject.toml"
    initial_content = """
[project]
dependencies = [
    "package1==1.0.0",
    "package2==2.0.0"
]
"""
    pyproject_path.write_text(initial_content)

    # Test install action
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "requests"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Installation failed. Output: {result.stdout}\nError: {result.stderr}"
    updated_content = pyproject_path.read_text()
    assert "requests" in updated_content, f"'requests' not found in updated content: {updated_content}"

    # Test uninstall action
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "uninstall", "package1"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    updated_content = pyproject_path.read_text()
    assert "package1==1.0.0" not in updated_content

# Keep other tests that don't use patches

def test_pyproject_toml_formatting(tmp_path):
    # Create a temporary pyproject.toml file
    pyproject_path = tmp_path / "pyproject.toml"
    initial_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "0.1.0"
description = "A test project"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
dependencies = [
    "click==8.0.3",
    "requests==2.26.0",
]

[tool.hatch.version]
path = "test_project/__about__.py"

[tool.hatch.envs.default]
dependencies = [
    "pytest",
    "pytest-cov"
]

[tool.ruff]
line-length = 120
select = ["E", "F", "W", "I", "N", "D", "UP", "S", "B", "A"]
ignore = ["E501", "D100", "D104"]
"""
    pyproject_path.write_text(initial_content)

    # Run the install command to add a new package
    result = subprocess.run(
        [sys.executable, "-m", "mbpy.cli", "install", "pytest"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Installation failed: {result.stderr}"

    # Read the updated pyproject.toml content
    updated_content = pyproject_path.read_text()

    # Check the formatting
    lines = updated_content.split("\n")
    for line in lines:
        if line.strip().startswith('"') and line.strip().endswith('",'):
            # Check indentation for dependency lines
            assert line.startswith("    "), f"Incorrect indentation for line: {line}"
        elif "=" in line and not line.strip().startswith("["):
            # Check indentation for key-value pairs
            assert line.startswith("    ") or not line.startswith(" "), f"Incorrect indentation for line: {line}"
        elif line.strip().startswith("[") and line.strip().endswith("]"):
            # Check that section headers are not indented
            assert not line.startswith(" "), f"Incorrect indentation for section header: {line}"

    # Check that the new package was added with correct formatting
    assert any(line.strip().startswith('"pytest') for line in lines), "New package not added with correct formatting"

    # Check that the overall structure is maintained
    assert "[build-system]" in updated_content
    assert "[project]" in updated_content
    assert "[tool.hatch.version]" in updated_content
    assert "[tool.hatch.envs.default]" in updated_content
    assert "[tool.ruff]" in updated_content
