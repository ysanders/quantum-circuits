#!/usr/bin/env python3
"""Generate Clifford tables using exact Q(sqrt(2), i) arithmetic.

This development tool is independent of the runtime package. It first builds
and verifies the finite group, then renders the tables as a Python module.
Run with --check to compare that module with the committed file.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

# Scalars use the basis (1, sqrt(2), i, i*sqrt(2)); matrices are row-major.
Scalar = tuple[Fraction, Fraction, Fraction, Fraction]
Quadratic = tuple[Fraction, Fraction]
Matrix = tuple[Scalar, Scalar, Scalar, Scalar]
CliffordIndex = tuple[int, int]  # (frame, phase exponent)


def scalar(
    a: int | Fraction = 0,
    b: int | Fraction = 0,
    c: int | Fraction = 0,
    d: int | Fraction = 0,
) -> Scalar:
    """Construct a + b*sqrt(2) + i*(c + d*sqrt(2)) exactly."""
    return Fraction(a), Fraction(b), Fraction(c), Fraction(d)


def add_scalars(left: Scalar, right: Scalar) -> Scalar:
    return (
        left[0] + right[0],
        left[1] + right[1],
        left[2] + right[2],
        left[3] + right[3],
    )


def negate_scalar(value: Scalar) -> Scalar:
    return -value[0], -value[1], -value[2], -value[3]


def quadratic_product(left: Quadratic, right: Quadratic) -> Quadratic:
    """Multiply a+b*sqrt(2) by c+d*sqrt(2), using sqrt(2)**2 = 2."""
    a, b = left
    c, d = right
    rational = a * c + 2 * b * d
    root_coefficient = a * d + b * c
    return rational, root_coefficient


def multiply_scalars(left: Scalar, right: Scalar) -> Scalar:
    """Multiply complex numbers whose real and imaginary parts lie in Q(sqrt(2))."""
    left_real = (left[0], left[1])
    left_imaginary = (left[2], left[3])
    right_real = (right[0], right[1])
    right_imaginary = (right[2], right[3])

    real_product = quadratic_product(left_real, right_real)
    imaginary_product = quadratic_product(left_imaginary, right_imaginary)
    real_imaginary = quadratic_product(left_real, right_imaginary)
    imaginary_real = quadratic_product(left_imaginary, right_real)
    # (a + ib)(c + id) = (ac - bd) + i(ad + bc).
    return (
        real_product[0] - imaginary_product[0],
        real_product[1] - imaginary_product[1],
        real_imaginary[0] + imaginary_real[0],
        real_imaginary[1] + imaginary_real[1],
    )


def conjugate_scalar(value: Scalar) -> Scalar:
    return value[0], value[1], -value[2], -value[3]


def matrix_product(left: Matrix, right: Matrix) -> Matrix:
    """Ordinary 2-by-2 matrix multiplication, in row-major order."""
    a00, a01, a10, a11 = left
    b00, b01, b10, b11 = right
    return (
        add_scalars(multiply_scalars(a00, b00), multiply_scalars(a01, b10)),
        add_scalars(multiply_scalars(a00, b01), multiply_scalars(a01, b11)),
        add_scalars(multiply_scalars(a10, b00), multiply_scalars(a11, b10)),
        add_scalars(multiply_scalars(a10, b01), multiply_scalars(a11, b11)),
    )


def adjoint(matrix: Matrix) -> Matrix:
    """Conjugate transpose: exchange the off-diagonal entries."""
    return (
        conjugate_scalar(matrix[0]),
        conjugate_scalar(matrix[2]),
        conjugate_scalar(matrix[1]),
        conjugate_scalar(matrix[3]),
    )


def scale(factor: Scalar, matrix: Matrix) -> Matrix:
    return (
        multiply_scalars(factor, matrix[0]),
        multiply_scalars(factor, matrix[1]),
        multiply_scalars(factor, matrix[2]),
        multiply_scalars(factor, matrix[3]),
    )


@dataclass(frozen=True, slots=True)
class CliffordTables:
    """Finite exact data, kept separate from its generated Python formatting."""

    frame_labels: tuple[str, ...]
    frame_product: tuple[tuple[CliffordIndex, ...], ...]
    frame_inverse: tuple[CliffordIndex, ...]
    pauli_action: tuple[tuple[int, ...], ...]
    clifford_words: tuple[str, ...]


def pauli_action_table(
    frames: tuple[Matrix, ...], paulis: tuple[Matrix, ...],
) -> tuple[tuple[int, ...], ...]:
    """Encode C P C^-1 as a signed axis: +/-1, +/-2, or +/-3 for X, Y, Z."""
    signed_paulis = {}
    for axis, pauli in enumerate(paulis, start=1):
        for sign in (1, -1):
            signed_paulis[scale(scalar(sign), pauli)] = sign * axis

    rows = []
    for frame in frames:
        inverse = adjoint(frame)
        row = []
        for pauli in paulis:
            image = matrix_product(matrix_product(frame, pauli), inverse)
            row.append(signed_paulis[image])
        rows.append(tuple(row))
    return tuple(rows)


def shortest_clifford_words(
    identity: Matrix, hadamard: Matrix, phase_gate: Matrix,
) -> dict[Matrix, str]:
    """Breadth-first search for shortest H/S words, retaining exact phase."""
    words = {identity: ''}
    queue = deque([identity])
    while queue:
        current = queue.popleft()
        for letter, gate in (('H', hadamard), ('S', phase_gate)):
            # Appending an executed gate multiplies on the left. The queue
            # visits increasing lengths, so the first word found is shortest.
            successor = matrix_product(gate, current)
            if successor not in words:
                words[successor] = words[current] + letter
                queue.append(successor)
    return words


def build_tables() -> CliffordTables:
    """Construct the 24 frames and their eight exact scalar phases."""
    zero = scalar()
    one = scalar(1)
    imaginary_unit = scalar(0, 0, 1)
    root_half = scalar(0, Fraction(1, 2))
    omega = scalar(0, Fraction(1, 2), 0, Fraction(1, 2))

    identity = (one, zero, zero, one)
    pauli_x = (zero, one, one, zero)
    pauli_y = (zero, negate_scalar(imaginary_unit), imaginary_unit, zero)
    pauli_z = (one, zero, zero, negate_scalar(one))
    hadamard = (root_half, root_half, root_half, negate_scalar(root_half))
    phase_gate = (one, zero, zero, imaginary_unit)
    paulis = (identity, pauli_x, pauli_y, pauli_z)
    representatives = (
        identity,
        hadamard,
        phase_gate,
        matrix_product(hadamard, phase_gate),
        matrix_product(phase_gate, hadamard),
        matrix_product(matrix_product(hadamard, phase_gate), hadamard),
    )

    # Enumeration order fixes frame = 4*representative + pauli.
    frame_matrices = []
    labels = []
    representative_names = ('I', 'H', 'S', 'HS', 'SH', 'HSH')
    for name, representative in zip(representative_names, representatives):
        for pauli_name, pauli in zip(('I', 'X', 'Y', 'Z'), paulis):
            frame_matrices.append(matrix_product(pauli, representative))
            labels.append((pauli_name + name).replace('I', '') or 'I')
    frames = tuple(frame_matrices)
    for frame in frames:
        assert matrix_product(frame, adjoint(frame)) == identity
    actions = pauli_action_table(frames, (pauli_x, pauli_y, pauli_z))
    assert len(set(actions)) == 24

    phases = [one]
    for _ in range(7):
        phases.append(multiply_scalars(phases[-1], omega))
    lookup = {}
    for frame_index, frame in enumerate(frames):
        for exponent, phase in enumerate(phases):
            lookup[scale(phase, frame)] = (frame_index, exponent)
    assert len(lookup) == 192

    products = []
    for left in frames:
        row = []
        for right in frames:
            row.append(lookup[matrix_product(left, right)])
        products.append(tuple(row))
    inverses = tuple(lookup[adjoint(frame)] for frame in frames)

    words = shortest_clifford_words(identity, hadamard, phase_gate)
    assert words.keys() == lookup.keys()
    clifford_words = []
    for frame in frames:
        for phase in phases:
            clifford_words.append(words[scale(phase, frame)])

    return CliffordTables(
        frame_labels=tuple(labels),
        frame_product=tuple(products),
        frame_inverse=inverses,
        pauli_action=actions,
        clifford_words=tuple(clifford_words),
    )


def render() -> str:
    """Render deterministic Python source from the verified exact tables."""
    tables = build_tables()
    lines = [
        '"""Generated by tools/generate_clifford_tables.py; do not edit by hand.',
        '',
        'C[4*b+p] = P[p] R[b], using matrix-product order.',
        'P = (I, X, Y, Z); R = (I, H, S, HS, SH, HSH).',
        'FRAME_PRODUCT[a][b] = (c, k) means C[a] C[b] = omega**k C[c].',
        'FRAME_INVERSE[a] = (c, k) means C[a]**-1 = omega**k C[c].',
        'PAULI_ACTION[a][j] encodes C[a] P[j] C[a]**-1 as +/-1,2,3 (X,Y,Z).',
        'CLIFFORD_WORDS[8*frame+phase] is an exact H/S word in execution order.',
        '"""',
        '',
        f'FRAME_LABELS = {tables.frame_labels!r}',
        '',
        'FRAME_PRODUCT = (',
    ]
    for label, row in zip(tables.frame_labels, tables.frame_product):
        lines.append(f'    {row!r},  # {label}')
    lines.extend([')', '', f'FRAME_INVERSE = {tables.frame_inverse!r}', ''])
    lines.append('PAULI_ACTION = (')
    for label, row in zip(tables.frame_labels, tables.pauli_action):
        lines.append(f'    {row!r},  # {label}')
    lines.extend([')', '', 'CLIFFORD_WORDS = ('])
    for word in tables.clifford_words:
        lines.append(f'    {word!r},')
    lines.extend([')', ''])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    path = root / 'quantum_circuits' / '_clifford_tables.py'
    source = render()
    if args.check:
        if not path.exists() or path.read_text(encoding='utf-8') != source:
            raise SystemExit('Clifford tables are missing or out of date.')
        print('Clifford tables match exact regeneration.')
    else:
        path.write_text(source, encoding='utf-8')
        print(f'Wrote {path}')


if __name__ == '__main__':
    main()
