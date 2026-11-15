"""A circuit's scalar phase is stored once, on the graph."""

import random
import unittest

from quantum_circuits import (
    CCZ, CZ, H, I, Intersection, S, Seq, T, Wire, WireSegment, gate, op, seq,
)
from tests.reference import apply, evaluate


class ScalarPhaseTests(unittest.TestCase):
    def setUp(self):
        self.wires = tuple(map(Wire, 'abc'))
        self.a, self.b, self.c = self.wires

    def test_a_scalar_has_no_position(self):
        omega = op(phase=1)
        expected = seq(wires=self.wires, phase=1)
        for wire in self.wires:
            body = seq(gate(omega, wire), wires=self.wires)
            self.assertEqual(body, expected)
            self.assertEqual(body.phase, 1)
            self.assertTrue(all(e.op is I for e in body.outputs))

    def test_a_scalar_does_not_block_a_pair(self):
        a, b, c = self.wires
        for interaction in (CZ(a, b), CCZ(a, b, c)):
            for wire in interaction.qubits:
                for k in range(1, 8):
                    body = seq(interaction, gate(op(phase=k), wire), interaction)
                    self.assertEqual(body, seq(wires=body.wires, phase=k))

    def test_labels_keep_their_operator_and_lose_their_scalar(self):
        a, b = self.a, self.b
        body = seq(gate(op('H', phase=3), a), CZ(a, b), gate(op('T', phase=6), a))
        self.assertEqual(body.phase, 1)
        self.assertEqual(body.vertices[0].inputs[0].op, H)
        self.assertEqual(body.outputs[0].op, T)
        # A product of scalar-free labels can still produce a scalar.
        word = seq(*(gate(x, a) for x in (S, H, S, H, S, H)))
        self.assertEqual(word, seq(wires=(a,), phase=1))

    def test_phases_add_under_composition(self):
        a, b = self.a, self.b
        left = seq(CZ(a, b), gate(H, a), phase=3)
        right = seq(gate(S, b), phase=7)
        self.assertEqual(seq(left, right).phase, 2)
        self.assertEqual(seq(left, right, phase=6).phase, 0)
        self.assertEqual(seq(left, phase=5), seq(CZ(a, b), gate(H, a), phase=0))
        self.assertIs(seq(left, phase=8), left)
        self.assertEqual(seq(phase=-1), Seq((), (), (), 7))

    def test_raw_construction(self):
        a, b = self.a, self.b
        self.assertEqual(Seq((a,), (), (WireSegment(a),), 11).phase, 3)
        for invalid in (True, 1.0, '1', None):
            with self.assertRaises(TypeError):
                Seq((a,), (), (WireSegment(a),), invalid)
            with self.assertRaises(TypeError):
                seq(wires=(a,), phase=invalid)
        scalar = op(phase=1)
        with self.assertRaisesRegex(ValueError, 'Seq.phase'):
            Seq((a,), (), (WireSegment(a, None, scalar),))
        vertex = Intersection('CZ', (WireSegment(a, None, op('H', phase=2)), WireSegment(b)))
        with self.assertRaisesRegex(ValueError, 'Seq.phase'):
            Seq((a, b), (vertex,), (WireSegment(a, 0), WireSegment(b, 0)))

    def test_random_circuits_keep_their_exact_scalar(self):
        rng = random.Random(77)
        for _ in range(100):
            raw = []
            for _ in range(rng.randrange(20)):
                if rng.randrange(2):
                    word = ''.join(rng.choices('HST', k=4))
                    raw.append(gate(op(word, phase=rng.randrange(8)), rng.choice(self.wires)))
                else:
                    size = rng.choice((2, 3))
                    raw.append((CZ if size == 2 else CCZ)(*rng.sample(self.wires, size)))
            k = rng.randrange(8)
            body = seq(*raw, wires=self.wires, phase=k)
            for vertex in body.vertices:
                self.assertTrue(all(e.op.phase == 0 for e in vertex.inputs))
            self.assertTrue(all(e.op.phase == 0 for e in body.outputs))
            shifted = seq(seq(*raw, wires=self.wires), phase=k)
            self.assertEqual(shifted, body)
            for basis in range(8):
                expected = apply([*raw, gate(op(phase=k), self.a)], self.wires, basis)
                actual = evaluate(body, self.wires, basis)
                self.assertLess(max(abs(x - y) for x, y in zip(actual, expected)), 1e-12)


if __name__ == '__main__':
    unittest.main()
