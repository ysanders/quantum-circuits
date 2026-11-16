# Quantum circuits

This codebase is written entirely for me.

Use it if you like it.

The package currently provides **exact single-qubit Clifford+T algebra**:
canonical immutable operators, composition, inversion, integer powers,
scalar phases, and H/S/T decompositions with minimal T-count. Runtime and
tests use only the Python standard library.

There is no circuit type yet. [DESIGN.md](DESIGN.md) records the library's
purpose, the foundation for a circuit type, a checked CCZ example, and the
open questions. The old graph prototype remains in Git history.

[Current API](#current-api) · [Development](#development) ·
[Circuit design](DESIGN.md)

## Current API

The top-level exports are `Clif`, `WireOp`, `op`, and
`I`, `X`, `Y`, `Z`, `H`, `S`, `T`.

### Exact single-qubit operators

`WireOp(initial: Clif, axes: str = '')` is an immutable canonical exact
Clifford+T operator, including global phase. The initial Clifford acts first;
the lowercase axis letters execute left to right, with no equal adjacent
letters. In matrix order:

```text
WireOp(C, 'xyz') = T_z T_y T_x C
T_z = diag(1, exp(i*pi/4))
T_x = H T_z H
T_y = S H T_z H S^-1
```

`op(*parts, phase=0)` normalizes strings, `Clif` values, and `WireOp`
values in execution order. Strings accept I/X/Y/Z/H/S/T and ignore whitespace.
The integer phase multiplies by `exp(i*pi/4)**phase` and is reduced modulo
eight. The top-level constants I/X/Y/Z/H/S/T are all `WireOp` values.

```python
from quantum_circuits import Clif, H, I, S, T, op

assert op("HS") == S @ H
assert op(Clif.from_word("HS")) == S @ H
assert op("TT") == S
assert T.inverse() @ T == I
assert T ** 8 == I
assert (H @ S) ** 3 == op(phase=1)
assert not op(phase=1).is_identity

u = op("HTSHT")
word = "".join(u.iter_gates())
assert op(word) == u
assert word.count("T") == u.t_count
```

| Interface | Contract |
| --- | --- |
| `u.initial`, `u.axes` | Frozen canonical fields |
| `a @ b` | Matrix product: apply b, then a |
| `u.inverse()` | Exact inverse/adjoint |
| `u ** n` | Integer power, including zero and negative powers |
| `u.t_count` | Minimal T-count for this isolated exact operator |
| `u.is_clifford`, `u.is_identity` | Exact predicates, including phase |
| `u.phase` | The exponent of the scalar factor in the canonical form, modulo eight |
| `u.unphased()` | The operator divided by `exp(i*pi/4)**u.phase` |
| `u.iter_gates()` | H/S/T word in execution order, with exactly `t_count` T gates; each run of H and S is a shortest word for its Clifford |
| Equality and hashing | Exact equality of canonical fields |
| `repr(u)` | An expression that evaluates to `u` |

Raw construction validates canonical fields; use `op` to normalize arbitrary
words. The emitted Clifford count need not be minimal. Runtime normalization
uses finite tables and exact integer operations. Its uniqueness and T-optimality
come from [Giles and Selinger, Proposition 8.2](https://www.mscs.dal.ca/~selinger/papers/ma-remarks.pdf).
For long words, batch parts into `op(*parts)`; repeatedly extending immutable
strings through composition incurs avoidable copying.

### Clifford values

`Clif(frame, phase=0)` supplies the supporting Clifford algebra. It denotes
`omega**phase * P[pauli] * R[rep]`, where `frame = 4*rep + pauli`,
`P = (I, X, Y, Z)`, and `R = (I, H, S, HS, SH, HSH)` in matrix order.
There are 24 frames and eight phases, hence 192 exact values.
`Clif.from_word(word, phase=0)` reduces a word in execution order and
multiplies by `omega**phase`; words accept I/X/Y/Z/H/S and ignore whitespace.
`op(c)` promotes a Clifford. Constants in `quantum_circuits.clifford`
have type `Clif`, unlike the top-level `WireOp` constants.

`Clif` also supports exact matrix multiplication with `@`, `inverse()`,
`is_identity`, and the read-only `frame`, `phase`, `rep`, and `pauli` fields.
Equality and hashing include the scalar phase. `repr` gives an expression
that evaluates to the value.

## Development

Use Python 3.10 or later. From the project root:

```sh
python3 -m examples.basic
python3 -m unittest discover -v
python3 tools/generate_clifford_tables.py --check
```

An editable installation is optional for importing from another project:

```sh
python3 -m pip install -e .
```

The tests check all 36,864 exact Clifford products against independent
numerical matrices, all frame triples for associativity, and 8,832 canonical
Clifford+T values for exact uniqueness through four T gates. They also check
short words exactly, scalar phases, inverses, powers, H/S/T lowering,
validation, hashing, and long-word normalization without recursion.
For canonical values through six T gates they compare `t_count` with a lower
bound computed from the exact matrix alone. `tests/test_ccz.py` compares the
CCZ body in DESIGN.md with the definition of CCZ.

The exact matrix oracle is independent of runtime tables and normalization,
while sharing the generator's elementary scalar arithmetic. A separate
numerical oracle uses conventional complex matrices. These are bounded
regression checks; the general normal-form guarantees rely on the cited
mathematical result.

`quantum_circuits/_clifford_tables.py` is generated. Change the generator
rather than editing entries, regenerate with
`python3 tools/generate_clifford_tables.py`, then verify with `--check`.

Keep implementations direct and explicit: ordinary functions, frozen values,
clear invariants, and local mutation where it makes an algorithm easier to
follow. The runtime accumulator documents its matrix-order stack invariant.
The table generator separates exact scalar and matrix arithmetic, finite-table
construction, and source rendering; it uses breadth-first search for H/S words.
The test oracles construct conventional matrices independently of those tables.
[AGENTS.md](AGENTS.md) records the development guidance.

| Location | Responsibility |
| --- | --- |
| `quantum_circuits/clifford.py` | Exact Clifford values and composition |
| `quantum_circuits/operators.py` | Exact Clifford+T values, normalization, and lowering |
| `quantum_circuits/_clifford_tables.py` | Generated finite tables |
| `tools/generate_clifford_tables.py` | Exact, reproducible table generation |
| `tests/test_clifford.py`, `tests/test_operators.py` | Algebra and public API checks |
| `tests/test_ccz.py` | The CCZ body as data, checked exactly |
| `tests/exact_reference.py`, `tests/reference.py` | Exact and numerical matrix oracles |
| `examples/basic.py` | Runnable single-qubit algebra example |
| `DESIGN.md` | Purpose, circuit foundation, CCZ example, open questions |
