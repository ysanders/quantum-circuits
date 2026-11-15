"""Reversible arithmetic recipes built from the existing circuit primitives."""

from collections.abc import Sequence

from .model import Apply, CCZ, CZ, Seq, Wire, _require_wires, seq
from .operators import H


def cnot(control: Wire, target: Wire) -> Seq:
    """Flip target when control is one, preserving computational-basis phases."""
    return seq(Apply(H, target), CZ(control, target), Apply(H, target),
               wires=(control, target))


def toffoli(a: Wire, b: Wire, target: Wire) -> Seq:
    """Flip target when both controls are one."""
    return seq(Apply(H, target), CCZ(a, b, target), Apply(H, target),
               wires=(a, b, target))


def maj(a: Wire, b: Wire, carry: Wire) -> Seq:
    """Write majority(a, b, carry) into a, and XOR the original a into b/carry.

    This is the Cuccaro adder's forward carry step. The outgoing carry is a.
    """
    return seq(cnot(a, b), cnot(a, carry), toffoli(b, carry, a),
               wires=(a, b, carry))


def uma(a: Wire, b: Wire, carry: Wire) -> Seq:
    """Undo MAJ's carry computation while writing the sum bit into b.

    Following maj(a, b, carry), this restores a and carry and replaces b by
    a XOR b XOR carry, using their values before MAJ. UMA is not MAJ's inverse.
    """
    return seq(toffoli(b, carry, a), cnot(a, carry), cnot(carry, b),
               wires=(a, b, carry))


def cuccaro_add(
    a: Sequence[Wire], b: Sequence[Wire], carry: Wire, *,
    overflow: Wire | None = None,
) -> Seq:
    """Add a and the incoming carry into b, restoring a and carry.

    Registers are nonempty, equally wide, and least-significant bit first.
    All supplied wires must be distinct. If their initial values are A, B, c,
    then b finishes as (A + B + c) modulo 2**len(a). If supplied, overflow is
    XORed with the outgoing carry; its initial value need not be zero.

    Use carry in |0> for ordinary addition. The circuit also works coherently
    for carry in |1> or a superposition. No preparation is performed here.
    The boundary order is (*a, *b, carry[, overflow]).

    This is the basic MAJ/UMA ripple from Cuccaro et al., quant-ph/0410184,
    section 2. It builds an explicit O(n)-size Seq for inspection and rewriting.
    """
    if not isinstance(a, Sequence) or not isinstance(b, Sequence):
        raise TypeError('registers must be ordered sequences of wires')
    a, b = tuple(a), tuple(b)
    if not a or len(a) != len(b):
        raise ValueError('registers must have the same nonzero width')
    wires = (*a, *b, carry) + (() if overflow is None else (overflow,))
    _require_wires(*wires)

    parts = []
    for i in range(len(a)):
        parts.append(maj(a[i], b[i], carry if i == 0 else a[i - 1]))
    if overflow is not None:
        parts.append(cnot(a[-1], overflow))
    for i in reversed(range(len(a))):
        parts.append(uma(a[i], b[i], carry if i == 0 else a[i - 1]))
    return seq(*parts, wires=wires)
