"""Exact single-qubit Clifford+T algebra and circuits of intersecting wires.

quantum_circuits.stream defines the stream that fixes what a circuit means.
Standard library only.
"""

from .circuit import Circuit, CircuitBuilder
from .clifford import Clif
from .operators import H, I, S, T, X, Y, Z, WireOp, op
from .wire import MEASURE, PREPARE, Wire

__all__ = [
    'Clif', 'WireOp', 'op', 'I', 'X', 'Y', 'Z', 'H', 'S', 'T',
    'Wire', 'PREPARE', 'MEASURE', 'Circuit', 'CircuitBuilder',
]
