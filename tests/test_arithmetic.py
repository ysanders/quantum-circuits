"""Check arithmetic recipes as full, phase-preserving basis permutations."""

import unittest

from quantum_circuits import Wire, seq
from quantum_circuits.arithmetic import cuccaro_add, maj, uma
from tests.reference import apply, leaves


class ArithmeticTests(unittest.TestCase):
    def assert_basis_map(self, body, expected):
        operations = tuple(leaves(body))
        for initial in range(1 << len(body.wires)):
            with self.subTest(initial=initial):
                actual = apply(operations, body.wires, initial)
                target = expected(initial)
                # A phase error is a failure even if the output bits are right.
                self.assertLess(max(abs(value - (index == target))
                                    for index, value in enumerate(actual)), 1e-12)

    def test_maj_and_uma(self):
        a, b, carry = wires = tuple(map(Wire, ('z', 'a', 'm')))

        def majority(initial):
            av, bv, cv = (initial >> i & 1 for i in range(3))
            return ((av & bv) ^ (av & cv) ^ (bv & cv)
                    | (bv ^ av) << 1 | (cv ^ av) << 2)

        def sum_bit(initial):
            av, bv, cv = (initial >> i & 1 for i in range(3))
            return av | (av ^ bv ^ cv) << 1 | cv << 2

        self.assert_basis_map(maj(a, b, carry), majority)
        self.assert_basis_map(seq(maj(a, b, carry), uma(a, b, carry), wires=wires), sum_bit)

    def test_addition_on_every_basis_state_through_three_bits(self):
        for width in range(1, 4):
            a = tuple(Wire(f'z{i}') for i in range(width))
            b = tuple(Wire(f'a{i}') for i in range(width))
            carry, overflow = Wire('carry'), Wire('overflow')
            mask = (1 << width) - 1
            for output in (None, overflow):
                with self.subTest(width=width, overflow=output):
                    body = cuccaro_add(a, b, carry, overflow=output)
                    self.assertEqual(body.wires, (*a, *b, carry) +
                                     (() if output is None else (output,)))

                    def expected(initial):
                        av = initial & mask
                        bv = initial >> width & mask
                        cv = initial >> (2 * width) & 1
                        total = av + bv + cv
                        result = av | (total & mask) << width | cv << (2 * width)
                        if output is not None:
                            ov = initial >> (2 * width + 1) & 1
                            result |= (ov ^ (total >> width)) << (2 * width + 1)
                        return result

                    self.assert_basis_map(body, expected)

    def test_register_contract(self):
        a, b, carry, overflow = map(Wire, ('a', 'b', 'carry', 'overflow'))
        self.assertEqual(cuccaro_add([a], [b], carry), cuccaro_add((a,), (b,), carry))
        for first, second in (((), ()), ((a,), ()), ((a,), (b, overflow))):
            with self.assertRaises(ValueError):
                cuccaro_add(first, second, carry)
        for first in ({a}, iter((a,)), (object(),)):
            with self.assertRaises(TypeError):
                cuccaro_add(first, (b,), carry)
        for first, second, incoming, outgoing in (
            ((a,), (Wire('a'),), carry, None),
            ((a, a), (b, overflow), carry, None),
            ((a,), (b,), a, None),
            ((a,), (b,), carry, b),
            ((a,), (b,), carry, carry),
        ):
            with self.assertRaises(ValueError):
                cuccaro_add(first, second, incoming, overflow=outgoing)
        for incoming, outgoing in ((None, None), (carry, 'overflow')):
            with self.assertRaises(TypeError):
                cuccaro_add((a,), (b,), incoming, overflow=outgoing)
