import pytest
from types import ModuleType
import sys
from typing import Any, cast
from mbpy.import_utils import default_export

def test_default_export():
    # Test callable function
    def test_func():
        return "test"
      
    
    test_func.__module__ = "test_module"
    sys.modules["test_module"] = ModuleType("test_module")
    
    exported = default_export(test_func)
    assert exported() == "test"
    assert isinstance(sys.modules["test_module"], ModuleType)
    assert sys.modules["test_module"]() == "test"

def test_default_export_static():
    # Test static value

    class Test:
      __module__ = "test_static"
    test_value = Test
    sys.modules["test_static"] = ModuleType("test_static")
    
    exported = default_export(test_value)
    assert exported == Test
    assert sys.modules["test_static"].__name__ == "test_static"

def test_default_export_missing_module():
    def test_func(): pass
    test_func.__module__ = "missing_module"
    
    with pytest.raises(ValueError, match="missing_module not found in sys.modules"):
        default_export(test_func)

def test_default_export_no_module_attr():
    test_obj = object()
    with pytest.raises(AttributeError, match="has no __module__ attribute"):
        default_export(test_obj)

def test_default_export_with_key():
    def test_func(): 
        return "keyed"
    sys.modules["test_key"] = ModuleType("test_key")
    
    exported = default_export(test_func, key="test_key")
    assert exported() == "keyed"
    assert sys.modules["test_key"]() == "keyed"