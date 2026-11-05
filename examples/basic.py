"""Run from the project root with: python3 -m examples.basic."""

from collections.abc import Callable

from quantum_circuits import (
    CCZ, CZ, Apply, H, I, Node, Wire, S, T,
    Seq, X, gate, op, seq,
)


def in_h_basis(make_body: Callable[[Wire], Node], target: Wire, *,
               wires: tuple[Wire, ...] | None = None) -> Seq:
    """A higher-order constructor using only ordinary Python functions."""
    return seq(Apply(H, target), make_body(target), Apply(H, target), wires=wires)


def cnot(control: Wire, target: Wire) -> Seq:
    return in_h_basis(lambda q: CZ(control, q), target, wires=(control, target))


def toffoli(a: Wire, b: Wire, target: Wire) -> Seq:
    return in_h_basis(lambda q: CCZ(a, b, q), target, wires=(a, b, target))


def main() -> None:
    a, b, t = map(Wire, ('a', 'b', 't'))
    assert op('HH') == I
    assert op('H', 'S') == S @ H

    print('H then S:', op('H', 'S'))
    print('Two H gates:', seq(Apply(H, t), Apply(H, t)))
    print('Same target:', seq(Apply(H, t), Apply(S, t)))
    print('Different targets:', seq(Apply(H, t), Apply(S, a)))
    print('Exposed fusion:', seq(Apply(X, t), Apply(H, a), Apply(H, a), Apply(X, t)))
    print('Phase survives:', seq(gate(op(phase=1), t)))

    print('T then T:', seq(gate(T, t), gate(T, t)))
    value = op('HTSHT')
    assert value.inverse() @ value == I
    lowered = ''.join(value.iter_gates())
    assert op(lowered) == value
    print('Canonical operator:', value)
    print('Exact H/S/T decomposition:', lowered)
    print('Minimal T-count:', value.t_count)

    print('CNOT recipe:', cnot(a, t))
    circuit = toffoli(a, b, t)
    print('Toffoli recipe:', circuit)
    print('Boundary wires:', circuit.wires)
    twice = seq(circuit, circuit)
    assert twice == seq(wires=circuit.wires)
    print('Interactions after composing two Toffolis:', len(twice.vertices))


if __name__ == '__main__':
    main()
