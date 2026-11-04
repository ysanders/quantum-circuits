"""Exact matrix oracle independent of the runtime tables and normaliser.

Reuse only the development tool's elementary Q(sqrt(2), i) arithmetic.
Construct all matrices here from the conventional definitions of H, S, T.
"""

from fractions import Fraction as F

from tools.generate_clifford_tables import (
    adjoint, mul, neg, product, scalar, scale,
)

ZERO, ONE, IMAG = scalar(), scalar(1), scalar(0, 0, 1)
ROOT_HALF = scalar(0, F(1, 2))
OMEGA = scalar(0, F(1, 2), 0, F(1, 2))
I = (ONE, ZERO, ZERO, ONE)
X = (ZERO, ONE, ONE, ZERO)
Y = (ZERO, neg(IMAG), IMAG, ZERO)
Z = (ONE, ZERO, ZERO, neg(ONE))
H = (ROOT_HALF, ROOT_HALF, ROOT_HALF, neg(ROOT_HALF))
S = (ONE, ZERO, ZERO, IMAG)
T = (ONE, ZERO, ZERO, OMEGA)
NAMED = dict(zip('IXYZHST', (I, X, Y, Z, H, S, T)))
BASES = (I, H, S, product(H, S), product(S, H), product(product(H, S), H))
FRAMES = tuple(product(p, r) for r in BASES for p in (I, X, Y, Z))
PHASES = [ONE]
for _ in range(7):
    PHASES.append(mul(PHASES[-1], OMEGA))
CLIFFORDS = tuple(scale(phase, frame) for frame in FRAMES for phase in PHASES)
AXES = {
    'x': product(product(H, T), H),
    'y': product(product(product(product(S, H), T), H), adjoint(S)),
    'z': T,
}


def matrix(value):
    c = value.initial
    result = CLIFFORDS[8 * c.frame + c.phase]
    for axis in value.axes:
        result = product(AXES[axis], result)
    return result


def word_matrix(word):
    result = I
    for letter in word:
        if not letter.isspace():
            result = product(NAMED[letter], result)
    return result
