# Core reference

All public value dataclasses are frozen and slotted. The runtime uses exact
integers and finite tables; floating-point arithmetic occurs only in tests.

## SingleQubitOperator

```python
@dataclass(frozen=True, slots=True, repr=False)
class SingleQubitOperator:
    initial: SingleQubitClifford
    axes: str = ''
```

The value denotes `T[axes[-1]] ... T[axes[0]] initial`: apply the initial
Clifford first, then the axes in string order. The exact matrices are
`T_z = T = diag(1, exp(i*pi/4))`, `T_x = H T H`, and
`T_y = S H T H S^-1`. These equations use matrix order. Each axis gate
includes the conventional T gate's scalar phase.

Axes contain only lowercase `x`, `y`, `z`, with unequal adjacent letters.
Empty axes represent a pure Clifford. These fields uniquely represent each
exact single-qubit Clifford+T operator, including global phase. The basis is
Giles and Selinger, *Remarks on Matsumoto and Amano's normal form for
single-qubit Clifford+T operators*, Proposition 8.2
([paper](https://www.mscs.dal.ca/~selinger/papers/ma-remarks.pdf)).
Its conjugated T definitions agree exactly with the ones above.

Raw construction validates canonical data. Incorrect field types raise
`TypeError`; invalid or repeated axes raise `ValueError`. Use `op` to
normalise words. There is no artificial length bound.

### Construction

```python
def op(
    *parts: str | SingleQubitClifford | SingleQubitOperator,
    phase: int = 0,
) -> SingleQubitOperator: ...
```

Parts execute left to right. Strings accept uppercase `I`, `X`, `Y`, `Z`,
`H`, `S`, `T`, ignoring whitespace. Unknown letters raise `ValueError`;
unsupported types raise `TypeError`. `phase` is an integer (not a Boolean),
reduced modulo eight; it multiplies the whole result by `omega**phase`,
where `omega = exp(i*pi/4)`.

```python
op()                         # exact identity
op('HTH')                    # H, then T, then H
op(H, T, H)                  # the same value
op('HS', T, 'SH')             # mixed words and values
op(clifford('HS'))            # explicit Clifford promotion
op(phase=1)                  # omega I
op('HT', phase=-1)           # omega^-1 times the specified word
```

All top-level constants `I`, `X`, `Y`, `Z`, `H`, `S`, `T` have type
`SingleQubitOperator`. An operator is independent of qubit names.

### Operations and properties

| Interface | Contract |
| --- | --- |
| `u.initial`, `u.axes` | Immutable canonical fields |
| `u.t_count` | `len(u.axes)`, minimal T-count for the isolated exact operator |
| `u.is_clifford` | Whether axes are empty |
| `u.is_identity` | Empty axes and an initial Clifford exactly equal to I |
| `a @ b` | Apply b, then a; returns a canonical operator |
| `u.inverse()` | Exact inverse/adjoint, in canonical form |
| `u ** n` | Integer power; zero gives I, negative powers use the inverse |
| `u.iter_gates()` | Lazy exact H/S/T decomposition in execution order |
| `repr(u)` / `str(u)` | Diagnostic phase/representative/Pauli/axes form |
| `u == v`, `hash(u)` | Generated dataclass equality and hashing of canonical fields |

`@` accepts only operators; promote other inputs with `op`. Unsupported
operands follow Python's `NotImplemented` protocol. Powers require integers
excluding Booleans; modular three-argument `pow` is not supported.

`iter_gates` emits exactly `t_count` T letters. It realises scalar phases
with H/S gates, so there is no external phase record. Its Clifford count
need not be minimal; identity emits nothing.

```python
assert op('TT') == S
assert T ** 8 == I
assert (H @ S) ** 3 == op(phase=1)
u = op('HTSHT')
assert u.inverse() @ u == I
assert op(''.join(u.iter_gates())) == u
```

`repr(op('HTH'))` is
`SingleQubitOperator(phase=0, rep=0, pauli=0, axes='x')`.
The Clifford coordinates describe `initial`; this diagnostic representation
is not an evaluable constructor expression. The operator itself is a suitable
dictionary key. Equal operators hash equally; Python hashes may collide and
are not persistent identifiers.

### Normalisation algorithm

A private accumulator stores an initial Clifford C and an axis stack in
matrix order. Read inputs backwards and right-multiply factors. A Clifford
factor changes only C. For T_a, look up the signed axis in `C P_a C^-1`.
The exact reductions are:

```text
C T_a = T_(+/-b) C
T_-b = T_b (omega S_b^-1)
T_b T_b = S_b, where S_b = T_b**2
```

Absorb the negative-axis correction into C. Push b unless it matches the
stack top; then pop and absorb S_b. Each factor needs bounded table work
without rescanning. Freeze the string once. Word normalisation, composition
of two operators, and inversion take time linear in input size.

Repeated immutable extensions still copy their strings: prefer `op(*parts)`
to a loop of `@` calls for a large word. `seq` uses mutable accumulators for
adjacent runs and freezes them once.

## Supporting Clifford algebra

`SingleQubitClifford(frame, phase=0)` denotes

```text
omega**phase * P[pauli] * R[rep]
frame = 4*rep + pauli
P = (I, X, Y, Z)
R = (I, H, S, HS, SH, HSH)
```

Labels below use matrix order, with the rightmost factor acting first.

| rep | Representative | pauli=0 | pauli=1 | pauli=2 | pauli=3 |
| --- | --- | --- | --- | --- | --- |
| 0 | I | 0: I | 1: X | 2: Y | 3: Z |
| 1 | H | 4: H | 5: XH | 6: YH | 7: ZH |
| 2 | S | 8: S | 9: XS | 10: YS | 11: ZS |
| 3 | HS | 12: HS | 13: XHS | 14: YHS | 15: ZHS |
| 4 | SH | 16: SH | 17: XSH | 18: YSH | 19: ZSH |
| 5 | HSH | 20: HSH | 21: XHSH | 22: YHSH | 23: ZHSH |

Frame is an integer in `range(24)`; phase is an integer reduced modulo eight.
Booleans are rejected. There are 192 exact values. `rep`, `pauli`,
`is_identity`, `@`, `inverse`, and `from_word` retain their existing meanings.
`clifford(*parts)` accepts strings and Clifford values in execution order,
using I/X/Y/Z/H/S. Submodule constants retain the Clifford type; top-level
constants use the operator type. `op(c)` promotes a Clifford.

Products, inverses, and constructors reuse the small Clifford pool. Generated
tables include phase corrections, signed Pauli actions, and exact H/S words.
The generator uses rational Q(sqrt(2), i) arithmetic; runtime only imports data.

## Circuit nodes

`Qubit(name: str)` identifies a wire by name. Equal names mean the same wire;
callers choose fresh names when needed. Repr quotes and escapes the name.

| Node or constructor | Meaning |
| --- | --- |
| `Gate(op, targ)` | Apply a SingleQubitOperator to a Qubit |
| `gate(value, targ)` | Construct a Gate from a string or operator |
| `CZGate(a, b)` | Negate amplitudes with both bits one |
| `CCZGate(a, b, c)` | Negate amplitudes with all three bits one |
| `Seq(parts)` | A validated tuple of locally normalised leaves |
| `seq(*parts)` | Normalise composition in execution order |

`gate` accepts strings and operators only; use `gate(op(c), q)` for a raw
Clifford. It retains identity until `seq` removes it. CZ/CCZ operands are
distinct Qubits, sorted by name for equality and hashing. `Primitive` names
the three leaf-node types; one Gate may contain many hardware primitives.
`Node` is `Primitive | Seq`.

`seq` flattens sequences, removes exact identities, and fuses adjacent
same-wire Gates. Cancellations can expose further fusion. Empty returns
`Seq(())`; a singleton returns its child. Phase-only operators survive.
Different wires and CZ/CCZ boundaries retain their order.

```python
assert seq(gate(T, q), gate(T, q)) == gate(S, q)
assert seq(gate(H, q), gate(T, q), gate(H, q)) == gate('HTH', q)
assert seq(gate(H, q), gate(H, q)) == seq()
```

Direct Seq construction rejects lists, nesting, singletons, identity gates,
and fusible neighbours. Circuit equality is structural after these local
rules, not a decision procedure for arbitrary multi-qubit equivalence.

Every node has a computed `.qubits` frozenset. This describes referenced
wires, not ownership or a declared interface. Cancelling H-H leaves no
referenced wires, even if a future enclosing contract declares a parameter.

## Verification

Run `python3 -m unittest discover -v`. Coverage includes:

- All 36,864 Clifford products and all 24-cubed frame associativity cases.
- Exact matrix uniqueness for all 8,832 canonical values through four T gates.
- Exact comparison of every H/S/T word through length six.
- Inverses and H/S/T decompositions for all 4,224 canonical values through three T gates.
- Signed-axis phase corrections, seeded random words and composition checks.
- Long words and same-wire runs, and complete three-qubit matrices before
  and after sequence normalisation.

The exact oracle constructs matrices independently of runtime tables and
normalisation, reusing only the generator's scalar arithmetic. A separate
numerical oracle uses conventional complex matrices. Bounded tests check
regressions; the general uniqueness and T-optimality guarantees come from
the normal-form theorem.
