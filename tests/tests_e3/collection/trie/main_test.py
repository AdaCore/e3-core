from __future__ import annotations
import os
import pytest
import time
from typing import TYPE_CHECKING
from e3.collection.trie import Trie

if TYPE_CHECKING:
    from typing import List


def load_words() -> List[str]:
    with open(os.path.join(os.path.dirname(__file__), "word_list.txt")) as fd:
        return [word for word in fd.read().splitlines() if word.strip()]


ENGLISH_WORD_LIST = load_words()


@pytest.mark.xfail(reason="unstable test, duration might be too short")
def test_simple_word_matching():
    t = Trie(word_list=ENGLISH_WORD_LIST[:10])

    start = time.time()
    for _j in range(10000):
        assert t.contains("across")
        assert not t.contains("whom")
        assert not t.contains("bonjour")
        assert not t.contains("acrosst")
    test1_time = time.time() - start

    t = Trie(word_list=ENGLISH_WORD_LIST)
    start = time.time()
    for _j in range(10000):
        assert t.contains("across")
        assert t.contains("whom")
        assert not t.contains("bonjour")
        assert not t.contains("acrosst")
    test2_time = time.time() - start

    # Using a 1000 word list should not impact the search time
    assert test2_time < 2 * test1_time


def test_prefix_matching():
    t = Trie(word_list=ENGLISH_WORD_LIST)
    assert t.match("across l'univers")
    assert t.match("across l'univers", delimiter=" ")
    assert t.match("across", delimiter=" ")
    assert not t.match("acrossl'univers", delimiter=" ")


def test_suffix_matching():
    t = Trie(word_list=ENGLISH_WORD_LIST, use_suffix=True)
    assert t.match("je parle a lot")
    assert t.match("je parlealot")
    assert t.match("je parle a lot", delimiter=" ")
    assert not t.match("je parle beaucoup", delimiter=" ")
    assert not t.match("je parlealot", delimiter=" ")
