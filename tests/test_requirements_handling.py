import pytest
from pathlib import Path
from mbpy.mpip import get_requirements_packages, modify_requirements

def test_get_requirements_packages_empty_file(tmp_path):
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.touch()
    
    result = get_requirements_packages(str(requirements_file))
    assert result == set()

def test_get_requirements_packages_with_content(tmp_path):
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("package1==1.0.0\npackage2>=2.0.0\n")
    
    result = get_requirements_packages(str(requirements_file))
    assert result == {"package1==1.0.0", "package2>=2.0.0"}

def test_modify_requirements_install(tmp_path):
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("existing_package==1.0.0\n")
    
    modify_requirements("new_package", "2.0.0", action="install", requirements=str(requirements_file))
    
    result = get_requirements_packages(str(requirements_file))
    assert "new_package==2.0.0" in result
    assert "existing_package==1.0.0" in result

def test_modify_requirements_uninstall(tmp_path):
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("package_to_remove==1.0.0\nkeep_package==2.0.0\n")
    
    modify_requirements("package_to_remove", action="uninstall", requirements=str(requirements_file))
    
    result = get_requirements_packages(str(requirements_file))
    assert "package_to_remove==1.0.0" not in result
    assert "keep_package==2.0.0" in result

def test_modify_requirements_nonexistent_file(tmp_path):
    nonexistent_file = tmp_path / "nonexistent.txt"
    
    modify_requirements("new_package", "1.0.0", action="install", requirements=str(nonexistent_file))
    
    assert nonexistent_file.exists()
    result = get_requirements_packages(str(nonexistent_file))
    assert "new_package==1.0.0" in result
import subprocess
import sys
from pathlib import Path

def test_requirements_install_format():
    # Create a temporary requirements file
    temp_req = Path("temp_requirements.txt")
    temp_req.write_text("""
click==8.1.7
packaging==24.1
requests==2.32.3
toml==0.10.2
tomlkit==0.13.0
markdown2==2.5.0
rich==13.7.1
mdstream==0.3.4
""".strip())

    try:
        # Run pip install with the requirements file
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(temp_req)],
            capture_output=True,
            text=True,
            check=True
        )

        # Check if there are any installed or already satisfied packages
        install_lines = [line for line in result.stdout.split('\n') if "Installing collected packages:" in line]
        already_satisfied_lines = [line for line in result.stdout.split('\n') if "Requirement already satisfied:" in line]
        
        installed_packages = []
        if install_lines:
            assert len(install_lines) == 1, "Expected installed packages to be on one line"
            installed_packages = install_lines[0].split(":")[1].strip().split(", ")
            print(f"Installed packages: {installed_packages}")
        
        satisfied_packages = len(already_satisfied_lines)
        if satisfied_packages:
            print(f"Already satisfied packages: {satisfied_packages}")
        
        total_packages = len(installed_packages) + satisfied_packages
        assert total_packages > 1, f"Expected multiple packages to be processed, but got {total_packages}"
        print(f"Total packages processed: {total_packages}")

    finally:
        # Clean up
        temp_req.unlink()
