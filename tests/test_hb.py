from typing import Literal
import pytest
import numpy as np
from mbpy.heartbeat import FloatByteLiteral, values

def test_values_length():
    assert len(values) == 255

def test_values_range():
    assert min(values) == -1.0
    assert max(values) == 1.0

def test_values_are_evenly_spaced():
    diffs = np.diff(values)
    # Check all differences are equal (within floating point precision)
    assert np.allclose(diffs, diffs[0])

def test_values_are_rounded():
    # Check all values are rounded to 6 decimal places
    for value in values:
        assert round(value, 6) == value

def test_float_byte_literal_type():
    # Check that FloatByteLiteral contains all values from the values array
    literal_values = [v for v in FloatByteLiteral.__args__]
    assert len(literal_values) == 255
    assert all(v in literal_values for v in values)
    assert all(v in values for v in literal_values)

def test_float_byte_literal_bounds():
    literal_values = [v for v in FloatByteLiteral.__args__]
    assert min(literal_values) == -1.0
    assert max(literal_values) == 1.0

if __name__ == "__main__":
    pytest.main([__file__])