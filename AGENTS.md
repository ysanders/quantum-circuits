# Working on quantum-circuits

Read [README.md](README.md) for the implemented API and [DESIGN.md](DESIGN.md)
for the circuit foundation, its checked example, and the open questions. Keep
implemented behavior distinct from plans.

## Purpose and scope

The library provides exact single-qubit Clifford+T algebra. No circuit type
exists yet.

Implement the requested increment and nothing beyond it. Preserve unrelated
work and avoid opportunistic redesigns. When a proposed change departs from
the foundation in DESIGN.md, or answers one of its open questions, explain
the change and settle that question before committing to it. Routine work
within the authorized scope should proceed without additional approval gates.

## Student style

Write as though preparing an undergraduate answer key: use the simplest
conventional construction that makes the mathematics and algorithm explicit.

- Prefer functions and frozen dataclasses for values and transformations.
  Use ordinary tuples, lists, dictionaries, and sets where they fit.
- Choose descriptive names and straightforward control flow. Use intermediate
  values and explicit loops when they make the argument easier to follow.
- State the invariant and explain why a non-obvious step preserves it.
  Comments should explain mathematics, ordering, or a design choice.
- Keep functions focused. Introduce a helper or abstraction when it makes a
  concrete operation clearer; avoid speculative extension points, generic
  frameworks, metaprogramming, and elaborate inheritance.
- A traditional object-oriented approach is welcome when it gives a clearer
  account of cohesive state or behavior. A small mutable builder or exact
  arithmetic helper can be appropriate. Functional style does not prohibit
  methods or local mutation.
- Accumulate locally and freeze once where practical. Avoid repeatedly copying
  an entire growing circuit or operator string merely to maintain immutability
  inside an algorithm.
- Use intelligible efficient algorithms. Explain a less obvious optimization
  with its invariant and a demonstrated reason for needing it.
- Validate public boundaries and malformed values explicitly. Prefer useful
  errors over silent coercion. Keep type annotations and docstrings concrete.
- Keep exact arithmetic exact. Floating-point calculations can be independent
  test oracles, not replacements for exact identities or phase bookkeeping.
- Do not rewrite sound code solely to change its programming paradigm.

The Clifford table generator is an explicit example of this policy. Organize
its exact scalar, matrix, and table calculations in whichever way explains
them most directly. There is no standing preference for or against an
object-oriented rewrite of that file.

## Verification and generated data

Use Python 3.10 or later. The current package and tests use only the standard
library. Keep dependencies proportionate to a concrete need.

Run checks appropriate to the change. For implementation changes, the
baseline commands from the repo root are:

```sh
python3 -m unittest discover -v
python3 tools/generate_clifford_tables.py --check
```

Run `python3 -m examples.basic` when changing the algebra API or its example.
For documentation changes, check links, examples, and consistency with the
actual exports; do not invent tests that merely repeat the prose.

`quantum_circuits/_clifford_tables.py` is generated. Change the generator
rather than hand-editing table entries, regenerate with
`python3 tools/generate_clifford_tables.py`, and verify with `--check`.

Check decompositions with independent exact semantics, including scalar phase
and boundary order, as `tests/test_ccz.py` does. Bounded enumeration and
random tests are regression evidence, not proofs of an unrestricted theorem.

Keep the current scope visible: only `Clif`, `WireOp`, `op`, and the
single-qubit gate constants are exported. The old graph implementation and
its tests remain in Git history; do not restore their normalization
requirements as validity rules. Do not document planned names as imports
until they exist.
