# Circuit design

This document says what the library is for and how it will represent a
circuit. Two other documents go with it. [README.md](README.md) documents
the code that exists today. [BACKEND.md](BACKEND.md) describes the tools
that will consume the circuits.

The library has no type for a circuit yet. The code so far handles operators
on one qubit.

[Purpose](#purpose) · [Where the library sits](#where-the-library-sits) ·
[Why a Merkle tree](#why-a-merkle-tree) ·
[Why the work is done early](#why-the-work-is-done-early) ·
[Foundation](#foundation) · [Example: CCZ](#example-ccz) ·
[Open questions](#open-questions) · [Next step](#next-step)

## Purpose

I am building a compiler for quantum algorithms with my research group. A
user writes an algorithm at a high level, and the compiler produces
circuits. A second team estimates what a circuit costs to run on a
fault-tolerant quantum computer. This document calls them the backend team.

This library sits between the two. It is the Python layer that holds the
compiler's circuits and passes them on. It is a prototype. It is also a
reference implementation, which means a small and clear version that other
code can be checked against.

### The problem

In September 2026 a test run counted the gates in one circuit. It found 29
billion. A tool that handles that circuit gate by gate does 29 billion
pieces of work.

Those gates came from 303 distinct subcircuits, each used many times. A tool
that handles each subcircuit once does 303 pieces of work. This library
stores a circuit so that tools can work that way.

### What the library holds

The library holds a circuit at one fixed stage of compilation. That stage
follows the standard picture of fault-tolerant computing. In that picture a
computation has three ingredients. They are Clifford gates on single qubits,
routes between qubits, and magic states. A magic state is a specially
prepared state. The computer uses one up to perform a gate that it cannot
perform directly.

The library has one kind of operation for each ingredient.

- **A Clifford gate on one qubit.** These are the gates that can be built
  from H and S. The library rewrites every run of them into one fixed form.
  Two runs that make the same gate are stored as the same value.
- **CZ.** This gate acts on two qubits. It multiplies a basis state by -1
  when both qubits are 1. It needs a route between the two qubits. CZ treats
  its two qubits alike. So a qubit needs a name, and it does not need a
  position in a list.
- **T.** This is the gate `diag(1, exp(i*pi/4))`. Each T uses up one magic
  state.

I assume the only magic states are T and CCZ. The representation does not
need CCZ. These assumptions are a starting point for a fuller picture.

The library does not work out what a circuit costs. The backend team does
that, with knowledge of the machine. The library keeps enough information
for a rough estimate.

### How the library holds it

The library stores a circuit as a tree of subcircuits. Each subcircuit is
stored once and translated once, however many times it is used.
[Why a Merkle tree](#why-a-merkle-tree) explains how.

### What else the library is for

The library is the base for three tools that I am writing myself. The first
is gridsynth, which approximates a rotation by a sequence of H, S and T
gates. The second computes the phase angles for quantum signal processing.
The third is polynomial evaluation.

## Where the library sits

```text
compiler  ->  this library  ->  backend team
                            ->  Qualtran
```

Circuits arrive from the compiler. They leave in two directions.

### To the backend team

The backend team estimates what a circuit costs on a machine built from
surface-code patches. They decide where each logical qubit sits. They decide
how operations are routed and when each one runs. They decide which factory
supplies each magic state. They report the number of physical qubits and the
run time. Those answers depend on the machine, and this library decides none
of them.

The library keeps its own representation. It offers the backend team a walk
over a circuit. The walk lists the gates of a subcircuit in the order they
run. It also marks each place where another subcircuit is used.
[BACKEND.md](BACKEND.md) describes their tools and the walk.

### To Qualtran

Qualtran is a Python library from Google for writing quantum algorithms and
counting what they cost. I plan to write circuits out in Qualtran's format,
for three reasons.

- **Qualtran keeps a program as a hierarchy.** Its unit is called a bloq. A
  bloq is made of smaller bloqs. Its
  [call graph](https://qualtran.readthedocs.io/en/latest/resource_counting/call_graph.html)
  lists each smaller bloq once, with the number of times it is used. One
  subcircuit here becomes one bloq there.
- **Qualtran counts what this library keeps apart.** It keeps separate
  counts of Clifford gates, T gates, Toffoli or CCZ gates, and rotations.
- **Qualtran turns counts into machine costs.** Its
  [physical cost models](https://qualtran.readthedocs.io/en/latest/surface_code/physical_cost_model.html)
  take those counts as input. One model follows Gidney and Fowler. The
  compiler project uses their assumptions as its standard for a defensible
  choice.

## Why a Merkle tree

A classical compiler compiles a function once. The machine code exists once,
and every call refers to it. A quantum circuit has no call. The machine runs
every use of a subcircuit in full. So the program it runs is as long as the
gate count.

The September run gives the numbers. Its circuit was a quantized
Metropolis-Hastings walk with 256 sites, 100 temperatures and 500 steps at
each temperature. It had 29 billion gates and 303 distinct subcircuits.

The work of translating that circuit can grow with the 303 and not with the
29 billion. For that, each subcircuit must be translated once, and each use
must refer to the result. So each subcircuit needs an identity.

A programmer gives a function an identity by naming it. Nobody names these
subcircuits. Programs generate them. The same subcircuit can be generated
more than once, by different routes. So the identity is computed from
content. It is a hash. The hash covers the subcircuit's own operations. It
also covers the hashes of the subcircuits it uses. A tree labelled this way
is called a Merkle tree. Two equal subcircuits get the same hash, wherever
they were built.

Compilers already do this under other names.

- **Separate compilation.** A compiler compiles a unit once, and other code
  refers to it. Here the unit is a subcircuit and the reference is its hash.
- **Hash consing and value numbering.** A compiler builds each distinct
  expression once. It looks the expression up under a hash of its operator
  and its operands. That is a Merkle tree over expressions.
  Common-subexpression elimination depends on it. Logic synthesis does the
  same to circuits and calls it structural hashing.
- **Build caches.** Bazel and Nix give each build step a key. The key is a
  hash of the step's inputs, and the inputs include the keys of its
  dependencies. If the key is unchanged, the stored result is reused. Here
  the stored results will be a subcircuit's translated forms, its gate
  counts, and the gate sequence found for a rotation.
- **Summaries over the call graph.** A compiler analyses a function once and
  uses the summary at every call. Here a subcircuit's gate counts are sums
  over the subcircuits it uses. Each of those counts is multiplied by its
  number of uses. Qualtran computes costs over its call graph in the same
  way.
- **Module instantiation.** A hardware description defines a module once,
  with named ports. Each instance connects those ports to wires. A
  subcircuit and its uses have that shape.

A hash matches two subcircuits only if they are written the same way. Two
choices remove ways of writing one thing twice. Clifford gates are put in
one fixed form. CZ has no order on its two qubits. The
[open questions](#open-questions) list the ways that remain.

One requirement follows. The wires belong to each use of a subcircuit and
not to the subcircuit. Otherwise one adder used on two registers would count
as two subcircuits.

## Why the work is done early

A tool can reuse a subcircuit only if it arrives as the same thing every
time. Qualtran counts a bloq once for each distinct value. The backend
team's tools reuse a result that is stored under a key. So the tree has to
exist before a circuit is written out.

Some work could grow with the number of gates the machine runs. The library
does that work while a circuit is being built. The work then grows with the
number of gates that are written down.

- A Clifford gate is merged into its neighbours as it is appended. The merge
  takes constant time and gives one of 192 shared values.
- A subcircuit will be hashed once, when it is built.
- A rotation will be approximated once for each angle and tolerance.

The September run showed what happens otherwise. Its table of subcircuits
reached 211 MB. One subcircuit was stored once for each of the 256 sites.
The copies differed only in the qubits they acted on. Cirq, Google's circuit
library, stored each copy as a separate object.

The backend team has measured the same cost.
[Moflic et al.](https://arxiv.org/abs/2507.20677) report runs of an adder
circuit. Storing and decomposing the circuit in their own tool took about 5%
of the run time. Building the circuit in Python took the rest.

## Foundation

These rules will define a circuit.

- **Shape.** A circuit is a finite directed graph with no cycles. It has an
  ordered list of inputs and an ordered list of outputs.
- **Vertices.** A vertex is an interaction between wires. The only
  elementary interaction is CZ on two different wires, where
  `CZ |a,b> = (-1)**(a*b) |a,b>`. CZ treats its two wires alike.
- **Edges.** A vertex has an input port and an output port for each of its
  wires. An edge starts at a circuit input or at an output port. It ends at
  an input port or at a circuit output. Every port has exactly one edge.
- **Labels.** Each edge carries an exact operator on one qubit, a `WireOp`.
- **Meaning.** The overall phase is part of what a circuit means. The order
  of storage is not. Internal names are not.
- **Validity.** A valid circuit need not be simplified. It may contain two
  equal CZs in a row. Removing them is a transformation.
- **CCZ.** CCZ is not elementary. The equation
  `CCZ |a,b,c> = (-1)**(a*b*c) |a,b,c>` defines the operation. A circuit
  built from CZ implements it, and that circuit is called a body. The
  definition and the body are separate things.

## Example: CCZ

CCZ acts on three wires a, b and c. This body uses six CZ vertices. They are
listed in an order that respects every wire.

```text
vertex   0     1     2     3     4     5
wires    b,c   a,c   b,c   a,c   a,b   a,b
```

Each wire meets four vertices, so it has five edges. The first edge comes
from the input. The next three join consecutive vertices. The last goes to
the output. Each edge carries a label. The labels below are gate words, in
the order the gates run.

```text
a:   I    I           I        T           I
b:   I    I           T H      H T^-1 H    H
c:   H    H T^-1 H    H T H    H T^-1 H    H T
```

Seven edges carry one T or T^-1 each. [tests/test_ccz.py](tests/test_ccz.py)
holds this data. It compares the body with the definition of CCZ on all
eight basis states. The arithmetic is exact and includes the phase.

### Why this body is CCZ

H then CZ then H on a wire is a CNOT onto that wire. So each vertex adds one
bit into another, modulo 2. Write `^` for that sum. Vertices 0 to 3 add into
c. Vertices 4 and 5 add into b.

T multiplies a basis state by `omega**x`. Here x is the bit on the wire and
`omega = exp(i*pi/4)`. T^-1 multiplies by `omega**(-x)`. The seven gates act
on the bits a, b, c, a^b, a^c, b^c and a^b^c. The three T^-1 gates act on
the three sums of two bits. The exponents add up as follows.

```text
a + b + c - (a^b) - (a^c) - (b^c) + (a^b^c) = 4*a*b*c
```

The total factor is `omega**(4*a*b*c)`, which equals `(-1)**(a*b*c)`.

## Open questions

1. **Are two subcircuits the same if they differ only by moving a gate that
   commutes?** T commutes with CZ. The T on wire a could sit on any of a's
   five edges. That gives five bodies and five hashes for one operator.
   Answering "no" costs repeated translation. It does not cost correctness.
2. **Where is the symmetry of an operation recorded?** CCZ treats a, b and c
   alike. This body does not. Its wires carry one, two and four T gates.
   Should a use on (a, b, c) and a use on (b, a, c) have the same hash?
3. **Do a subcircuit's wire names enter its hash?** The purpose gives a
   qubit a name and no position. The foundation gives a circuit ordered
   inputs and outputs. Suppose names enter the hash. Then two subcircuits
   that differ only in naming are translated twice. Suppose they do not.
   Then a fixed numbering must replace the names before hashing. The walk in
   BACKEND.md needs that numbering too.

## Next step

The next step is a subcircuit as a node of the tree. A node holds its own
operations. It holds its uses of other subcircuits, with the wires supplied
to each. It holds a hash over both. The CCZ body is the first node.

Three tests come with it. The body built twice has one hash. A circuit that
uses the body twice stores it once. The check in `tests/test_ccz.py` passes
when it is run from the node.

These pieces of work come later.

- The walk for the backend team.
- Inversion.
- Arithmetic.
- Preparation and measurement.
- Writing out to Qualtran.

An earlier and longer plan is in the Git history. Run
`git show fbf69f9:DESIGN.md` to read it.
