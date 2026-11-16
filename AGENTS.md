# Working on quantum-circuits

This file guides anyone who changes this repository, human or AI.

Read three documents first. [README.md](README.md) documents the code that
exists. [DESIGN.md](DESIGN.md) gives the library's purpose, the plan for
circuits and the open questions. [BACKEND.md](BACKEND.md) describes the
tools that will consume the circuits. Keep what is implemented apart from
what is planned.

## Purpose and scope

The library provides exact Clifford+T algebra on one qubit. No circuit type
exists yet.

Do the work that was asked for and stop there. Leave unrelated work alone.
Do not redesign things in passing.

Some changes depart from the foundation in DESIGN.md. Others answer one of
its open questions. Explain such a change and settle the question before
committing to it. Routine work inside the agreed scope needs no further
approval.

## Student style

Write the code as an answer key for an undergraduate. Use the simplest
conventional construction that makes the mathematics and the algorithm
plain.

- **Values and functions.** Prefer functions and frozen dataclasses. Use
  ordinary tuples, lists, dictionaries and sets where they fit.
- **Names and control flow.** Choose descriptive names. Keep control flow
  simple. Use intermediate values and explicit loops when they make the
  argument easier to follow.
- **Invariants.** State the invariant. Explain why a step that is not
  obvious preserves it. A comment explains mathematics, ordering or a design
  choice.
- **Small functions.** Give each function one job. Add a helper when it
  makes a concrete operation clearer. Do not add extension points for needs
  that do not exist. Avoid generic frameworks, metaprogramming and deep
  inheritance.
- **Objects.** A class is welcome when it gives a clearer account of state
  and behaviour that belong together. A small mutable builder can be
  appropriate. So can a helper for exact arithmetic. A functional style does
  not forbid methods or local mutation.
- **Copying.** Build up a result locally and freeze it once. Do not copy a
  whole growing circuit or operator string at each step only to keep it
  immutable.
- **Efficiency.** Use efficient algorithms that a reader can follow. If an
  optimisation is not obvious, state its invariant and show why it is
  needed.
- **Errors.** Check inputs at public boundaries. Reject a malformed value
  with a useful error. Do not convert it silently. Keep type annotations and
  docstrings concrete.
- **Exactness.** Keep exact arithmetic exact. Floating point may serve as an
  independent check in tests. It does not replace an exact identity or the
  tracking of phase.
- **Paradigm.** Do not rewrite sound code only to change its programming
  style.

The Clifford table generator is an example of this policy. Organise its
exact scalar, matrix and table calculations in the way that explains them
best. There is no standing preference for or against rewriting that file
with classes.

## Checks and generated data

Use Python 3.10 or later. The package and its tests use only the standard
library. Add a dependency only for a concrete need.

Run the checks that fit the change. For a change to the code, run these from
the repository root.

```sh
python3 -m unittest discover -v
python3 tools/generate_clifford_tables.py --check
```

Run `python3 -m examples.basic` as well when you change the interface of the
algebra or its example.

For a change to the documents, check the links and the examples. Check that
the text agrees with what the package exports. Do not add tests that only
repeat the prose.

`quantum_circuits/_clifford_tables.py` is generated. Do not edit its entries
by hand. Change the generator, regenerate with
`python3 tools/generate_clifford_tables.py`, and then verify with `--check`.

Check a decomposition against an independent exact calculation, as
`tests/test_ccz.py` does. Include the phase and the order of the inputs and
outputs. A bounded enumeration or a random test is evidence against
regressions. It is not a proof of a general theorem.

Keep the current scope visible. The package exports only `Clif`, `WireOp`,
`op` and the gate constants for one qubit. An older graph implementation and
its tests remain in the Git history. Do not bring back its normalisation
requirements as rules for validity. Do not document a planned name as an
import until it exists.
