# Future circuit design

This document records the agreed direction for the circuit rewrite. The
current implementation contains only exact single-qubit algebra, documented
in [README.md](README.md). Circuit, block, equivalence, and process names below
are planned responsibilities, not available imports.

The goal is a library for constructing, inspecting, comparing, and rewriting
quantum circuits, independent of a particular execution backend. Its
hierarchical representation uses open directed port multigraphs: exact
single-qubit operators label edges, interactions are vertices, and subcircuits
can remain named, opaque blocks until an explicit expansion chooses a body.

[Foundation](#foundation) · [Hierarchy and equivalence](#hierarchy-and-equivalence) ·
[Regions and incidence](#regions-and-incidence) ·
[Preparation and measurement](#preparation-and-measurement) ·
[Rewrite plan](#rewrite-plan) · [Mathematical background](#mathematical-background)

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

The two operands are symmetric. `PhaseInteraction` names this vertex.
A CCZ is a three-wire operation represented through hierarchy, with a
verified implementation using binary interactions and
single-qubit operators. Blocks may have any interface arity. Preparation,
measurement, and classical operations will have their own vertex forms; the
binary restriction applies to the elementary unitary interaction.

Single-qubit operators retain exact scalar phase. A circuit can collect those
scalar factors into one explicit circuit phase; that phase remains part of
its exact semantics. An uninterrupted quantum edge can carry the canonical
product of its one-qubit processing, with its
scalar factor accounted for separately. A block boundary remains visible
until an explicit transformation removes it.

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

The rewrite proceeds through separate, usable increments. The first step is
complete; the remaining steps are future work.

1. **Cut back to the exact algebra — complete.** Retain `Clif`, `WireOp`,
   the generated tables, their generator, and independent algebra tests.
   Remove the old graph, builder, passes, and dependent arithmetic APIs and
   examples. Keep the public package coherent and the current API explicit.
2. **Write the graph, builder, and hierarchical CCZ.** Introduce explicit
   ports, separate typed boundaries, binary `PhaseInteraction` vertices,
   stable operation references, and opaque block occurrences. Keep structural
   validation independent of reduction. Build a small mutable builder for the
   immutable graph values and supply CCZ with a verified binary reference body.
   Implement explicit expansion through boundary reconnection and fresh
   instantiation, preserving labels and accounting for each occurrence's phase
   exactly once. Support unitary inversion while retaining block boundaries.
   Restore the arithmetic recipes and check expanded circuits with independent,
   phase-sensitive semantics, including any separately stored circuit scalar.
3. **Regions and known equivalences.** Extend the boundary reconnection
   mechanism to extraction, boxing, and contextual substitution. Add structural
   comparison and a separate equivalence store with justified rules and
   congruence. Begin with one-wire fusion, CZ/CCZ involution, disjoint
   interchange, and valid diagonal commutations. Bounded explicit rewriting
   is a useful first implementation; a full equality-saturation engine is
   not a prerequisite.
4. **Quantum and classical processes.** Add preparation, measurement, discard,
   and inspectable classical conditionals. Keep process contracts distinct
   from exact unitary equality. Implement and verify temporary-AND cleanup.
5. **Implementation selection.** Compare equivalent representations in context
   and account for their resources. Support target choices such as a binary
   CCZ body or an AutoCCZ protocol. Full factory layout and physical routing
   are separate downstream concerns.

Arithmetic should remain expressed through ordinary functions. Restore the
Cuccaro adder using the basic ripple in
[Cuccaro et al., section 2](https://arxiv.org/abs/quant-ph/0410184), with explicit
ordered interfaces, coherent carry restoration, optional overflow, and full
phase checks. The old recipes and graph tests are available in Git history;
their eager reduction and stored-field equality are not requirements of the
new graph. The transformations should make arithmetic results inspectable
without requiring a general-purpose compiler framework first.

## Mathematical background

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
