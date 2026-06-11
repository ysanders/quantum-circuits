from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Iterator, Iterable, Any

# messages -------------------------------------------------------------

class Message: pass

@dataclass(frozen=True)
class Enter(Message): frag: "Frag"

@dataclass(frozen=True)
class Exit(Message): frag: "Frag"

class Skip(Message): pass

class Halt(Message, Exception): pass


# frags and operations -------------------------------------------------

Script = Callable[[], Iterator]

class Op(Message): pass

@dataclass(frozen=True)
class Qubit: name: str

@dataclass(frozen=True)
class Measure(Op): q: Qubit

@dataclass(frozen=True)
class SingleGate(Op):
    angle: Fraction
    q:     Qubit

    def __post_init__(self):
        object.__setattr__(self, 'angle', self.angle % 2)

@dataclass(frozen=True)
class DoubleGate(Op):
    angle: Fraction
    q0:    Qubit
    q1:    Qubit

    def __post_init__(self):
        object.__setattr__(self, 'angle', self.angle % 2)


class X(SingleGate): pass
class Y(SingleGate): pass
class Z(SingleGate): pass

class XX(DoubleGate): pass
class YY(DoubleGate): pass
class ZZ(DoubleGate): pass

@dataclass(frozen=True)
class Frag:
    fn: Script

    def emit(self) -> Iterator:
        if isinstance((yield Enter(self)), Skip):
            yield Exit(self)
            return None
        gen = self.fn(); sent = value = None
        while True:
            try: item = gen.send(sent)
            except StopIteration as stop: value = stop.value; break
            if isinstance(item, Halt): raise item
            if isinstance(item, Frag): sent = yield from item.emit()
            else: sent = yield item
        yield Exit(self)
        return value


