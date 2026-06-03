# quantum-circuits

A personal research and teaching support library. **WIP**

Main functionality: the `Frag` abstraction (below).
Reference constructions are built on top of it — presently a Cuccaro ripple-carry adder and the QFT (see the demo in `frag.py`),
with QROM, QSP phase-angle computation, LCU, and QSVT planned.

This library is intentionally minimal.
No comprehensive catalogue of arithmetic circuits, no support for backends such as
[Qiskit](https://www.ibm.com/quantum/qiskit) or [Cirq](https://quantumai.google/cirq),
though translation is easy by design. This library does not even use [NumPy](https://numpy.org/);
aside from the standard library, the sole (optional) import is [mpmath](https://mpmath.org/).

> [!IMPORTANT]
> Expects Python 3.14. Optional dependence on `mpmath`.

---

## The Frag abstraction

A quantum circuit is a stream of `Op`s (an "opstream"), each targeting at most two `Qubit` objects.
A `Qubit` wraps a `name` string that serves as its identity.

There are three kinds of `Op`: `Gate`, `Ising`, and `Measure`.

- A **`Gate`** is a single-qubit Pauli rotation. The three types — `X`, `Y`, `Z` — each carry an angle θ and a target `q`;
  semantically the gate is $\exp(i\theta P)$ for $P = X, Y, Z$.
- An **`Ising`** is a two-qubit Pauli-pair rotation. The three types — `XX`, `YY`, `ZZ` — each carry an angle θ and two qubits `q0`, `q1`;
  semantically the gate is $\exp(i\theta\, P \otimes P)$.
- A **`Measure`** targets exactly one `Qubit`.

There is no controlled gate, and no controlled rotation, among the primitives.
Entanglement enters only through the `Ising` rotations; every controlled operation — `CNOT`, `CZ`, controlled phase, Toffoli —
is the programmer's to build as a combinator from an `Ising` entangler and local rotations, exact up to a global phase.
Multi-controlled and open (|0⟩) controls are likewise combinators. The demo builds the standard ladder.

A `Frag` is the central data structure: a frozen, hashable value that wraps a *generative procedure*.
The procedure (`fn`, of type `Script`) is a no-argument generator function — a thunk — that yields operations and child `Frag`s, and may `return` a value.
You construct a fragment by wrapping its procedure, `Frag(body)`; there is no subclassing and no registration.
A registration process, against a `Library`, is planned but deferred in pursuit of a minimal core;
it is the intended home for the canonical, content-addressed identity of a circuit.
Parameters (qubits, angles, register sizes) live in the procedure's closure, so a parameterised fragment is produced by a factory that returns a `Frag`.

`emit` is a free function, not a method.
`emit(frag)` is a lazy, depth-first walk that yields the annotated opstream, recursing into any child `Frag` the procedure yields —
so a fragment calls another simply by yielding it.
A child's `return` value propagates back as the value of the `yield` that produced it, giving fragments honest subroutine semantics.
`emit` is not itself the interpreter: a *driver* consumes the stream and decides what it means — tracing its structure, flattening it to bare ops, or (later) simulating it.
The demo includes two such drivers.

The stream is of two kinds.

**Operations** — `Gate`, `Ising`, `Measure` — the raw circuit primitives.

**Messages** carry structure and control out of band.

- `Enter` and `Exit` bracket each fragment a driver enters, letting a consumer track structure.
  They also expose the backward channel: the driver sends values back *into* `emit`, which arrive as the value of the corresponding `yield`.
- `Skip` answers an `Enter`: it tells `emit` to skip that fragment's body.
  A skipped fragment is a leaf — it yields its `Enter` and no `Exit`.
- `Halt` is yielded *by* a fragment and is an interrupt: it unwinds every open fragment back to the driver, emitting no further `Exit`s, and the driver receives it.
  It is both a `Message` and an `Exception` — the exception is what performs the unwind.
- A `Measure` is answered the same way an `Enter` is: the fragment that yielded it receives the driver's outcome as the value of its `yield`.
  There is presently no dedicated result wrapper; the outcome is sent in directly.

Numerical values come in many kinds, some of which are merely potential numeric values.
These include gate angles and polynomials of various kinds (regular/Taylor, Chebyshev, Laurent).
Each is carried by `Expr`, which presently is a single type wrapping a string and defining equality by that string;
subtypes for the various polynomial kinds are planned, for maximum flexibility in circuit construction —
a parametric circuit family like QAOA benefits from revisable gate angles.
Keeping values symbolic supports optional `mpmath` representations, frequently required for advanced functionality such as QSP phase-angle computation.

> [!CAUTION]
> This design is not stable. All of the above is subject to breaking change. That includes core structural decisions.
