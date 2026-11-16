# Quantum circuits

This codebase is written entirely for me.

Use it if you like it.

## What this is

A Python library for constructing and inspecting circuits for my quantum
algorithms and compiler. The planned scope includes reusable circuits,
rotation synthesis and coherent arithmetic on quantum registers.
[DESIGN.md](DESIGN.md) explains the model and its uses, including
polynomial evaluation and QSP circuits built from supplied phase angles.

Today the package provides exact single-qubit Clifford+T algebra: composition,
inverses, integer powers and H/S/T output with the minimum T count. Operators
have unique stored forms, including phase, for exact equality and hashing.

There is no circuit type, rotation synthesiser or arithmetic API yet. The
next work is preparation and measurement, followed by wire intersections.
The older circuit prototype remains in Git history.

The package and its tests use only the Python standard library.

[Current API](#current-api) · [Development](#development) ·
[Circuit design](DESIGN.md)

## Current API

The package exports `Clif`, `WireOp`, `op` and the constants `I`, `X`, `Y`,
`Z`, `H`, `S` and `T`.

### Exact operators on one qubit

A `WireOp` is an immutable, exact one-qubit Clifford+T operator, including
phase. Its constructor is `WireOp(initial: Clif, axes: str = '')`.

- `initial` is a Clifford gate, held as a `Clif`. It acts first.
- `axes` contains x, y and z, each denoting a T gate about that axis.
  They act from left to right, with no equal adjacent letters.

In matrix order:

```text
WireOp(C, 'xyz') = T_z T_y T_x C
T_z = diag(1, exp(i*pi/4))
T_x = H T_z H
T_y = S H T_z H S^-1
```

`op(*parts, phase=0)` builds a `WireOp` from strings, `Clif` values and
`WireOp` values, in execution order. Strings accept I, X, Y, Z, H, S and T;
whitespace is ignored. The integer `phase` multiplies the result by
`exp(i*pi/4)**phase` and is reduced modulo eight. The package's gate
constants are `WireOp` values.

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

| Interface | What it gives |
| --- | --- |
| `u.initial`, `u.axes` | The two stored fields. They cannot be changed |
| `a @ b` | The matrix product. It applies b and then a |
| `u.inverse()` | The exact inverse |
| `u ** n` | An integer power. Zero and negative powers work |
| `u.t_count` | The fewest T gates that any word for this operator can have |
| `u.is_clifford`, `u.is_identity` | Exact tests. They take the phase into account |
| `u.phase` | The power of `exp(i*pi/4)` in the stored form, modulo eight |
| `u.unphased()` | The operator divided by `exp(i*pi/4)**u.phase` |
| `u.iter_gates()` | A word in H, S and T, in the order the gates act. It has exactly `t_count` T gates. Each run of H and S is a shortest word for its Clifford gate |
| Equality and hashing | Two operators are equal when their stored fields are equal |
| `repr(u)` | Python code that evaluates to `u` |

`WireOp(...)` requires fields already in canonical form; use `op` to
reduce arbitrary words. Reduction uses finite tables and exact integer
arithmetic. Uniqueness and minimal T count follow from
[Giles and Selinger, Proposition 8.2](https://www.mscs.dal.ca/~selinger/papers/ma-remarks.pdf).
The emitted word need not minimise the total H and S count.

For a long word, pass all the parts to one call of `op`. Building the
operator one `@` at a time copies the growing string each time.

### Clifford values

A `Clif` is an exact Clifford gate on one qubit, phase included.
`Clif(frame, phase=0)` stands for the matrix
`omega**phase * P[pauli] * R[rep]`. Here `omega = exp(i*pi/4)` and
`frame = 4*rep + pauli`. `P` is the list `(I, X, Y, Z)`. `R` is the list
`(I, H, S, HS, SH, HSH)`, with each product written in matrix order. There
are 24 frames and eight phases, which gives 192 values.

`Clif.from_word(word, phase=0)` builds a `Clif` from a word. The letters act
in the order written. The word may contain I, X, Y, Z, H and S. Spaces are
ignored. The result is multiplied by `omega**phase`.

`op(c)` turns a `Clif` into a `WireOp`. The module
`quantum_circuits.clifford` defines its own constants `I`, `X`, `Y`, `Z`,
`H` and `S`. Those are `Clif` values. The constants exported by the package
are `WireOp` values.

A `Clif` supports `@` for the matrix product, `inverse()` and `is_identity`.
Its fields `frame`, `phase`, `rep` and `pauli` are read-only. Equality and
hashing include the phase. `repr` gives Python code that evaluates to the
value.

## Development

Use Python 3.10 or later. Run these from the project root.

```sh
python3 -m examples.basic
python3 -m unittest discover -v
python3 tools/generate_clifford_tables.py --check
```

For use from another project, optionally install in editable mode:

```sh
python3 -m pip install -e .
```

### What the tests check

- All 36,864 Clifford products against independent matrices, and
  associativity for every triple of frames.
- Distinctness of the 8,832 stored forms with up to four T gates, and
  minimal T counts against an exact matrix lower bound up to six T gates.
- Words, phases, inverses, powers, H/S/T output, input validation, hashing
  and reduction of a long word without recursion.
- The CCZ body in DESIGN.md against its exact definition, in
  `tests/test_ccz.py`.

The exact matrix reference shares basic scalar arithmetic with the table
generator, but uses neither runtime tables nor reduction code. A separate
reference uses floating-point complex matrices. These checks are bounded;
the general guarantees rest on the theorem cited above.

### Generated tables

`quantum_circuits/_clifford_tables.py` is generated. Do not edit its
entries. Change the generator, regenerate with
`python3 tools/generate_clifford_tables.py`, and then verify with `--check`.

### Style of the code

Use direct, conventional Python with explicit invariants and local mutation
where it clarifies an algorithm. [AGENTS.md](AGENTS.md) gives the full
working rules. The table generator separates exact arithmetic, table
construction and source output; it finds shortest H/S words by breadth-first
search.

### Where things are

| Location | What it holds |
| --- | --- |
| `quantum_circuits/clifford.py` | Exact Clifford values and their products |
| `quantum_circuits/operators.py` | Exact Clifford+T values, their reduction, and their output as gates |
| `quantum_circuits/_clifford_tables.py` | The generated finite tables |
| `tools/generate_clifford_tables.py` | The exact, reproducible table generator |
| `tests/test_clifford.py`, `tests/test_operators.py` | Tests of the algebra and the public interface |
| `tests/test_ccz.py` | The CCZ body as data, checked exactly |
| `tests/exact_reference.py`, `tests/reference.py` | The exact and the numerical reference matrices |
| `examples/basic.py` | A runnable example of the algebra on one qubit |
| `DESIGN.md` | Purpose, planned circuit model, arithmetic use case and external-tool context |
