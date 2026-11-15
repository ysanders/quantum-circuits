"""Build an adder and inspect its graph: python3.14 -m examples.arithmetic."""

from collections import Counter

from quantum_circuits import Wire
from quantum_circuits.arithmetic import cuccaro_add


def main() -> None:
    # Demonstrate a reusable arithmetic recipe with caller-supplied registers.
    # Registers are ordered from the least to the most significant bit.
    width = 4
    a = tuple(Wire(f'a{i}') for i in range(width))
    b = tuple(Wire(f'b{i}') for i in range(width))
    carry, overflow = Wire('carry'), Wire('overflow')

    for output in (None, overflow):
        body = cuccaro_add(a, b, carry, overflow=output)
        print('With overflow output:' if output is not None else 'Modulo 16:')
        print('  Wires:', tuple(w.name for w in body.wires))
        print('  Intersections:', dict(Counter(v.kind for v in body.vertices)))


if __name__ == '__main__':
    main()
