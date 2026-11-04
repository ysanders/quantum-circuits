# Design boundaries

This is a single-author environment for constructing quantum algorithms from
immutable descriptions. Ordinary Python functions provide abstraction and
higher-order construction. Consumers can inspect returned values without
executing those functions again.

## Implemented foundation

`SingleQubitOperator` is the central single-qubit value. Constructors discard
word history and produce a unique Clifford-plus-axis representation, including
global phase. Frozen-dataclass equality and hashing follow from those fields.
`SingleQubitClifford` remains supporting algebra with exact generated tables.
Neither type depends on qubit names.

`Gate` attaches a target to an operator. CZ and CCZ are separate symmetric
nodes. `seq` flattens visible sequences and combines adjacent single-qubit
operations on the same wire. It does not commute gates. Canonical single-qubit
equality and local structural circuit equality are different guarantees.

The implemented API, conventions, normaliser, and verification scope are in
[docs/core.md](docs/core.md). There is one runtime package, one test suite,
and one example directory; no compatibility model is retained.

## Compilation boundary

The eventual downstream vocabulary is single-qubit Cliffords, T, CZ, and CCZ.
A stored Gate is a compact operator value; it need not be one downstream
instruction. `iter_gates` gives an exact H/S/T lowering with minimal T-count
for the isolated operator. This makes no claim about whole-circuit
optimisation, magic-state choice, or routing.

Arbitrary rotations are outside the exact type. Their synthesis needs an
explicit approximation tolerance and phase guarantee, producing an exact
operator value plus error information. That stage is not implemented here.

## Further work

The next semantic milestone remains interchangeable coherent and measured
cleanup of a temporary AND, followed by arithmetic using that contract.
Measurement results need explicit classical slots and inspectable branches.
Cleanup contracts must specify the valid input subspace and preserve coherence
and entanglement on it. Basis-state output tests alone cannot establish that.

Contracts, named fragments, Repeat, Measure, If, resource analysis, arbitrary
rotation synthesis, and export are not implemented. Generic adjoint and
coherent-control transformations must eventually distinguish unitary
descriptions from implementations with measurement and classical feedback.

No ownership system, global operator interning, symbolic expression framework,
or general proof engine is needed for the foundation. `.qubits` reports
referenced wires; a future fragment signature can declare its interface even
when its body simplifies to identity.
