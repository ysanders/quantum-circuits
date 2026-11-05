from dataclasses import FrozenInstanceError
from itertools import product
import random
import unittest

from quantum_circuits import (
    H, I, S, T, X, Y, Z, Clif, WireOp, clifford, op,
)
from tests import exact_reference as exact
from tests.reference import dagger, mm, operator_matrix, word_matrix


def canonical_axes(max_length):
    yield ''
    level = ['']
    for _ in range(max_length):
        level = [prefix + a for prefix in level for a in 'xyz' if not prefix.endswith(a)]
        yield from level


class OperatorTests(unittest.TestCase):
    def assertMatrixClose(self, actual, expected):
        self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-11)

    def test_agreed_interface(self):
        self.assertEqual(op(), I)
        self.assertEqual(op(''), I)
        self.assertEqual(op(' \n\t'), I)
        self.assertEqual(op('HS'), S @ H)
        self.assertEqual(op(' H\nS '), op(H, S))
        self.assertEqual(op('HS', T, 'SH'), op('HSTSH'))
        self.assertEqual(op(clifford('HS')), op('HS'))
        self.assertEqual(op('HTH'), op(H, T, H))
        self.assertEqual(op('TT'), S)
        self.assertEqual(T @ T, S)
        self.assertEqual(T ** 8, I)
        self.assertEqual(T ** -1, T.inverse())
        self.assertEqual(op('HTH').t_count, 1)
        self.assertEqual(op('HTH').axes, 'x')
        self.assertEqual(op('SSSHTHS').axes, 'y')
        for value in (I, X, Y, Z, H, S, T, op()):
            self.assertIs(type(value), WireOp)

    def test_validation_and_operator_types(self):
        for axes in ('xx', 'xyzz', 'X', ' x', 'x y', 'T', 'a'):
            with self.assertRaises(ValueError):
                WireOp(I.initial, axes)
        for initial, axes in ((I, ''), (None, ''), (I.initial, []), (I.initial, 0)):
            with self.assertRaises(TypeError):
                WireOp(initial, axes)
        for value in (None, 1, ['H'], {'H'}, 1j):
            with self.assertRaises(TypeError):
                op(value)
            self.assertIs(H.__matmul__(value), NotImplemented)
        self.assertIs(H.__matmul__(H.initial), NotImplemented)
        for word in ('h', 'T!', 'x', 'S†'):
            with self.assertRaises(ValueError):
                op(word)
        for value in (True, 1.0, '1', None):
            with self.assertRaises(TypeError):
                op(phase=value)
            with self.assertRaises(TypeError):
                H ** value
        with self.assertRaises(TypeError):
            H @ 'H'
        with self.assertRaises(TypeError):
            pow(T, 2, 3)

    def test_repr_immutability_and_properties(self):
        self.assertEqual(repr(op('HTH')), "WireOp(phase=0, rep=0, pauli=0, axes='x')")
        self.assertEqual(repr(S), "WireOp(phase=0, rep=2, pauli=0, axes='')")
        self.assertEqual(str(T), repr(T))
        self.assertFalse(hasattr(T, '__dict__'))
        for name, value in (('axes', ''), ('initial', H.initial)):
            with self.assertRaises(FrozenInstanceError):
                setattr(T, name, value)
        self.assertTrue(I.is_identity)
        self.assertFalse(op(phase=1).is_identity)
        self.assertTrue(op(phase=1).is_clifford)
        self.assertTrue(S.is_clifford)
        self.assertFalse(T.is_clifford)
        self.assertEqual(S.t_count, 0)

    def test_exact_phase_and_hashing(self):
        self.assertEqual((H @ S) ** 3, op(phase=1))
        self.assertEqual(X @ Z, op(Y, phase=6))
        for phase in range(-16, 17):
            self.assertEqual(op('HT', phase=phase), op('HT', phase=phase % 8))
            self.assertEqual(op('HT', phase=phase), op(phase=phase) @ op('HT'))
        self.assertEqual(len({op('HT', phase=k) for k in range(8)}), 8)
        self.assertEqual({op('TT'): 7}[S], 7)
        self.assertEqual(hash(op('HTH')), hash(H @ T @ H))

    def test_exact_short_words(self):
        # Every H/S/T word through length six, retaining full phase.
        matrix_cache = {}
        for length in range(7):
            for letters in product('HST', repeat=length):
                word = ''.join(letters)
                value = op(word)
                if value not in matrix_cache:
                    matrix_cache[value] = exact.matrix(value)
                self.assertEqual(matrix_cache[value], exact.word_matrix(word), word)
                self.assertLessEqual(value.t_count, word.count('T'))

    def test_exact_uniqueness_of_8832_canonical_values(self):
        # All 192 initial Cliffords and all canonical axis strings through
        # four T's. Independent exact matrices, not rounded matrix hashes.
        seen = set()
        axis_products = {'': exact.I}
        for axes in canonical_axes(4):
            if axes:
                axis_products[axes] = exact.product(exact.AXES[axes[-1]], axis_products[axes[:-1]])
            for frame in range(24):
                for phase in range(8):
                    value = WireOp(Clif(frame, phase), axes)
                    matrix = exact.product(axis_products[axes], exact.CLIFFORDS[8 * frame + phase])
                    self.assertNotIn(matrix, seen, value)
                    seen.add(matrix)
                    self.assertEqual(op(value), value)
        self.assertEqual(len(seen), 8832)

    def test_all_bounded_inverses_and_lowerings(self):
        for axes in canonical_axes(3):
            for frame in range(24):
                for phase in range(8):
                    value = WireOp(Clif(frame, phase), axes)
                    inverse = value.inverse()
                    self.assertEqual(inverse @ value, I)
                    self.assertEqual(value @ inverse, I)
                    self.assertEqual(inverse.inverse(), value)
                    self.assertEqual(inverse.t_count, value.t_count)
                    self.assertMatrixClose(operator_matrix(inverse), dagger(operator_matrix(value)))
                    iterator = value.iter_gates()
                    self.assertIs(iter(iterator), iterator)
                    word = ''.join(iterator)
                    self.assertTrue(set(word) <= set('HST'))
                    self.assertEqual(word.count('T'), value.t_count)
                    self.assertEqual(op(word), value)
                    self.assertMatrixClose(word_matrix(word), operator_matrix(value))
        self.assertEqual(list(I.iter_gates()), [])

    def test_all_signed_axis_conjugations(self):
        for frame in range(24):
            c = op(Clif(frame))
            for axes in ('x', 'y', 'z'):
                t = WireOp(I.initial, axes)
                for value in (c @ t, t @ c, c @ t @ c.inverse()):
                    self.assertEqual(value.t_count, 1)
                self.assertMatrixClose(operator_matrix(c @ t), mm(operator_matrix(c), operator_matrix(t)))
                self.assertMatrixClose(operator_matrix(t @ c), mm(operator_matrix(t), operator_matrix(c)))
        # X flips the z axis: X T X = omega T^-1, not merely T^-1.
        self.assertEqual(X @ T @ X, op(T.inverse(), phase=1))

    def test_random_words_composition_and_associativity(self):
        rng = random.Random(3401)
        for _ in range(400):
            word = ''.join(rng.choices('IXYZHST', k=rng.randrange(150)))
            a, b = sorted((rng.randrange(len(word) + 1), rng.randrange(len(word) + 1)))
            u, v, w = map(op, (word[:a], word[a:b], word[b:]))
            expected = op(word)
            self.assertEqual(op(u, v, w), expected)
            self.assertEqual(w @ (v @ u), expected)
            self.assertEqual((w @ v) @ u, expected)
            self.assertMatrixClose(operator_matrix(expected), word_matrix(word))

    def test_integer_powers_against_matrices(self):
        for word in ('HT', 'HST', 'T', 'SH', 'SHSHSH'):
            value = op(word)
            self.assertEqual(value ** 0, I)
            for exponent in range(-7, 8):
                unit = operator_matrix(value)
                if exponent < 0:
                    unit = dagger(unit)
                expected = operator_matrix(I)
                for _ in range(abs(exponent)):
                    expected = mm(unit, expected)
                self.assertMatrixClose(operator_matrix(value ** exponent), expected)

    def test_long_word_and_inverse_without_recursion(self):
        word = 'HT' * 20000
        value = op(word)
        self.assertEqual(value.t_count, 20000)
        self.assertEqual(op(''.join(value.iter_gates())), value)
        self.assertEqual(value.inverse() @ value, I)


if __name__ == '__main__':
    unittest.main()
