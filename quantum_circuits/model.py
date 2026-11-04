"""Immutable primitive operations and local sequence normalisation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .operators import SingleQubitOperator, _Accumulator, op


@dataclass(frozen=True, slots=True)
class Qubit:
    """A named wire: equal names identify the same wire."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError('a qubit name must be a string')

    def __repr__(self) -> str:
        return f'Qubit({self.name!r})'


def _require_qubits(*qubits: Qubit) -> None:
    if not all(isinstance(q, Qubit) for q in qubits):
        raise TypeError('gate operands must be Qubit values')
    if len(set(qubits)) != len(qubits):
        raise ValueError('a gate must have distinct qubit operands')


@dataclass(frozen=True, slots=True)
class Gate:
    """Apply a canonical single-qubit operator to a named wire."""

    op: SingleQubitOperator
    targ: Qubit

    def __post_init__(self) -> None:
        if not isinstance(self.op, SingleQubitOperator):
            raise TypeError('op must be a SingleQubitOperator; use gate() for words')
        _require_qubits(self.targ)

    @property
    def qubits(self) -> frozenset[Qubit]:
        return frozenset((self.targ,))


def gate(value: str | SingleQubitOperator, targ: Qubit) -> Gate:
    """Apply a word or operator; keep an identity until seq() removes it."""
    if isinstance(value, str):
        value = op(value)
    return Gate(value, targ)


@dataclass(frozen=True, slots=True)
class CZGate:
    a: Qubit
    b: Qubit

    def __post_init__(self) -> None:
        _require_qubits(self.a, self.b)
        a, b = sorted((self.a, self.b), key=lambda q: q.name)
        object.__setattr__(self, 'a', a)
        object.__setattr__(self, 'b', b)

    @property
    def qubits(self) -> frozenset[Qubit]:
        return frozenset((self.a, self.b))


@dataclass(frozen=True, slots=True)
class CCZGate:
    a: Qubit
    b: Qubit
    c: Qubit

    def __post_init__(self) -> None:
        _require_qubits(self.a, self.b, self.c)
        a, b, c = sorted((self.a, self.b, self.c), key=lambda q: q.name)
        object.__setattr__(self, 'a', a)
        object.__setattr__(self, 'b', b)
        object.__setattr__(self, 'c', c)

    @property
    def qubits(self) -> frozenset[Qubit]:
        return frozenset((self.a, self.b, self.c))


Primitive: TypeAlias = Gate | CZGate | CCZGate
_PRIMITIVE_TYPES = (Gate, CZGate, CCZGate)


@dataclass(frozen=True, slots=True)
class Seq:
    """A sequence already normalised under seq()'s local rules.

    Empty is identity. A nonempty Seq contains at least two primitives,
    no exact identity gates, and no fusible neighbouring single-qubit gates.
    Use seq() to flatten or simplify input; direct construction validates.
    """

    parts: tuple[Primitive, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.parts, tuple):
            raise TypeError('Seq.parts must be a tuple; use seq(*parts)')
        if len(self.parts) == 1:
            raise ValueError('a singleton is its child; use seq(*parts)')
        previous = None
        for part in self.parts:
            if not isinstance(part, _PRIMITIVE_TYPES):
                raise TypeError('Seq.parts must contain primitives; use seq() to flatten sequences')
            if isinstance(part, Gate):
                if part.op.is_identity:
                    raise ValueError('Seq cannot store an exact identity gate; use seq()')
                if isinstance(previous, Gate) and previous.targ == part.targ:
                    raise ValueError('Seq cannot store fusible neighbours; use seq()')
            previous = part

    @property
    def qubits(self) -> frozenset[Qubit]:
        """Referenced wires in this body, not an operation's declared signature."""
        return frozenset(q for part in self.parts for q in part.qubits)


Node: TypeAlias = Primitive | Seq
_EMPTY = Seq(())


@dataclass(slots=True)
class _GateRun:
    """Temporary mutable run; never stored in a circuit value."""

    targ: Qubit
    value: _Accumulator


def seq(*parts: Node) -> Node:
    """Compose in execution order and perform exact local normalisation.

    Flatten Seq children, eliminate exact identities, and fuse adjacent
    same-wire single-qubit operators. Preserve phase-only operations and
    the order of all other operations. No commutation or gate expansion.
    """
    stack: list[Primitive | _GateRun] = []
    # Reverse traversal lets each run use constant-time right-product steps.
    # Freeze each surviving run once, avoiding repeated copies of its axes.
    for part in reversed(parts):
        if isinstance(part, Seq):
            children = part.parts
        elif isinstance(part, _PRIMITIVE_TYPES):
            children = (part,)
        else:
            raise TypeError('seq() accepts primitive operations and Seq values')
        for child in reversed(children):
            if isinstance(child, Gate):
                if child.op.is_identity:
                    continue
                if stack and isinstance(stack[-1], (Gate, _GateRun)) and stack[-1].targ == child.targ:
                    previous = stack.pop()
                    run = previous if isinstance(previous, _GateRun) else _GateRun(previous.targ, _Accumulator(previous.op))
                    run.value.right_operator(child.op)
                    if run.value.is_identity:
                        continue
                    stack.append(run)
                    continue
            stack.append(child)
    if not stack:
        return _EMPTY
    normal = tuple(
        Gate(part.value.freeze(), part.targ) if isinstance(part, _GateRun) else part
        for part in reversed(stack)
    )
    if len(normal) == 1:
        return normal[0]
    return Seq(normal)
