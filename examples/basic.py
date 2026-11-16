"""Show exact composition, inversion, lowering, and phase bookkeeping.

Run from the project root with: python3 -m examples.basic.
"""

from quantum_circuits import H, I, S, T, clifford, op


def main() -> None:
    # Words list gates in execution order; matrix products apply the right first.
    assert op('HH') == I
    assert op('H', 'S') == S @ H
    assert op(clifford('HS')) == S @ H
    assert op('TT') == S
    assert T ** 8 == I

    print('H then S:', op('H', 'S'))
    print('Two H gates:', op('HH'))
    print('T then T:', op(T, T))
    print('T in the H basis:', H @ T @ H)

    operator = op('HTSHT')
    assert operator.inverse() @ operator == I
    gate_word = ''.join(operator.iter_gates())
    assert op(gate_word) == operator
    print('Canonical operator:', operator)
    print('Exact H/S/T decomposition:', gate_word)
    print('Minimal T-count:', operator.t_count)

    # This product is omega times identity, so its phase must survive reduction.
    scalar = (H @ S) ** 3
    assert scalar == op(phase=1)
    assert not scalar.is_identity
    assert scalar.unphased() == I
    print('Scalar phase exponent:', scalar.phase)


if __name__ == '__main__':
    main()
