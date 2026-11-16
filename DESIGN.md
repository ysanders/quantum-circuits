# Circuit design

No circuit type exists yet. [README.md](README.md) documents what is
implemented: exact single-qubit Clifford+T operators. This document records
the purpose of the library, its place between the compiler and the backend
team, the foundation for circuits, one checked example, and the open
questions.

[Purpose](#purpose) · [Where this layer sits](#where-this-layer-sits) ·
[Why a Merkle tree](#why-a-merkle-tree) ·
[Why the work is done before extraction](#why-the-work-is-done-before-extraction) ·
[Foundation](#foundation) · [Example: CCZ](#example-ccz) ·
[Open questions](#open-questions) · [Next step](#next-step)

## Purpose

This library is the Python layer between the compiler's output and the
backend team's tools. It sits above Qualtran, which is its extraction target.
It is part prototype, part reference implementation.

It holds a circuit at one chosen point in compilation: the canonical form of
fault-tolerant execution, which is single-qubit Cliffords plus routing plus
magic state distillation. Single-qubit Cliffords are normalised. The only
other primitives are T and CZ. CZ is symmetric, so a qubit needs a name and
no position. The magic states assumed are T and CCZ; the representation does
not need CCZ, which is a starting point for the more complex picture. Cost
analysis proper happens further down. This layer keeps the information a
heuristic needs.

A complex circuit is a Merkle tree of subcircuits. A subcircuit is then
lowered once, however often it is used.

The library is also the foundation for tools I am writing myself: gridsynth,
quantum signal processing phase angles, and polynomial evaluation.

## Where this layer sits

```text
compiler  ->  this layer  ->  Qualtran  ->  backend team
```

The compiler's circuit-level output arrives here.

The backend team compiles a logical program for a machine and costs it. They
decide where logical qubits are placed, how operations are routed between
them, when each operation runs, which factory supplies each magic state, and
how ancillas are allocated and reused. Those decisions depend on the device,
and they set the cost of a computation. This layer makes none of them.

This layer gives the backend team a program in a form their tools accept and
at a size they can store. The program names every operation that consumes a
magic state and every pair of qubits that must interact, and it keeps the
subcircuit structure.

Qualtran is that form, for four reasons.

- The backend team's tools read Cirq. Cirq's fault-tolerant resource
  estimation [has moved to Qualtran](https://groups.google.com/g/cirq-announce/c/ODloFuQoze0),
  and Qualtran [interoperates with Cirq](https://qualtran.readthedocs.io/en/latest/cirq_interop/cirq_interop.html),
  which its documentation describes as analogous to a quantum assembly
  language.
- Qualtran keeps a program as a hierarchy. A bloq decomposes into bloqs, and
  its [call graph](https://qualtran.readthedocs.io/en/latest/resource_counting/call_graph.html)
  lists each callee once with the number of calls. One subcircuit here
  becomes one bloq there.
- Qualtran's accounting separates what this layer separates: Cliffords from
  T, Toffoli or CCZ, and rotations.
- Qualtran's [physical cost models](https://qualtran.readthedocs.io/en/latest/surface_code/physical_cost_model.html)
  take those counts as input. One of them follows Gidney and Fowler, whose
  expectations are the compiler project's standard for a defensible choice.

## Why a Merkle tree

A classical compiler compiles a function once. The machine code exists once,
and each call site refers to it. A circuit has no call. The machine executes
every use of a subcircuit in place, so the program it executes is as long as
its gate count. In September 2026 a costing run of the quantized
Metropolis-Hastings walk (256 sites, 100 temperatures, 500 steps each)
counted 29 billion gates. They came from 303 distinct subcircuits.

The work of lowering can scale with 303 and not with 29 billion. It does so
if each subcircuit is lowered once and each use refers to the result. That
requires every subcircuit to have an identity.

A programmer gives a function its identity by naming it. Nobody names these
subcircuits: programs generate them, and the same subcircuit is generated
more than once, by different routes. The identity is therefore computed from
content. It is a hash of the subcircuit's own operations together with the
hashes of the subcircuits it uses. A tree whose nodes are labelled this way
is a Merkle tree. Equal subcircuits have equal hashes wherever they were
built.

Compilers already work this way, under other names.

- **Separate compilation.** A unit is compiled once and linked by reference.
  Here the unit is a subcircuit and the reference is its hash.
- **Hash consing and value numbering.** A compiler builds each distinct
  expression once by looking it up under a hash of its operator and the
  identities of its operands. That is a Merkle tree over expressions, and
  common-subexpression elimination depends on it. Logic synthesis does the
  same to circuits and calls it structural hashing.
- **Build caches.** Bazel and Nix key each build step on a hash of its
  inputs, which include the hashes of its dependencies. An unchanged hash
  means the stored result is reused. Here the stored results will be a
  subcircuit's lowered form, its counts, a gridsynth word, and its Qualtran
  bloq.
- **Summaries over the call graph.** A compiler analyses a function once and
  uses the summary at every call. Here a subcircuit's counts are the sums of
  its children's counts, each multiplied by its number of uses. Qualtran
  computes costs over its call graph in the same way.
- **Module instantiation.** A hardware description defines a module once,
  with formal ports, and each instance connects those ports to wires. A
  subcircuit and its uses have that shape.

A hash identifies equal things only when equal things are written the same
way. Normalising Cliffords and using a symmetric CZ each remove one way of
writing an operation twice. The open questions list ways that remain.

One requirement follows. The wires a subcircuit acts on belong to each use
and not to the subcircuit. Otherwise the same adder on two registers is two
subcircuits.

## Why the work is done before extraction

Qualtran counts a bloq once per distinct value, so equal subcircuits have to
reach it as equal values. The tree therefore has to exist before extraction,
and extraction then creates one bloq for each distinct subcircuit.

Work whose cost could follow the gate count belongs here, at a cost that
follows what is written. A Clifford is already fused as it is appended, in
constant time, into one of 192 shared values. A subcircuit will be hashed
once, when it is built. A rotation will be synthesised once for each angle
and tolerance.

The September run measured the failure this prevents. Its table of
subcircuits reached 211 MB because one subcircuit was stored once for each of
the 256 sites. The copies differed only in the qubits they acted on, and Cirq
stored each as a separate object.

## Foundation

- A circuit is a finite directed acyclic graph with an ordered input boundary
  and an ordered output boundary.
- A vertex is an interaction. The only elementary interaction is CZ on two
  distinct wires, `CZ |a,b> = (-1)**(a*b) |a,b>`. Its two operands are
  symmetric.
- A vertex has an input port and an output port for each of its wires. An
  edge runs from a boundary input or an output port to an input port or a
  boundary output. Every port has exactly one edge.
- An edge is labelled by an exact `WireOp`.
- Scalar phase is part of a circuit's meaning. Storage order and internal
  names are not.
- Validity does not require a reduced form. A circuit may contain two
  adjacent equal CZs; removing them is a transformation.
- CCZ is not elementary. `CCZ |a,b,c> = (-1)**(a*b*c) |a,b,c>` defines the
  operation. A body built from CZ implements it. The definition and the body
  are separate.

## Example: CCZ

Wires a, b, c. Six CZ vertices, listed in an order consistent with every
wire:

```text
vertex   0     1     2     3     4     5
wires    b,c   a,c   b,c   a,c   a,b   a,b
```

Each wire meets four vertices and so has five edges: from the input, between
consecutive vertices, and to the output. The edge labels, as gate words in
execution order:

```text
a:   I    I           I        T           I
b:   I    I           T H      H T^-1 H    H
c:   H    H T^-1 H    H T H    H T^-1 H    H T
```

Seven edges carry one T or T^-1 each. [tests/test_ccz.py](tests/test_ccz.py)
holds this data and compares it with the definition of CCZ on all eight basis
states, in exact arithmetic, phase included.

H, CZ, H on a target wire is a CNOT, so each vertex adds one bit into another
modulo 2, written `^`: vertices 0 to 3 add into c, vertices 4 and 5 add into
b. T multiplies a basis state by `omega**x`, where x is the bit on its wire
and `omega = exp(i*pi/4)`; T^-1 multiplies by `omega**(-x)`. The seven gates
act on the bits a, b, c, a^b, a^c, b^c and a^b^c, with T^-1 on the three
pairwise sums, and

```text
a + b + c - (a^b) - (a^c) - (b^c) + (a^b^c) = 4*a*b*c
```

so the total factor is `omega**(4*a*b*c) = (-1)**(a*b*c)`.

## Open questions

1. **Are subcircuits that differ by a commuting label one subcircuit?** T
   commutes with CZ, so the T on wire a could label any of a's five edges:
   five bodies, five hashes, one operator. A "no" costs duplicated lowering.
   It does not cost correctness.
2. **Where is the symmetry of an operation recorded?** CCZ is symmetric in
   a, b, c. This body is not: its wires carry one, two and four T gates. Do
   a use of CCZ on (a, b, c) and a use on (b, a, c) have one hash?
3. **Do a subcircuit's own names enter its hash?** The purpose gives a qubit
   a name and no position; the foundation above gives a circuit ordered
   boundaries. If names enter the hash, two subcircuits that differ only in
   naming are lowered twice. If they do not, something canonical replaces
   them before hashing.

## Next step

A subcircuit as a node of the tree: its own operations, its uses of other
subcircuits with the wires supplied to each, and a hash over both. The CCZ
body is the first node. Its tests: the body built twice has one hash, a
circuit that uses it twice stores it once, and the check in
`tests/test_ccz.py` repeats from the node.

Inversion, arithmetic, preparation and measurement, and extraction to
Qualtran follow. An earlier, longer plan is in Git history:
`git show fbf69f9:DESIGN.md`.
