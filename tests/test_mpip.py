# import asyncio
# import os
# from pathlib import Path
# from unittest.mock import patch

# import pytest

# from mbpy.helpers._env import get_ordered_environs
# from mbpy.pkg.dependency import normalize_path
# from mbpy.pkg.mpip import (
#     Dependency,
#     modify_dependencies,
#     modify_pyproject,
#     modify_requirements,
# )
# from mbpy.pkg.pypi import find_and_sort, get_latest_version, get_package_info, get_package_names
# from mbpy.pkg.toml import (
#     find_toml_file,
#     is_group,
# )


# @pytest.fixture(scope="session")
# def event_loop():
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()

# @pytest.mark.asyncio
# async def test_dependency_to_string():
#     dep = Dependency('requests', '2.25.1')
#     result = await dep.to_string()
#     assert result == 'requests>=2.25.1'

#     dep = Dependency('numpy', extras=['random', 'linalg'])
#     result = await dep.to_string()
#     assert result == 'numpy[random, linalg]'

#     dep = Dependency('pandas', conditions='python_version >= "3.6"')
#     result = await dep.to_string()
#     assert result == 'pandas; python_version >= "3.6"'

#     dep = Dependency('git+https://github.com/user/repo.git')
#     result = await dep.to_string()
#     assert result == 'repo @ git+https://github.com/user/repo.git'

#     result = await dep.to_string(requirements=True)
#     assert result == 'git+https://github.com/user/repo.git'

# @pytest.mark.asyncio
# async def test_dependency_format_installation():
#     import tempfile
#     from contextlib import chdir
#     with tempfile.TemporaryDirectory("local_path") as temp_dir,chdir(Path(temp_dir).parent):
#         dep = Dependency('-e ./local_package')
#         result = await dep.requirements_name
#         assert result.startswith('-e') and result.endswith('local_package')
#         result = await dep.to_string()
#         assert result.startswith('local_package @ ')
#         assert result.endswith('local_package')

# @pytest.mark.asyncio
# async def test_getbase():
#     assert await Dependency('package>=1.0.0').base == 'package'


# def test_is_group():
#     assert is_group('[group]')
#     assert not is_group('dependencies = [')
#     assert not is_group('# This is a comment')

# def test_get_ordered_environs():
#     os.environ['VIRTUAL_ENV'] = '/path/to/venv'
#     envs = get_ordered_environs()
#     assert 'VIRTUAL_ENV' in envs

# @pytest.mark.asyncio
# async def test_find_toml_file(tmp_path):
#     pyproject_file = tmp_path / 'pyproject.toml'
#     pyproject_file.touch()
#     found_file = await find_toml_file(cwd=str(tmp_path))
#     assert Path(str(found_file)).resolve() == Path(str(pyproject_file)).resolve()

# @pytest.mark.asyncio
# async def test_get_requirements_packages(tmp_path):
#     req_file = tmp_path / 'requirements.txt'
#     req_file.write_text('requests>=2.25.1\nnumpy>=1.21.0\n')
#     packages = await get_requirements_packages(str(req_file))
#     assert 'requests>=2.25.1' in packages
#     assert 'numpy>=1.21.0' in packages


# @pytest.mark.asyncio
# async def test_dependency_with_multiple_conditions():
#     dep = Dependency('package', conditions='python_version >= "3.6" and os_name == "posix"')
#     result = await dep.to_string()
#     assert result == 'package; python_version >= "3.6" and os_name == "posix"'

# @pytest.mark.asyncio
# async def test_modify_requirements(tmp_path):
#     # Setup: Create a temporary requirements.txt file
#     requirements = tmp_path / "requirements.txt"
#     requirements.write_text("requests>=2.25.0\nnumpy==1.19.0\n")
    
#     # Test installing a new package
#     await modify_requirements("pandas>=1.1.0", action="install", requirements=str(requirements))
#     assert "pandas>=1.1.0" in requirements.read_text()
    
#     # Test uninstalling a package
#     await modify_requirements("numpy", action="uninstall", requirements=str(requirements))
#     assert "numpy==1.19.0" not in requirements.read_text()

# @pytest.mark.asyncio
# async def test_modify_pyproject(tmp_path):
#     # Setup: Create a temporary pyproject.toml file
#     pyproject = tmp_path / "pyproject.toml"
#     pyproject.write_text("""
#     [project]
#     name = "test_project"
#     version = "0.1.0"
#     dependencies = [
#         "requests>=2.25.0",
#         "numpy==1.19.0"
#     ]
#     """)
    
#     # Test installing a new package
#     await modify_pyproject(
#         package="pandas==1.1.0",
#         action="install",
#         pyproject_path=str(pyproject)
#     )
#     content = pyproject.read_text()
#     assert 'pandas>=1.1.0' in content
    
#     # Test uninstalling a package
#     await modify_pyproject(
#         package=Dependency('numpy'),
#         action="uninstall",
#         pyproject_path=str(pyproject)
#     )
#     content = pyproject.read_text()
#     assert 'numpy==1.19.0' not in content

# @pytest.mark.asyncio
# async def test_normalize_path():
#     # Test file URI
#     path = 'file:///home/user/project'
#     normalized = normalize_path(path)
#     assert normalized == Path('/home/user/project')
    
#     # Test regular path
#     path = '/home/user/project'
#     normalized = normalize_path(path)
#     assert normalized == Path('/home/user/project')

# @pytest.mark.asyncio
# async def test_get_latest_version():
#     version = await get_latest_version("requests")
#     assert version is not None
#     assert isinstance(version, str)

# @pytest.mark.asyncio
# async def test_get_package_names():
#     package_names = await get_package_names("requests")
#     assert "requests" in package_names

# @pytest.mark.asyncio
# async def test_get_package_info():
#     package_info = await get_package_info("requests")
#     assert package_info["name"].lower() == "requests"
#     assert "version" in package_info

# @pytest.mark.asyncio
# async def test_find_and_sort():
#     packages = await find_and_sort("requests", limit=5)
#     assert len(packages) <= 5
#     assert all("requests" in pkg["name"].lower() for pkg in packages)

# def test_equals_pkg():
#     matcher = equals_pkg('requests')
#     assert matcher('requests>=2.25.1')
#     assert not matcher('numpy')

# @pytest.mark.asyncio
# async def test_get_pkg_name(tmp_path):
#     # Setup: Create a temporary pyproject.toml
#     project_dir = tmp_path / "project"
#     project_dir.mkdir()
#     pyproject = project_dir / "pyproject.toml"
#     pyproject.write_text("""
#     [project]
#     name = "test_pkg"
#     """)
    
#     pkg_name = await Dependency(str(project_dir)).base
#     assert pkg_name == "test_pkg"

# def test_syncgetbase():
#     assert Dependency.syncgetbase('package>=1.0.0') == 'package'
#     assert Dependency.syncgetbase('git+https://github.com/user/repo.git') == 'git+https://github.com/user/repo.git'
#     assert Dependency.syncgetbase('-e ./local_package') == './local_package'

# def test_getversion():
#     assert Dependency.getversion('package>=1.0.0') == '1.0.0'
#     assert Dependency.getversion('package') == ''
#     assert Dependency.getversion('git+https://github.com/user/repo.git') == ''

# def test_getextras():
#     assert Dependency.getextras('package[extra1,extra2]') == ['extra1', 'extra2']
#     assert Dependency.getextras('package') == ''

# @pytest.mark.asyncio
# async def test_pkg_str():
#     pkg = await Dependency("requests", "2.25.0").to_string()
#     assert pkg == "requests>=2.25.0"
    
#     pkg = await Dependency("numpy", extras=["random", "linalg"]).to_string()
#     assert pkg == "numpy[random, linalg]"

# @pytest.mark.asyncio
# async def test_format_pkg():
#     pkg = await Dependency("requests", "2.25.0").to_string()
#     assert pkg == "requests>=2.25.0"
    
#     pkg = await Dependency("numpy", extras=["random", "linalg"]).to_string()
#     assert pkg == "numpy[random, linalg]"

# @pytest.mark.asyncio
# async def test_name_and_version():
#     name, version = await Dependency('package>=1.0.0').base , await Dependency('package>=1.0.0').version
#     assert name == 'package'
#     assert version == '1.0.0'

# @pytest.mark.asyncio
# async def test_modify_requirements_install(tmp_path):
#     # Setup: Create a temporary requirements.txt
#     requirements = tmp_path / "requirements.txt"
#     requirements.write_text("requests>=2.25.0\n")
    
#     # Test installing a package
#     await modify_requirements("numpy==1.19.0", action="install", requirements=str(requirements))
#     assert "numpy==1.19.0" in requirements.read_text()

# @pytest.mark.asyncio
# async def test_modify_requirements_uninstall(tmp_path):
#     # Setup: Create a temporary requirements.txt
#     requirements = tmp_path / "requirements.txt"
#     requirements.write_text("requests>=2.25.0\nnumpy==1.19.0\n")
    
#     # Test uninstalling a package
#     await modify_requirements("numpy", action="uninstall", requirements=str(requirements))
#     assert "numpy==1.19.0" not in requirements.read_text()

# @pytest.mark.asyncio
# async def test_modify_pyproject_install(tmp_path):
#     # Setup: Create a temporary pyproject.toml
#     pyproject = tmp_path / "pyproject.toml"
#     pyproject.write_text("""
#     [project]
#     name = "test_project"
#     version = "0.1.0"
#     dependencies = [
#         "requests>=2.25.0"
#     ]
#     """)
    
#     # Test installing a package
#     await modify_pyproject(
#         package="numpy>=1.19.0",
#         action="install",
#         pyproject_path=str(pyproject)
#     )
#     content = pyproject.read_text()
#     assert 'numpy>=1.19.0' in content

# @pytest.mark.asyncio
# async def test_modify_pyproject_uninstall(tmp_path):
#     # Setup: Create a temporary pyproject.toml
#     pyproject = tmp_path / "pyproject.toml"
#     pyproject.write_text("""
#     [project]
#     name = "test_project"
#     version = "0.1.0"
#     dependencies = [
#         "requests>=2.25.0",
#         "numpy==1.19.0"
#     ]
#     """)
    
#     # Test uninstalling a package
#     await modify_pyproject(
#         package="numpy",
#         action="uninstall",
#         pyproject_path=str(pyproject)
#     )
#     content = pyproject.read_text()
#     assert 'numpy==1.19.0' not in content

# @pytest.mark.asyncio
# async def test_modify_dependencies_install():
#     dependencies = ['requests>=2.25.0', 'numpy==1.19.0']
#     updated = await modify_dependencies(dependencies, "pandas>=1.1.0", "install")
#     assert "pandas>=1.1.0" in updated

# @pytest.mark.asyncio
# async def test_modify_dependencies_uninstall():
#     dependencies = ['requests>=2.25.0', 'numpy==1.19.0']
#     updated = await modify_dependencies(dependencies, "numpy==1.19.0", "uninstall")
#     assert "numpy==1.19.0" not in updated

# @pytest.mark.asyncio
# async def test_dependency_malformed_conditions():

#     with pytest.raises(ValueError):
#         dep = Dependency("requests", conditions='python_version >> "3.6"')
#         await dep.to_string()

# @pytest.mark.asyncio
# async def test_dependency_with_or_condition():
#     dep = Dependency("requests", conditions='python_version < "3.6" or platform_system == "Linux"')
#     dep_str = await dep.to_string()
#     assert dep_str == 'requests; python_version < "3.6" or platform_system == "Linux"'

