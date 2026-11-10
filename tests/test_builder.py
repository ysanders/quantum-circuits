import random
import unittest

from quantum_circuits import Builder, CCZ, CZ, H, S, T, Wire, gate, op, seq


def random_parts(rng, wires, count):
    parts = []
    for _ in range(count):
        choice = rng.randrange(4)
        if choice == 0:
            parts.append(gate(op(''.join(rng.choices('HST', k=3))), rng.choice(wires)))
        elif choice == 1:
            parts.append(CCZ(*rng.sample(wires, 3)))
        else:
            interaction = CZ(*rng.sample(wires, 2))
            parts.extend([interaction] * rng.choice((1, 2)))
    return parts


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.wires = tuple(map(Wire, 'abcd'))
        self.a, self.b, self.c, self.d = self.wires

    def test_add_one_part_at_a_time_agrees_with_seq(self):
        rng = random.Random(31)
        for _ in range(100):
            parts = random_parts(rng, self.wires, rng.randrange(25))
            builder = Builder(self.wires)
            for part in parts:
                self.assertIs(builder.add(part), builder)
            self.assertEqual(builder.freeze(), seq(*parts, wires=self.wires))

    def test_freeze_is_repeatable_and_the_builder_continues(self):
        rng = random.Random(32)
        for _ in range(100):
            parts = random_parts(rng, self.wires, 20)
            cut = rng.randrange(len(parts) + 1)
            builder = Builder(self.wires).add(*parts[:cut])
            first = builder.freeze()
            self.assertEqual(first, seq(*parts[:cut], wires=self.wires))
            self.assertEqual(builder.freeze(), first)
            builder.add(*parts[cut:])
            self.assertEqual(builder.freeze(), seq(*parts, wires=self.wires))
            self.assertEqual(first, seq(*parts[:cut], wires=self.wires))

    def test_pairs_cancel_across_a_freeze(self):
        a, b, c = self.a, self.b, self.c
        builder = Builder().add(gate(S, a), CZ(a, b), gate(H, a), CCZ(a, b, c))
        self.assertEqual(len(builder.freeze().vertices), 2)
        builder.add(CCZ(a, b, c), gate(H, a), CZ(a, b))
        self.assertEqual(builder.freeze(), seq(gate(S, a), wires=(a, b, c)))

    def test_interface_follows_first_appearance_or_the_declaration(self):
        a, b, c = self.a, self.b, self.c
        self.assertEqual(Builder().add(gate(H, c), CZ(b, a)).freeze().wires, (c, a, b))
        self.assertEqual(Builder((c, b, a)).freeze(), seq(wires=(c, b, a)))
        self.assertEqual(Builder(iter((c, b, a))).add(gate(T, a)).freeze().wires, (c, b, a))

    def test_invalid_use(self):
        a, b = self.a, self.b
        for unordered in ({a, b}, frozenset((a, b))):
            with self.assertRaises(TypeError):
                Builder(unordered)
        with self.assertRaises(ValueError):
            Builder((a, a))
        with self.assertRaises(ValueError):
            Builder((a,)).add(CZ(a, b))
        with self.assertRaises(ValueError):
            Builder((a,)).add(seq(wires=(b,)))
        for invalid in (None, 'H', [gate(H, a)]):
            with self.assertRaises(TypeError):
                Builder().add(invalid)


if __name__ == '__main__':
    unittest.main()
