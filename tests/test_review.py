"""Regression cases for circuit interfaces and sharing immutable graph records."""

import unittest

from quantum_circuits import CCZ, CZ, H, Wire, S, gate, seq


class GraphReviewTests(unittest.TestCase):
    def test_recipe_interfaces_follow_argument_order(self):
        from examples.basic import cnot, toffoli
        a, b, target = map(Wire, ('z', 'a', 'middle'))
        self.assertEqual(cnot(a, target).wires, (a, target))
        self.assertEqual(toffoli(a, b, target).wires, (a, b, target))

    def test_declared_boundary_has_an_order(self):
        wires = tuple(map(Wire, 'cba'))
        self.assertEqual(seq(wires=iter(wires)).wires, wires)
        for unordered in (set(wires), frozenset(wires)):
            with self.assertRaises(TypeError):
                seq(wires=unordered)

    def test_appending_preserves_prefix_and_fuses_at_the_boundary(self):
        a, b, c = wires = tuple(map(Wire, 'abc'))
        first = seq(CZ(a, b), gate(H, a), wires=wires)
        both = seq(first, gate(S, a), CCZ(a, b, c))
        self.assertIs(first.vertices[0], both.vertices[0])
        self.assertEqual(both, seq(CZ(a, b), gate(H, a), gate(S, a),
                                   CCZ(a, b, c), wires=wires))
        # An operator before the first vertex must still be attached to its input.
        before = seq(gate(S, a), first, wires=wires)
        self.assertEqual(before.vertices[0].inputs[0].op, S)

    def test_sparse_erasure_shares_prefix_and_reindexes_suffix(self):
        a, b, c, d = wires = tuple(map(Wire, 'abcd'))
        prefix, pair = CZ(a, b), CZ(c, d)
        suffix = (CCZ(a, b, c), CZ(b, c))
        first = seq(prefix, pair, wires=wires)
        result = seq(first, pair, *suffix)
        self.assertIs(result.vertices[0], first.vertices[0])
        self.assertEqual(result, seq(prefix, *suffix, wires=wires))
