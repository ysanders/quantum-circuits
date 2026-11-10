"""Graph passes. Each takes a Seq and returns a Seq for the same circuit."""

from __future__ import annotations

from heapq import heappop, heappush

from .model import Apply, Builder, CCZ, CZ, Seq, Wire, _wire_key

__all__ = ['canonical_order']

# A run is a maximal set of vertices joined along one wire by identity labels.
# It is named by its wire and the index of its first stored vertex.
Run = tuple[Wire, int]


def canonical_order(body: Seq) -> Seq:
    """Reorder interactions that commute, and cancel the pairs this exposes.

    CZ and CCZ are diagonal, so two interactions commute when every wire they
    share carries only identity labels between them. seq() keeps them in the
    order written and cancels a pair only when it is directly connected.

    This pass returns the same graph for any two circuits that differ only by
    exchanging such interactions, exchanging operations on disjoint wires, or
    inserting and removing adjacent equal pairs. Any other label between two
    interactions fixes their order, including a diagonal one such as T.
    """
    if not isinstance(body, Seq):
        raise TypeError('canonical_order() expects a Seq')
    while True:
        reordered = _reorder(body)
        if reordered == body:
            return reordered
        # A cancelled pair can leave two labels that multiply to identity,
        # joining two runs. Their vertices commute only on the next round.
        body = reordered


def _reorder(body: Seq) -> Seq:
    """Emit the vertices again, smallest ready vertex first."""
    vertices = body.vertices
    run_of: dict[tuple[int, Wire], Run] = {}
    members: dict[Run, list[int]] = {}
    label = {}                          # the label that precedes a run
    following: dict[Run, Run] = {}      # the next run on the same wire
    waiting: dict[Run, int] = {}        # vertices of the preceding run not yet emitted
    blocked = [0] * len(vertices)       # runs of a vertex that still wait

    for index, vertex in enumerate(vertices):
        for edge in vertex.inputs:
            wire, source = edge.wire, edge.source
            if source is not None and edge.op.is_identity:
                run = run_of[source, wire]
            else:
                run = (wire, index)
                label[run] = edge.op
                if source is not None:
                    previous = run_of[source, wire]
                    following[previous] = run
                    waiting[run] = len(members[previous])
            run_of[index, wire] = run
            members.setdefault(run, []).append(index)
            if run in waiting:
                blocked[index] += 1

    builder = Builder(body.wires, body.phase)
    ready: list[tuple[tuple, int]] = []

    def release(run: Run) -> None:
        builder.add(Apply(label[run], run[0]))
        for index in members[run]:
            blocked[index] -= 1
            if not blocked[index]:
                heappush(ready, (_vertex_key(vertices[index]), index))

    for run in members:
        if run not in waiting:
            builder.add(Apply(label[run], run[0]))
    for index, vertex in enumerate(vertices):
        if not blocked[index]:
            heappush(ready, (_vertex_key(vertex), index))

    while ready:
        # Ready vertices with equal keys lie in the same run on every wire.
        # They leave the heap consecutively, and the builder cancels them.
        _, index = heappop(ready)
        vertex = vertices[index]
        wires = tuple(edge.wire for edge in vertex.inputs)
        builder.add(CZ(*wires) if vertex.kind == 'CZ' else CCZ(*wires))
        for wire in wires:
            run = following.get(run_of[index, wire])
            if run is not None:
                waiting[run] -= 1
                if not waiting[run]:
                    release(run)

    for edge in body.outputs:
        builder.add(Apply(edge.op, edge.wire))
    return builder.freeze()


def _vertex_key(vertex) -> tuple:
    return tuple(_wire_key(edge.wire) for edge in vertex.inputs), vertex.kind
