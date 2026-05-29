
# quantum-circuits

A personal research and teaching support library. **WIP**

Main functionality: the `Frag` abstraction (see below).
Also includes reference implementations of standard constructions such as arithmetic circuits, QROM, QFT, QSP phase angle calculation, LCU, QSVT.

This library is intentionally minimal.
No comprehensive list of arithmetic circuits, no support for backends such as
[Qiskit](https://www.ibm.com/quantum/qiskit) or [Cirq](https://quantumai.google/cirq),
though translation is easy by design. This library does not even support [NumPy](https://numpy.org/);
aside from standard libraries, the sole (optional) import is [mpmath](https://mpmath.org/).

> [!IMPORTANT]
> Expects Python 3.14. Optional dependence on `mpmath`.

---

## The Frag abstraction

A quantum circuit is a stream of `Gate` and `Measure` objects ("gatestream"), each of which target a single qubit.
There are three `Gate` types: `X`, `Y`, and `Z`. Instances are defined by an angle θ and an optional control qubit.
Semantically, the gate is $\exp(iθP)$ for $P=X,Y,Z$.

A `Frag` is a lazy constructor that emits a gatestream (via `emit()`),
possibly including announcements (e.g. enter/exit the `Frag` instance) or calls to other fragment types.
One defines a new fragment type by subclassing `Frag`, i.e. `class MyCircuit(Frag): ...`.
A `Frag` subclass must be bound to a `Library` instance; otherwise, a `TypeError` is raised.
`Frag` itself cannot be instantiated for this reason; its library is `None` and its parent class `FragMeta` does not allow registration of `Frag`.

Calling a `Frag` subclass therefore create frozen and hashable instances from `Qubit` inputs.
A `Qubit` wraps a string (`name`) that constitutes its unique identifier; no two qubits have the same `name`.
A `Frag` call cannot refer to the same `Qubit` twice; this is checked on instantiation.

The `emit()` method of `Frag` yields an annotated gatestream. Raw gatestreams consist only of `Gate` and `Measure` objects.
Annotations are instances of `Announce`; typically they announce entry and exit of a `Frag` subclass or structured calls (e.g. `Zip`),
enabling the downstream consumer to send a `Skip` instruction.

The underlying generator is an instance of `Script`;
a subclass of `Frag` requires a `Script` instance at definition time.
The `emit()` method is therefore a lazy depth-first traversal of the call tree specified by a `Script`, 
yielding a stream of `Gate`, `Measure`, and `Announcement` objects.
Thus the `Frag` class is consciously designed to enable memoisation.

Numerical values such as gate angles, polynomial coefficients, and register sizes are `Expr` subtypes:
`str` wrappers that are immutable, hashable, and define equality by `str` equality.
This decision supports `mpmath` representations, which are strictly optional
but frequently required for certain advanced functionality such as phase angle computaions for quantum signal processing.

> [!CAUTION]
> This design is not stable. All of the above is subject to breaking change. That includes core structural decisions.

## Structure

```
quantum_circuits/
├── core/          Frag base class, Script, Expr types, Gate primitives, FragLibrary
├── stdlib/        QFT, arithmetic, QROM, phase estimation, amplitude amplification
├── classical/     Phase-finding, polynomial approximation, continued fractions
├── combinators/   QSP, QSVT, LCU, controlled-U, reflection
└── print/         SVG and TikZ circuit diagrams
```

