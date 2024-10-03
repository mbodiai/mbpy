import pytest
import subprocess
import sys
from pathlib import Path
from mbpy.cli import run_command
import tomlkit
from tempfile import TemporaryDirectory
from mbpy.mpip import find_toml_file, get_requirements_packages, search_parents_for_file
@pytest.fixture
def tmp_path():
    with TemporaryDirectory() as tmp_file:
        yield Path(tmp_file)

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
wrapt==1.16.1
"""
    requirements_path.write_text(requirements_content)

    # Run the upgrade command
    for i in run_command(
        [sys.executable, "-m", "mbpy.cli", "install", "-r", str(requirements_path), "-U"],
        cwd=tmp_path,
    ):
        print(i)
    


    # Read and parse the updated pyproject.toml
    updated_content = pyproject_path.read_text()
    updated_pyproject = tomlkit.parse(updated_content)

    # Check if the dependencies were updated correctly
    dependencies = updated_pyproject["project"]["dependencies"]
    assert any(dep.startswith("click==") for dep in dependencies), f"click not updated in {dependencies}"
    assert any(dep.startswith("requests==") for dep in dependencies), f"requests not updated in {dependencies}"
    assert any(dep.startswith("toml==") for dep in dependencies), f"toml not updated in {dependencies}"
    assert any(dep.startswith("packaging") for dep in dependencies), f"packaging not added in {dependencies}"
    assert any(dep.startswith("requests==") for dep in dependencies), f"requests not updated in {dependencies}"
    assert any(dep.startswith("toml==") for dep in dependencies), f"toml not updated in {dependencies}"
    assert any(dep.startswith("packaging==") for dep in dependencies), f"packaging not added in {dependencies}"

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
    assert "click==" in updated_requirements
    assert "requests==" in updated_requirements
    assert "toml==" in updated_requirements
    assert "packaging==" in updated_requirements

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
    result = str(run_command(
        [sys.executable, "-m", "mbpy.cli", "install", "wrapt"] + ["--debug"],
        cwd=tmp_path,
        debug=True,
    ))
    print(f"path: {pyproject_path.absolute()}")
    assert pyproject_path.name and pyproject_path.absolute() == find_toml_file(pyproject_path.absolute()).absolute(), f"Expected {pyproject_path.name}, got {find_toml_file(pyproject_path.name).name}"
    updated_content = pyproject_path.read_text()
    print(f"updated_content: {updated_content}")

    str(run_command(
        [sys.executable, "-m", "mbpy.cli", "uninstall", "funkify"],
    ))
    updated_content = pyproject_path.read_text()
    assert "funkify" not in updated_content, f"'funkify' found in updated content: {updated_content}"

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

def test_get_requirements_packages(tmp_path):
        requirements_path = tmp_path / "requirements.txt"

        # Test with an empty requirements file
        requirements_path.touch()
        packages = get_requirements_packages(str(requirements_path))
        assert packages == set(), f"Expected empty set, got {packages}"

        # Test with a non-empty requirements file
        requirements_content = """
        click==8.0.3
        requests==2.26.0
        # This is a comment
        toml==0.10.2
        """
        requirements_path.write_text(requirements_content)
        packages = get_requirements_packages(str(requirements_path))
        expected_packages = {"click==8.0.3", "requests==2.26.0", "toml==0.10.2"}
        assert packages == expected_packages, f"Expected {expected_packages}, got {packages}"

        # Test with as_set=False
        packages_list = get_requirements_packages(str(requirements_path), as_set=False)
        expected_packages_list = ["click==8.0.3", "requests==2.26.0", "toml==0.10.2"]
        assert packages_list == expected_packages_list, f"Expected {expected_packages_list}, got {packages_list}"

        # Test with a missing requirements file
        missing_requirements_path = tmp_path / "missing_requirements.txt"
        packages = get_requirements_packages(str(missing_requirements_path))
        assert packages == set(), f"Expected empty set for missing file, got {packages}"
        assert missing_requirements_path.exists(), "Expected missing requirements file to be created"
        def test_search_parents_for_file_found(tmp_path):
            # Create a temporary directory structure
            root_dir = tmp_path / "root"
            root_dir.mkdir()
            sub_dir = root_dir / "sub"
            sub_dir.mkdir()
            target_file = root_dir / "pyproject.toml"
            target_file.touch()

            # Change to subdirectory
            current_dir = sub_dir

            # Call the function
            found_file = search_parents_for_file("pyproject.toml", cwd=current_dir)

            # Assert the file was found
            assert found_file == target_file, f"Expected {target_file}, got {found_file}"

def test_search_parents_for_file_not_found(tmp_path):
    # Create a temporary directory structure
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    sub_dir = root_dir / "sub"
    sub_dir.mkdir()

    # Change to subdirectory
    current_dir = sub_dir

    # Call the function
    found_file = search_parents_for_file("pyproject.toml", cwd=current_dir)

    # Assert the file was not found
    assert not found_file.exists(), f"Expected file not to be found, but got {found_file}"

def test_search_parents_for_file_max_levels(tmp_path):
    # Create a temporary directory structure
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    level1_dir = root_dir / "level1"
    level1_dir.mkdir()
    level2_dir = level1_dir / "level2"
    level2_dir.mkdir()
    level3_dir = level2_dir / "level3"
    level3_dir.mkdir()
    target_file = root_dir / "pyproject.toml"
    target_file.touch()

    # Change to level3 directory
    current_dir = level3_dir

    # Call the function with max_levels=2
    found_file = search_parents_for_file("pyproject.toml", max_levels=2, cwd=current_dir)

    # Assert the file was not found within the max_levels
    assert not found_file.exists(), f"Expected file not to be found within max_levels, but got {found_file}"

def test_search_parents_for_file_in_current_directory(tmp_path):
    # Create a temporary directory structure
    current_dir = tmp_path / "current"
    current_dir.mkdir()
    target_file = current_dir / "pyproject.toml"
    target_file.touch()

    # Call the function
    found_file = search_parents_for_file("pyproject.toml", cwd=current_dir)

    # Assert the file was found in the current directory
    assert found_file == target_file, f"Expected {target_file}, got {found_file}"

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, force=True)
    with TemporaryDirectory() as tmp_path:
        tmp_path = Path(tmp_path)
        # test_upgrade_from_requirements_file(tmp_path)
        test_modify_dependencies(tmp_path)
        test_pyproject_toml_formatting(tmp_path)
        test_get_requirements_packages()
        test_search_parents_for_file_found()
        test_search_parents_for_file_not_found()
        test_search_parents_for_file_max_levels()
        test_search_parents_for_file_in_current_directory()