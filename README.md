# Quantum circuits

This codebase is written entirely for me.

Use it if you like it.

## What this is

This is a Python library for large quantum circuits. The circuits it is
meant for are built from subcircuits that are used many times. The library
will store each subcircuit once. That part is planned.
[DESIGN.md](DESIGN.md) explains the purpose and the plan.
[BACKEND.md](BACKEND.md) describes the tools that will consume the circuits.

The code that exists today works on one qubit. It handles every operator
that can be built from the gates H, S and T. These are called Clifford+T
operators.

- **It is exact.** No number is rounded. The overall phase is kept.
- **Each operator has one stored form.** Two operators are equal exactly
  when their stored forms are equal.
- **It does algebra.** It multiplies operators, inverts them and raises them
  to integer powers.
- **It writes an operator back out as gates.** The output is a sequence of
  H, S and T with the fewest possible T gates.

The code and its tests need only the Python standard library.

There is no type for a circuit yet. An older prototype of a circuit graph
remains in the Git history.

[Current API](#current-api) · [Development](#development) ·
[Circuit design](DESIGN.md) · [Backend tools](BACKEND.md)

## Current API

The package exports `Clif`, `WireOp`, `op` and the constants `I`, `X`, `Y`,
`Z`, `H`, `S` and `T`.

### Exact operators on one qubit

A `WireOp` is an exact Clifford+T operator on one qubit, phase included. The
constructor is `WireOp(initial: Clif, axes: str = '')`. A value never
changes after it is made. It has two fields.

- `initial` is a Clifford gate, held as a `Clif`. It acts first.
- `axes` is a string of the letters x, y and z. Each letter is one T gate
  about that axis. The letters act from left to right. No letter appears
  twice in a row.

As a matrix product, the fields mean this.

```text
WireOp(C, 'xyz') = T_z T_y T_x C
T_z = diag(1, exp(i*pi/4))
T_x = H T_z H
T_y = S H T_z H S^-1
```

`op(*parts, phase=0)` builds a `WireOp` from parts. A part is a string, a
`Clif` or a `WireOp`. The parts act in the order given. A string may contain
the letters I, X, Y, Z, H, S and T. Spaces are ignored. `phase` is an
integer. It multiplies the result by `exp(i*pi/4)**phase` and is taken
modulo eight. The constants `I`, `X`, `Y`, `Z`, `H`, `S` and `T` exported by
the package are `WireOp` values.

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

Calling `WireOp(...)` directly checks that the fields are already in the
stored form. Use `op` to build an operator from any word.

The word from `iter_gates` uses the fewest T gates. It may not use the
fewest H and S gates.

The library reduces a word with finite tables and exact integer arithmetic.
The stored form is unique, and it uses the fewest T gates. Both facts come
from [Giles and Selinger, Proposition 8.2](https://www.mscs.dal.ca/~selinger/papers/ma-remarks.pdf).

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

To import the package from another project, install it in editable mode.
This step is optional.

```sh
python3 -m pip install -e .
```

### What the tests check

- All 36,864 products of two Clifford values, against matrices computed
  independently.
- Associativity, for every triple of frames.
- That the 8,832 stored forms with up to four T gates are all different
  operators.
- Short words, phases, inverses and powers.
- The output in H, S and T.
- The checking of inputs, and hashing.
- That a long word is reduced without recursion.
- That `t_count` meets a lower bound for stored forms with up to six T
  gates. The bound is computed from the exact matrix alone.
- That the CCZ body in DESIGN.md equals the definition of CCZ. This test is
  `tests/test_ccz.py`.

The tests use two independent references. The first computes exact matrices.
It shares only basic scalar arithmetic with the table generator. It does not
use the library's tables or its reduction code. The second uses ordinary
complex matrices in floating point.

These tests cover a bounded set of cases. The general guarantees rest on the
theorem cited above.

### Generated tables

`quantum_circuits/_clifford_tables.py` is generated. Do not edit its
entries. Change the generator, regenerate with
`python3 tools/generate_clifford_tables.py`, and then verify with `--check`.

### Style of the code

The code is meant to be direct. It uses ordinary functions and values that
do not change. It states its invariants. It changes local state where that
makes an algorithm easier to follow.

The table generator keeps three jobs apart. It does exact arithmetic, builds
the finite tables, and writes the source file. It finds the shortest words
in H and S by breadth-first search.

[AGENTS.md](AGENTS.md) records the guidance for anyone who works on the
code.

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
| `DESIGN.md` | The purpose, the plan for circuits, the CCZ example and the open questions |
| `BACKEND.md` | The tools that will consume the circuits, and what the library offers them |
