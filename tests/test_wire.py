"""Tests for one-wire circuits and their lowering to the stream."""

import itertools
import unittest

from quantum_circuits import MEASURE, PREPARE, Clif, H, I, S, T, Wire, WireOp, op
from quantum_circuits.stream import (
    CLASSICAL, QUANTUM, CliffordGate, Measure, Port, Prepare, TGate,
    check_stream, expand,
)
from quantum_circuits.wire import lower_operator
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
    """Multiply CLIF and T records exactly, using the reference matrices.

    The reference builds frame k as P[k % 4] R[k // 4] from the conventional
    H, S and Pauli matrices, without the library's tables.
    """
    result = exact.I
    for record in records:
        if isinstance(record, CliffordGate):
            gate = exact.FRAMES[record.frame]
        else:
            gate = exact.T
        result = matrix_product(gate, result)
    return result


class CompositionTests(unittest.TestCase):
    def test_prepare_operate_measure(self) -> None:
        wire = PREPARE.then(H).then(MEASURE)
        self.assertEqual(wire, Wire(prepared=True, operator=H, measured=True))
        self.assertEqual(wire.inputs, ())
        self.assertEqual(wire.outputs, (CLASSICAL,))

    def test_boundaries(self) -> None:
        self.assertEqual(Wire(operator=T).inputs, (QUANTUM,))
        self.assertEqual(Wire(operator=T).outputs, (QUANTUM,))
        self.assertEqual(PREPARE.outputs, (QUANTUM,))
        self.assertEqual(MEASURE.inputs, (QUANTUM,))

    def test_then_applies_operators_in_order(self) -> None:
        # Execution order: H acts first, so the matrix product is T @ H.
        self.assertEqual(Wire(operator=H).then(T), Wire(operator=T @ H))
        self.assertEqual(Wire(operator=H).then(Wire(operator=T)), Wire(operator=T @ H))
        self.assertEqual(PREPARE.then(op('HT')).operator, op('HT'))

    def test_then_keeps_phase(self) -> None:
        wire = Wire(operator=op(phase=3)).then(op(phase=6))
        self.assertEqual(wire.operator, op(phase=1))

    def test_then_is_associative(self) -> None:
        pieces = (PREPARE, Wire(operator=H), Wire(operator=op('TS')), MEASURE)
        first, second, third, fourth = pieces
        left = first.then(second).then(third).then(fourth)
        right = first.then(second.then(third.then(fourth)))
        self.assertEqual(left, right)

    def test_rejects_impossible_connections(self) -> None:
        with self.assertRaises(ValueError):
            MEASURE.then(H)
        with self.assertRaises(ValueError):
            Wire(operator=H).then(PREPARE)

    def test_rejects_malformed_values(self) -> None:
        with self.assertRaises(TypeError):
            Wire(prepared=1)
        with self.assertRaises(TypeError):
            Wire(operator=Clif(0))
        with self.assertRaises(TypeError):
            Wire().then('H')


class LoweringTests(unittest.TestCase):
    def test_records_reproduce_operator_up_to_phase(self) -> None:
        for operator in bounded_operators():
            with self.subTest(operator=operator):
                lowered = records_matrix(lower_operator(operator, 'q'))
                target = exact.operator_matrix(operator)
                self.assertTrue(
                    any(scale(phase, lowered) == target for phase in exact.PHASES))

    def test_records_alternate(self) -> None:
        for operator in bounded_operators():
            with self.subTest(operator=operator):
                records = lower_operator(operator, 'q')
                kinds = [type(record) for record in records]
                self.assertEqual(kinds.count(TGate), operator.t_count)
                for first, second in zip(kinds, kinds[1:]):
                    self.assertFalse(first is second is CliffordGate)
                for record in records:
                    if isinstance(record, CliffordGate):
                        self.assertNotEqual(record.frame, 0)

    def test_phase_is_dropped(self) -> None:
        self.assertEqual(lower_operator(op(T, phase=3), 'q'), lower_operator(T, 'q'))
        self.assertEqual(lower_operator(op(phase=5), 'q'), ())
        self.assertEqual(lower_operator(I, 'q'), ())

    def test_example_records(self) -> None:
        self.assertEqual(lower_operator(op('HT'), 'q'),
                         (CliffordGate(4, 'q'), TGate('q')))
        self.assertEqual(lower_operator(S, 'a'), (CliffordGate(8, 'a'),))

    def test_rejects_bad_arguments(self) -> None:
        with self.assertRaises(TypeError):
            lower_operator('HT', 'q')
        with self.assertRaises(ValueError):
            lower_operator(I, 'not a name')


class StreamTests(unittest.TestCase):
    def test_prepared_measured_wire(self) -> None:
        flat = expand(check_stream(PREPARE.then(op('HT')).then(MEASURE).to_stream()))
        self.assertEqual(flat.inputs, ())
        self.assertEqual(flat.operations, (
            Prepare('0'), CliffordGate(4, '0'), TGate('0'), Measure('0'),
        ))
        self.assertEqual(flat.outputs, (Port(CLASSICAL, '0'),))

    def test_unitary_wire(self) -> None:
        flat = expand(check_stream(Wire(operator=op('TH')).to_stream('a')))
        self.assertEqual(flat.inputs, (Port(QUANTUM, '0'),))
        self.assertEqual(flat.outputs, (Port(QUANTUM, '0'),))
        self.assertEqual(flat.operations, (TGate('0'), CliffordGate(4, '0')))

    def test_digest_ignores_name_and_phase(self) -> None:
        first = check_stream(Wire(operator=T).to_stream('a'))
        second = check_stream(Wire(operator=op(T, phase=3)).to_stream('b'))
        self.assertEqual(first.root.digest, second.root.digest)
        third = check_stream(PREPARE.then(T).to_stream('a'))
        self.assertNotEqual(first.root.digest, third.root.digest)


if __name__ == '__main__':
    unittest.main()
