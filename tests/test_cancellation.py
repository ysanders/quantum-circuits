import random
import unittest
from unittest.mock import patch

from quantum_circuits import CCZ, CZ, H, Wire, S, T, gate, op, seq
from quantum_circuits.operators import _Accumulator
from tests.reference import apply, evaluate


class CancelPairsTests(unittest.TestCase):
    def setUp(self):
        self.wires = tuple(map(Wire, 'abcd'))
        self.a, self.b, self.c, self.d = self.wires

    def test_even_and_odd_runs_of_each_kind(self):
        for interaction in (CZ(self.a, self.b), CCZ(self.a, self.b, self.c)):
            for count in range(7):
                body = seq(*([interaction] * count), wires=self.wires)
                expected = seq(*([interaction] * (count % 2)), wires=self.wires)
                self.assertEqual(body, expected)
                self.assertEqual(len(body.vertices), count % 2)

    def test_all_ports_must_match_and_have_exact_identity(self):
        a, b, c, d = self.wires
        for interaction in (CZ(a, b), CCZ(a, b, c)):
            for wire in interaction.qubits:
                for op_on_wire in (H, T):
                    body = seq(interaction, gate(op_on_wire, wire), interaction)
                    self.assertEqual(len(body.vertices), 2)
        for interactions in (
            (CZ(a, b), CZ(a, c)),
            (CZ(a, b), CCZ(a, b, c)),
            (CCZ(a, b, c), CZ(a, b)),
            (CCZ(a, b, c), CCZ(a, b, d)),
            (CZ(a, b), CZ(b, c), CZ(a, b)),
            (CCZ(a, b, c), CZ(c, d), CCZ(a, b, c)),
        ):
            body = seq(*interactions)
            self.assertEqual(len(body.vertices), len(interactions))

    def test_erase_across_disjoint_events_and_reconnect_in_order(self):
        a, b, c, d = self.wires
        pair, disjoint = CZ(a, b), CZ(c, d)
        left = (gate(H, a), gate(T, b))
        right = (gate(S, a), CCZ(a, b, c), gate(H, b))
        body = seq(*left, pair, disjoint, CZ(b, a), *right, wires=self.wires)
        self.assertEqual(body, seq(*left, disjoint, *right, wires=self.wires))
        pair3 = CCZ(c, b, a)
        body = seq(*left, pair3, gate(H, d), CCZ(a, b, c), gate(S, a), wires=self.wires)
        self.assertEqual(body, seq(*left, gate(H, d), gate(S, a), wires=self.wires))

    def test_inner_pair_exposes_outer_pair_after_edge_fusion(self):
        a, b, c, d = self.wires
        outer, inner = CZ(a, b), CCZ(a, b, c)
        body = seq(outer, gate(H, a), inner, gate(T, d), inner, gate(H, a), outer,
                   wires=self.wires)
        self.assertEqual(body, seq(gate(T, d), wires=self.wires))

    def test_join_reopens_a_label_in_a_compiled_block(self):
        a, b, c, d = self.wires
        outer, inner = CZ(a, b), CCZ(a, b, c)
        left = seq(gate(S, a), outer, gate(H, a), inner, wires=self.wires)
        right = seq(inner, gate(T, d), gate(H, a), outer, gate(H, a))
        self.assertEqual(len(left.vertices), 2)
        self.assertEqual(len(right.vertices), 2)
        self.assertEqual(seq(left, right), seq(gate(S, a), gate(T, d), gate(H, a),
                                               wires=self.wires))
        self.assertEqual(len(left.vertices), 2)

    def test_flat_and_precompiled_repeated_block(self):
        a, b, _, _ = self.wires
        u = op('HT')
        for z in (CZ(a, b), CCZ(a, b, self.c)):
            block = (gate(u, a), z, z)
            compiled = seq(*block, wires=self.wires)
            expected = seq(gate(u ** 512, a), wires=self.wires)
            self.assertEqual(seq(*(block * 512), wires=self.wires), expected)
            self.assertEqual(seq(*([compiled] * 512)), expected)

    def test_erasing_pairs_batches_the_reopened_segment(self):
        a, b, _, _ = self.wires
        cz = CZ(a, b)
        block = (gate('HT', a), cz, cz)
        n = 64
        visits = 0
        multiply = _Accumulator.right_operator

        def counted(accumulator, operand):
            nonlocal visits
            visits += operand.t_count
            multiply(accumulator, operand)

        with patch.object(_Accumulator, 'right_operator', counted):
            body = seq(*(block * n))
        self.assertEqual(body.outputs[0].op, op('HT' * n))
        # The eager implementation revisited n*(n-1)/2 axis letters here.
        self.assertLessEqual(visits, 2 * n)

    def test_random_erasure_agrees_with_full_matrices_and_reaches_fixed_point(self):
        rng = random.Random(214)
        wires = self.wires[:3]
        for _ in range(64):
            raw = []
            for _ in range(15):
                if rng.randrange(3) == 0:
                    raw.append(gate(op(''.join(rng.choices('HST', k=5)), phase=rng.randrange(8)),
                                    rng.choice(wires)))
                else:
                    size = rng.choice((2, 3))
                    interaction = (CZ if size == 2 else CCZ)(*rng.sample(wires, size))
                    raw.extend([interaction] * rng.choice((1, 2)))
            body = seq(*raw, wires=wires)
            cut = rng.randrange(len(raw) + 1)
            joined = seq(seq(*raw[:cut]), seq(*raw[cut:]), wires=wires)
            for basis in range(8):
                expected = apply(raw, wires, basis)
                actual = evaluate(body, wires, basis)
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-12)
                actual = evaluate(joined, wires, basis)
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-12)
