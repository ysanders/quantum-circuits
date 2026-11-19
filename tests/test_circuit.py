"""Tests for circuits whose wires meet at CZ vertices."""

import unittest

from quantum_circuits import Circuit, I


class StoredOrderTests(unittest.TestCase):
    def test_constructor_requires_stored_order(self) -> None:
        segments = ((I, I), (I, I), (I, I), (I, I))
        Circuit(segments, ((0, 1), (2, 3)))
        with self.assertRaises(ValueError):
            Circuit(segments, ((2, 3), (0, 1)))

    def test_constructor_rejects_inconsistent_values(self) -> None:
        cases = {
            'too few segments': lambda: Circuit(((I,), (I, I)), ((0, 1),)),
            'pair out of order': lambda: Circuit(((I, I), (I, I)), ((1, 0),)),
            'missing wire': lambda: Circuit(((I, I), (I, I)), ((0, 2),)),
            'prepared wire out of range': lambda: Circuit(((I,),), (), frozenset({1})),
        }
        for description, attempt in cases.items():
            with self.subTest(description), self.assertRaises(ValueError):
                attempt()
        with self.assertRaises(TypeError):
            Circuit(((I,),), (), {0})


if __name__ == '__main__':
    unittest.main()
