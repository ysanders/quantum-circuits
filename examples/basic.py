"""Run from the project root with: python3 -m examples.basic."""

from collections.abc import Callable

from quantum_circuits import (
    CCZGate, CZGate, Gate, H, I, Node, Qubit, S, T,
    X, gate, op, seq,
)


def in_h_basis(make_body: Callable[[Qubit], Node], target: Qubit) -> Node:
    """A higher-order constructor using only ordinary Python functions."""
    return seq(Gate(H, target), make_body(target), Gate(H, target))


def cnot(control: Qubit, target: Qubit) -> Node:
    return in_h_basis(lambda q: CZGate(control, q), target)


def toffoli(a: Qubit, b: Qubit, target: Qubit) -> Node:
    return in_h_basis(lambda q: CCZGate(a, b, q), target)


def main() -> None:
    a, b, t = map(Qubit, ('a', 'b', 't'))
    assert op('HH') == I
    assert op('H', 'S') == S @ H

    print('H then S:', op('H', 'S'))
    print('Two H gates:', seq(Gate(H, t), Gate(H, t)))
    print('Same target:', seq(Gate(H, t), Gate(S, t)))
    print('Different targets:', seq(Gate(H, t), Gate(S, a)))
    print('Exposed fusion:', seq(Gate(X, t), Gate(H, a), Gate(H, a), Gate(X, t)))
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
    print('Referenced qubits:', sorted(q.name for q in circuit.qubits))


if __name__ == '__main__':
    main()
