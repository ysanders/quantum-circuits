from dataclasses import dataclass
from typing import Callable, Iterator, Iterable, Any


# A fragment body: a no-arg generator yielding Ops and child Frags,
# sent measurement outcomes, returning a value.
Script = Callable[[], Iterator]


# values ---------------------------------------------------------------

@dataclass(frozen=True)
class Expr:
    value: str


@dataclass(frozen=True)
class Qubit:
    name: str


# operations -----------------------------------------------------------

class Op:
    pass


@dataclass(frozen=True)
class Gate(Op):                  # single-qubit  exp(i theta P)
    angle: Expr
    q:     Qubit


class X(Gate): pass
class Y(Gate): pass
class Z(Gate): pass


@dataclass(frozen=True)
class Ising(Op):                 # two-qubit  exp(i theta P (x) P)
    angle: Expr
    q0:    Qubit
    q1:    Qubit


class XX(Ising): pass
class YY(Ising): pass
class ZZ(Ising): pass


@dataclass(frozen=True)
class Measure(Op):
    qubit: Qubit


# messages -------------------------------------------------------------

class Message:
    pass


@dataclass(frozen=True)
class Enter(Message):
    frag: "Frag"


@dataclass(frozen=True)
class Exit(Message):
    frag: "Frag"


class Skip(Message):             # sent INTO a frag at Enter: don't run its body
    pass


class Halt(Message, Exception):  # yielded FROM a frag: interrupt, unwind to driver
    pass                         # a Message in the protocol, an Exception for unwind


# frag -----------------------------------------------------------------

@dataclass(frozen=True)
class Frag:
    fn: Script


def emit(frag: Frag) -> Iterator:
    if isinstance((yield Enter(frag)), Skip):
        return None                          # skipped: a leaf, no body, no Exit
    gen = frag.fn()
    sent = value = None
    while True:
        try:
            item = gen.send(sent)
        except StopIteration as stop:
            value = stop.value               # normal completion: the frag's value
            break
        if isinstance(item, Halt):
            raise item                        # interrupt: unwinds outward, no Exit
        if isinstance(item, Frag):
            sent = yield from emit(item)
        else:
            sent = yield item
    yield Exit(frag)
    return value


# demo ------------------------------------------------------------------

if __name__ == "__main__":
    from collections import Counter

    def hadamard(q):                             # = iH
        def proc():
            yield Y(angle=Expr("pi/4"), q=q)
            yield Z(angle=Expr("pi/2"), q=q)
        return Frag(proc)

    def not_(q):                                 # = iX
        def proc():
            yield X(angle=Expr("pi/2"), q=q)
        return Frag(proc)

    def tgate(q):                                # = T
        def proc():
            yield Z(angle=Expr("-pi/8"), q=q)
        return Frag(proc)

    def tdag(q):                                 # = T†
        def proc():
            yield Z(angle=Expr("pi/8"), q=q)
        return Frag(proc)

    def cz(a, b):                                # = CZ
        def proc():
            yield ZZ(angle=Expr("pi/4"), q0=a, q1=b)
            yield Z(angle=Expr("-pi/4"), q=a)
            yield Z(angle=Expr("-pi/4"), q=b)
        return Frag(proc)

    def cnot(c, t):                              # = CNOT
        def proc():
            yield hadamard(t)
            yield cz(c, t)
            yield hadamard(t)
        return Frag(proc)

    def toffoli(a, b, c):                        # = CCNOT
        def proc():
            yield hadamard(c)
            yield cnot(b, c); yield tdag(c)
            yield cnot(a, c); yield tgate(c)
            yield cnot(b, c); yield tdag(c)
            yield cnot(a, c); yield tgate(b); yield tgate(c)
            yield hadamard(c)
            yield cnot(a, b); yield tgate(a); yield tdag(b)
            yield cnot(a, b)
        return Frag(proc)

    def cphase(c, t, level):                     # controlled e^{2*pi*i / 2^level} on |11>
        d = 2 ** (level + 1)                     # ZZ angle = phase/4 (rotation convention)
        def proc():
            yield ZZ(angle=Expr(f"pi/{d}"), q0=c, q1=t)
            yield Z(angle=Expr(f"-pi/{d}"), q=c)
            yield Z(angle=Expr(f"-pi/{d}"), q=t)
        return Frag(proc)

    def swap(a, b):                              # three CNOTs
        def proc():
            yield cnot(a, b); yield cnot(b, a); yield cnot(a, b)
        return Frag(proc)

    def maj(c, b, a):                            # Cuccaro majority: a <- carry(a,b,c)
        def proc():
            yield cnot(a, b)
            yield cnot(a, c)
            yield toffoli(c, b, a)
        return Frag(proc)

    def uma(c, b, a):                            # Cuccaro unmajority-and-add (2-CNOT)
        def proc():
            yield toffoli(c, b, a)
            yield cnot(a, c)
            yield cnot(c, b)
        return Frag(proc)

    def adder(a, b, c0, z):                      # b := a + b; z <- carry out; c0 ancilla (= 0)
        def proc():
            n = len(a)
            yield maj(c0, b[0], a[0])
            for i in range(1, n):
                yield maj(a[i-1], b[i], a[i])
            yield cnot(a[n-1], z)
            for i in range(n-1, 0, -1):
                yield uma(a[i-1], b[i], a[i])
            yield uma(c0, b[0], a[0])
        return Frag(proc)

    def qft(qs):                                 # qs[0] most significant
        def proc():
            n = len(qs)
            for j in range(n):
                yield hadamard(qs[j])
                for k in range(j+1, n):
                    yield cphase(qs[k], qs[j], k-j+1)
            for i in range(n // 2):
                yield swap(qs[i], qs[n-1-i])
        return Frag(proc)

    def measure_correct(q):                      # measure, flip if 1
        def proc():
            outcome = yield Measure(q)           # driver sends the outcome back
            if outcome:
                yield not_(q)                    # conditional correction (a child Frag)
            return outcome                       # captured as this fragment's value
        return Frag(proc)

    def label(frag):
        return frag.fn.__qualname__.split(".")[0]

    def run(frag: Frag, outcomes: Iterable[int] = ()) -> Any:   # driver A: nested trace, skip repeats
        gen, outcomes, seen, depth, sent = emit(frag), iter(outcomes), set(), 0, None
        while True:
            try:
                msg = gen.send(sent)
            except StopIteration as stop:
                return stop.value                # normal: the top frag's value
            except Halt as halt:
                print("  " * depth + f"halt: {halt}"); return halt   # interrupt
            sent = None
            if isinstance(msg, Enter):
                if msg.frag in seen:
                    print("  " * depth + f"skip {label(msg.frag)} (seen)"); sent = Skip()
                else:
                    seen.add(msg.frag); print("  " * depth + f"enter {label(msg.frag)}"); depth += 1
            elif isinstance(msg, Exit):
                depth -= 1; print("  " * depth + f"exit {label(msg.frag)}")
            elif isinstance(msg, Measure):
                sent = next(outcomes, 0); print("  " * depth + f"measure {msg.qubit.name} -> {sent}")
            elif isinstance(msg, Ising):
                print("  " * depth + f"{type(msg).__name__} {msg.q0.name},{msg.q1.name} @ {msg.angle.value}")
            else:                                # single-qubit Gate
                print("  " * depth + f"{type(msg).__name__} {msg.q.name} @ {msg.angle.value}")

    def ops(frag: Frag) -> tuple[list[Op], Any]:  # driver B: flatten to Ops, capture the value
        gen, out, sent = emit(frag), [], None
        while True:
            try:
                msg = gen.send(sent)
            except StopIteration as stop:
                return out, stop.value           # ops AND the captured value
            sent = None
            if isinstance(msg, Measure):
                out.append(msg); sent = 0        # kept as an Op; static outcome 0
            elif isinstance(msg, Op):
                out.append(msg)

    def summary(name, structure, frag):          # flatten and report the gate histogram
        g, _ = ops(frag)
        h = Counter(type(x).__name__ for x in g)
        body = ', '.join(f'{k} x{v}' for k, v in sorted(h.items()))
        print(f"  {name}: {structure}  ->  {len(g)} primitive gates  ({body})")

    q0, q1, q2 = Qubit("q0"), Qubit("q1"), Qubit("q2")

    print("CNOT = H . CZ . H, CZ built from one ZZ entangler (nested structure):")
    run(cnot(q0, q1))

    print("\nFlattening nontrivial circuits to the primitive gate stream:")
    summary("Toffoli", "canonical Clifford+T", toffoli(q0, q1, q2))

    a3 = [Qubit(f"a{i}") for i in range(3)]
    b3 = [Qubit(f"b{i}") for i in range(3)]
    c0, z = Qubit("c0"), Qubit("z")
    summary("adder(n=3)", "3 MAJ + 3 UMA + 1 CNOT", adder(a3, b3, c0, z))

    qs = [Qubit(f"x{i}") for i in range(3)]
    summary("QFT(n=3)", "3 H + 3 controlled-phase + 1 swap", qft(qs))

    print("\nMeasurement send-path and value flow (driver A):")
    value = run(measure_correct(q0), outcomes=[1])
    print("returned:", value)

    print("\nMeasure survives flattening; the value is captured (driver B, static outcome 0):")
    mops, mval = ops(measure_correct(q0))
    print(f"  ops = {[type(o).__name__ for o in mops]}, captured value = {mval}")

    print("\nSkip message (same child instance yielded twice):")
    h = hadamard(q0)
    def twice():
        yield h
        yield h
    run(Frag(twice))

    print("\nHalt interrupt: unwinds every context back to the driver (no Exit emitted):")
    def guarded(q):                              # yields Halt partway; the rest is unreachable
        def proc():
            yield hadamard(q)
            yield Halt("guard tripped")
            yield not_(q)                        # never reached
        return Frag(proc)
    def outer(q):                                # Halt fires nested; outer never exits cleanly
        def proc():
            yield not_(q)
            yield guarded(q)
            yield hadamard(q)                    # never reached
        return Frag(proc)
    halted = run(outer(q0))
    print("returned:", repr(halted))

