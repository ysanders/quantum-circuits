"""Independent single-qubit complex matrices; never use the runtime tables."""

from __future__ import annotations

import cmath
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantum_circuits import Clif, WireOp

Matrix = tuple[complex, complex, complex, complex]

IDENTITY = (1, 0, 0, 1)
PAULI_X = (0, 1, 1, 0)
PAULI_Y = (0, -1j, 1j, 0)
PAULI_Z = (1, 0, 0, -1)
ROOT_HALF = 1 / math.sqrt(2)
HADAMARD = (ROOT_HALF, ROOT_HALF, ROOT_HALF, -ROOT_HALF)
PHASE_S = (1, 0, 0, 1j)
OMEGA = cmath.exp(1j * math.pi / 4)
PHASE_T = (1, 0, 0, OMEGA)


def matrix_product(left: Matrix, right: Matrix) -> Matrix:
    """Ordinary 2-by-2 matrix multiplication, with row-major entries."""
    a00, a01, a10, a11 = left
    b00, b01, b10, b11 = right
    return (
        a00 * b00 + a01 * b10,
        a00 * b01 + a01 * b11,
        a10 * b00 + a11 * b10,
        a10 * b01 + a11 * b11,
    )


def adjoint(matrix: Matrix) -> Matrix:
    """Conjugate transpose, including scalar phase."""
    return (
        complex(matrix[0]).conjugate(),
        complex(matrix[2]).conjugate(),
        complex(matrix[1]).conjugate(),
        complex(matrix[3]).conjugate(),
    )


PAULIS = (IDENTITY, PAULI_X, PAULI_Y, PAULI_Z)
REPRESENTATIVES = (
    IDENTITY,
    HADAMARD,
    PHASE_S,
    matrix_product(HADAMARD, PHASE_S),
    matrix_product(PHASE_S, HADAMARD),
    matrix_product(matrix_product(HADAMARD, PHASE_S), HADAMARD),
)
FRAMES = tuple(
    matrix_product(pauli, representative)
    for representative in REPRESENTATIVES
    for pauli in PAULIS
)

# Construct T_x = H T H and T_y = S T_x S^-1 directly from conventional gates.
AXIS_X = matrix_product(matrix_product(HADAMARD, PHASE_T), HADAMARD)
AXIS_Y = matrix_product(matrix_product(PHASE_S, AXIS_X), adjoint(PHASE_S))
AXIS_GATES = {'x': AXIS_X, 'y': AXIS_Y, 'z': PHASE_T}
NAMED = {
    'I': IDENTITY,
    'X': PAULI_X,
    'Y': PAULI_Y,
    'Z': PAULI_Z,
    'H': HADAMARD,
    'S': PHASE_S,
    'T': PHASE_T,
}


def clifford_matrix(value: Clif) -> Matrix:
    """Evaluate a Clifford from its frame and scalar exponent."""
    phase = OMEGA ** value.phase
    frame = FRAMES[value.frame]
    return phase * frame[0], phase * frame[1], phase * frame[2], phase * frame[3]


def operator_matrix(value: WireOp) -> Matrix:
    """Evaluate the initial Clifford followed by the axes in execution order."""
    result = clifford_matrix(value.initial)
    for axis in value.axes:
        result = matrix_product(AXIS_GATES[axis], result)
    return result


def word_matrix(word: str) -> Matrix:
    """Evaluate a raw gate word without calling the runtime normalizer."""
    result = IDENTITY
    for letter in word:
        if letter.isspace():
            continue
        result = matrix_product(NAMED[letter], result)
    return result
