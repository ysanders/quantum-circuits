# Working on quantum-circuits

Read [README.md](README.md) for the current exact-algebra API and
[DESIGN.md](DESIGN.md) for the future circuit architecture and rewrite
milestones. Keep implemented behavior distinct from planned capabilities.

## Purpose and scope

The current library provides exact single-qubit Clifford+T algebra. The old
graph prototype and its dependent arithmetic APIs have been removed. The goal
remains hierarchical circuit representations using existing graph theory and
compiler techniques, with exact quantum semantics. Keep the representation
independent of a particular execution backend.

Implement the requested increment. The roadmap is direction for future work,
not an instruction to implement every layer in one task. Preserve unrelated
work and avoid opportunistic redesigns. When a proposed change departs from
the agreed foundation, explain the departure and settle that design question
before committing to it. Routine work within the authorized scope should
proceed without additional approval gates.

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

## Architectural foundation

These rules describe the target of the rewrite. No circuit graph is currently
implemented; introduce it in deliberate increments on top of the exact algebra.

- A circuit is a finite open directed acyclic port multigraph. Its meaning
  comes from ports, connections, labels, and boundaries, not vertex storage
  order or internal wire names.
- Separate ordered input and output boundaries. Ports distinguish quantum and
  classical data. Preparation and measurement may change the interface.
- The elementary unitary `PhaseInteraction` is exactly CZ on two distinct
  quantum wires. Its operands are symmetric. Do not generalize it to arbitrary
  arity or retain CCZ as a second elementary interaction in the new core.
- Exact single-qubit `WireOp` values label quantum edges. Preserve scalar
  phase and the distinction between execution order and matrix order.
  If a graph collects scalar factors separately and stores labels with
  `op.phase == 0`, preserve the full exact operator when moving phase.
- Blocks may have arbitrary arity. CCZ denotes an exact three-wire operation
  with known implementations, including a verified binary reference body.
  Author-facing CZ and CCZ constructors can remain convenient.
- Block occurrences bind abstract operation references to actual ports.
  Definitions have formal local interfaces; instantiate with fresh internal
  identities. Expand blocks explicitly and preserve their boundaries until
  intentionally removed.
- Quantum data has linear use: no implicit copy, fanout, or discard. Classical
  values can have multiple consumers. All quantum and classical dependencies
  participate in acyclicity checks.
- Graph validity is structural, not an optimization normal form. Valid
  unreduced circuits must be representable.

Use a small local builder where it clarifies construction. Keep immutable
circuit values separate from mutable construction and optimization state.
Arithmetic recipes should remain ordinary functions wherever that is enough.

## Hierarchy, equivalence, and rewriting

Keep structural equality, known semantic equivalence, and implementation
selection separate.

Structural comparison respects ordered external boundaries, port roles, vertex
semantics, and edge labels, while ignoring irrelevant internal renaming and
storage indices. A stable topological sort alone is not graph canonicalization.

Treat the abstract CCZ expression as analogous to an e-node, with established
equivalent expressions in an e-class. Store equivalences separately from
immutable circuits, using stable references. Adding alternatives or merging
classes must not mutate circuit values or invalidate their hashes.

Record the justification for each equivalence: a rule, derivation, or explicitly
trusted registration. Equal signatures alone do not establish equality.
Support congruence under valid serial and parallel composition and contextual
replacement. An equivalence graph can be cyclic; each extracted circuit must
remain finite and acyclic.

Build region extraction, boxing, substitution, expansion, and instantiation
around one boundary-aware substitution mechanism. For atomic contraction,
check directed convexity. For a partition, also check that the whole quotient
is acyclic; individual convexity does not suffice.

Assign each cut-edge label and phase exactly once. Include regions containing
only single-qubit processing through explicit edge cuts or subdivisions.
Do not silently factor a canonical operator to manufacture a region boundary.

Use incidence structures as a complementary view: wires, distinct event
occurrences, and participation, supplemented with per-wire order, labels,
and boundaries. Incidence alone does not encode circuit semantics. The binary
choice does not require imposing finite-geometric design axioms.

Begin with small, explicit rewrite rules and bounded search. Sophisticated
mathematical foundations do not require a large framework or dependency.
Keep operation identity through lowering so a backend can select a native
CCZ/AutoCCZ realization. Evaluate costs in context; a binary reference body
or isolated minimum T-count is not a universal execution cost.

## Preparation, measurement, and cleanup

Extend the graph using typed ports, explicit sources and sinks, and classical
dependencies. Preserve the exact unitary core.

- Preparation, a unitary extension of that preparation, and a general quantum
  process have different contracts. Do not merge unitary operators merely
  because they prepare the same state from a specified input.
- Measurement returns symbolic classical data during construction. Keep
  conditional branches inspectable and their interfaces compatible.
- Specify whether measurement consumes or retains its quantum input and
  whether each classical outcome remains externally visible.
- Use instrument semantics where outcomes are visible. Hiding an outcome
  sums its branch maps; it changes the observable interface.
- Separate exact phase-sensitive unitary equivalence from channel/process
  equivalence and protocol implementation relationships. A channel forgets
  global phase; coherent control can make that phase observable.
- Do not infer an adjoint or coherent control operation from a measurement
  recipe or a state-preparation contract.
- Treat AutoCCZ as a resource-consuming implementation of a logical contract,
  with its measurements and corrections accounted for.
- For temporary-AND cleanup, state the valid subspace, external interface,
  hidden outcomes, and ancilla obligations. Preserve coherence and arbitrary
  external entanglement on the valid subspace.
- Discard, reset, and release are distinct. Clean release promises prior
  restoration to zero and disentanglement. Dirty borrowing requires restoring
  the promised state and correlations. Reset is not reversible cleanup.

The first process example should be measured temporary-AND cleanup, with an
independent semantic check. Dense matrices or channel representations can
serve as small test oracles without becoming the runtime model.

## Verification and generated data

Use Python 3.10 or later. The current package and tests use only the standard
library. Keep dependencies proportionate to a concrete need.

Run checks appropriate to the change. For implementation changes affecting
the algebra, graphs, or arithmetic, the baseline commands from the repo root
are:

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

Use independent semantic tests for rewrites and decompositions. Compare exact
or appropriately checked small matrices, including scalar phases and boundary
order. Test renaming, repeated instantiation, parallel edges, idle wires, and
composition where relevant. Bounded enumeration and random tests are regression
evidence, not proofs of an unrestricted theorem.

For processes, test branch probabilities, conditional states, hidden outcomes,
and off-diagonal coherences or a complete small channel representation.
Computational-basis density inputs alone cannot establish preservation of
superposition. Test cleanup only against its stated input-subspace contract,
including correlations with an external reference where relevant.

Keep the current scope visible: only `Clif`, `clifford`, `WireOp`, `op`, and
the single-qubit gate constants are exported. Circuit construction, graph
passes, arithmetic recipes, hierarchy, and processes are future work. The old
graph implementation and its tests remain available in Git history; do not
restore their normalization requirements as structural validity rules. Update
these statements as implementation milestones land. Do not document planned
names as imports until they exist.
