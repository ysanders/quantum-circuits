from dataclasses import FrozenInstanceError
import random
import subprocess
import sys
from pathlib import Path
import unittest

from quantum_circuits.clifford import H, I, S, X, Y, Z, Clif, clifford
from quantum_circuits._clifford_tables import FRAME_LABELS
from tests.reference import FRAMES, PAULI_X, PAULI_Z, dagger, matrix, mm


class CliffordTests(unittest.TestCase):
    def test_frame_enumeration(self):
        self.assertEqual(FRAME_LABELS, (
            'I', 'X', 'Y', 'Z', 'H', 'XH', 'YH', 'ZH',
            'S', 'XS', 'YS', 'ZS', 'HS', 'XHS', 'YHS', 'ZHS',
            'SH', 'XSH', 'YSH', 'ZSH', 'HSH', 'XHSH', 'YHSH', 'ZHSH',
        ))
        for frame, label in enumerate(FRAME_LABELS):
            # Labels are matrix order, whereas the parser is execution order.
            self.assertEqual(clifford(label[::-1]), Clif(frame))
        self.assertEqual((I.frame, X.frame, Y.frame, Z.frame, H.frame, S.frame), (0, 1, 2, 3, 4, 8))

    def test_read_only_properties_and_repr(self):
        c = Clif(23, 11)
        self.assertEqual((c.rep, c.pauli, c.phase), (5, 3, 3))
        self.assertEqual(repr(c), 'Clif(phase=3, rep=5, pauli=3)')
        with self.assertRaises(FrozenInstanceError):
            c.frame = 0
        self.assertFalse(hasattr(c, '__dict__'))

    def test_canonical_phase_and_hash(self):
        for phase in range(-24, 25):
            a = Clif(7, phase)
            b = Clif(7, phase % 8)
            self.assertEqual(a, b)
            self.assertEqual(hash(a), hash(b))
        self.assertEqual(hash(clifford('HXH')), hash(Z))
        self.assertEqual(len({Clif(f, k) for f in range(24) for k in range(8)}), 192)

    def test_validation(self):
        for frame in (-1, 24, 100):
            with self.assertRaises(ValueError):
                Clif(frame)
        for frame, phase in ((True, 0), (0, False), (1.0, 0), (0, 0.5), ('1', 0)):
            with self.assertRaises(TypeError):
                Clif(frame, phase)

    def test_word_execution_order(self):
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

    def test_named_relations_and_phases(self):
        self.assertEqual(H @ H, I)
        self.assertEqual(S @ S, Z)
        self.assertEqual(H @ X @ H, Z)
        self.assertEqual(S.inverse(), Clif(11))
        self.assertEqual(H @ S @ H @ S @ H @ S, Clif(0, 1))
        self.assertFalse(Clif(0, 1).is_identity)
        self.assertTrue(Clif(0, 8).is_identity)
        self.assertEqual(X @ Z, Clif(2, 6))

    def test_all_36864_products_against_independent_matrices(self):
        values = [Clif(f, k) for f in range(24) for k in range(8)]
        matrices = {c: matrix(c) for c in values}
        for a in values:
            for b in values:
                actual = matrices[a @ b]
                expected = mm(matrices[a], matrices[b])
                error = max(abs(x - y) for x, y in zip(actual, expected))
                self.assertLess(error, 1e-12, (a, b))

    def test_all_inverses_against_matrices(self):
        for frame in range(24):
            for phase in range(8):
                c = Clif(frame, phase)
                inverse = c.inverse()
                self.assertEqual(c @ inverse, I)
                self.assertEqual(inverse @ c, I)
                self.assertEqual(inverse.inverse(), c)
                self.assertLess(max(abs(a - b) for a, b in zip(matrix(inverse), dagger(matrix(c)))), 1e-12)

    def test_associativity_on_all_frame_triples(self):
        frames = [Clif(f) for f in range(24)]
        for a in frames:
            for b in frames:
                for c in frames:
                    self.assertEqual((a @ b) @ c, a @ (b @ c))

    def test_distinct_pauli_actions(self):
        def rounded(m):
            return tuple((round(complex(x).real, 10), round(complex(x).imag, 10)) for x in m)
        actions = {
            (rounded(mm(mm(c, PAULI_X), dagger(c))), rounded(mm(mm(c, PAULI_Z), dagger(c))))
            for c in FRAMES
        }
        self.assertEqual(len(actions), 24)

    def test_long_words_against_independent_matrices(self):
        rng = random.Random(291)
        named = {name: matrix(c) for name, c in zip('IXYZHS', (I, X, Y, Z, H, S))}
        for _ in range(50):
            word = ''.join(rng.choices('IXYZHS', k=200))
            expected = matrix(I)
            for name in word:
                expected = mm(named[name], expected)
            self.assertLess(max(abs(a - b) for a, b in zip(matrix(clifford(word)), expected)), 1e-12)

    def test_unsupported_matmul(self):
        self.assertIs(H.__matmul__(object()), NotImplemented)
        with self.assertRaises(TypeError):
            H @ 2

    def test_factory_results_share_values(self):
        self.assertIs(H @ H, I)
        self.assertIs(H.inverse(), H)
        self.assertIs(clifford('S'), S)

    def test_exact_table_regeneration(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / 'tools/generate_clifford_tables.py'), '--check'],
            capture_output=True, text=True, check=True,
        )
        self.assertIn('match exact regeneration', result.stdout)


if __name__ == '__main__':
    unittest.main()
