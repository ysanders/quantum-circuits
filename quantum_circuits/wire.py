"""One-wire circuits: preparation, an exact operator, and measurement.

Preparation creates a wire in |0>. Measurement in the computational basis
destroys a wire and produces a classical outcome. Until wires can
intersect, a circuit that uses these primitives has one wire. Its stream,
from to_stream, fixes what it means (DESIGN.md, Stream).
"""

from __future__ import annotations

from dataclasses import dataclass

from .clifford import Clif
from .operators import I, WireOp
from .stream import (
    CLASSICAL, QUANTUM, CliffordGate, End, Measure, Port, Prepare, Record,
    Start, TGate, assign_digests,
)

__all__ = ['Wire', 'PREPARE', 'MEASURE', 'lower_operator']


def _append_clifford(records: list[Record], word: str, qubit: str) -> None:
    """Append the CLIF record for an H/S word, or nothing for an identity frame."""
    frame = Clif.from_word(word).frame
    if frame:
        records.append(CliffordGate(frame, qubit))


def lower_operator(operator: WireOp, qubit: str) -> tuple[Record, ...]:
    """Stream records for an operator on one qubit, up to global phase.

    CLIF and T records alternate, with at most one CLIF between consecutive
    T gates and no CLIF for an identity frame. The records contain exactly
    operator.t_count T gates. Operators that differ only in phase give
    equal records.
    """
    if not isinstance(operator, WireOp):
        raise TypeError('operator must be a WireOp')
    Port(QUANTUM, qubit)  # rejects a qubit name the stream cannot write
    records: list[Record] = []
    # iter_gates gives an exact H/S/T word in execution order. Each run of H
    # and S between T gates is one Clifford; its frame drops the phase.
    clifford_word = ''
    for gate in operator.iter_gates():
        if gate == 'T':
            _append_clifford(records, clifford_word, qubit)
            records.append(TGate(qubit))
            clifford_word = ''
        else:
            clifford_word += gate
    _append_clifford(records, clifford_word, qubit)
    return tuple(records)


@dataclass(frozen=True, slots=True)
class Wire:
    """A one-wire circuit, in execution order.

    prepared: the wire starts by preparing |0>, not at an input port.
    operator: the exact operator the wire applies, including phase.
    measured: the wire ends with a computational-basis measurement, not at
    an output port, so its output is a classical outcome.
    """

    prepared: bool = False
    operator: WireOp = I
    measured: bool = False

    def __post_init__(self) -> None:
        if type(self.prepared) is not bool or type(self.measured) is not bool:
            raise TypeError('prepared and measured must be booleans')
        if not isinstance(self.operator, WireOp):
            raise TypeError('operator must be a WireOp')

    @property
    def inputs(self) -> tuple[str, ...]:
        """Input port kinds: none after a preparation, else one quantum port."""
        return () if self.prepared else (QUANTUM,)

    @property
    def outputs(self) -> tuple[str, ...]:
        """Output port kinds: one classical port after a measurement, else quantum."""
        return (CLASSICAL,) if self.measured else (QUANTUM,)

    def then(self, other: Wire | WireOp) -> Wire:
        """This wire followed by other, which receives its quantum output."""
        if isinstance(other, WireOp):
            other = Wire(operator=other)
        if not isinstance(other, Wire):
            raise TypeError('a wire continues with a Wire or a WireOp')
        if self.measured:
            raise ValueError('a measured wire has no quantum output to continue')
        if other.prepared:
            raise ValueError('a prepared wire has no quantum input to connect')
        # @ is the matrix product, so the right operand acts first.
        return Wire(self.prepared, other.operator @ self.operator, other.measured)

    def to_stream(self, name: str = 'q') -> tuple[Record, ...]:
        """This wire as a checked stream: a root definition on the qubit name.

        The stream carries no global phase, so wires that differ only in
        phase give equal streams. The qubit's name does not enter the digest.
        """
        quantum_port = Port(QUANTUM, name)
        input_ports = () if self.prepared else (quantum_port,)
        output_ports = (Port(CLASSICAL, name),) if self.measured else (quantum_port,)
        records: list[Record] = [Start('root', input_ports)]
        if self.prepared:
            records.append(Prepare(name))
        records.extend(lower_operator(self.operator, name))
        if self.measured:
            records.append(Measure(name))
        records.append(End('root', output_ports))
        return assign_digests(records)


PREPARE = Wire(prepared=True)
MEASURE = Wire(measured=True)
