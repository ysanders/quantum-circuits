"""Check a body for CCZ: six CZ interactions and seven T gates.

CCZ |a,b,c> = (-1)**(a*b*c) |a,b,c>. No circuit type exists yet, so the body
is plain data: the CZ vertices in order, and the exact single-qubit operator
on every edge. DESIGN.md explains why this body is CCZ.
"""

import unittest

from quantum_circuits import H, I, T, WireOp, op
from tests import exact_reference as exact
from tools.generate_clifford_tables import (
    Scalar, add_scalars, multiply_scalars, negate_scalar,
)

A, B, C = 0, 1, 2
T_INVERSE = T ** -1

# The two wires of each CZ vertex, in an order consistent with every wire.
VERTICES = ((B, C), (A, C), (B, C), (A, C), (A, B), (A, B))

# EDGE_LABELS[wire] lists the operator on each edge of that wire: from the
# input to its first vertex, between consecutive vertices, and from its last
# vertex to the output. Words are in execution order.
EDGE_LABELS = (
    (I, I, I, T, I),
    (I, I, op('TH'), op('H', T_INVERSE, 'H'), H),
    (H, op('H', T_INVERSE, 'H'), op('HTH'), op('H', T_INVERSE, 'H'), op('HT')),
)


def apply_operator(state: list[Scalar], operator: WireOp, wire: int) -> list[Scalar]:
    """Apply an exact single-qubit operator to one wire of a state vector."""
    m00, m01, m10, m11 = exact.operator_matrix(operator)
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


def apply_cz(state: list[Scalar], first: int, second: int) -> list[Scalar]:
    """Negate each amplitude whose bits on both wires are one."""
    mask = (1 << first) | (1 << second)
    return [
        negate_scalar(amplitude) if index & mask == mask else amplitude
        for index, amplitude in enumerate(state)
    ]


def body_output(basis_index: int) -> list[Scalar]:
    """Run the body on one basis state. Bit w of an index is the value on wire w."""
    state = [exact.ZERO] * 8
    state[basis_index] = exact.ONE
    next_edge = [0, 0, 0]  # the first unused label on each wire
    for vertex in VERTICES:
        for wire in vertex:
            state = apply_operator(state, EDGE_LABELS[wire][next_edge[wire]], wire)
            next_edge[wire] += 1
        state = apply_cz(state, *vertex)
    for wire in (A, B, C):
        state = apply_operator(state, EDGE_LABELS[wire][next_edge[wire]], wire)
    return state


class CCZBodyTests(unittest.TestCase):
    def test_shape(self) -> None:
        self.assertEqual(len(VERTICES), 6)
        for wire in (A, B, C):
            vertices_on_wire = sum(wire in vertex for vertex in VERTICES)
            self.assertEqual(len(EDGE_LABELS[wire]), vertices_on_wire + 1)
        t_counts = [sum(label.t_count for label in labels) for labels in EDGE_LABELS]
        self.assertEqual(t_counts, [1, 2, 4])

    def test_body_is_ccz_exactly(self) -> None:
        # The eight outputs are the columns of the body's matrix, so this
        # comparison is complete. Equality is exact and includes phase.
        for basis_index in range(8):
            a, b, c = (basis_index >> wire & 1 for wire in (A, B, C))
            expected = [exact.ZERO] * 8
            expected[basis_index] = negate_scalar(exact.ONE) if a * b * c else exact.ONE
            self.assertEqual(body_output(basis_index), expected, basis_index)


if __name__ == '__main__':
    unittest.main()
