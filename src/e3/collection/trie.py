from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Iterable, Dict, Optional


class Trie:
    """Implements a trie data structure.

    This structure can be used to do the following:

    * check if a word match a suffix in a list of suffixes
    * check if a word match a prefix in a list of prefixes
    * check if a word is in a list of words

    This is more efficient than iterating other sets or than using a simple
    regexp that concatenates the list of words/prefixes/suffixes
    """

    # Used as special symbols to mark end of a word in the trie database.
    END_MARKER = ""

    def __init__(
        self,
        word_list: Optional[Iterable[str]] = None,
        use_suffix: bool = False,
        match_delimiter: str = "",
    ) -> None:
        """Initialize a trie structure.

        :param word_list: a list of words to add to the trie
        :param use_suffix: use suffix matching rather then prefix matching
        :param match_delimiter: set default value for match function mode delimiter.
        """
        self.tree: Dict[str, Any] = {}
        self.match_delimiter = match_delimiter
        self.word_iterator: Callable[[str], Iterable[str]] = lambda x: iter(x)
        if use_suffix:
            self.word_iterator = lambda x: reversed(x)

        if word_list is not None:
            for word in word_list:
                self.add(word)

    def add(self, word: str) -> None:
        """Add a word to the trie.

        :param word: the word to add
        """
        cursor = self.tree

        for letter in self.word_iterator(word):
            if letter not in cursor:
                cursor[letter] = {}
            cursor = cursor[letter]

        if self.END_MARKER not in cursor:
            cursor[self.END_MARKER] = 1

    def contains(self, word: str) -> bool:
        """Check whether word is in the trie.

        :param word: a word
        :return: True if the word is in the trie, False otherwise
        """
        cursor = self.tree

        for letter in self.word_iterator(word):
            if letter in cursor:
                cursor = cursor[letter]
            else:
                return False

        return self.END_MARKER in cursor

    def __contains__(self, word: str) -> bool:
        return self.contains(word)

    def match(self, word: str, delimiter: Optional[str] = None) -> bool:
        """Check if there is word in the trie which is a prefix/suffix of word.

        :param word: the word to check
        :param delimiter: if None use the default delimiter. If delimiter is ''
            then the function returns True whenever a word in the trie is a
            prefix or suffix of word. If delimiter is a non empty string then
            the function returns True if there is a word W in the trie such as
            W is equal to word or if W is a prefix/suffix of word and that the
            next/previous character in word is in delimiter.
        :return: True if matched, False otherwise
        """
        if delimiter is None:
            delimiter = self.match_delimiter

        cursor = self.tree

        for letter in self.word_iterator(word):
            if self.END_MARKER in cursor and (not delimiter or letter in delimiter):
                return True
            else:
                cursor = cursor.get(letter, None)
                if cursor is None:
                    return False

        return self.END_MARKER in cursor
