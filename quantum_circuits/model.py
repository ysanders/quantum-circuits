"""Immutable port graphs and constructors for named quantum wires."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from .operators import I, WireOp, op


@dataclass(frozen=True, slots=True)
class Wire:
    """A named wire: equal names identify the same wire."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError('a wire name must be a string')

    def __repr__(self) -> str:
        return f'Wire({self.name!r})'


def _wire_key(wire: Wire) -> str:
    """The order in which symmetric ports are stored."""
    return wire.name


def _require_wires(*wires: Wire) -> None:
    if not all(isinstance(q, Wire) for q in wires):
        raise TypeError('wires must be Wire values')
    if len(set(wires)) != len(wires):
        raise ValueError('wire names must be distinct')


@dataclass(frozen=True, slots=True)
class Apply:
    """Apply a canonical single-qubit operator to a named wire."""

    op: WireOp
    targ: Wire

    def __post_init__(self) -> None:
        if not isinstance(self.op, WireOp):
            raise TypeError('op must be a WireOp; use gate() for words')
        _require_wires(self.targ)

    @property
    def qubits(self) -> frozenset[Wire]:
        return frozenset((self.targ,))


def gate(value: str | WireOp, targ: Wire) -> Apply:
    """Apply a word or operator; retain its wire even for identity."""
    if isinstance(value, str):
        value = op(value)
    return Apply(value, targ)


@dataclass(frozen=True, slots=True)
class CZ:
    """Apply |ab> -> (-1)**(a*b) |ab> to two distinct named wires.

    The operands are symmetric and stored in name order. This primitive is
    its own inverse, so a directly connected equal pair cancels.
    """

    a: Wire
    b: Wire

    def __post_init__(self) -> None:
        _require_wires(self.a, self.b)
        a, b = sorted((self.a, self.b), key=_wire_key)
        object.__setattr__(self, 'a', a)
        object.__setattr__(self, 'b', b)

    @property
    def qubits(self) -> frozenset[Wire]:
        return frozenset((self.a, self.b))


@dataclass(frozen=True, slots=True)
class CCZ:
    """Apply |abc> -> (-1)**(a*b*c) |abc> to three distinct named wires.

    All three operands are symmetric and stored in name order. This primitive
    is its own inverse, so a directly connected equal pair cancels.
    """

    a: Wire
    b: Wire
    c: Wire

    def __post_init__(self) -> None:
        _require_wires(self.a, self.b, self.c)
        a, b, c = sorted((self.a, self.b, self.c), key=_wire_key)
        object.__setattr__(self, 'a', a)
        object.__setattr__(self, 'b', b)
        object.__setattr__(self, 'c', c)

    @property
    def qubits(self) -> frozenset[Wire]:
        return frozenset((self.a, self.b, self.c))


Primitive: TypeAlias = Apply | CZ | CCZ
Kind: TypeAlias = Literal['CZ', 'CCZ']


@dataclass(frozen=True, slots=True)
class WireSegment:
    """A wire segment ending at the port that stores this edge.

    The wire name selects a port on the source vertex. None denotes the
    fragment input on that wire.
    """

    wire: Wire
    source: int | None = None
    op: WireOp = I

    def __post_init__(self) -> None:
        if not isinstance(self.wire, Wire) or not isinstance(self.op, WireOp):
            raise TypeError('an edge requires a Wire and a WireOp')
        if self.source is not None:
            if type(self.source) is not int:
                raise TypeError('source must be a vertex index or None')
            if self.source < 0:
                raise ValueError('source indices must be nonnegative')


@dataclass(frozen=True, slots=True)
class Intersection:
    """One CZ or CCZ occurrence, with a paired input and output port on each wire."""

    kind: Kind
    inputs: tuple[WireSegment, ...]

    def __post_init__(self) -> None:
        if self.kind not in ('CZ', 'CCZ'):
            raise ValueError('unknown interaction kind')
        if not isinstance(self.inputs, tuple) or not all(isinstance(e, WireSegment) for e in self.inputs):
            raise TypeError('vertex inputs must be a tuple of edges')
        if len(self.inputs) != (2 if self.kind == 'CZ' else 3):
            raise ValueError('incorrect number of input ports')
        wires = tuple(e.wire for e in self.inputs)
        _require_wires(*wires)
        # Both gates are symmetric. Permute entire ports, including their labels.
        object.__setattr__(self, 'inputs', tuple(sorted(self.inputs, key=lambda e: _wire_key(e.wire))))


@dataclass(frozen=True, slots=True)
class Seq:
    """An open port multigraph. Intersection indices give a topological traversal."""

    wires: tuple[Wire, ...]
    vertices: tuple[Intersection, ...]
    outputs: tuple[WireSegment, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.wires, tuple):
            raise TypeError('wires must be an ordered tuple of Wire values')
        _require_wires(*self.wires)
        if not isinstance(self.vertices, tuple) or not isinstance(self.outputs, tuple):
            raise TypeError('vertices and outputs must be tuples')

        # One current port per wire enforces acyclicity, linear use and continuity.
        latest: dict[Wire, int | None] = dict.fromkeys(self.wires)
        for index, vertex in enumerate(self.vertices):
            if not isinstance(vertex, Intersection):
                raise TypeError('expected an Intersection')
            for edge in vertex.inputs:
                if edge.wire not in latest or edge.source != latest[edge.wire]:
                    raise ValueError('vertex input must use the current port on a declared wire')
                latest[edge.wire] = index
            source = vertex.inputs[0].source
            if (
                source is not None
                and self.vertices[source].kind == vertex.kind
                and all(e.source == source and e.op.is_identity for e in vertex.inputs)
            ):
                raise ValueError('directly cancellable vertex pair; use seq() to compose a block')
        if not all(isinstance(e, WireSegment) for e in self.outputs):
            raise TypeError('outputs must contain edges')
        if tuple(e.wire for e in self.outputs) != self.wires:
            raise ValueError('outputs must match the declared wires in order')
        if any(e.source != latest[e.wire] for e in self.outputs):
            raise ValueError('output must use the current port on its wire')

    @property
    def qubits(self) -> frozenset[Wire]:
        """The declared interface, including idle wires."""
        return frozenset(self.wires)


Node: TypeAlias = Primitive | Seq


def seq(*parts: Node, wires: Iterable[Wire] | None = None) -> Seq:
    """Compose a block by wire name, reducing wire labels and direct CZ/CCZ pairs.

    Supply an ordered iterable of wires to fix the interface. Otherwise its order
    follows first appearance, including the complete interfaces of nested Seqs.
    """
    if isinstance(wires, (set, frozenset)):
        raise TypeError('wires requires an ordered iterable such as a tuple or list')
    boundary = None if wires is None else tuple(wires)
    if boundary is not None:
        _require_wires(*boundary)
    if len(parts) == 1 and isinstance(parts[0], Seq) and boundary in (None, parts[0].wires):
        return parts[0]

    latest: dict[Wire, int | None] = dict.fromkeys(boundary or ())
    vertices: dict[int, Intersection] = {}
    next_index = 0

    # A source port identifies one segment. Its factors can stay here even
    # after a vertex closes it: erasing that vertex reopens the same segment.
    runs: dict[tuple[Wire, int | None], list[WireOp]] = {}

    def add(wire: Wire, value: WireOp) -> None:
        source = latest.setdefault(wire, None)
        if not value.is_identity:
            runs.setdefault((wire, source), []).append(value)

    def take_label(
        wire: Wire, source: int | None, suffix: WireOp = I,
    ) -> WireOp:
        factors = runs.pop((wire, source), None)
        if not factors:
            return suffix
        if not suffix.is_identity:
            factors.append(suffix)
        return factors[0] if len(factors) == 1 else op(*factors)

    def is_clear(wire: Wire) -> bool:
        # Only a candidate pair needs its intervening product now. Cache a
        # nonidentity result for the surviving edge.
        label = take_label(wire, latest[wire])
        if label.is_identity:
            return True
        add(wire, label)
        return False

    def interact(kind: Kind, operands: tuple[Wire, ...]) -> None:
        nonlocal next_index
        source = latest.get(operands[0])
        if (
            source is not None
            and vertices[source].kind == kind
            and all(latest.get(w) == source for w in operands)
            and all(is_clear(w) for w in operands)
        ):
            for edge in vertices.pop(source).inputs:
                latest[edge.wire] = edge.source
                add(edge.wire, edge.op)
            return

        inputs = tuple(WireSegment(w, latest.get(w)) for w in operands)
        vertices[next_index] = Intersection(kind, inputs)
        for wire in operands:
            latest[wire] = next_index
        next_index += 1

    def append_graph(body: Seq) -> None:
        nonlocal next_index
        for wire in body.wires:
            latest.setdefault(wire, None)
        if next_index == 0 and not runs:
            # The first reduced body can share its vertices. Its stored input
            # labels rejoin the pending factors if a later join erases a vertex.
            vertices.update(enumerate(body.vertices))
            next_index = len(body.vertices)
            for edge in body.outputs:
                latest[edge.wire] = edge.source
        else:
            for vertex in body.vertices:
                for edge in vertex.inputs:
                    add(edge.wire, edge.op)
                interact(vertex.kind, tuple(e.wire for e in vertex.inputs))
        for edge in body.outputs:
            add(edge.wire, edge.op)

    for part in parts:
        if isinstance(part, Apply):
            add(part.targ, part.op)
        elif isinstance(part, CZ):
            interact('CZ', (part.a, part.b))
        elif isinstance(part, CCZ):
            interact('CCZ', (part.a, part.b, part.c))
        elif isinstance(part, Seq):
            append_graph(part)
        else:
            raise TypeError('seq() accepts gate applications and Seq values')

    if boundary is not None and len(boundary) != len(latest):
        raise ValueError('circuit uses a wire outside the declared interface')

    # Compact indices only once. Retain original records wherever the source
    # port and the exact label still agree.
    moved: dict[int, int] = {}

    def finish_edge(edge: WireSegment) -> WireSegment:
        value = take_label(edge.wire, edge.source, edge.op)
        source = moved.get(edge.source, edge.source) if edge.source is not None else None
        if source == edge.source and value == edge.op:
            return edge
        return WireSegment(edge.wire, source, value)

    result: list[Intersection] = []
    for old, vertex in vertices.items():
        if old != len(result):
            moved[old] = len(result)
        inputs = tuple(finish_edge(e) for e in vertex.inputs)
        result.append(vertex if inputs == vertex.inputs else Intersection(vertex.kind, inputs))
    outputs = tuple(finish_edge(WireSegment(wire, source)) for wire, source in latest.items())
    return Seq(tuple(latest), tuple(result), outputs)
