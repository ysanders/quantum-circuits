# Working on quantum-circuits

Read [README.md](README.md) for the implemented API and
[DESIGN.md](DESIGN.md) for purpose, mathematics and planned work.
This file gives instructions for changing the repository.

## Purpose and scope

Build a small Python library for the author's quantum algorithms and
compiler. It must construct, inspect and manipulate circuits, sharing
subcircuit definitions across uses on different registers.

The intended scope is:

- Circuit representation, construction and shared definitions.
- Rotation synthesis: approximate a specified single-qubit rotation to a
  requested accuracy using Clifford+T gates.
- Coherent arithmetic constructors, including polynomial evaluation on
  quantum registers. Python builds the circuit; the quantum computer
  performs the arithmetic.

For quantum signal processing (QSP), accept phase angles computed by an
external library. Physical layout, scheduling and machine resource
estimation also belong to external tools. Their authors write adapters;
backend requirements do not determine this library's mathematical model.

## Current state and next work

Only exact single-qubit Clifford+T algebra exists. The public exports are
`Clif`, `WireOp`, `op`, `I`, `X`, `Y`, `Z`, `H`, `S` and `T`.
Circuit types, rotation synthesis and arithmetic constructors are planned.

Next add single-qubit preparation and measurement, then wire intersections.
The measurement output contract remains open. The old graph and arithmetic
recipes in Git history are references, not requirements for the new model.

## Working rules

- Stay within the requested task. Long-term design goals do not authorise
  unrelated implementation work.
- Ask a focused question when an algorithm's meaning or an interface's
  intent is unclear. Do not turn an assumption into a design premise.
- Explain and settle design departures and open questions before
  implementing them. Routine work within agreed scope needs no approval.
- Use ordered local ports and explicit occurrence bindings. Caller wire
  names must not enter a definition's identity.
- Preserve exact unitary phase, boundary order and measurement dependencies.
- Separate graph validity from simplification. Do not restore the old
  normalisation requirements as validity rules.
- Keep primitive preparation and measurement single-qubit, and the
  elementary unitary intersection binary CZ. Larger operations have bodies.
- Develop through concrete circuits. Permutation-invariant hashing must
  not delay construction.
- Keep README.md about available code and DESIGN.md about rationale,
  examples, open questions and external tools. Label proposals and never
  document an unimplemented name as an import.

## Student style

Write as an undergraduate answer key: use conventional constructions that
make the mathematics and algorithm plain.

- **Values and objects.** Prefer functions, frozen dataclasses and ordinary
  collections. Use classes when they clarify related state and behaviour;
  methods, local mutation and small mutable builders are welcome.
- **Names and flow.** Use descriptive names, simple control flow and
  explicit intermediate values or loops where they help the reader.
- **Invariants.** State them and explain non-obvious preservation steps.
  Comments should explain mathematics, ordering or design choices.
- **Functions.** Give each one a clear job. Add helpers for concrete
  operations, not speculative extension points. Avoid generic frameworks,
  metaprogramming and deep inheritance.
- **Efficiency.** Build results locally and freeze once. Avoid copying a
  growing circuit or operator string at every step. Use readable efficient
  algorithms; explain why a non-obvious optimisation is needed and correct.
- **Inputs.** Validate public boundaries and reject malformed values with
  useful errors. Do not silently coerce them. Keep annotations and
  docstrings concrete.
- **Exactness.** Preserve exact arithmetic and phase. Floating point can
  provide independent test evidence, not replace an exact identity.
- **Existing code.** Do not rewrite sound code solely to change its paradigm.

Apply these criteria to the Clifford table generator too. Choose functions
or classes according to which explains its calculations most clearly.

## Checks and generated data

Use Python 3.10 or later and the standard library. Add a dependency only for
a concrete need.

For code changes, run from the repository root:

```sh
python3 -m unittest discover -v
python3 tools/generate_clifford_tables.py --check
```

Also run `python3 -m examples.basic` when changing the algebra's interface
or its example. For documentation changes, check links, examples and
agreement with package exports; do not add tests that repeat prose.

Never edit entries in `quantum_circuits/_clifford_tables.py` by hand.
Change the generator, run `python3 tools/generate_clifford_tables.py`,
then verify with `--check`.

Check decompositions with independent exact calculations, including phase
and boundary order, as in `tests/test_ccz.py`. Bounded enumeration and
random tests provide regression evidence, not general proofs.
