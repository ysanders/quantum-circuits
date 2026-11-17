"""Circuits whose wires intersect at CZ vertices (DESIGN.md, Circuit representation).

Each wire is a sequence of segments. A segment runs between two of the
wire's events, or between an event and an end of the wire, and carries the
exact WireOp applied there. The events are CZ vertices, each joining two
distinct wires. A wire starts at an input port or by preparing |0>, and ends
at an output port or with a measurement in the computational basis.

The stream from to_stream fixes what a circuit means (DESIGN.md, Stream).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from .operators import I, WireOp
from .stream import (
    CLASSICAL, QUANTUM, CZGate, End, Measure, Port, Prepare, Record, Start,
    assign_digests,
)
from .wire import lower_operator

__all__ = ['Circuit', 'CircuitBuilder']


Pair = tuple[int, int]


def _canonical_order(wire_count: int, vertices: tuple[Pair, ...]) -> tuple[Pair, ...]:
    """Reorder CZ vertices into the canonical time order.

    vertices may be any time order. A vertex is ready when it is the next
    unprocessed event on both of its wires. The canonical order repeatedly
    takes the ready vertex with the smallest wire pair. Two ready vertices
    never share a pair, because the later one waits on both wires.

    The result depends only on each wire's sequence of partner wires, not
    on the order of the input, so equal structures get equal orders.
    """
    events: list[list[int]] = [[] for _ in range(wire_count)]  # vertex indices
    for index, (first, second) in enumerate(vertices):
        events[first].append(index)
        events[second].append(index)
    next_event = [0] * wire_count

    def is_ready(index: int) -> bool:
        return all(
            next_event[wire] < len(events[wire])
            and events[wire][next_event[wire]] == index
            for wire in vertices[index]
        )

    ready = [(pair, index) for index, pair in enumerate(vertices) if is_ready(index)]
    heapq.heapify(ready)
    queued = {index for _, index in ready}
    order = []
    while ready:
        pair, index = heapq.heappop(ready)
        order.append(pair)
        for wire in pair:
            next_event[wire] += 1
        # Only the next events on this vertex's two wires can have become ready.
        for wire in pair:
            if next_event[wire] < len(events[wire]):
                candidate = events[wire][next_event[wire]]
                if candidate not in queued and is_ready(candidate):
                    heapq.heappush(ready, (vertices[candidate], candidate))
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
    CZ vertices as wire pairs (a, b) with a < b, in canonical time order.
    Wires in prepared start by preparing |0>; the others start at input
    ports, in wire order. Wires in measured end with a measurement; every
    wire ends at an output port, quantum or classical, in wire order.

    Build circuits with CircuitBuilder, which puts vertices in canonical
    order. The constructor rejects any other order.
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
        if _canonical_order(wire_count, self.vertices) != self.vertices:
            raise ValueError(
                'vertices must be in canonical time order; build with CircuitBuilder')
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
        on. Names do not enter the digest. The stream carries no global phase.

        Records follow the canonical vertex order. For each vertex, the
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

        def emit_next_segment(wire: int) -> None:
            if segments_emitted[wire] == 0 and wire in self.prepared:
                records.append(Prepare(names[wire]))
            segment = self.segments[wire][segments_emitted[wire]]
            records.extend(lower_operator(segment, names[wire]))
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
        records.append(End('root', output_ports))
        return assign_digests(records)


class CircuitBuilder:
    """Builds a Circuit from operations appended in execution order.

    Wires 0 to input_count - 1 start at input ports. prepare adds a wire
    that starts by preparing |0>. A measured wire takes no further
    operations. build freezes the operations so far into a Circuit.
    """

    def __init__(self, input_count: int) -> None:
        if type(input_count) is not int or input_count < 0:
            raise ValueError('input_count must be a nonnegative integer')
        # Invariant: finished[w] holds wire w's segments up to its last
        # vertex, and pending[w] is the product of operators applied since.
        self._finished: list[list[WireOp]] = [[] for _ in range(input_count)]
        self._pending: list[WireOp] = [I] * input_count
        self._vertices: list[tuple[int, int]] = []
        self._prepared: set[int] = set()
        self._measured: set[int] = set()

    def _check_open(self, wire: object) -> None:
        if type(wire) is not int or not 0 <= wire < len(self._pending):
            raise ValueError(f'{wire!r} is not a wire of this circuit')
        if wire in self._measured:
            raise ValueError(f'wire {wire} has been measured')

    def prepare(self) -> int:
        """Add a wire that starts by preparing |0>, and return its index."""
        self._finished.append([])
        self._pending.append(I)
        wire = len(self._pending) - 1
        self._prepared.add(wire)
        return wire

    def apply(self, operator: WireOp, wire: int) -> None:
        """Apply a single-qubit operator to a wire."""
        if not isinstance(operator, WireOp):
            raise TypeError('operator must be a WireOp')
        self._check_open(wire)
        # @ is the matrix product, so the new operator acts after the pending one.
        self._pending[wire] = operator @ self._pending[wire]

    def cz(self, first: int, second: int) -> None:
        """Apply CZ to two distinct wires."""
        self._check_open(first)
        self._check_open(second)
        if first == second:
            raise ValueError('CZ needs two distinct wires')
        for wire in (first, second):
            self._finished[wire].append(self._pending[wire])
            self._pending[wire] = I
        self._vertices.append((min(first, second), max(first, second)))

    def measure(self, wire: int) -> None:
        """End a wire with a measurement in the computational basis."""
        self._check_open(wire)
        self._measured.add(wire)

    def build(self) -> Circuit:
        """Freeze the operations so far into a Circuit."""
        segments = tuple(
            tuple(finished) + (pending,)
            for finished, pending in zip(self._finished, self._pending)
        )
        vertices = _canonical_order(len(segments), tuple(self._vertices))
        return Circuit(segments, vertices, frozenset(self._prepared),
                       frozenset(self._measured))
