# Circuit design

No circuit type exists yet. [README.md](README.md) documents what is
implemented: exact single-qubit Clifford+T operators. This document records
the foundation for circuits, one checked example, and the questions that
example leaves open.

[Foundation](#foundation) · [Example: CCZ](#example-ccz) ·
[Open questions](#open-questions) · [Next step](#next-step)

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

1. **Is the written word of an edge needed?** The third edge of wire b is
   written T then H. Its label, `op('TH')`, is
   `WireOp(initial=Clif.from_word('H'), axes='x')`, which reads H then T_x.
   The label keeps the product and not the word.
2. **Are graphs that differ by a commuting label equal?** T commutes with CZ,
   so the T on wire a could label any of a's five edges: five graphs, one
   operator.
3. **Where is the symmetry of an operation recorded?** CCZ is symmetric in
   a, b, c. This body is not: its wires carry one, two and four T gates.
4. **What states the meaning of an operation on n wires?** For three wires,
   eight basis states give the whole matrix, so the test is complete. The
   number of basis states doubles with each wire.

## Next step

A circuit value that holds this example: six CZ vertices, fifteen labelled
edges, two ordered boundaries. Its first test repeats the check in
`tests/test_ccz.py`, starting from that value. If the answer to question 1
is yes, an edge label is not a single `WireOp`, so that question comes first.

Blocks, expansion, inversion, arithmetic, equivalence, preparation and
measurement are deferred until that exists. The earlier plan for them is in
Git history: `git show fbf69f9:DESIGN.md`.
