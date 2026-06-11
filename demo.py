from dataclasses import dataclass
from typing import Callable, Iterator, Iterable, Any

Script = Callable[[], Iterator]

@dataclass(frozen=True)
class Expr: value: str

@dataclass(frozen=True)
class Qubit: name: str

class Op: pass

@dataclass(frozen=True)
class SingleGate(Op):
    angle: Expr
    q:     Qubit

@dataclass(frozen=True)
class DoubleGate(Op):
    angle: Expr
    q0:    Qubit
    q1:    Qubit

class X(SingleGate): pass
class Y(SingleGate): pass
class Z(SingleGate): pass

class XX(DoubleGate): pass
class YY(DoubleGate): pass
class ZZ(DoubleGate): pass

@dataclass(frozen=True)
class Measure(Op): qubit: Qubit

class Message: pass

@dataclass(frozen=True)
class Enter(Message): frag: "Frag"

@dataclass(frozen=True)
class Exit(Message): frag: "Frag"

class Skip(Message): pass

class Halt(Message, Exception): pass

@dataclass(frozen=True)
class Frag:
    fn: Script
    qs: Qubit | Iterable[Qubit]

def emit(frag: Frag) -> Iterator:
    if isinstance((yield Enter(frag)), Skip): return None 
    gen = frag.fn(frag.qs)
    sent = value = None
    while True:
        try: item = gen.send(sent)
        except StopIteration as stop: value = stop.value; break
        if isinstance(item, Halt): raise item
        if isinstance(item, Frag): sent = yield from emit(item)
        else: sent = yield item
    yield Exit(frag)
    return value

# Standard Frags

def hadamard(targ: Qubit):
    def proc(q):
        yield Y(angle=Expr("π/4"), q=q)
        yield X(angle=Expr("π/2"), q=q)
    return Frag(proc, targ)

def cz(fst: Qubit, snd: Qubit):
    def proc(qpair):
        yield ZZ(angle=Expr("π/4"), q0=qpair[0], q1=qpair[1])
        yield Z(angle=Expr("-π/4"), q=qpair[0])
        yield Z(angle=Expr("-π/4"), q=qpair[1])
    return Frag(proc, (fst, snd))

def cnot(ctrl: Qubit, targ: Qubit):
    def proc(qpair):
        yield hadamard(qpair[1])
        yield cz(*qpair)
        yield hadamard(qpair[1])
    return Frag(proc, (ctrl, targ))


if __name__ == "__main__":
    for op in emit(hadamard(Qubit('test'))):
        print(op)

    for op in emit(cz(Qubit("fst"), Qubit("snd"))):
        print(op)

    for op in emit(cnot(Qubit("ctrl"), Qubit("targ"))):
        print(op)

