"""Tests for circuits whose wires meet at CZ vertices.

tests/test_ccz.py checks a full body exactly; these tests check the
builder's rules, the canonical vertex order, boundaries and streams.
"""

import unittest

from quantum_circuits import (
    MEASURE, PREPARE, Circuit, CircuitBuilder, H, I, T, op,
)
from quantum_circuits.stream import (
    CLASSICAL, QUANTUM, CliffordGate, CZGate, Measure, Port, Prepare,
    check_stream, expand,
)


def parity_check() -> Circuit:
    """Measure the Z value of wire 0 onto a prepared wire, using H CZ H."""
    builder = CircuitBuilder(1)
    ancilla = builder.prepare()
    builder.apply(H, ancilla)
    builder.cz(0, ancilla)
    builder.apply(H, ancilla)
    builder.measure(ancilla)
    return builder.build()


def disjoint_pairs(first_pair: tuple, second_pair: tuple) -> Circuit:
    builder = CircuitBuilder(4)
    builder.cz(*first_pair)
    builder.cz(*second_pair)
    return builder.build()


class BuilderTests(unittest.TestCase):
    def test_prepared_and_measured_wires(self) -> None:
        circuit = parity_check()
        self.assertEqual(circuit.segments, ((I, I), (H, H)))
        self.assertEqual(circuit.vertices, ((0, 1),))
        self.assertEqual(circuit.prepared, frozenset({1}))
        self.assertEqual(circuit.measured, frozenset({1}))
        self.assertEqual(circuit.input_wires, (0,))
        self.assertEqual(circuit.inputs, (QUANTUM,))
        self.assertEqual(circuit.outputs, (QUANTUM, CLASSICAL))

    def test_operators_accumulate_between_vertices(self) -> None:
        builder = CircuitBuilder(2)
        builder.apply(H, 0)
        builder.apply(T, 0)
        builder.cz(0, 1)
        builder.apply(T, 1)
        self.assertEqual(builder.build().segments, ((T @ H, I), (I, T)))

    def test_cz_is_symmetric(self) -> None:
        self.assertEqual(disjoint_pairs((1, 0), (3, 2)), disjoint_pairs((0, 1), (2, 3)))

    def test_consecutive_equal_czs_are_kept(self) -> None:
        builder = CircuitBuilder(2)
        builder.cz(0, 1)
        builder.cz(0, 1)
        circuit = builder.build()
        self.assertEqual(circuit.vertices, ((0, 1), (0, 1)))
        self.assertEqual(circuit.segments, ((I, I, I), (I, I, I)))

    def test_rejects_invalid_operations(self) -> None:
        builder = CircuitBuilder(2)
        builder.measure(1)
        cases = {
            'operator on a measured wire': lambda: builder.apply(H, 1),
            'CZ with a measured wire': lambda: builder.cz(0, 1),
            'measuring twice': lambda: builder.measure(1),
            'CZ on one wire': lambda: builder.cz(0, 0),
            'missing wire': lambda: builder.apply(H, 2),
            'negative input count': lambda: CircuitBuilder(-1),
            'boolean input count': lambda: CircuitBuilder(True),
        }
        for description, attempt in cases.items():
            with self.subTest(description), self.assertRaises(ValueError):
                attempt()
        with self.assertRaises(TypeError):
            builder.apply('H', 0)


class CanonicalOrderTests(unittest.TestCase):
    def test_order_of_commuting_vertices_does_not_matter(self) -> None:
        first = disjoint_pairs((0, 1), (2, 3))
        second = disjoint_pairs((2, 3), (0, 1))
        self.assertEqual(first, second)
        self.assertEqual(first.vertices, ((0, 1), (2, 3)))
        self.assertEqual(check_stream(first.to_stream()).root.digest,
                         check_stream(second.to_stream()).root.digest)

    def test_ready_vertex_with_smallest_pair_comes_first(self) -> None:
        builder = CircuitBuilder(4)
        builder.cz(2, 3)
        builder.cz(0, 1)
        builder.cz(1, 2)
        # (2, 3) and (0, 1) are ready at the start; (1, 2) waits for both.
        self.assertEqual(builder.build().vertices, ((0, 1), (2, 3), (1, 2)))

    def test_order_follows_each_wire(self) -> None:
        builder = CircuitBuilder(3)
        builder.cz(1, 2)
        builder.cz(0, 1)
        # (0, 1) follows (1, 2) on wire 1, despite its smaller pair.
        self.assertEqual(builder.build().vertices, ((1, 2), (0, 1)))

    def test_constructor_requires_canonical_order(self) -> None:
        segments = ((I, I), (I, I), (I, I), (I, I))
        Circuit(segments, ((0, 1), (2, 3)))
        with self.assertRaises(ValueError):
            Circuit(segments, ((2, 3), (0, 1)))

    def test_constructor_rejects_inconsistent_values(self) -> None:
        cases = {
            'too few segments': lambda: Circuit(((I,), (I, I)), ((0, 1),)),
            'pair out of order': lambda: Circuit(((I, I), (I, I)), ((1, 0),)),
            'missing wire': lambda: Circuit(((I, I), (I, I)), ((0, 2),)),
            'prepared wire out of range': lambda: Circuit(((I,),), (), frozenset({1})),
        }
        for description, attempt in cases.items():
            with self.subTest(description), self.assertRaises(ValueError):
                attempt()
        with self.assertRaises(TypeError):
            Circuit(((I,),), (), {0})


class StreamTests(unittest.TestCase):
    def test_parity_check_stream(self) -> None:
        flat = expand(check_stream(parity_check().to_stream()))
        self.assertEqual(flat.inputs, (Port(QUANTUM, '0'),))
        self.assertEqual(flat.operations, (
            Prepare('1'), CliffordGate(4, '1'), CZGate('0', '1'),
            CliffordGate(4, '1'), Measure('1'),
        ))
        self.assertEqual(flat.outputs, (Port(QUANTUM, '0'), Port(CLASSICAL, '1')))

    def test_one_wire_circuit_matches_wire(self) -> None:
        builder = CircuitBuilder(0)
        wire = builder.prepare()
        builder.apply(op('HT'), wire)
        builder.measure(wire)
        circuit_digest = check_stream(builder.build().to_stream()).root.digest
        one_wire = PREPARE.then(op('HT')).then(MEASURE)
        wire_digest = check_stream(one_wire.to_stream()).root.digest
        self.assertEqual(circuit_digest, wire_digest)

    def test_names(self) -> None:
        records = parity_check().to_stream(('data', 'ancilla'))
        self.assertEqual(records[0].ports, (Port(QUANTUM, 'data'),))
        with self.assertRaises(ValueError):
            parity_check().to_stream(('only_one',))
        with self.assertRaises(ValueError):
            parity_check().to_stream(('same', 'same'))


if __name__ == '__main__':
    unittest.main()
