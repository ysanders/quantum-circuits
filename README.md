# Quantum circuits

This codebase is written entirely for me.

Use it if you like it.

## What this is

A Python library that serves as a lowering target for my quantum compiler.
Circuits are built from shared definitions, so a consumer can walk one
without expanding it and extract it to Qualtran, Cirq, Qiskit or another
library. [DESIGN.md](DESIGN.md) explains the model and its uses, including
polynomial evaluation.

Today the package provides the exact single-qubit Clifford+T algebra that
will label wire segments: composition, inverses, integer powers and H/S/T
output with the minimum T count. Operators have unique stored forms,
including phase, for exact equality and hashing.

A `Circuit` holds wires that meet at CZ vertices. A wire can start by
preparing `|0>` and end with a measurement in the computational basis.

It also provides `quantum_circuits.stream`, which parses, checks and expands
the stream: the text format that fixes what a circuit means.

Circuits cannot share subcircuit definitions yet, and there is no rotation
synthesiser or arithmetic API. The older circuit prototype remains in Git
history.

The package and its tests use only the Python standard library.

[Current API](#current-api) · [Development](#development) ·
[Circuit design](DESIGN.md)

## Current API

The package exports `Clif`, `WireOp`, `op`, `Circuit`, `CircuitBuilder`
and the gate constants `I`, `X`, `Y`, `Z`, `H`, `S` and `T`.

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

### Circuits

A `Circuit` holds wires that meet at CZ vertices. `CircuitBuilder(n)`
starts `n` wires at input ports and appends operations in execution order:

- `prepare()` adds a wire that starts by preparing `|0>`, and returns its
  index.
- `apply(u, w)` applies the `WireOp` `u` to wire `w`.
- `cz(a, b)` applies CZ to two distinct wires.
- `measure(w)` ends wire `w` with a measurement in the computational basis.
  The wire takes no further operations.
- `build()` freezes the operations so far into a `Circuit`.

A circuit stores `segments[w]`, the operators on wire `w` before, between
and after its vertices, and `vertices`, the CZ wire pairs `(a, b)` with
`a < b`. `prepared` and `measured` are frozensets of wire indices. Input
port `i` belongs to the `i`-th wire in `input_wires`. Every wire ends at an
output port, in wire order, which is classical if the wire was measured.
`inputs` and `outputs` give the port kinds.

`vertices` are stored in a fixed time order, described in
[DESIGN.md](DESIGN.md#one-qubit-processing-and-intersections), so circuits
that differ only in the order of commuting CZs are equal.
`to_stream(names=None)` gives the circuit as a checked stream, with wires
named `q0`, `q1` and so on unless `names` is given. The stream drops global
phase.

`quantum_circuits.circuit.lower_operator(u, qubit)` gives the stream
records for one operator. CLIF and T records alternate, with at most one
CLIF between T gates and exactly `u.t_count` T gates.

```python
from quantum_circuits import CircuitBuilder, H
from quantum_circuits.stream import format_stream

builder = CircuitBuilder(1)
ancilla = builder.prepare()
builder.apply(H, ancilla)
builder.cz(0, ancilla)
builder.apply(H, ancilla)
builder.measure(ancilla)
circuit = builder.build()
assert circuit.outputs == ("q", "c")
lines = format_stream(circuit.to_stream()).splitlines()
expected = ["PREP q1", "CLIF 4 q1", "CZ q0 q1", "CLIF 4 q1", "MEAS q1"]
assert lines[1:6] == expected
```

### The stream

`quantum_circuits.stream` reads, checks and expands the text format in
[DESIGN.md](DESIGN.md#stream). The package does not re-export it.

- `parse_stream(text)` turns stream text into a tuple of records. It checks
  the format, not the rules.
- `format_stream(records)` writes records as stream text.
- `assign_digests(records)` replaces placeholder labels with digests and
  checks every other rule.
- `check_stream(records)` checks every rule, including that each label is
  its definition's digest. It returns a `Program`, which holds each
  `Definition` in canonical form, in the order they end, root last.
- `expand(program)` replaces every use by its definition's body. It returns
  a `FlatCircuit` of operation records, named 0, 1, 2 and so on.

A stream that breaks the format or a rule raises `StreamError`, a
`ValueError` that names the offending line or record. Records are frozen
dataclasses: `CliffordGate`, `TGate`, `CZGate`, `Prepare`, `Measure`,
`ClassicalOp`, `Discard`, `Report`, `Start`, `End` and `Request`. Name lists
hold `Port(kind, name)` values, with kind `QUANTUM` (`'q'`) or `CLASSICAL`
(`'c'`).

```python
from quantum_circuits.stream import (
    assign_digests, check_stream, expand, format_stream, parse_stream,
)

text = (
    "START <root> (q:x)\n"
    "START <work> (q:x)\n"
    "PREP w\n"
    "CZ x w\n"
    "MEAS w\n"
    "DISCARD w\n"
    "END <work> (q:x)\n"
    "REQUEST <work> (q:x) (q:x)\n"
    "END <root> (q:x)\n"
)
program = check_stream(assign_digests(parse_stream(text)))
assert len(program.definitions) == 2
flat = expand(program)
assert format_stream(flat.operations).splitlines()[4:6] == ["PREP 2", "CZ 0 2"]
```

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
- The CCZ body in DESIGN.md, built with `CircuitBuilder`, against its exact
  definition: the stored circuit with phase, and its stream up to global
  phase, in `tests/test_ccz.py`.
- Circuits in `tests/test_circuit.py`: the builder's rules, the canonical
  vertex order, boundaries and streams.
- The lowering of every operator with at most three T gates, against
  independent exact matrices up to phase, in `tests/test_lowering.py`.
- The stream in `tests/test_stream.py`: text round trips, a digest computed
  independently from DESIGN.md's encoding, digests that ignore names,
  expansion with fresh names, and one stream breaking each rule.

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
| `quantum_circuits/circuit.py` | Circuits of intersecting wires, their builder, and their lowering to the stream |
| `quantum_circuits/stream.py` | Stream records, text, checker, digests and expansion |
| `tools/generate_clifford_tables.py` | The exact, reproducible table generator |
| `tests/test_clifford.py`, `tests/test_operators.py` | Tests of the algebra and the public interface |
| `tests/test_ccz.py` | The CCZ body, built and checked exactly |
| `tests/test_circuit.py` | Tests of the builder, vertex order, boundaries and streams |
| `tests/test_lowering.py` | Tests of lowering operators to stream records |
| `tests/test_stream.py` | Tests of the stream format, rules and expansion |
| `tests/exact_reference.py`, `tests/reference.py` | The exact and the numerical reference matrices |
| `examples/basic.py` | A runnable example of the algebra on one qubit |
| `DESIGN.md` | Purpose, planned circuit model, the stream, arithmetic use case and external-tool context |
