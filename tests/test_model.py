from dataclasses import FrozenInstanceError
from itertools import permutations
import random
import unittest

from quantum_circuits import (
    CCZGate, CZGate, Gate, H, I, Qubit, S, Seq, SingleQubitClifford,
    T, X, Y, Z, op, gate, seq,
)
from tests.reference import apply, leaves


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.t = map(Qubit, ('a', 'b', 't'))

    def test_named_qubit_identity_hash_and_repr(self):
        self.assertEqual(self.a, Qubit('a'))
        self.assertEqual(hash(self.a), hash(Qubit('a')))
        self.assertNotEqual(self.a, self.b)
        for name in ('a', 'a\nb', "q'0", 'q"1', 'α'):
            self.assertEqual(repr(Qubit(name)), f'Qubit({name!r})')
        with self.assertRaises(TypeError):
            Qubit(4)

    def test_immutable_values(self):
        values = (
            (self.a, 'name', 'other'),
            (Gate(H, self.a), 'op', X),
            (gate(T, self.a), 'targ', self.b),
            (CZGate(self.a, self.b), 'a', self.t),
            (CCZGate(self.a, self.b, self.t), 'a', self.t),
            (seq(Gate(H, self.a), Gate(S, self.b)), 'parts', ()),
        )
        for value, field, new in values:
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, field, new)
            hash(value)

    def test_gate_repr_and_qubits(self):
        c = Gate(H, self.a)
        self.assertEqual(repr(c), "Gate(op=SingleQubitOperator(phase=0, rep=1, pauli=0, axes=''), targ=Qubit('a'))")
        self.assertEqual(c.qubits, frozenset((self.a,)))

    def test_symmetric_gate_operands(self):
        cz = CZGate(self.a, self.b)
        self.assertEqual(cz, CZGate(self.b, self.a))
        self.assertEqual(hash(cz), hash(CZGate(self.b, self.a)))
        expected = CCZGate(self.a, self.b, self.t)
        for wires in permutations((self.a, self.b, self.t)):
            self.assertEqual(CCZGate(*wires), expected)
            self.assertEqual(hash(CCZGate(*wires)), hash(expected))
        self.assertEqual(expected.qubits, frozenset((self.a, self.b, self.t)))
        self.assertEqual(gate(T, self.t).qubits, frozenset((self.t,)))

    def test_invalid_gate_operands(self):
        for make in (
            lambda: Gate('H', self.a), lambda: Gate(H, 'a'),
            lambda: gate(T, 'a'), lambda: CZGate(self.a, 'b'),
        ):
            with self.assertRaises(TypeError):
                make()
        for make in (
            lambda: CZGate(self.a, Qubit('a')),
            lambda: CCZGate(self.a, self.b, self.a),
        ):
            with self.assertRaises(ValueError):
                make()

    def test_empty_and_singleton(self):
        self.assertEqual(seq(), Seq(()))
        self.assertEqual(seq().qubits, frozenset())
        c = Gate(H, self.a)
        self.assertIs(seq(c), c)
        self.assertIs(seq(seq(), c, seq()), c)

    def test_same_target_fuses_in_execution_order(self):
        self.assertEqual(seq(Gate(H, self.t), Gate(S, self.t)), Gate(S @ H, self.t))
        self.assertNotEqual(S @ H, H @ S)
        self.assertEqual(seq(Gate(H, self.t), Gate(X, self.t), Gate(H, self.t)), Gate(Z, self.t))

    def test_t_runs_and_word_constructor(self):
        self.assertEqual(gate('HTH', self.t), gate(H @ T @ H, self.t))
        self.assertEqual(seq(gate(T, self.t), gate(T, self.t)), gate(S, self.t))
        self.assertEqual(seq(*(gate(x, self.t) for x in 'HTH')), gate('HTH', self.t))
        self.assertEqual(seq(*(gate(T, self.t) for _ in range(8))), seq())
        with self.assertRaises(ValueError):
            Seq((gate(T, self.t), gate(T, self.t)))
        with self.assertRaises(TypeError):
            gate(SingleQubitClifford(0), self.t)

    def test_long_run_and_cancellations_exposing_prior_runs(self):
        raw = [gate(x, self.t) for x in 'HT' * 10000]
        self.assertEqual(seq(*raw), gate('HT' * 10000, self.t))
        body = seq(
            gate(T, self.t), gate(H, self.a), gate(S, self.b),
            gate(S.inverse(), self.b), gate(H, self.a), gate(T, self.t),
        )
        self.assertEqual(body, gate(S, self.t))

    def test_different_targets_retain_order(self):
        a, b = Gate(H, self.a), Gate(S, self.b)
        result = seq(a, b)
        self.assertEqual(result.parts, (a, b))
        self.assertNotEqual(seq(a, b), seq(b, a))
        self.assertEqual(result.qubits, frozenset((self.a, self.b)))

    def test_nested_sequences_flatten_and_expose_fusion(self):
        result = seq(
            seq(Gate(X, self.t), Gate(H, self.a)),
            seq(Gate(H, self.a), Gate(X, self.t)),
        )
        self.assertEqual(result, seq())
        a, b, c = gate(T, self.a), gate(T, self.b), gate(T, self.t)
        self.assertEqual(seq(seq(a, b), c).parts, (a, b, c))

    def test_identity_and_phase_only_operations(self):
        self.assertEqual(seq(Gate(I, self.a)), seq())
        self.assertEqual(seq(Gate(H, self.a), Gate(H, self.a)).qubits, frozenset())
        phase = Gate(op(phase=1), self.a)
        self.assertEqual(seq(phase), phase)
        self.assertEqual(seq(phase).qubits, frozenset((self.a,)))
        result = seq(*(Gate(op, self.a) for op in (S, H, S, H, S, H)))
        self.assertEqual(result, phase)
        self.assertEqual(seq(phase, Gate(op(phase=7), self.a)), seq())

    def test_entangling_boundaries(self):
        for boundary in (CZGate(self.a, self.t), CCZGate(self.a, self.b, self.t)):
            h = Gate(H, self.t)
            result = seq(h, boundary, h)
            self.assertEqual(result.parts, (h, boundary, h))

    def test_normalised_sequence_construction_is_enforced(self):
        h = Gate(H, self.a)
        for parts in ((h,), (h, h), (Gate(I, self.a), gate(T, self.b))):
            with self.assertRaises(ValueError):
                Seq(parts)
        for parts in ([], (seq(), gate(T, self.a)), ('H', 'S')):
            with self.assertRaises(TypeError):
                Seq(parts)
        for invalid in (None, 'H', [h]):
            with self.assertRaises(TypeError):
                seq(invalid)

    def test_equivalent_normalised_sequences_hash_equally(self):
        a = seq(Gate(op('HXH'), self.a), gate(T, self.b))
        b = seq(Gate(Z, Qubit('a')), gate(T, Qubit('b')))
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_random_normalisation_preserves_complete_three_qubit_matrices(self):
        rng = random.Random(812)
        wires = (self.a, self.b, self.t)
        for _ in range(200):
            raw = []
            for _ in range(rng.randrange(30)):
                choice = rng.randrange(6)
                if choice < 3:
                    raw.append(Gate(op(SingleQubitClifford(rng.randrange(24), rng.randrange(8)), ''.join(rng.choices('HST', k=8))), rng.choice(wires)))
                elif choice == 3:
                    raw.append(gate(T, rng.choice(wires)))
                elif choice == 4:
                    raw.append(CZGate(*rng.sample(wires, 2)))
                else:
                    raw.append(CCZGate(*rng.sample(wires, 3)))
            result = seq(*raw)
            self.assertEqual(seq(result), result)
            flat = tuple(leaves(result))
            for basis in range(8):
                expected = apply(raw, wires, basis)
                actual = apply(flat, wires, basis)
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-12)

    def test_cnot_and_toffoli_recipes(self):
        for controls in ((self.a,), (self.a, self.b)):
            wires = (*controls, self.t)
            central = CZGate(*wires) if len(controls) == 1 else CCZGate(*wires)
            circuit = seq(Gate(H, self.t), central, Gate(H, self.t))
            for basis in range(1 << len(wires)):
                mask = (1 << len(controls)) - 1
                target = basis ^ (1 << len(controls)) if basis & mask == mask else basis
                expected = [0j] * (1 << len(wires))
                expected[target] = 1
                actual = apply(tuple(leaves(circuit)), wires, basis)
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-12)

    def test_t_adjoint_recipe(self):
        circuit = seq(Gate(S.inverse(), self.t), gate(T, self.t))
        from tests.reference import OMEGA
        self.assertAlmostEqual(apply(tuple(leaves(circuit)), (self.t,), 1)[1], OMEGA.conjugate())


if __name__ == '__main__':
    unittest.main()
