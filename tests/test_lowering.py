"""Tests for lowering one-qubit operators to stream records."""

import itertools
import unittest

from quantum_circuits import Clif, I, S, T, WireOp, op
from quantum_circuits.circuit import lower_operator
from quantum_circuits.stream import CliffordGate, Phase, TGate
from tests import exact_reference as exact
from tools.generate_clifford_tables import matrix_product, scale


def bounded_operators():
    """Every operator with at most three T gates, in canonical form.

    That is each of the 192 Cliffords followed by each alternating axis
    string of length at most three.
    """
    axis_strings = ['']
    for length in (1, 2, 3):
        for axes in itertools.product('xyz', repeat=length):
            if all(first != second for first, second in zip(axes, axes[1:])):
                axis_strings.append(''.join(axes))
    for frame in range(24):
        for phase in range(8):
            for axes in axis_strings:
                yield WireOp(Clif(frame, phase), axes)


def records_matrix(records) -> tuple:
    """Multiply CLIF, T and PHASE records using independent exact matrices.

    The reference builds frame k as P[k % 4] R[k // 4] from the conventional
    H, S and Pauli matrices, without the library's tables.
    """
    result = exact.I
    for record in records:
        if isinstance(record, CliffordGate):
            gate = exact.FRAMES[record.frame]
        elif isinstance(record, TGate):
            gate = exact.T
        elif isinstance(record, Phase):
            gate = scale(exact.PHASES[record.exponent], exact.I)
        else:
            raise AssertionError(f'unexpected record {record}')
        result = matrix_product(gate, result)
    return result


class LoweringTests(unittest.TestCase):
    def test_records_reproduce_operator_exactly(self) -> None:
        for operator in bounded_operators():
            with self.subTest(operator=operator):
                lowered = records_matrix(lower_operator(operator, 'q'))
                target = exact.operator_matrix(operator)
                self.assertEqual(lowered, target)

    def test_records_alternate(self) -> None:
        for operator in bounded_operators():
            with self.subTest(operator=operator):
                records = lower_operator(operator, 'q')
                kinds = [type(record) for record in records
                         if not isinstance(record, Phase)]
                self.assertEqual(kinds.count(TGate), operator.t_count)
                for first, second in zip(kinds, kinds[1:]):
                    self.assertFalse(first is second is CliffordGate)
                for record in records:
                    if isinstance(record, CliffordGate):
                        self.assertNotEqual(record.frame, 0)

    def test_phase_is_preserved(self) -> None:
        self.assertEqual(lower_operator(op(T, phase=3), 'q'),
                         (TGate('q'), Phase(3)))
        self.assertEqual(lower_operator(op(phase=5), 'q'), (Phase(5),))
        self.assertEqual(lower_operator(I, 'q'), ())

    def test_phase_from_decomposition_is_preserved(self) -> None:
        # This operator's phase field is zero, but its H/S/T decomposition
        # contributes omega**6 when its Clifford runs are replaced by frames.
        operator = WireOp(Clif(1), 'y')
        self.assertEqual(operator.phase, 0)
        records = lower_operator(operator, 'q')
        self.assertEqual(records[-1], Phase(6))
        self.assertEqual(records_matrix(records), exact.operator_matrix(operator))

    def test_example_records(self) -> None:
        self.assertEqual(lower_operator(op('HT'), 'q'),
                         (CliffordGate(4, 'q'), TGate('q')))
        self.assertEqual(lower_operator(S, 'a'), (CliffordGate(8, 'a'),))

    def test_rejects_bad_arguments(self) -> None:
        with self.assertRaises(TypeError):
            lower_operator('HT', 'q')
        with self.assertRaises(ValueError):
            lower_operator(I, 'not a name')


if __name__ == '__main__':
    unittest.main()
