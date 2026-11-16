"""Exact matrix oracle independent of the runtime tables and normalizer.

Reuse only the development tool's elementary Q(sqrt(2), i) arithmetic.
Construct all matrices here from the conventional definitions of H, S, T.
"""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from tools.generate_clifford_tables import (
    Matrix,
    Scalar,
    add_scalars,
    adjoint,
    matrix_product,
    multiply_scalars,
    negate_scalar,
    scalar,
    scale,
)

if TYPE_CHECKING:
    from quantum_circuits import WireOp

ZERO = scalar()
ONE = scalar(1)
IMAGINARY_UNIT = scalar(0, 0, 1)
HALF = scalar(Fraction(1, 2))
ROOT_TWO = scalar(0, 1)
ROOT_HALF = scalar(0, Fraction(1, 2))
OMEGA = scalar(0, Fraction(1, 2), 0, Fraction(1, 2))
I = (ONE, ZERO, ZERO, ONE)
X = (ZERO, ONE, ONE, ZERO)
Y = (ZERO, negate_scalar(IMAGINARY_UNIT), IMAGINARY_UNIT, ZERO)
Z = (ONE, ZERO, ZERO, negate_scalar(ONE))
H = (ROOT_HALF, ROOT_HALF, ROOT_HALF, negate_scalar(ROOT_HALF))
S = (ONE, ZERO, ZERO, IMAGINARY_UNIT)
T = (ONE, ZERO, ZERO, OMEGA)
NAMED = {'I': I, 'X': X, 'Y': Y, 'Z': Z, 'H': H, 'S': S, 'T': T}

REPRESENTATIVES = (
    I,
    H,
    S,
    matrix_product(H, S),
    matrix_product(S, H),
    matrix_product(matrix_product(H, S), H),
)
FRAMES = tuple(
    matrix_product(pauli, representative)
    for representative in REPRESENTATIVES
    for pauli in (I, X, Y, Z)
)


def powers_of_omega() -> tuple[Scalar, ...]:
    """The eight exact scalar phases, starting at omega**0 = 1."""
    phases = [ONE]
    for _ in range(7):
        phases.append(multiply_scalars(phases[-1], OMEGA))
    return tuple(phases)


PHASES = powers_of_omega()
CLIFFORDS = tuple(
    scale(phase, frame)
    for frame in FRAMES
    for phase in PHASES
)
AXIS_X = matrix_product(matrix_product(H, T), H)
AXIS_Y = matrix_product(matrix_product(S, AXIS_X), adjoint(S))
AXES = {'x': AXIS_X, 'y': AXIS_Y, 'z': T}


def operator_matrix(value: WireOp) -> Matrix:
    """Evaluate a canonical operator exactly, including its scalar phase."""
    clifford_index = 8 * value.initial.frame + value.initial.phase
    result = CLIFFORDS[clifford_index]
    for axis in value.axes:
        result = matrix_product(AXES[axis], result)
    return result


def word_matrix(word: str) -> Matrix:
    """Evaluate a raw word exactly, without normalizing it first."""
    result = I
    for letter in word:
        if letter.isspace():
            continue
        result = matrix_product(NAMED[letter], result)
    return result


def t_count_lower_bound(matrix: Matrix) -> int:
    """A number of T gates that every H/S/T word for this operator needs.

    Conjugation by U rotates the Pauli axes: U P_j U^-1 = sum_i R[i][j] P_i,
    so R[i][j] = trace(P_i U P_j U^-1) / 2 for P = (X, Y, Z). H and S permute
    the axes up to sign. T fixes Z, sends X to (X + Y)/sqrt(2), and sends Y
    to (Y - X)/sqrt(2). A word with k T gates therefore gives entries of the
    form (a + b*sqrt(2)) / sqrt(2)**k with integers a and b. Return the least
    k for which every entry of R has that form.
    """
    inverse = adjoint(matrix)
    paulis = (X, Y, Z)
    left_factors = [matrix_product(pauli, matrix) for pauli in paulis]    # P_i U
    right_factors = [matrix_product(pauli, inverse) for pauli in paulis]  # P_j U^-1
    entries = []
    for left in left_factors:
        for right in right_factors:
            product = matrix_product(left, right)
            trace = add_scalars(product[0], product[3])
            entries.append(multiply_scalars(HALF, trace))

    # Multiply by sqrt(2) until every coefficient is an integer. This ends
    # for Clifford+T operators, whose denominators are powers of sqrt(2).
    exponent = 0
    while any(coefficient.denominator != 1 for entry in entries for coefficient in entry):
        entries = [multiply_scalars(ROOT_TWO, entry) for entry in entries]
        exponent += 1
    return exponent
