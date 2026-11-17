"""Check a body for CCZ: six CZ interactions and seven T gates.

CCZ |a,b,c> = (-1)**(a*b*c) |a,b,c>. CircuitBuilder builds the body from
DESIGN.md, and two independent exact simulations check it: one of the
stored circuit, with phase, and one of its stream, up to global phase.
DESIGN.md explains why this body is CCZ.
"""

import unittest

from quantum_circuits import Circuit, CircuitBuilder, H, I, T, WireOp, op
from quantum_circuits.stream import CliffordGate, CZGate, TGate, check_stream, expand
from tests import exact_reference as exact
from tools.generate_clifford_tables import (
    Matrix, Scalar, add_scalars, multiply_scalars, negate_scalar,
)

A, B, C = 0, 1, 2
T_INVERSE = T ** -1

# The table in DESIGN.md. VERTICES gives the two wires of each CZ vertex,
# in an order consistent with every wire.
VERTICES = ((B, C), (A, C), (B, C), (A, C), (A, B), (A, B))

# SEGMENTS[wire] lists the operator on each segment of that wire: from the
# input to its first vertex, between consecutive vertices, and from its last
# vertex to the output. Words are in execution order.
SEGMENTS = (
    (I, I, I, T, I),
    (I, I, op('TH'), op('H', T_INVERSE, 'H'), H),
    (H, op('H', T_INVERSE, 'H'), op('HTH'), op('H', T_INVERSE, 'H'), op('HT')),
)


def build_ccz_body() -> Circuit:
    """Build the body in execution order, one operation at a time."""
    builder = CircuitBuilder(3)
    builder.apply(H, C)
    builder.cz(B, C)                            # vertex 0
    builder.apply(op('H', T_INVERSE, 'H'), C)
    builder.cz(A, C)                            # vertex 1
    builder.apply(op('HTH'), C)
    builder.cz(B, C)                            # vertex 2
    builder.apply(op('TH'), B)
    builder.apply(op('H', T_INVERSE, 'H'), C)
    builder.cz(A, C)                            # vertex 3
    builder.cz(A, B)                            # vertex 4
    builder.apply(T, A)
    builder.apply(op('H', T_INVERSE, 'H'), B)
    builder.cz(A, B)                            # vertex 5
    builder.apply(H, B)
    builder.apply(op('HT'), C)
    return builder.build()


def apply_matrix(state: list[Scalar], matrix: Matrix, wire: int) -> list[Scalar]:
    """Apply an exact 2x2 matrix to one wire of a state vector."""
    m00, m01, m10, m11 = matrix
    mask = 1 << wire
    result = list(state)
    for index in range(len(state)):
        if not index & mask:
            low, high = state[index], state[index | mask]
            result[index] = add_scalars(
                multiply_scalars(m00, low), multiply_scalars(m01, high))
            result[index | mask] = add_scalars(
                multiply_scalars(m10, low), multiply_scalars(m11, high))
    return result


def apply_operator(state: list[Scalar], operator: WireOp, wire: int) -> list[Scalar]:
    """Apply an exact single-qubit operator, including its phase."""
    return apply_matrix(state, exact.operator_matrix(operator), wire)


def apply_cz(state: list[Scalar], first: int, second: int) -> list[Scalar]:
    """Negate each amplitude whose bits on both wires are one."""
    mask = (1 << first) | (1 << second)
    return [
        negate_scalar(amplitude) if index & mask == mask else amplitude
        for index, amplitude in enumerate(state)
    ]


def basis_state(basis_index: int) -> list[Scalar]:
    state = [exact.ZERO] * 8
    state[basis_index] = exact.ONE
    return state


def ccz_column(basis_index: int) -> list[Scalar]:
    """Column basis_index of CCZ. Bit w of an index is the value on wire w."""
    a, b, c = (basis_index >> wire & 1 for wire in (A, B, C))
    column = basis_state(basis_index)
    if a * b * c:
        column[basis_index] = negate_scalar(exact.ONE)
    return column


def circuit_output(circuit: Circuit, basis_index: int) -> list[Scalar]:
    """Run a stored circuit on one basis state, from its vertices and segments."""
    state = basis_state(basis_index)
    next_segment = [0] * circuit.wire_count
    for vertex in circuit.vertices:
        for wire in vertex:
            segment = circuit.segments[wire][next_segment[wire]]
            state = apply_operator(state, segment, wire)
            next_segment[wire] += 1
        state = apply_cz(state, *vertex)
    for wire in range(circuit.wire_count):
        state = apply_operator(state, circuit.segments[wire][next_segment[wire]], wire)
    return state


def stream_output(operations, basis_index: int) -> list[Scalar]:
    """Run flat stream records on one basis state; names 0, 1, 2 are wires."""
    state = basis_state(basis_index)
    for record in operations:
        if isinstance(record, CliffordGate):
            state = apply_matrix(state, exact.FRAMES[record.frame], int(record.qubit))
        elif isinstance(record, TGate):
            state = apply_matrix(state, exact.T, int(record.qubit))
        elif isinstance(record, CZGate):
            state = apply_cz(state, int(record.first), int(record.second))
        else:
            raise AssertionError(f'unexpected record {record}')
    return state


class CCZBodyTests(unittest.TestCase):
    def test_builder_gives_design_table(self) -> None:
        circuit = build_ccz_body()
        self.assertEqual(circuit.vertices, VERTICES)
        self.assertEqual(circuit.segments, SEGMENTS)

    def test_shape(self) -> None:
        circuit = build_ccz_body()
        self.assertEqual(len(circuit.vertices), 6)
        t_counts = [
            sum(label.t_count for label in labels) for labels in circuit.segments]
        self.assertEqual(t_counts, [1, 2, 4])

    def test_body_is_ccz_exactly(self) -> None:
        # The eight outputs are the columns of the body's matrix, so this
        # comparison is complete. Equality is exact and includes phase.
        circuit = build_ccz_body()
        for basis_index in range(8):
            self.assertEqual(circuit_output(circuit, basis_index),
                             ccz_column(basis_index), basis_index)

    def test_stream_is_ccz_up_to_global_phase(self) -> None:
        # The stream drops global phase, so one phase must serve every column.
        flat = expand(check_stream(build_ccz_body().to_stream()))
        outputs = [stream_output(flat.operations, index) for index in range(8)]
        matching_phases = [
            phase for phase in exact.PHASES
            if all(
                [multiply_scalars(phase, amplitude) for amplitude in ccz_column(index)]
                == outputs[index]
                for index in range(8)
            )
        ]
        self.assertEqual(len(matching_phases), 1)


if __name__ == '__main__':
    unittest.main()
