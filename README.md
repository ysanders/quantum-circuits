# Quantum circuits

This package is a place to develop quantum algorithms, compare implementations
of their subroutines, and inspect the circuits they produce. Its direction is a
hierarchical circuit representation built from open directed port multigraphs:
exact single-qubit operators label edges, interactions are vertices, and
subcircuits can remain named, opaque blocks until a compilation step chooses
an implementation.

**The architecture below is the agreed direction for a rewrite.** The current
prototype still uses `Seq`, `Intersection`, and primitive CZ and CCZ gates.
It implements exact Clifford+T algebra, graph composition, direct pair
cancellation, and a Cuccaro adder. Hierarchical blocks, equivalence classes,
preparation, and measurement are not implemented yet. The
[current API](#current-api) section describes what runs today.

[Foundation](#foundation) · [Hierarchy and equivalence](#hierarchy-and-equivalence) ·
[Regions and incidence](#regions-and-incidence) ·
[Preparation and measurement](#preparation-and-measurement) ·
[Rewrite plan](#rewrite-plan) · [Current API](#current-api) ·
[Development](#development)

## Foundation

The representation separates three things: processing on one qubit,
interactions between qubits, and the choice of implementation for a larger
operation.

| Part of the target model | Meaning |
| --- | --- |
| Quantum edge | A connection between explicit ports, labelled by an exact single-qubit `WireOp` |
| `PhaseInteraction` | One elementary CZ interaction on two distinct quantum wires |
| Block occurrence | An abstract operation bound to actual ports, with separately recorded implementations |
| Boundary | Separate ordered input and output ports, with quantum or classical types |
| Circuit | A finite directed acyclic port multigraph, possibly containing opaque blocks |

The elementary unitary interaction is strictly binary:

```text
CZ |a,b> = (-1)**(a*b) |a,b>
```

The two operands are symmetric. `PhaseInteraction` replaces `Intersection`
as the name for this vertex. A CCZ is a three-wire operation represented through
hierarchy, with a verified implementation using binary interactions and
single-qubit operators. Blocks may have any interface arity. Preparation,
measurement, and classical operations will have their own vertex forms; the
binary restriction applies to the elementary unitary interaction.

Single-qubit labels retain exact scalar phase. An uninterrupted quantum edge
can carry the canonical product of all its one-qubit processing. A block
boundary remains visible until an explicit transformation removes it.

Connections identify source ports explicitly. Wire names help authors write
circuits, but internal names and storage indices do not define circuit meaning.
Quantum connections have linear use: no implicit copying, branching, or
discarding. Classical values may be copied and used by several consumers.
Both kinds of dependency must respect acyclicity.

Graph validity is a structural question. A valid graph may contain cancellable
gates or other reducible expressions. Construction, validation, normalization,
and optimization have separate responsibilities.

## Hierarchy and equivalence

CCZ names the exact map

```text
CCZ |a,b,c> = (-1)**(a*b*c) |a,b,c>
```

independently of any particular circuit body. An abstract CCZ expression is
analogous to an e-node; its known equivalent expressions belong to an e-class.
This distinction lets a compiler retain CCZ as an atomic operation while also
knowing how to expand it. Atomicity is relative to the compilation stage.

A block occurrence binds an abstract operation reference to actual ports.
Definitions use formal local ports; instantiation binds the boundary and gives
internal occurrences fresh identities. Reusing a definition must not accidentally
join its internal wires to those of another instance.

Keep three notions distinct:

| Question | Required notion |
| --- | --- |
| Do two values describe the same decorated graph? | Structural equality, respecting boundary order, port roles, and labels while ignoring internal renaming |
| Are two expressions known to implement the same operation? | Semantic equivalence, justified by rules, derivations, or explicitly trusted registrations |
| Which realization should be executed? | Implementation selection under a target and cost model |

A topological ordering is a way to store or traverse a DAG. It is not a
canonical graph identity. Choosing a stable topological sort alone does not
solve graph isomorphism or establish semantic equivalence.

The equivalence store lives separately from immutable circuit values. Adding
an alternative or merging equivalence classes must not change an existing
circuit's fields or hash. Stable operation references can resolve through that
store. Matching interfaces is necessary for replacement, but does not prove
two operations equal. An e-class records established alternatives; it does not
claim to enumerate every mathematically equivalent circuit.

Equivalence must be compatible with valid serial composition, parallel
composition, and substitution into a surrounding circuit. The equivalence
structure may contain cycles, as e-graphs do, while each extracted circuit
remains finite and acyclic.

A binary reference body for CCZ does not prescribe its execution cost.
A fault-tolerant backend may select an AutoCCZ protocol while the circuit still
contains the logical CCZ operation. Preserve that information through
compilation. Measurement-based protocols implement an external logical
contract; their relation to an exact unitary is addressed separately below.

Cost is contextual. A locally cheap implementation may make surrounding
optimization or scheduling more expensive. Resource states, ancillas,
classical reaction time, and backend constraints can affect selection.
The T-count of an isolated `WireOp` is not a whole-circuit optimality result.

## Regions and incidence

Hierarchy should use one explicit region-substitution mechanism for extraction,
boxing, expansion, instantiation, and local rewrites. A region exposes an
ordered boundary; replacement reconnects that boundary and preserves all labels
and dependencies.

A region contracted to one atomic occurrence must be directed-convex: a
directed path between vertices inside it must not leave and re-enter it.
For a partition into several blocks, also check that the entire quotient graph
is acyclic. Checking each region independently is insufficient. These checks
include classical dependencies once those are present.

Cuts through labelled edges need a precise ownership rule so that each
single-qubit operator and scalar phase is included exactly once. Regions may
also consist entirely of single-qubit processing, with no interaction vertex.
Support such regions through edge cuts or subdivisions; a set of interaction
vertices alone is not enough. Do not silently invent a factorization of a
canonical `WireOp` to create a requested cut.

Finite incidence structures offer a useful complementary view. Let Q be the
set of wires, E the set of interaction occurrences, and I a relation contained
in Q × E recording participation. Repeated interactions on the same wires
are distinct members of E. Add the event order along each wire, the edge
labels, and the open boundary to recover circuit structure; the combined
orders must be acyclic. Incidence alone does not determine a circuit.

The corresponding bipartite incidence graph, or Levi graph, also accommodates
events of arbitrary arity. Thus the binary foundation is a choice of elementary
semantics, not a prerequisite for using ordinary graph algorithms. There is no
requirement that circuits satisfy the additional axioms of a finite projective
plane or a combinatorial design.

This approach draws on existing graph theory and compiler mathematics:
hierarchical port graphs, string diagrams, graph substitution and rewriting,
and equivalence graphs compatible with serial and parallel composition.
Graph structure accounts for wiring; quantum semantics supplies the additional
equations. The implementation should introduce only the machinery needed by
concrete circuit examples.

## Preparation and measurement

Preparation and measurement will extend the same graph infrastructure using
typed quantum and classical ports and separate input and output boundaries.
The exact unitary algebra remains useful within that larger model.

An initial vocabulary can be small: prepare zero, discard a quantum system,
measure in the Z basis, and apply an explicit classically conditioned operation.
X-basis measurement can be expressed using H followed by Z measurement.
A destructive measurement has type Q → C; a retained-qubit measurement has
type Q → Q ⊗ C. Their contracts differ, whether or not both are primitives.

Constructing a measurement produces a symbolic classical value. It does not
sample a Python Boolean. Classical branches must remain inspectable, with
compatible external interfaces and explicit dependencies.

Preparation is a map from an empty quantum input to a state. It is not
identified with a particular unitary extension: both I and Z prepare
`|0>` from `|0>`, but they are different unitary operators. Likewise,
a measurement is described by an instrument, including outcome probabilities
and conditional post-measurement states. Exposing a classical outcome and
hiding it by summing over outcomes have different observable interfaces.

Exact unitary equality, process equivalence, and implementation contracts
must remain distinct. The channel `rho -> U rho U†` forgets global phase,
so I and -I induce the same channel but have different coherently controlled
versions. A measurement-based realization of a unitary channel must not
silently enter an exact, phase-sensitive unitary e-class. Adjoint and coherent
control transformations require an appropriate unitary description or a
separate justified construction.

The first useful example is cleanup of a temporary AND. On the valid subspace
spanned by `|a,b,ab>`, measuring the ancilla in the X basis produces an
outcome m and a data phase `(-1)**(m*a*b)`. A CZ conditioned on m removes
that phase. The ancilla is consumed and the internal outcome is hidden.
The contract must preserve arbitrary superpositions and entanglement with an
external system on this subspace. Coherent and measured cleanup can be
compared only after their boundaries and ancilla obligations are matched.

Discard, reset, and release have different meanings. Reset destroys the old
quantum information. Clean release asserts that a qubit has already been
restored to zero and disentangled. A borrowed dirty qubit must be restored to
its promised original state, including correlations. Reset cannot discharge
a reversible cleanup obligation.

Small independent instrument or channel calculations will support tests.
Checking only computational-basis density matrices would miss dephasing;
tests must also cover coherences, branch probabilities, conditional outputs,
and hidden outcomes. Dense matrices need not become the runtime representation.

## Rewrite plan

The rewrite proceeds through usable increments. The names below describe
responsibilities, not an already available API.

1. **Graph, builder, and hierarchical CCZ.** Preserve the exact `Clif` and
   `WireOp` algebra. Introduce explicit ports, separate typed boundaries,
   binary `PhaseInteraction` vertices, and opaque block occurrences.
   Supply CCZ with a verified binary reference body. Use a small mutable
   builder that freezes an immutable result. Keep the arithmetic recipes
   working and check expanded circuits with independent, phase-sensitive
   semantics.
2. **Regions and known equivalences.** Implement boundary-aware extraction,
   substitution, expansion, and fresh instantiation. Add structural comparison
   and a separate equivalence store with justified rules and congruence.
   Begin with one-wire fusion, CZ/CCZ involution, disjoint interchange, and
   valid diagonal commutations. Bounded explicit rewriting is a useful first
   implementation; a full equality-saturation engine is not a prerequisite.
3. **Quantum and classical processes.** Add preparation, measurement, discard,
   and inspectable classical conditionals. Keep process contracts distinct
   from exact unitary equality. Implement and verify temporary-AND cleanup.
4. **Implementation selection.** Compare equivalent representations in context
   and account for their resources. Support target choices such as a binary
   CCZ body or an AutoCCZ protocol. Full factory layout and physical routing
   are separate downstream concerns.

Arithmetic remains expressed through ordinary functions. The graph and its
transformations should make those functions' results inspectable without
requiring a general-purpose compiler framework first.

## Current API

Everything in this section describes the existing prototype. In particular,
`Intersection` is still exported, and CCZ is still primitive. The proposed
`PhaseInteraction`, block, and equivalence APIs do not exist yet.

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
from quantum_circuits import H, I, S, T, clifford, op

assert op("HS") == S @ H
assert op(clifford("HS")) == S @ H
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
| `u.iter_gates()` | H/S/T word in execution order, with exactly `t_count` T gates |
| Equality and hashing | Exact equality of canonical fields |

Raw construction validates canonical fields; use `op` to normalize arbitrary
words. The emitted Clifford count need not be minimal. Runtime normalization
uses finite tables and exact integer operations. Its uniqueness and T-optimality
come from [Giles and Selinger, Proposition 8.2](https://www.mscs.dal.ca/~selinger/papers/ma-remarks.pdf).
For long words, batch parts into `op(*parts)`; repeatedly extending immutable
strings through composition incurs avoidable copying.

`Clif(frame, phase=0)` supplies the supporting Clifford algebra. It denotes
`omega**phase * P[pauli] * R[rep]`, where `frame = 4*rep + pauli`,
`P = (I, X, Y, Z)`, and `R = (I, H, S, HS, SH, HSH)` in matrix order.
There are 24 frames and eight phases, hence 192 exact values.
`clifford(*parts)` constructs Clifford words in execution order;
`op(c)` promotes a Clifford. Constants in `quantum_circuits.clifford`
have type `Clif`, unlike the top-level `WireOp` constants.

### Wires and graphs

`Wire(name)` identifies a qubit by name; equal names mean the same wire.
`Apply(u, q)` binds a `WireOp` to a wire, and `gate(word, q)` also
accepts an operator word. `CZ(a, b)` and `CCZ(a, b, c)` require distinct
wires and store their symmetric operands in name order.

```python
from quantum_circuits import Apply, CCZ, CZ, H, Wire, WireSegment, gate, op, seq

a, b, c = map(Wire, "abc")
assert gate("HTH", a) == Apply(op("HTH"), a)

body = seq(Apply(H, c), CZ(a, b), Apply(H, c), wires=(a, b, c))
assert len(body.vertices) == 1
assert body.outputs == (
    WireSegment(a, 0), WireSegment(b, 0), WireSegment(c)
)

left = seq(CZ(a, b), CCZ(a, b, c))
right = seq(CCZ(c, b, a), CZ(b, a))
assert seq(left, right) == seq(wires=left.wires)
```

The two H gates above share an uninterrupted segment on c, so their product
is identity. The CCZ pair in the final composition cancels, exposing a CZ pair
which also cancels.

`seq(*parts, wires=None)` accepts applications, CZ, CCZ, and existing
`Seq` values in execution order. An explicit `wires=` fixes the entire
ordered interface, including idle wires. Otherwise, first appearance determines
the order. Nested graphs are flattened and compose by wire name.
`seq()` is the empty circuit; `seq(wires=(a,))` is a one-wire identity.

| Current value | Stored structure |
| --- | --- |
| `Seq(wires, vertices, outputs)` | One ordered interface used for both input and output, a topological vertex tuple, and output edges |
| `Intersection(kind, inputs)` | A CZ or CCZ occurrence with two or three incoming edges and corresponding outgoing ports |
| `WireSegment(wire, source=None, op=I)` | An edge labelled by a `WireOp`; source is a vertex index, or `None` for the input boundary |

The destination stores each edge. The source index and wire identify its source
port. Labels U followed by V compose as `V @ U`. Graph construction checks
that each edge uses the current port on its wire.

Current reduction cancels equal interactions only when directly connected on
all participating wires through exact identity labels. It does not implement
general diagonal commutation. A scalar phase or a T label blocks this direct
match. Raw `Seq` construction rejects such immediately cancellable pairs;
this coupling between validity and reduction will change in the rewrite.
`cancel_pairs(body)` is currently a compatibility function returning body.

Current `Seq` equality and hashing compare stored fields, including wire
names and traversal order. They are neither graph-isomorphism tests nor
semantic-equivalence tests. Even regrouping construction can change the stored
ordering of disjoint vertices. Prefer batching parts in one `seq` call over
repeatedly rebuilding a growing immutable graph.

### Arithmetic

`quantum_circuits.arithmetic` provides `cnot`, `toffoli`, `maj`,
`uma`, and `cuccaro_add` as ordinary functions returning `Seq`.
The adder takes two nonempty, equal-width registers in least-significant-bit
order, a carry wire, and an optional overflow wire. All wires must be distinct.

```text
(A, B, c, z) -> (A, (A+B+c) mod 2**n, c, z XOR floor((A+B+c)/2**n))
```

Omit overflow for modular addition. The input carry is restored; both initial
carry values work coherently. An overflow wire need not start in zero.
The recipe performs no state preparation or measurement.

```python
from quantum_circuits import Wire
from quantum_circuits.arithmetic import cuccaro_add

a = tuple(Wire(f"a{i}") for i in range(4))
b = tuple(Wire(f"b{i}") for i in range(4))
carry, overflow = Wire("carry"), Wire("overflow")
adder = cuccaro_add(a, b, carry, overflow=overflow)

assert adder.wires == (*a, *b, carry, overflow)
assert sum(v.kind == "CCZ" for v in adder.vertices) == 8
```

This constructs and inspects a circuit; it does not execute an addition.
The recipe follows the basic ripple in
[Cuccaro et al., section 2](https://arxiv.org/abs/quant-ph/0410184) and
materializes a graph of size O(n).

## Development

Write the implementation in a student style: as direct, conventional, and
explicit as an undergraduate answer key. Prefer ordinary functions and frozen
dataclasses, clear invariants, familiar algorithms, and descriptive intermediate
values. Local mutation and a small object-oriented helper are appropriate when
they make the algorithm easier to follow. Mathematical sophistication should
not require elaborate software machinery.

This applies equally to the Clifford table generator. Its exact scalar,
matrix, and table computations should be easy to explain; there is no
requirement either to rewrite it using classes or to avoid classes.
[AGENTS.md](AGENTS.md) records the detailed development guidance.

### Running and verification

Use Python 3.10 or later. Runtime and tests use only the standard library.
From the project root, with `python3` pointing to a suitable interpreter:

```sh
python3 --version
python3 -m examples.basic
python3 -m examples.arithmetic
python3 -m unittest discover -v
python3 tools/generate_clifford_tables.py --check
```

An editable installation is optional for importing from another project:

```sh
python3 -m pip install -e .
```

The tests include exhaustive Clifford products, bounded enumeration of exact
single-qubit normal forms, exact and numerical matrix comparisons, graph
validation and pair cancellation, and small adders with carry restoration,
overflow, and phase checks. The exact matrix oracle is independent of runtime
tables and normalization, while sharing the generator's scalar arithmetic.
A separate numerical oracle uses conventional complex matrices.

These tests establish bounded regression checks. General normal-form
guarantees rely on their mathematical results. Future graph rewrites need
independent semantic checks; process tests must also cover off-diagonal
coherences and classical outcomes.

### Project layout

| Location | Current responsibility |
| --- | --- |
| `quantum_circuits/operators.py` | Exact single-qubit values, normalization, and lowering |
| `quantum_circuits/clifford.py` | Exact Clifford algebra |
| `quantum_circuits/_clifford_tables.py` | Generated finite tables |
| `quantum_circuits/model.py` | Current wires, graph values, composition, and direct cancellation |
| `quantum_circuits/arithmetic.py` | Reversible arithmetic recipes |
| `quantum_circuits/passes.py` | Compatibility entry point for pair cancellation |
| `examples/` | Runnable construction examples |
| `tests/` | Interface tests and independent semantic checks |
| `tools/generate_clifford_tables.py` | Exact, reproducible table generation |
| `AGENTS.md` | Architectural and coding guidance for future work |

### Mathematical background

The following are foundations to draw on as the implementation needs them:

- [Selinger, A survey of graphical languages for monoidal categories](https://www.mscs.dal.ca/~selinger/papers/graphical.pdf):
  composition and wiring through string diagrams.
- [Attributed Hierarchical Port Graphs and Applications](https://arxiv.org/abs/1802.06492):
  port graphs with hierarchical structure.
- [String Diagram Rewrite Theory II](https://arxiv.org/abs/2104.14686):
  rewriting with symmetric monoidal structure and convex matches.
- [Equivalence Hypergraphs: DPO Rewriting for Monoidal E-Graphs](https://arxiv.org/html/2406.15882v2):
  equivalence structures compatible with diagram composition.
- [Categories of Quantum and Classical Channels](https://arxiv.org/abs/1305.3821):
  a mathematical setting for quantum and classical processes.
- [Flexible layout of surface code computations using AutoCCZ states](https://arxiv.org/abs/1905.08916)
  and [Halving the cost of quantum addition](https://arxiv.org/abs/1709.06648):
  motivating protocols for implementation selection and measured cleanup.
