import pytest
import subprocess
import sys
from pathlib import Path

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
    assert "package3==3.0.0" in updated_content

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
