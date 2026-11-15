import random
import unittest

from quantum_circuits import CCZ, CZ, H, S, T, Wire, gate, op, seq
from tests.reference import evaluate


def random_body(rng, wires):
    raw = []
    for _ in range(rng.randrange(25)):
        choice = rng.randrange(5)
        if choice < 2:
            word = ''.join(rng.choices('HST', k=rng.randrange(1, 6)))
            raw.append(gate(op(word, phase=rng.randrange(8)), rng.choice(wires)))
        elif choice < 4:
            raw.append(CZ(*rng.sample(wires, 2)))
        else:
            raw.append(CCZ(*rng.sample(wires, 3)))
    order = list(wires)
    rng.shuffle(order)
    return seq(*raw, wires=order, phase=rng.randrange(8))


class InverseTests(unittest.TestCase):
    def setUp(self):
        self.wires = tuple(map(Wire, 'abcd'))
        self.a, self.b, self.c, self.d = self.wires

    def test_small_cases(self):
        a, b, c = self.a, self.b, self.c
        self.assertEqual(seq().inverse(), seq())
        self.assertEqual(seq(wires=(b, a), phase=3).inverse(), seq(wires=(b, a), phase=5))
        self.assertEqual(seq(gate(T, a)).inverse(), seq(gate(T.inverse(), a)))
        self.assertEqual(seq(gate(H, a), gate(S, a)).inverse(), seq(gate(S.inverse(), a), gate(H, a)))
        body = seq(gate(H, c), CCZ(a, b, c), gate(T, a), CZ(a, b), gate(S, b))
        expected = seq(gate(S.inverse(), b), CZ(a, b), gate(T.inverse(), a), CCZ(a, b, c),
                       gate(H, c), wires=body.wires)
        self.assertEqual(body.inverse(), expected)

    def test_inverse_cancels_on_either_side_and_is_an_involution(self):
        rng = random.Random(41)
        for _ in range(300):
            body = random_body(rng, self.wires)
            inverse = body.inverse()
            identity = seq(wires=body.wires)
            self.assertEqual(inverse.wires, body.wires)
            self.assertEqual(seq(body, inverse), identity)
            self.assertEqual(seq(inverse, body), identity)
            self.assertEqual(inverse.inverse(), body)
            self.assertEqual(len(inverse.vertices), len(body.vertices))

    def test_inverse_of_a_composition_reverses_the_parts(self):
        rng = random.Random(42)
        for _ in range(100):
            left, right = random_body(rng, self.wires), random_body(rng, self.wires)
            both = seq(left, right, wires=self.wires)
            self.assertEqual(both.inverse(), seq(right.inverse(), left.inverse(), wires=self.wires))

    def test_inverse_matrix_is_the_conjugate_transpose(self):
        rng = random.Random(43)
        wires = self.wires[:3]
        for _ in range(40):
            body = random_body(rng, wires)
            inverse = body.inverse()
            columns = [evaluate(body, wires, k) for k in range(8)]
            for row in range(8):
                actual = evaluate(inverse, wires, row)
                for col in range(8):
                    self.assertAlmostEqual(actual[col], columns[col][row].conjugate(), places=11)


if __name__ == '__main__':
    unittest.main()
