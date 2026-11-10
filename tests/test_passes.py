import random
import unittest

from quantum_circuits import Apply, CCZ, CZ, H, S, T, Wire, Z, canonical_order, gate, op, seq
from tests.reference import apply, evaluate


def toffoli(a, b, target):
    return seq(Apply(H, target), CCZ(a, b, target), Apply(H, target))


def random_raw(rng, wires, count):
    raw = []
    for _ in range(count):
        choice = rng.randrange(6)
        if choice == 0:
            word = ''.join(rng.choices('HST', k=rng.randrange(1, 4)))
            raw.append(gate(op(word, phase=rng.randrange(8)), rng.choice(wires)))
        elif choice < 4:
            raw.append(CZ(*rng.sample(wires, 2)))
        else:
            raw.append(CCZ(*rng.sample(wires, 3)))
    return raw


def commute(first, second):
    """Whether two adjacent primitives may be exchanged without changing the circuit."""
    both_interactions = not isinstance(first, Apply) and not isinstance(second, Apply)
    return both_interactions or not first.qubits & second.qubits


def variant(rng, raw, wires):
    """An equal circuit: exchange commuting neighbours, insert and remove equal pairs."""
    out = list(raw)
    for _ in range(4 * len(out) + 8):
        move = rng.randrange(8)
        if move == 0:
            size = rng.choice((2, 3))
            pair = (CZ if size == 2 else CCZ)(*rng.sample(wires, size))
            at = rng.randrange(len(out) + 1)
            out[at:at] = [pair, pair]
        elif len(out) >= 2:
            at = rng.randrange(len(out) - 1)
            first, second = out[at], out[at + 1]
            if move == 1 and first == second and not isinstance(first, Apply):
                del out[at:at + 2]
            elif commute(first, second):
                out[at], out[at + 1] = second, first
    return out


class CanonicalOrderTests(unittest.TestCase):
    def setUp(self):
        self.wires = tuple(map(Wire, 'abcd'))
        self.a, self.b, self.c, self.d = self.wires

    def test_pair_separated_by_a_commuting_interaction(self):
        a, b, c = self.a, self.b, self.c
        body = seq(CZ(a, b), CZ(b, c), CZ(a, b))
        self.assertEqual(len(body.vertices), 3)
        self.assertEqual(canonical_order(body), seq(CZ(b, c), wires=(a, b, c)))
        body = seq(CCZ(a, b, c), CZ(a, c), CZ(b, c), CCZ(a, b, c), CZ(a, c))
        self.assertEqual(canonical_order(body), seq(CZ(b, c), wires=(a, b, c)))

    def test_written_order_of_commuting_interactions_does_not_matter(self):
        a, b, c, d = self.wires
        parts = (CZ(c, d), CZ(a, b), CCZ(b, c, d), CZ(a, d))
        results = set()
        rng = random.Random(5)
        for _ in range(24):
            order = list(parts)
            rng.shuffle(order)
            results.add(canonical_order(seq(*order, wires=self.wires)))
        self.assertEqual(len(results), 1)
        kinds = [(v.kind, tuple(e.wire.name for e in v.inputs)) for v in results.pop().vertices]
        self.assertEqual(kinds, [('CZ', ('a', 'b')), ('CZ', ('a', 'd')),
                                 ('CCZ', ('b', 'c', 'd')), ('CZ', ('c', 'd'))])

    def test_toffolis_sharing_controls(self):
        a, b, c, d = self.wires
        body = seq(toffoli(a, b, c), toffoli(a, b, d), toffoli(a, b, c), wires=self.wires)
        self.assertEqual(len(body.vertices), 3)
        self.assertEqual(canonical_order(body), seq(toffoli(a, b, d), wires=self.wires))

    def test_a_nonidentity_label_fixes_the_order(self):
        a, b, c = self.a, self.b, self.c
        for label in (H, T, S, Z):
            body = seq(CZ(a, b), gate(label, a), CZ(a, b), wires=(a, b, c))
            self.assertEqual(canonical_order(body), body)
            # The same label on a wire the pair does not share is no obstacle.
            body = seq(CZ(a, b), gate(label, c), CZ(b, c), CZ(a, b))
            self.assertEqual(len(canonical_order(body).vertices), 1)

    def test_cancellation_that_joins_two_runs(self):
        a, b, c, d = self.wires
        body = seq(CZ(a, b), gate(H, a), CZ(a, c), CZ(c, d), CZ(a, c), gate(H, a),
                   CZ(b, d), CZ(a, b), wires=self.wires)
        self.assertEqual(len(body.vertices), 6)
        expected = canonical_order(seq(CZ(c, d), CZ(b, d), wires=self.wires))
        self.assertEqual(canonical_order(body), expected)
        self.assertEqual(len(expected.vertices), 2)

    def test_interface_phase_and_fixed_point(self):
        a, b, c, d = self.wires
        order = (d, b, a, c)
        body = seq(CZ(c, d), gate(op('H', phase=3), b), CZ(a, b), wires=order, phase=2)
        result = canonical_order(body)
        self.assertEqual(result.wires, order)
        self.assertEqual(result.phase, 5)
        self.assertEqual(canonical_order(result), result)
        self.assertEqual(canonical_order(seq()), seq())
        self.assertEqual(canonical_order(seq(wires=order, phase=1)), seq(wires=order, phase=1))
        for invalid in (None, CZ(a, b), [body]):
            with self.assertRaises(TypeError):
                canonical_order(invalid)

    def test_equal_circuits_reach_the_same_graph(self):
        rng = random.Random(1110)
        for _ in range(300):
            raw = random_raw(rng, self.wires, rng.randrange(25))
            expected = canonical_order(seq(*raw, wires=self.wires))
            self.assertEqual(canonical_order(expected), expected)
            for _ in range(4):
                other = variant(rng, raw, self.wires)
                self.assertEqual(canonical_order(seq(*other, wires=self.wires)), expected)
            cut = rng.randrange(len(raw) + 1)
            halves = seq(canonical_order(seq(*raw[:cut])), canonical_order(seq(*raw[cut:])),
                         wires=self.wires)
            self.assertEqual(canonical_order(halves), expected)

    def test_the_pass_preserves_complete_matrices(self):
        rng = random.Random(1111)
        wires = self.wires
        for _ in range(60):
            raw = random_raw(rng, wires, rng.randrange(30))
            body = seq(*raw, wires=wires)
            result = canonical_order(body)
            self.assertLessEqual(len(result.vertices), len(body.vertices))
            for basis in range(16):
                expected = apply(raw, wires, basis)
                actual = evaluate(result, wires, basis)
                self.assertLess(max(abs(x - y) for x, y in zip(actual, expected)), 1e-12)

    def test_inverse_commutes_with_the_pass(self):
        rng = random.Random(1112)
        for _ in range(100):
            body = seq(*random_raw(rng, self.wires, 20), wires=self.wires)
            self.assertEqual(canonical_order(canonical_order(body).inverse()),
                             canonical_order(body.inverse()))


if __name__ == '__main__':
    unittest.main()
