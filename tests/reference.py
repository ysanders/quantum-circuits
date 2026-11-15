"""Independent complex-matrix oracle; never uses the multiplication tables."""

import cmath
import math

from quantum_circuits import CCZ, CZ, Apply

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


def leaves(body):
    """Interpret graph labels on named wires for the independent matrix oracle."""
    for vertex in body.vertices:
        for edge in vertex.inputs:
            yield Apply(edge.op, edge.wire)
        interaction = CZ if vertex.kind == 'CZ' else CCZ
        yield interaction(*(edge.wire for edge in vertex.inputs))
    for edge in body.outputs:
        yield Apply(edge.op, edge.wire)


def evaluate(body, wires, input_index):
    """One column of a graph's matrix, including its scalar phase."""
    column = apply(tuple(leaves(body)), wires, input_index)
    return [OMEGA ** body.phase * v for v in column]


def apply(operations, wires, input_index):
    """Apply a raw list of primitives to a basis vector, retaining phase."""
    positions = {q: i for i, q in enumerate(wires)}
    vector = [0j] * (1 << len(wires))
    vector[input_index] = 1
    for op in operations:
        if isinstance(op, Apply):
            u = operator_matrix(op.op)
            mask = 1 << positions[op.targ]
            out = vector.copy()
            for j in range(len(vector)):
                if not j & mask:
                    v0, v1 = vector[j], vector[j | mask]
                    out[j] = u[0] * v0 + u[1] * v1
                    out[j | mask] = u[2] * v0 + u[3] * v1
            vector = out
        elif isinstance(op, (CZ, CCZ)):
            mask = sum(1 << positions[q] for q in op.qubits)
            vector = [-v if j & mask == mask else v for j, v in enumerate(vector)]
        else:
            raise TypeError(type(op))
    return vector
