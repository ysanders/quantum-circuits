"""Circuits whose wires intersect at CZ vertices (DESIGN.md, Circuit representation).

Each wire is a sequence of segments. A segment runs between two of the
wire's events, or between an event and an end of the wire, and carries the
exact WireOp applied there. The events are CZ vertices, each joining two
distinct wires. A wire starts at an input port or by preparing |0>, and ends
at an output port or with a measurement in the computational basis.

The stream from to_stream gives a circuit's operational semantics
(DESIGN.md, Stream).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from .clifford import Clif
from .operators import I, WireOp
from .stream import (
    CLASSICAL, QUANTUM, CliffordGate, CZGate, End, Measure, Phase, Port, Prepare,
    Record, Start, TGate, assign_digests,
)

__all__ = ['Circuit', 'lower_operator']


def _append_clifford(records: list[Record], word: str, qubit: str) -> int:
    """Append the Clifford's frame and return its scalar phase exponent."""
    clifford = Clif.from_word(word)
    if clifford.frame:
        records.append(CliffordGate(clifford.frame, qubit))
    return clifford.phase


def lower_operator(operator: WireOp, qubit: str) -> tuple[Record, ...]:
    """Exact stream records for an operator on one qubit, including phase.

    CLIF and T records alternate, with at most one CLIF between consecutive
    T gates and no CLIF for an identity frame. The records contain exactly
    operator.t_count T gates. A final PHASE record carries the product of
    the Clifford runs' scalar factors, unless that product is identity.
    """
    if not isinstance(operator, WireOp):
        raise TypeError('operator must be a WireOp')
    Port(QUANTUM, qubit)  # rejects a qubit name the stream cannot write
    records: list[Record] = []
    # iter_gates gives an exact H/S/T word in execution order. Each run of H
    # and S between T gates is one Clifford. Replacing a run by its frame
    # contributes its scalar factor to phase, so exact equality is preserved.
    phase = 0
    clifford_word = ''
    for gate in operator.iter_gates():
        if gate == 'T':
            phase += _append_clifford(records, clifford_word, qubit)
            records.append(TGate(qubit))
            clifford_word = ''
        else:
            clifford_word += gate
    phase += _append_clifford(records, clifford_word, qubit)
    if phase % 8:
        records.append(Phase(phase % 8))
    return tuple(records)


Pair = tuple[int, int]


def _stored_order(wire_count: int, vertices: tuple[Pair, ...]) -> tuple[Pair, ...]:
    """Put CZ vertices, given in any valid time order, into the stored order.

    CZs on disjoint wires can be applied in either order with the same
    result, so the stored order must not depend on the order given. The
    stored order is built one vertex at a time. At each step, the vertices
    that may come next are those with no unstored vertex before them on
    either of their wires. Of these, take the one with the smallest wire
    pair, comparing first wires and then second wires. Two vertices that
    may come next never share a pair, because the later one waits on both
    wires.
    """
    events: list[list[int]] = [[] for _ in range(wire_count)]  # vertex indices
    for index, (first, second) in enumerate(vertices):
        events[first].append(index)
        events[second].append(index)
    next_event = [0] * wire_count

    def can_come_next(index: int) -> bool:
        return all(
            next_event[wire] < len(events[wire])
            and events[wire][next_event[wire]] == index
            for wire in vertices[index]
        )

    # A heap of (pair, index), so the smallest pair is popped first.
    candidates = [
        (pair, index) for index, pair in enumerate(vertices) if can_come_next(index)]
    heapq.heapify(candidates)
    queued = {index for _, index in candidates}
    order = []
    while candidates:
        pair, index = heapq.heappop(candidates)
        order.append(pair)
        for wire in pair:
            next_event[wire] += 1
        # Storing a vertex can only free the next vertex on each of its wires.
        for wire in pair:
            if next_event[wire] < len(events[wire]):
                candidate = events[wire][next_event[wire]]
                if candidate not in queued and can_come_next(candidate):
                    heapq.heappush(candidates, (vertices[candidate], candidate))
                    queued.add(candidate)
    return tuple(order)


def _check_wire_set(value: object, wire_count: int, role: str) -> None:
    if type(value) is not frozenset:
        raise TypeError(f'{role} must be a frozenset of wire indices')
    for wire in value:
        if type(wire) is not int or not 0 <= wire < wire_count:
            raise ValueError(f'{role} contains {wire!r}, which is not a wire index')


@dataclass(frozen=True, slots=True)
class Circuit:
    """A circuit of wires that meet at CZ vertices.

    segments[w] lists wire w's operators in execution order; it has one
    more entry than the number of vertices on wire w. vertices lists the
    CZ vertices as wire pairs (a, b) with a < b, in stored order (see
    _stored_order and DESIGN.md).
    Wires in prepared start by preparing |0>; the others start at input
    ports, in wire order. Wires in measured end with a measurement; every
    wire ends at an output port, quantum or classical, in wire order.
    """

    segments: tuple[tuple[WireOp, ...], ...]
    vertices: tuple[tuple[int, int], ...] = ()
    prepared: frozenset[int] = frozenset()
    measured: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        if type(self.segments) is not tuple:
            raise TypeError('segments must be a tuple with one entry per wire')
        for wire_segments in self.segments:
            if type(wire_segments) is not tuple or not wire_segments:
                raise TypeError('each wire needs a nonempty tuple of segments')
            for segment in wire_segments:
                if not isinstance(segment, WireOp):
                    raise TypeError('each segment must be a WireOp')
        wire_count = len(self.segments)
        if type(self.vertices) is not tuple:
            raise TypeError('vertices must be a tuple of wire pairs')
        events_per_wire = [0] * wire_count
        for vertex in self.vertices:
            if (type(vertex) is not tuple or len(vertex) != 2
                    or not all(type(wire) is int for wire in vertex)):
                raise TypeError('each vertex must be a pair of wire indices')
            first, second = vertex
            if not 0 <= first < second < wire_count:
                raise ValueError(
                    f'vertex {vertex} must join two wires a < b of the {wire_count}')
            events_per_wire[first] += 1
            events_per_wire[second] += 1
        for wire, count in enumerate(events_per_wire):
            if len(self.segments[wire]) != count + 1:
                raise ValueError(
                    f'wire {wire} meets {count} vertices, so it needs {count + 1} '
                    f'segments, not {len(self.segments[wire])}')
        if _stored_order(wire_count, self.vertices) != self.vertices:
            raise ValueError(
                'vertices are not in stored order')
        _check_wire_set(self.prepared, wire_count, 'prepared')
        _check_wire_set(self.measured, wire_count, 'measured')

    @property
    def wire_count(self) -> int:
        return len(self.segments)

    @property
    def input_wires(self) -> tuple[int, ...]:
        """The wires that start at input ports; input port i is the i-th of them."""
        return tuple(
            wire for wire in range(self.wire_count) if wire not in self.prepared)

    @property
    def inputs(self) -> tuple[str, ...]:
        """Input port kinds: one quantum port for each wire that is not prepared."""
        return (QUANTUM,) * len(self.input_wires)

    @property
    def outputs(self) -> tuple[str, ...]:
        """Output port kinds in wire order: classical if measured, else quantum."""
        return tuple(
            CLASSICAL if wire in self.measured else QUANTUM
            for wire in range(self.wire_count)
        )

    def to_stream(self, names: tuple[str, ...] | None = None) -> tuple[Record, ...]:
        """This circuit as a checked stream: one root definition.

        names gives each wire's stream name; the default is q0, q1, and so
        on. Names do not enter the digest. Exact phase is retained in a
        PHASE record before END when the total scalar is nontrivial.

        Records follow the stored vertex order. For each vertex, the
        segments that end there come first, its lower wire's then its upper
        wire's, then the CZ. The final segments follow in wire order, each
        with its measurement. A prepared wire's PREP precedes its first
        segment.
        """
        if names is None:
            names = tuple(f'q{wire}' for wire in range(self.wire_count))
        if (type(names) is not tuple or len(names) != self.wire_count
                or len(set(names)) != self.wire_count):
            raise ValueError('names must be a tuple of distinct names, one per wire')
        records: list[Record] = [
            Start('root', tuple(
                Port(QUANTUM, names[wire]) for wire in self.input_wires))
        ]
        segments_emitted = [0] * self.wire_count
        phase = 0

        def emit_next_segment(wire: int) -> None:
            nonlocal phase
            if segments_emitted[wire] == 0 and wire in self.prepared:
                records.append(Prepare(names[wire]))
            segment = self.segments[wire][segments_emitted[wire]]
            for record in lower_operator(segment, names[wire]):
                if isinstance(record, Phase):
                    phase += record.exponent
                else:
                    records.append(record)
            segments_emitted[wire] += 1

        for first, second in self.vertices:
            emit_next_segment(first)
            emit_next_segment(second)
            records.append(CZGate(names[first], names[second]))
        for wire in range(self.wire_count):
            emit_next_segment(wire)
            if wire in self.measured:
                records.append(Measure(names[wire]))
        output_ports = tuple(
            Port(kind, names[wire]) for wire, kind in enumerate(self.outputs))
        if phase % 8:
            records.append(Phase(phase % 8))
        records.append(End('root', output_ports))
        return assign_digests(records)
