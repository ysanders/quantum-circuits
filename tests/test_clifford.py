"""Check exact Clifford values against independent conventional matrices."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import random
import subprocess
import sys
import unittest

from quantum_circuits._clifford_tables import FRAME_LABELS
from quantum_circuits.clifford import Clif, H, I, S, X, Y, Z, clifford
from tests.reference import (
    FRAMES, PAULI_X, PAULI_Z, Matrix, adjoint, clifford_matrix, matrix_product,
)


class CliffordTests(unittest.TestCase):
    def assertMatrixClose(self, actual: Matrix, expected: Matrix) -> None:
        error = max(abs(left - right) for left, right in zip(actual, expected))
        self.assertLess(error, 1e-12)

    def test_frame_enumeration(self) -> None:
        expected_labels = (
            'I', 'X', 'Y', 'Z', 'H', 'XH', 'YH', 'ZH',
            'S', 'XS', 'YS', 'ZS', 'HS', 'XHS', 'YHS', 'ZHS',
            'SH', 'XSH', 'YSH', 'ZSH', 'HSH', 'XHSH', 'YHSH', 'ZHSH',
        )
        self.assertEqual(FRAME_LABELS, expected_labels)
        for frame, label in enumerate(FRAME_LABELS):
            # Labels use matrix order; the word parser uses execution order.
            execution_word = label[::-1]
            self.assertEqual(clifford(execution_word), Clif(frame))
        named_frames = (I.frame, X.frame, Y.frame, Z.frame, H.frame, S.frame)
        self.assertEqual(named_frames, (0, 1, 2, 3, 4, 8))

    def test_read_only_properties_and_repr(self) -> None:
        value = Clif(23, 11)
        self.assertEqual((value.rep, value.pauli, value.phase), (5, 3, 3))
        self.assertEqual(repr(value), 'Clif(phase=3, rep=5, pauli=3)')
        with self.assertRaises(FrozenInstanceError):
            value.frame = 0
        self.assertFalse(hasattr(value, '__dict__'))

    def test_canonical_phase_and_hash(self) -> None:
        for phase in range(-24, 25):
            value = Clif(7, phase)
            reduced = Clif(7, phase % 8)
            self.assertEqual(value, reduced)
            self.assertEqual(hash(value), hash(reduced))
        self.assertEqual(hash(clifford('HXH')), hash(Z))
        values = {
            Clif(frame, phase)
            for frame in range(24)
            for phase in range(8)
        }
        self.assertEqual(len(values), 192)

    def test_validation(self) -> None:
        for frame in (-1, 24, 100):
            with self.assertRaises(ValueError):
                Clif(frame)
        invalid_fields = ((True, 0), (0, False), (1.0, 0), (0, 0.5), ('1', 0))
        for frame, phase in invalid_fields:
            with self.assertRaises(TypeError):
                Clif(frame, phase)

    def test_word_execution_order(self) -> None:
        self.assertEqual(clifford(), I)
        self.assertEqual(clifford(''), I)
        self.assertEqual(clifford(' H\nS '), S @ H)
        self.assertEqual(clifford('H', S), S @ H)
        self.assertEqual(clifford('HS').frame, 16)
        self.assertEqual(clifford('SH').frame, 12)
        self.assertEqual(clifford('XZ'), Clif(2, 2))
        self.assertEqual(clifford('ZX'), Clif(2, 6))
        for word in ('T', 'h', 'H!'):
            with self.assertRaises(ValueError):
                clifford(word)
        for value in (None, 3, ['H']):
            with self.assertRaises(TypeError):
                clifford(value)
        with self.assertRaises(TypeError):
            Clif.from_word(None)

    def test_named_relations_and_phases(self) -> None:
        self.assertEqual(H @ H, I)
        self.assertEqual(S @ S, Z)
        self.assertEqual(H @ X @ H, Z)
        self.assertEqual(S.inverse(), Clif(11))
        self.assertEqual(H @ S @ H @ S @ H @ S, Clif(0, 1))
        self.assertFalse(Clif(0, 1).is_identity)
        self.assertTrue(Clif(0, 8).is_identity)
        self.assertEqual(X @ Z, Clif(2, 6))

    def test_all_36864_products_against_independent_matrices(self) -> None:
        values = [
            Clif(frame, phase)
            for frame in range(24)
            for phase in range(8)
        ]
        matrices = {value: clifford_matrix(value) for value in values}
        for left in values:
            for right in values:
                actual = matrices[left @ right]
                expected = matrix_product(matrices[left], matrices[right])
                error = max(abs(a - b) for a, b in zip(actual, expected))
                self.assertLess(error, 1e-12, (left, right))

    def test_all_inverses_against_matrices(self) -> None:
        for frame in range(24):
            for phase in range(8):
                value = Clif(frame, phase)
                inverse = value.inverse()
                self.assertEqual(value @ inverse, I)
                self.assertEqual(inverse @ value, I)
                self.assertEqual(inverse.inverse(), value)
                expected = adjoint(clifford_matrix(value))
                self.assertMatrixClose(clifford_matrix(inverse), expected)

    def test_associativity_on_all_frame_triples(self) -> None:
        frames = [Clif(frame) for frame in range(24)]
        for first in frames:
            for second in frames:
                for third in frames:
                    left_grouped = (first @ second) @ third
                    right_grouped = first @ (second @ third)
                    self.assertEqual(left_grouped, right_grouped)

    def test_distinct_pauli_actions(self) -> None:
        def rounded_entries(matrix: Matrix) -> tuple[tuple[float, float], ...]:
            return tuple(
                (round(complex(entry).real, 10), round(complex(entry).imag, 10))
                for entry in matrix
            )

        actions = set()
        for frame in FRAMES:
            inverse = adjoint(frame)
            image_x = matrix_product(matrix_product(frame, PAULI_X), inverse)
            image_z = matrix_product(matrix_product(frame, PAULI_Z), inverse)
            actions.add((rounded_entries(image_x), rounded_entries(image_z)))
        self.assertEqual(len(actions), 24)

    def test_long_words_against_independent_matrices(self) -> None:
        rng = random.Random(291)
        named = {
            name: clifford_matrix(value)
            for name, value in zip('IXYZHS', (I, X, Y, Z, H, S))
        }
        for _ in range(50):
            word = ''.join(rng.choices('IXYZHS', k=200))
            expected = clifford_matrix(I)
            for letter in word:
                expected = matrix_product(named[letter], expected)
            self.assertMatrixClose(clifford_matrix(clifford(word)), expected)

    def test_unsupported_matmul(self) -> None:
        self.assertIs(H.__matmul__(object()), NotImplemented)
        with self.assertRaises(TypeError):
            H @ 2

    def test_factory_results_share_values(self) -> None:
        self.assertIs(H @ H, I)
        self.assertIs(H.inverse(), H)
        self.assertIs(clifford('S'), S)

    def test_exact_table_regeneration(self) -> None:
        root = Path(__file__).resolve().parents[1]
        generator = root / 'tools' / 'generate_clifford_tables.py'
        result = subprocess.run(
            [sys.executable, str(generator), '--check'],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn('match exact regeneration', result.stdout)


if __name__ == '__main__':
    unittest.main()
