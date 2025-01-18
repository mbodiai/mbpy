from pathlib import Path
import platform
import sys
from typing import Any, cast
import pytest

from mbpy.import_utils import (
    smart_import,
    import_plt, 
    default_export,
    bootstrap_third_party,
    _cache,
    lazy_import
)
import pytest
from unittest.mock import patch
import sys
from mbpy.import_utils import lazy_import, _LazyModule

@pytest.fixture
def clean_json_import():
    """Fixture to ensure clean json import state"""
    had_json = "json" in sys.modules
    original_json = sys.modules.get("json")
    
    if "json" in sys.modules:
        del sys.modules["json"]
    
    yield
    
    if had_json:
        sys.modules["json"] = original_json
    elif "json" in sys.modules:
        del sys.modules["json"]

@pytest.fixture
def mock_spinner():
    """Mock spinner to prevent sys.exit"""
    with patch('mbpy.Spinner') as mock_spinner:
        # Prevent cleanup from calling sys.exit
        mock_spinner.cleanup = lambda *args, **kwargs: None
        yield mock_spinner

# Test smart_import functionality
def test_smart_import_basic():
    os = smart_import("os")
    assert os.name in ("nt", "posix")
    
    math = smart_import("math")
    assert math.pi > 3.14

def test_smart_import_lazy():
    os = smart_import("os", "lazy")
    assert os.name in ("nt", "posix")
    
    math = smart_import("math", "lazy")
    assert math.pi > 3.14

def test_smart_import_function():
    sin = smart_import("math.sin","lazy")
    assert callable(sin)
    assert sin(0) == 0

def test_smart_import_with_attribute():
    sin = smart_import("math.sin") 
    assert callable(sin)
    assert sin(0) == 0

def test_smart_import_with_attribute():
    json = smart_import("json") 
    assert hasattr(json, "dumps")
    assert callable(json.dumps)
    assert json.dumps({"key": "value"}) == '{"key": "value"}'

def test_smart_import_invalid():
    with pytest.raises(ImportError):
        smart_import("not_a_real_module")

def test_smart_import_caching():
    # First import
    os1 = smart_import("os")
    # Should return cached version
    os2 = smart_import("os") 
    assert os1 is os2
    assert "os" in _cache or "os" in sys.modules

# Test import_plt functionality
def test_import_plotext():
        plt = import_plt("plotext")
        assert hasattr(plt, "plot")

def test_import_plt_matplotlib():
  # from matplotlib import pyplot as plt
  plt = import_plt("matplotlib")
  assert hasattr(plt, "plot")



# Test bootstrap functionality
def test_bootstrap_third_party():
    test_mod = "json"
    test_location = "mbpy.test_utils"
    
    result = bootstrap_third_party(test_mod, test_location)
    assert result is not None
    assert hasattr(result, "dumps")
    
    # Verify module is properly registered
    qualified_name = f"{test_location}.{test_mod}"
    assert qualified_name in sys.modules

def test_bootstrap_invalid():
    with pytest.raises(ImportError):
        bootstrap_third_party("invalid_module", "invalid_location")

# Test error cases
def test_smart_import_type_errors():
    with pytest.raises(ValueError):
        smart_import(123)  # type: ignore

# Test platform-specific behavior
@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS specific test")
def test_macos_backend():
    plt = import_plt("matplotlib")
    assert plt is not None
    assert hasattr(plt, "plot")

# Cleanup helper
@pytest.fixture(autouse=True)
def cleanup():
    cached = list(_cache.keys())
    yield
    # Restore cache state
    for key in list(_cache.keys()):
        if key not in cached:
            del _cache[key]