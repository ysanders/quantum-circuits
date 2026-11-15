"""Run from the project root with: python3 -m examples.basic."""

from quantum_circuits import H, I, S, T, clifford, op


def main() -> None:
    assert op('HH') == I
    assert op('H', 'S') == S @ H
    assert op(clifford('HS')) == S @ H
    assert op('TT') == S
    assert T ** 8 == I

    print('H then S:', op('H', 'S'))
    print('Two H gates:', op('HH'))
    print('T then T:', op(T, T))
    print('T in the H basis:', H @ T @ H)

    value = op('HTSHT')
    assert value.inverse() @ value == I
    lowered = ''.join(value.iter_gates())
    assert op(lowered) == value
    print('Canonical operator:', value)
    print('Exact H/S/T decomposition:', lowered)
    print('Minimal T-count:', value.t_count)

    scalar = (H @ S) ** 3
    assert scalar == op(phase=1)
    assert not scalar.is_identity
    assert scalar.unphased() == I
    print('Scalar phase exponent:', scalar.phase)


if __name__ == '__main__':
    main()
