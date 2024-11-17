import pytest
from mbpy.utils.type_utils import is_seqcont, is_seq, is_mapping
from cProfile import runctx
from cytoolz.cytoolz import merge, merge_with




def test_is_seqcont():
    assert is_seqcont([1, 2, 3])
    assert is_seqcont((1, 2, 3))
    assert is_seqcont('abc')
    assert not is_seqcont(1)
    assert not is_seqcont({1, 2, 3})
    assert not is_seqcont({'a': 1, 'b': 2})
    assert not is_seqcont({'a': 1, 'b': 2}.items())
    

def test_merge_with():
    assert merge_with(sum, {1: 1, 2: 2}, {1: 2, 3: 3}) == {1: 3, 2: 2, 3: 3}

def test_cytoolz_merge():
    



    merge.__doc__ = cytoolz.merge.__doc__
    merge_with.__doc__ = cytoolz.merge_with.__doc__
