# Quantum circuits

A personal compiler front end built from small, immutable Python values.
Write circuit constructors as ordinary Python functions; inspect and transform
their returned data separately.

The foundation provides canonical, exact single-qubit Clifford+T operators
and local circuit composition. Python 3.10 or later; no runtime or test
dependencies beyond the standard library.

## Start here

From this directory, without installation:

```sh
python3 -m examples.basic
python3 -m unittest discover -v
```

```python
from quantum_circuits import Qubit, H, I, S, T, op, gate, seq

q = Qubit('q')
assert op('HS') == S @ H
assert op('HTH') == H @ T @ H
assert op('TT') == S
assert T.inverse() @ T == I
assert seq(gate(T, q), gate(T, q)) == gate(S, q)

u = op('HTSHT')
assert op(''.join(u.iter_gates())) == u
```

`op` and `seq` use **execution order**. `@` is matrix multiplication, so its
right operand acts first. All phases are retained. Equivalent single-qubit
operators have identical canonical fields and compare equal; frozen dataclasses
supply hashing automatically.

## Project layout

| Location | Purpose |
| --- | --- |
| `quantum_circuits/operators.py` | `SingleQubitOperator`, normalisation, constructors, and lowering |
| `quantum_circuits/clifford.py` | Supporting exact Clifford algebra |
| `quantum_circuits/model.py` | Qubits, gates, and normalising `seq` |
| `examples/basic.py` | Runnable examples, including higher-order constructors |
| `tests/` | Exact and numerical matrix checks, plus interface tests |
| `tools/generate_clifford_tables.py` | Reproducible exact tables and H/S words |
| [docs/core.md](docs/core.md) | Complete interface and representation reference |
| [DESIGN.md](DESIGN.md) | Implementation boundaries and further work |

Check the generated tables with:

```sh
python3 tools/generate_clifford_tables.py --check
```

An editable installation is optional, for importing from another project:

```sh
python3 -m pip install -e .
```

## Migration from the Clifford-only core

`SingleQubitOperator` is now the central value type. Top-level `I`, `X`, `Y`,
`Z`, `H`, `S`, and `T` are all operator values. Replace `Clif(c, q)` with
`gate(op(c), q)`, and `TGate(q)` with `gate(T, q)`. Use `op` for ordinary word
construction. The `clifford` helper remains available for the supporting
`SingleQubitClifford` type; promote its result explicitly with `op`.

Circuit nodes are `Gate`, `CZGate`, `CCZGate`, and `Seq`. `seq` combines adjacent
same-wire single-qubit operators. Whole-circuit equality remains structural
after those local reductions.

Contracts, named fragments, repetition, measurement and classical control,
arbitrary-rotation approximation, and backend export remain future work.
