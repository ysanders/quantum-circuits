# Circuit design

## Purpose and scope

This personal library supports the author's quantum algorithms and compiler.
It will construct circuits from reusable subcircuits, inspect their structure
and expand them into elementary operations. A subcircuit's definition is
shared across uses on different registers.

The scope has three parts:

- **Circuit construction:** operations, wiring, preparation, measurement
  and shared subcircuit definitions.
- **Rotation synthesis:** approximate a specified single-qubit rotation to
  a requested accuracy using Clifford+T gates.
- **Coherent arithmetic:** construct additions, multiplications and
  polynomial evaluations on quantum registers. Python builds the circuit;
  the quantum computer performs the arithmetic.

For quantum signal processing (QSP), an external library computes the phase
angles. This library takes those angles as input and constructs the circuit.

Only exact single-qubit Clifford+T algebra is implemented today; see
[README.md](README.md). The circuit model and constructors below are planned.

[Arithmetic example](#arithmetic-example) · [Circuit representation](#circuit-representation) ·
[Shared subcircuits](#shared-subcircuits) · [Equality and hashing](#equality-and-hashing) ·
[Example: CCZ](#example-ccz) · [External tools](#external-tools) ·
[Implementation order](#implementation-order)

## Arithmetic example

Grover–Rudolph state preparation motivates coherent polynomial evaluation:
a rotation angle requires an arcsine calculation on a value in a quantum
register. A truncated Taylor series gives one possible, inefficient
approximation. This example illustrates the arithmetic required; it does
not prescribe an approximation method.

For `p(x) = a_0 + a_1*x + ... + a_d*x**d`, a constructor takes coefficients,
register widths and numerical conventions. It builds arithmetic for an
input register that may be in superposition. One possible interface is:

```text
|x> |0> |0_work>  ->  |x> |p_tilde(x)> |0_work>
```

Here `p_tilde(x)` is the finite-precision result encoded as a bit string.
The map must preserve coherence across x values and restore the working
qubits. In the state-preparation example, the result controls a rotation,
then its calculation can be uncomputed.

Such constructions need explicit register order, reusable adders and
multipliers, and working-qubit restoration. Their bodies must remain
inspectable so a subroutine's implementation can be changed independently.

Polynomial approximation, finite-precision arithmetic and rotation synthesis
have separate approximation errors. The gate algebra describes the chosen
circuit exactly, including phase; agreement with the requested function or
rotation is approximate.

## Circuit representation

Circuits describe logical operations and their dependencies. Physical
placement, routing and scheduling belong to external consumers.

### One-qubit processing and intersections

Each stretch of quantum wire carries a `WireOp`, the exact product of its
Clifford+T gates. Combining consecutive one-qubit operations uses the
existing algebra.

An intersection joins wires at an operation. The only elementary unitary
intersection is CZ on two distinct wires:

```text
CZ |a,b> = (-1)**(a*b) |a,b>
```

CZ is symmetric in its arguments. Larger operations have bodies built from
CZ and one-qubit processing. An operation's definition is independent of
its chosen body, as the CCZ example below shows.

Intersections are vertices; stretches of wire are labelled edges. Each CZ
has an input and output port for each wire. Connections identify these
ports explicitly. A one-wire unitary circuit can be a labelled edge alone.

### Preparation and measurement

Preparation creates a quantum wire. Measurement exposes a classical
outcome. Both primitives act on one qubit; larger preparations and
measurements are circuits built from them.

The proposed first primitives are preparation of `|0>` and Z measurement.
H after preparation produces `|+>`; H before Z measurement gives X
measurement. Whether measurement consumes its qubit or retains a quantum
output remains to be settled.

Construction records a symbolic result and its dependencies without
sampling an outcome. Preparation and measurement are separate from the
unitary `WireOp` algebra.

### Boundaries and validity

A circuit has separate ordered input and output boundaries, with quantum
or classical ports. Preparation and measurement allow these boundaries
to differ in size and type.

The operation graph is a finite directed acyclic graph (DAG). Every quantum
port has exactly one edge: quantum values cannot branch or vanish
implicitly. Classical results may have several consumers. Both kinds of
dependency must be acyclic.

The graph records event order along each wire as well as which wires meet.
Storage order and internal names have no mathematical meaning. Exact unitary
semantics includes boundary order and overall phase.

Validity concerns connections, not simplification. Two consecutive equal
CZs form a valid circuit; cancelling them is a transformation.

## Shared subcircuits

A definition contains a body with ordered local ports. Each occurrence
binds those ports to wires in its surrounding circuit. For example, a
three-qubit body's ports 0, 1 and 2 can bind to (a, b, c) in one use and
(x, y, z) in another. Both uses share the definition; caller names belong
to the occurrences.

Expansion creates fresh internal occurrences and reconnects the boundary
through each binding. Shared definitions must never join the internal
wires of separate uses.

Definitions form a second DAG, whose edges refer to child definitions.
It resembles a parse tree over the operations, with repeated subcircuits
shared. Recursive definitions are excluded.

Tools can inspect, translate or summarise each definition once. Gate
counting can multiply a child's count by its number of uses. Explicit
expansion remains available when a task needs elementary operations.

## Equality and hashing

Local ports allow reuse on different caller wires while preserving
argument roles. A further goal is to give fragments the same canonical
body and digest when they differ only by a permutation of qubit indices.
Canonicalisation must retain the boundary permutations needed to reconnect
each occurrence correctly. It need not delay circuit construction.

A digest will cover boundaries, operations, connections and child digests,
forming a Merkle DAG. Specify its encoding and recognised equivalences
when implementing it. Python's `hash()` is not a persistent identifier,
and a topological traversal does not provide canonical graph labelling.

Different bodies can implement the same operation: moving T through CZ is
one example. Recognising such identities is later transformation work.
The initial representation may miss sharing opportunities while preserving
correct circuit semantics.

## Example: CCZ

CCZ is defined by `CCZ |a,b,c> = (-1)**(a*b*c) |a,b,c>`. It negates
`|111>` and fixes the other computational basis states. Its definition is
independent of the body chosen to implement it.

This body uses six CZ vertices, listed in an order consistent with each
wire.

```text
vertex   0     1     2     3     4     5
wires    b,c   a,c   b,c   a,c   a,b   a,b
```

Each wire meets four vertices and has five edges: one from the input,
three between vertices and one to the output. Their labels are gate words
in execution order:

```text
a:   I    I           I        T           I
b:   I    I           T H      H T^-1 H    H
c:   H    H T^-1 H    H T H    H T^-1 H    H T
```

Seven edges carry one T or T^-1 each. [tests/test_ccz.py](tests/test_ccz.py)
checks this body against CCZ on all eight basis states, exactly and with
phase included.

### Why this body is CCZ

H, CZ, H on a target wire implements CNOT: addition modulo 2, written `^`.
Vertices 0 to 3 add into c; vertices 4 and 5 add into b. Together, these
additions restore the input bits.

T contributes `omega**x` on bit x, where `omega = exp(i*pi/4)`; T^-1
contributes `omega**(-x)`. The seven gates act on a, b, c, a^b, a^c, b^c
and a^b^c, with T^-1 on the pairwise sums. Thus:

```text
a + b + c - (a^b) - (a^c) - (b^c) + (a^b^c) = 4*a*b*c
```

The total factor is `omega**(4*a*b*c)`, which equals `(-1)**(a*b*c)`.

## External tools

Resource estimators translate logical circuits into hardware and time
requirements under a machine model. Those estimates depend on layout,
scheduling, error correction and magic-state supply, not just gate counts.

Rottnest coordinates such a compilation and estimation pipeline. Qualtran
represents algorithms as composable blocks, called bloqs, and supports
[resource counting over their call graph](https://qualtran.readthedocs.io/en/latest/resource_counting/call_graph.html).
Both are possible consumers; their adapters are their authors' responsibility.

### Rottnest research

These notes summarise public code and papers examined on 16 November 2026.
No backend code or adapter was run.

| Tool | Role in the recorded pipeline |
| --- | --- |
| Rottnest | Reads logical circuits, coordinates compilation and reports resource estimates |
| Pandora | Stores circuits in a database and divides them into reusable pieces |
| Cabaliser | Compiles a piece into a graph state and measurement description |
| T scheduler | Synthesises rotations and schedules their T-state resources |

Rottnest divides a circuit into pieces called widgets that fit a machine
register. Cabaliser translates each into a graph state, local Clifford
operations and measurements. A graph state is prepared from `|+>` qubits
by applying CZ along its graph's edges. This graph describes a state;
it is distinct from this library's operation DAG.

Later stages handle layout, scheduling, magic states and code distance.
See [Nguyen et al., Section V](https://arxiv.org/abs/2509.13546) for the
pipeline, [Saadatmand et al.](https://arxiv.org/abs/2406.06015) for the
machine, and [Moflic et al.](https://arxiv.org/abs/2507.20677) for Pandora.

The snapshot suggests four considerations for an adapter:

- **Vocabulary:** Cabaliser accepts basic Cliffords, CNOT, CZ, tagged Z
  rotations and measurement on numbered qubits. Its additional output
  Clifford labels are not accepted as input.
- **Rotations:** each tagged rotation adds a graph qubit and is synthesised
  later. Expanding it into T gates beforehand changes this representation.
  Angles are in units of pi; precision is run-wide despite the presence of
  per-rotation tolerance fields.
- **Reuse:** START/END markers cache a subcircuit result; REQUEST reuses it
  with another wire binding. Markers also end widgets, so call boundaries
  can affect estimates.
- **Semantics:** the parser does not preserve general classical control,
  and the pipeline decomposes CCZ into T gates. Supported measurement and
  control contracts would need to be established.

Sources: [Cabaliser](https://github.com/QSI-BAQS/cabaliser) (`9bc6ed1`),
[rottnest_py](https://github.com/QSI-BAQS/rottnest_py) (`0109b89`),
[t_scheduler](https://github.com/QSI-BAQS/t_scheduler) (`5af6a31`) and
[rottnest_example_executables](https://github.com/QSI-BAQS/rottnest_example_executables)
(`289b3dc`). Private repositories and Pandora's source were not examined.

### Library boundary

Consumers should be able to inspect a definition's ordered ports,
operations, measurement dependencies and child bindings without expanding
every occurrence. Adapters choose serialization, decomposition and call
boundaries, and match port, angle, phase and measurement conventions.

Exact traversal retains unitary phase; any consumer-specific omission
belongs in its adapter. The library's semantics remain independent of
consumer limitations. No adapter is implemented yet.

## Implementation order

First add single-qubit preparation and measurement, settling their contracts
and composition with the existing algebra. Then introduce intersections
through explicit ports, starting with CZ. Represent the CCZ body above and
reuse its independent exact check.

Shared definitions and bindings build on this structure. Rotation synthesis
and coherent arithmetic constructors supply the higher-level operations.
General equivalence machinery, permutation canonicalisation and adapters
can follow as needed.
