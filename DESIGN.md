# Circuit design

## Purpose and scope

This library is a lowering target for the author's quantum compiler. Its
job is to manage memory while a consumer iterates through a hierarchically
constructed circuit. Each subcircuit definition is stored once and shared
across uses on different registers. A consumer walks the circuit from the
root definition and descends into any definition it does not recognise.
An extractor for Qualtran, Cirq, Qiskit or another library stops at
operations its target provides. The author need not choose a target
library.

The library's circuit types are an abstraction over the [stream](#stream)
language. Every circuit they build lowers to a stream, which fixes its
meaning. They should express everything the stream can; anything they
cannot yet express is a gap to close.

The scope has three parts:

- **Circuit construction:** operations, wiring, preparation, measurement
  and shared subcircuit definitions.
- **Rotation synthesis:** approximate a specified single-qubit rotation to
  a requested accuracy using Clifford+T gates.
- **Coherent arithmetic:** construct additions, multiplications and
  polynomial evaluations on quantum registers. Python builds the circuit;
  the quantum computer performs the arithmetic.

Exact single-qubit Clifford+T algebra, circuits of wires that intersect at
CZ, with preparation and measurement, and the stream are implemented today;
see [README.md](README.md). Subcircuits, classical data and the
constructors below are planned.

[Arithmetic example](#arithmetic-example) · [Circuit representation](#circuit-representation) ·
[Shared subcircuits](#shared-subcircuits) · [Stream](#stream) ·
[Equality and hashing](#equality-and-hashing) ·
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

A circuit means a time-ordered sequence of primitive operations on
addressed qubits. The primitives are single-qubit Clifford gates, T, CZ on
two distinct qubits, and single-qubit preparation and measurement in the
computational basis. Physical placement, routing and scheduling belong to
external consumers. The [stream](#stream) makes this sequence precise.

The library stores a circuit under a programming discipline: wires that
intersect pairwise. The discipline is a convenience; the sequence defines
the circuit.

### One-qubit processing and intersections

Each segment of wire, between two intersections or between an intersection
and a boundary port, carries a `WireOp`: the exact product of its Clifford+T
gates. Combining consecutive one-qubit operations uses the existing algebra.
In the stream, a segment lowers to CLIF and T records in alternation, with
at most one CLIF between consecutive T gates.

An intersection joins wires at an operation. The only elementary unitary
intersection is CZ on two distinct wires:

```text
CZ |a,b> = (-1)**(a*b) |a,b>
```

CZ is symmetric in its arguments. Larger operations have bodies built from
CZ and one-qubit processing. An operation's definition is independent of
its chosen body, as the CCZ example below shows.

Intersections are vertices; stretches of wire are labelled edges. A
one-wire unitary circuit can be a labelled edge alone.

`Circuit` stores each wire's segments in order and each CZ as the pair of
wires it joins. CZs on disjoint wires can be applied in either order with
the same result, so the stored order of CZs must not depend on the order
of construction. `Circuit` fixes the order one CZ at a time. At each step,
the CZs that may come next are those with no unstored CZ before them on
either of their wires. Of these, it stores the one with the smallest wire
pair, comparing first wires and then second wires.

For example, CZ(2, 3) followed by CZ(0, 1) is stored as (0, 1), (2, 3). But
CZ(1, 2) followed by CZ(0, 1) keeps its order, because on wire 1 the CZ
(0, 1) comes after (1, 2). Two constructions of the same circuit therefore
give equal stored forms and equal streams. The stream follows the stored
order: for each CZ, the segments that end there, then the CZ; the final
segments and measurements come last.

### Preparation and measurement

Preparation of `|0>` creates a wire. Z measurement destroys a wire and
produces a classical outcome. Both act on one qubit in the computational
basis; other preparations and measurements are circuits built from them.
H after preparation produces `|+>`; H before Z measurement gives X
measurement.

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
through each binding. A definition used twice must never join the
internal wires of the two uses.

Definitions form a second DAG, whose edges refer to child definitions.
It resembles a parse tree over the operations, with repeated subcircuits
shared. Recursive definitions are excluded.

Tools can inspect, translate or summarise each definition once. Gate
counting can multiply a child's count by its number of uses. Explicit
expansion remains available when a task needs elementary operations.

## Stream

The stream fixes what a circuit means. It writes a circuit as records in
time order, one per line, in 7-bit ASCII. Emitting it to consumers is a
secondary use.

Fields are separated by single spaces, and every line, including the last,
ends with a line feed. A name is a nonempty string of ASCII letters, digits
and underscores. A label is printable ASCII without spaces or parentheses.
A name list is written in parentheses, with each entry `q:name` for a
quantum name or `c:name` for a classical one.

### Records

Quantum operations:

- `CLIF k q`: the single-qubit Clifford with frame `k`, up to phase. Frame
  `k` denotes the matrix product `P[k % 4] R[k // 4]`, with
  `P = (I, X, Y, Z)` and `R = (I, H, S, HS, SH, HSH)`, as in `Clif`.
- `T q`.
- `CZ a b`, with `a` and `b` distinct.
- `PREP q`: prepare `|0>` under a new name `q`.
- `MEAS q`: measure `q` in the computational basis. Afterwards `q` names
  the classical outcome.

`CLIF`, `T` and `CZ` take an optional condition `if c`, where `c` is a
classical name. The gate acts only when `c` is 1.

Classical operations write a new name: `XOR a b -> c`, `AND a b -> c` and
`NOT a -> c`. `DISCARD c` ends a classical name. `REPORT c` ends it and
returns its value; only the root reports.

Definitions:

- `START d (names)` opens definition `d` and binds its ordered input ports.
- `END d (names)` closes it and binds its ordered output ports.
- `REQUEST d (ins) (outs)` uses a definition that has already ended.

The stream is one definition, the root. A definition's first use appears
inline between `START` and `END`; later uses are `REQUEST` records.
`START` and `END` nest and match by `d`. No `d` opens twice, and a
`REQUEST` follows its definition's `END`, which excludes recursion.

### Names

- **Single assignment:** `PREP`, a classical operation, the root's `START`
  list or a `REQUEST` output list introduces a name. No name is introduced
  twice. `MEAS` turns a quantum name into a classical one.
- **Uses:** an inline block and a `REQUEST` are both uses. A use's input
  list is its `START` list or `ins`; its output list is its `END` list or
  `outs`. A name in both lists continues, and the definition's `START` name
  at that input position must be its `END` name at that output position. A
  name only in the input list ends at the use. A name only in the output
  list is new to the caller.
- **Kinds:** a gate uses a quantum name only while it is quantum. A
  classical name can be read any number of times, as a condition or an
  input.
- **Ending:** within each definition, each quantum name ends exactly once,
  by `MEAS`, a use or the `END` list. Each classical name, including a
  measured one, ends exactly once, by `DISCARD`, `REPORT`, a use or the
  `END` list.
- **Scope:** a definition's records use only its `START` names, the names
  it introduces and the names its uses return.

### Digests

A definition's label `d` is its digest: `sha256:` followed by the SHA-256
of the definition's records as stream text, with `d` omitted from its own
`START` and `END`. Before hashing, `START` names become their positions 0,
1, 2 and so on; introduced names continue the count in order of
introduction. Each nested `START ... END` block becomes the `REQUEST` record
for that use.

The digest depends on record order. Library normalisation makes equal
constructions emit equal records. Equal digests then identify a definition
across streams, as a standard library needs. For now a stream contains
every definition it uses; linking against a library can come later.

### Meaning

Replacing each `REQUEST` by its definition's body, with ports rebound and
internal names made fresh, gives a flat straight-line program. That program
is the circuit. A condition decides whether a gate acts, never which record
comes next. The stream carries no global phase; the library keeps phase for
upstream use.

`quantum_circuits.stream` checks these rules and computes this meaning;
[README.md](README.md#the-stream) documents it.

### Example

Measurement-based uncomputation of AND, used twice. The inputs `t` and `u`
hold `a AND b` and `b AND c`. Labels in angle brackets are placeholders,
which `assign_digests` replaces with digests.

```text
START <root> (q:a q:b q:c q:t q:u)
START <undo> (q:a q:b q:t)
CLIF 4 t
MEAS t
CZ a b if t
DISCARD t
END <undo> (q:a q:b)
REQUEST <undo> (q:b q:c q:u) (q:b q:c)
END <root> (q:a q:b q:c)
```

`CLIF 4` is H. The `REQUEST` binds ports 0, 1 and 2 to `b`, `c` and `u`.
To compute `<undo>`, the hasher renames `a`, `b` and `t` to 0, 1 and 2.

## Equality and hashing

Identical definitions should have identical digests. Equivalent definitions
need not, because canonicalisation trades against efficiency. Simple
equivalent circuits should share a digest, as `op('TT')` and `S` already
share a stored form. Complex equivalent circuits will likely not.

Local ports allow reuse on different caller wires while preserving
argument roles. A further goal is to give fragments the same canonical
body and digest when they differ only by a permutation of qubit indices.
Canonicalisation must retain the boundary permutations needed to reconnect
each occurrence correctly. It need not delay circuit construction.

The [stream](#stream) gives a digest's encoding. Child digests enter a
parent's, forming a Merkle DAG. Python's `hash()` is not a persistent
identifier, and a topological traversal does not provide canonical graph
labelling.

Different bodies can implement the same operation: moving T through CZ is
one example. Recognising such identities is later transformation work.

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
builds this body with `CircuitBuilder` and checks it against CCZ on all
eight basis states, exactly and with phase included. It also checks the
body's stream, up to global phase.

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
Both are possible consumers. Their teams decide whether and how to read
the stream.

### Rottnest research

These notes summarise public code and papers examined on 16 and 17 November
2026. No backend code or adapter was run.

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

An adapter from the stream to Rottnest would meet four differences:

- **Vocabulary:** Cabaliser accepts basic Cliffords, CNOT, CZ, tagged Z
  rotations and measurement on numbered qubits. Its additional output
  Clifford labels are not accepted as input. It has no preparation
  instruction; every qubit enters a widget as an input.
- **Rotations:** each tagged rotation adds a graph qubit and is synthesised
  later. Expanding it into T gates beforehand changes this representation.
  Angles are in units of pi; precision is run-wide despite the presence of
  per-rotation tolerance fields.
- **Reuse:** START/END markers open and close a cost frame; REQUEST adds a
  finished frame's cost to the current one. The composer does no qubit
  remapping. Markers also end widgets, so call boundaries can affect
  estimates.
- **Semantics:** the parser strips classical control and applies the gate
  unconditionally, and the pipeline decomposes CCZ into T gates.
  Cabaliser conditions only a Pauli, on a qubit measured in the same
  instruction. The stream's other conditioned gates and its classical
  operations have no counterpart.

Sources: [Cabaliser](https://github.com/QSI-BAQS/cabaliser) (`9bc6ed1`),
[rottnest_py](https://github.com/QSI-BAQS/rottnest_py) (`0109b89`),
[t_scheduler](https://github.com/QSI-BAQS/t_scheduler) (`5af6a31`) and
[rottnest_example_executables](https://github.com/QSI-BAQS/rottnest_example_executables)
(`289b3dc`). Private repositories and Pandora's source were not examined.

### Library boundary

Consumers read the stream or inspect definitions directly: ordered ports,
operations, measurement dependencies and child bindings, without expanding
every occurrence. An adapter translates either into its consumer's format,
decomposition and call boundaries.

The library keeps exact phase; the stream omits it. Any further omission
belongs in an adapter. The library's semantics remain independent of
consumer limitations. No adapter is implemented yet.

## Implementation order

Wires intersect at CZ, and the CCZ body above is built and checked
exactly. The remaining work on circuits closes the gaps between what
`Circuit` can express and what the stream can:

- **Subcircuits:** a circuit that uses other circuits, each use binding a
  subcircuit's ports to the caller's wires. These lower to `START`, `END`
  and `REQUEST`. This comes next.
- **Classical data:** gates conditioned on measurement outcomes, `XOR`,
  `AND` and `NOT`, `DISCARD` and `REPORT`.

Rotation synthesis and coherent arithmetic constructors then supply the
higher-level operations. General equivalence machinery, permutation
canonicalisation and adapters can follow as needed.
