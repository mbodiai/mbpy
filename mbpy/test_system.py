import pytest
from pathlib import Path
from build import SystemCSpecs, ProjectCSpecs, BuildConfig


def test_system_specs_detection():
    specs = SystemCSpecs.detect()
    assert specs.compiler_path
    assert specs.include_paths
    assert isinstance(specs.supports_c17, bool)


def test_project_specs_from_cmake():
    cmake_content = """
    cmake_minimum_required(VERSION 3.13)
    set(TREE_SITTER_ABI_VERSION 14)
    """
    path = Path("test_cmake")
    path.write_text(cmake_content)

    try:
        specs = ProjectCSpecs.from_cmake(path)
        assert specs.abi_version == 14
        assert specs.c_standard == 11  # default
    finally:
        path.unlink()


def test_build_config():
    system = SystemCSpecs.detect()
    project = ProjectCSpecs()
    config = BuildConfig(system, project)

    env = config.get_env()
    assert "CC" in env
    assert "CFLAGS" in env
    assert "-std=c" in env["CFLAGS"]


def test_invalid_cmake():
    specs = ProjectCSpecs.from_cmake(Path("nonexistent"))
    assert specs.abi_version == 14  # default
