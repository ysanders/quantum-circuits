"""Independent single-qubit complex matrices; never use the runtime tables."""

import cmath
import math

IDENTITY = (1, 0, 0, 1)
PAULI_X = (0, 1, 1, 0)
PAULI_Y = (0, -1j, 1j, 0)
PAULI_Z = (1, 0, 0, -1)
HADAMARD = tuple(x / math.sqrt(2) for x in (1, 1, 1, -1))
PHASE_S = (1, 0, 0, 1j)
OMEGA = cmath.exp(1j * math.pi / 4)


def mm(a, b):
    return (
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
    )


def dagger(a):
    return tuple(complex(a[j]).conjugate() for j in (0, 2, 1, 3))


PAULIS = (IDENTITY, PAULI_X, PAULI_Y, PAULI_Z)
BASES = (
    IDENTITY, HADAMARD, PHASE_S,
    mm(HADAMARD, PHASE_S), mm(PHASE_S, HADAMARD),
    mm(mm(HADAMARD, PHASE_S), HADAMARD),
)
FRAMES = tuple(mm(p, r) for r in BASES for p in PAULIS)


def matrix(op):
    return tuple(OMEGA ** op.phase * x for x in FRAMES[op.frame])


AXIS_GATES = {
    'x': mm(mm(HADAMARD, (1, 0, 0, OMEGA)), HADAMARD),
    'y': mm(mm(mm(mm(PHASE_S, HADAMARD), (1, 0, 0, OMEGA)), HADAMARD), dagger(PHASE_S)),
    'z': (1, 0, 0, OMEGA),
}
NAMED = dict(zip('IXYZHST', (IDENTITY, PAULI_X, PAULI_Y, PAULI_Z, HADAMARD, PHASE_S, AXIS_GATES['z'])))


def operator_matrix(op):
    result = matrix(op.initial)
    for axis in op.axes:
        result = mm(AXIS_GATES[axis], result)
    return result


def word_matrix(word):
    result = IDENTITY
    for letter in word:
        if not letter.isspace():
            result = mm(NAMED[letter], result)
    return result
