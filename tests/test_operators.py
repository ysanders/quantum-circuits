"""Check canonical Clifford+T operators, retaining exact scalar phases."""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from itertools import product
import random
import unittest

from quantum_circuits import Clif, H, I, S, T, X, Y, Z, WireOp, op
from quantum_circuits._clifford_tables import CLIFFORD_WORDS
from tests import exact_reference as exact
from tests.reference import Matrix, adjoint, matrix_product, operator_matrix, word_matrix


def canonical_axes(max_length: int) -> Iterator[str]:
    """Enumerate alternating axis strings by increasing length."""
    yield ''
    level = ['']
    for _ in range(max_length):
        next_level = []
        for prefix in level:
            for axis in 'xyz':
                if not prefix.endswith(axis):
                    next_level.append(prefix + axis)
        level = next_level
        yield from level


class OperatorTests(unittest.TestCase):
    def assertMatrixClose(self, actual: Matrix, expected: Matrix) -> None:
        error = max(abs(left - right) for left, right in zip(actual, expected))
        self.assertLess(error, 1e-11)

    def test_agreed_interface(self) -> None:
        self.assertEqual(op(), I)
        self.assertEqual(op(''), I)
        self.assertEqual(op(' \n\t'), I)
        self.assertEqual(op('HS'), S @ H)
        self.assertEqual(op(' H\nS '), op(H, S))
        self.assertEqual(op('HS', T, 'SH'), op('HSTSH'))
        self.assertEqual(op(Clif.from_word('HS')), op('HS'))
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

    def test_validation_and_operator_types(self) -> None:
        for axes in ('xx', 'xyzz', 'X', ' x', 'x y', 'T', 'a'):
            with self.assertRaises(ValueError):
                WireOp(I.initial, axes)
        invalid_fields = ((I, ''), (None, ''), (I.initial, []), (I.initial, 0))
        for initial, axes in invalid_fields:
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

    def test_repr_immutability_and_properties(self) -> None:
        self.assertEqual(repr(op('HTH')), "WireOp(initial=Clif.from_word('I'), axes='x')")
        self.assertEqual(repr(S), "WireOp(initial=Clif.from_word('S'), axes='')")
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

    def test_exact_phase_and_hashing(self) -> None:
        self.assertEqual((H @ S) ** 3, op(phase=1))
        self.assertEqual(X @ Z, op(Y, phase=6))
        for phase in range(-16, 17):
            value = op('HT', phase=phase)
            self.assertEqual(value, op('HT', phase=phase % 8))
            self.assertEqual(value, op(phase=phase) @ op('HT'))
        phased_values = {op('HT', phase=phase) for phase in range(8)}
        self.assertEqual(len(phased_values), 8)
        lookup = {op('TT'): 7}
        self.assertEqual(lookup[S], 7)
        self.assertEqual(hash(op('HTH')), hash(H @ T @ H))

    def test_scalar_factor_of_every_bounded_canonical_value(self) -> None:
        for frame in range(24):
            for axes in canonical_axes(3):
                unphased = WireOp(Clif(frame), axes)
                self.assertEqual(unphased.phase, 0)
                self.assertIs(unphased.unphased(), unphased)
                for phase in range(1, 8):
                    value = WireOp(Clif(frame, phase), axes)
                    self.assertEqual(value.phase, phase)
                    self.assertEqual(value.unphased(), unphased)
                    self.assertEqual(op(unphased, phase=phase), value)

    def test_exact_short_words(self) -> None:
        # Every H/S/T word through length six, retaining full phase.
        matrix_cache = {}
        for length in range(7):
            for letters in product('HST', repeat=length):
                word = ''.join(letters)
                value = op(word)
                if value not in matrix_cache:
                    matrix_cache[value] = exact.operator_matrix(value)
                expected = exact.word_matrix(word)
                self.assertEqual(matrix_cache[value], expected, word)
                self.assertLessEqual(value.t_count, word.count('T'))

    def test_exact_uniqueness_of_8832_canonical_values(self) -> None:
        # All 192 initial Cliffords and all canonical axis strings through
        # four T's. Independent exact matrices, not rounded matrix hashes.
        seen = set()
        axis_products = {'': exact.I}
        for axes in canonical_axes(4):
            if axes:
                # The shorter prefix was visited first; append the last gate
                # by multiplying its matrix on the left.
                last_axis = exact.AXES[axes[-1]]
                prefix_product = axis_products[axes[:-1]]
                axis_products[axes] = exact.matrix_product(last_axis, prefix_product)
            for frame in range(24):
                for phase in range(8):
                    value = WireOp(Clif(frame, phase), axes)
                    initial = exact.CLIFFORDS[8 * frame + phase]
                    matrix = exact.matrix_product(axis_products[axes], initial)
                    self.assertNotIn(matrix, seen, value)
                    seen.add(matrix)
                    self.assertEqual(op(value), value)
        self.assertEqual(len(seen), 8832)

    def test_t_count_meets_an_independent_lower_bound(self) -> None:
        # exact.t_count_lower_bound(U) holds for every H/S/T word denoting U.
        # Equality therefore shows that t_count is minimal for each value
        # checked, without appeal to the cited normal-form theorem.
        rng = random.Random(712)
        for axes in canonical_axes(6):
            value = WireOp(Clif(rng.randrange(24), rng.randrange(8)), axes)
            bound = exact.t_count_lower_bound(exact.operator_matrix(value))
            self.assertEqual(bound, value.t_count, value)

    def test_all_bounded_inverses_and_lowerings(self) -> None:
        namespace = {'WireOp': WireOp, 'Clif': Clif}
        for axes in canonical_axes(3):
            for frame in range(24):
                for phase in range(8):
                    value = WireOp(Clif(frame, phase), axes)
                    inverse = value.inverse()
                    self.assertEqual(inverse @ value, I)
                    self.assertEqual(value @ inverse, I)
                    self.assertEqual(inverse.inverse(), value)
                    self.assertEqual(inverse.t_count, value.t_count)
                    expected_inverse = adjoint(operator_matrix(value))
                    self.assertMatrixClose(operator_matrix(inverse), expected_inverse)

                    iterator = value.iter_gates()
                    self.assertIs(iter(iterator), iterator)
                    word = ''.join(iterator)
                    self.assertTrue(set(word) <= set('HST'))
                    self.assertEqual(word.count('T'), value.t_count)
                    self.assertEqual(op(word), value)
                    self.assertMatrixClose(word_matrix(word), operator_matrix(value))
                    # No run of H and S is longer than the table's shortest
                    # word for the same Clifford.
                    for run in word.split('T'):
                        clifford = Clif.from_word(run)
                        shortest = CLIFFORD_WORDS[8 * clifford.frame + clifford.phase]
                        self.assertEqual(len(run), len(shortest), word)

                    self.assertEqual(eval(repr(value), namespace), value)
        self.assertEqual(list(I.iter_gates()), [])

    def test_all_signed_axis_conjugations(self) -> None:
        for frame in range(24):
            initial = op(Clif(frame))
            for axis in 'xyz':
                rotation = WireOp(I.initial, axis)
                left_product = initial @ rotation
                right_product = rotation @ initial
                conjugated = initial @ rotation @ initial.inverse()
                for value in (left_product, right_product, conjugated):
                    self.assertEqual(value.t_count, 1)
                initial_matrix = operator_matrix(initial)
                rotation_matrix = operator_matrix(rotation)
                self.assertMatrixClose(
                    operator_matrix(left_product),
                    matrix_product(initial_matrix, rotation_matrix),
                )
                self.assertMatrixClose(
                    operator_matrix(right_product),
                    matrix_product(rotation_matrix, initial_matrix),
                )
        # X flips the z axis: X T X = omega T^-1, not merely T^-1.
        self.assertEqual(X @ T @ X, op(T.inverse(), phase=1))

    def test_random_words_composition_and_associativity(self) -> None:
        rng = random.Random(3401)
        for _ in range(400):
            word = ''.join(rng.choices('IXYZHST', k=rng.randrange(150)))
            first_cut, second_cut = sorted((
                rng.randrange(len(word) + 1),
                rng.randrange(len(word) + 1),
            ))
            first = op(word[:first_cut])
            middle = op(word[first_cut:second_cut])
            last = op(word[second_cut:])
            expected = op(word)
            self.assertEqual(op(first, middle, last), expected)
            self.assertEqual(last @ (middle @ first), expected)
            self.assertEqual((last @ middle) @ first, expected)
            self.assertMatrixClose(operator_matrix(expected), word_matrix(word))

    def test_integer_powers_against_matrices(self) -> None:
        for word in ('HT', 'HST', 'T', 'SH', 'SHSHSH'):
            value = op(word)
            self.assertEqual(value ** 0, I)
            for exponent in range(-7, 8):
                factor = operator_matrix(value)
                if exponent < 0:
                    factor = adjoint(factor)
                expected = operator_matrix(I)
                for _ in range(abs(exponent)):
                    expected = matrix_product(factor, expected)
                self.assertMatrixClose(operator_matrix(value ** exponent), expected)

    def test_long_word_and_inverse_without_recursion(self) -> None:
        word = 'HT' * 20000
        value = op(word)
        self.assertEqual(value.t_count, 20000)
        self.assertEqual(op(''.join(value.iter_gates())), value)
        self.assertEqual(value.inverse() @ value, I)


if __name__ == '__main__':
    unittest.main()
