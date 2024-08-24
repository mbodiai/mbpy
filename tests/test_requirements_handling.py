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
