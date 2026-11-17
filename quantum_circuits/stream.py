"""The stream: a circuit written as text records in time order.

DESIGN.md (Stream) states the rules that check_stream enforces and the
meaning that expand computes. Stream text is 7-bit ASCII with one record
per line; every line, including the last, ends with a line feed.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

__all__ = [
    'QUANTUM', 'CLASSICAL', 'Port', 'Record',
    'Phase', 'CliffordGate', 'TGate', 'CZGate', 'Prepare', 'Measure', 'ClassicalOp',
    'Discard', 'Report', 'Start', 'End', 'Request',
    'StreamError', 'Definition', 'Program', 'FlatCircuit',
    'parse_stream', 'format_stream', 'check_stream', 'assign_digests', 'expand',
]

QUANTUM = 'q'
CLASSICAL = 'c'
_KIND_WORDS = {QUANTUM: 'quantum', CLASSICAL: 'classical'}

_NAME = re.compile(r'[A-Za-z0-9_]+')
# Printable ASCII except space (0x20) and parentheses (0x28 and 0x29).
_LABEL = re.compile(r"[!-'*-~]+")
_FRAME_NUMBER = re.compile(r'0|[1-9][0-9]?')
_CLASSICAL_ARITY = {'XOR': 2, 'AND': 2, 'NOT': 1}


class StreamError(ValueError):
    """Stream text or records that break the format or a rule in DESIGN.md."""


# Validation of record fields.

def _check_name(value: object, role: str) -> None:
    """Reject anything but a nonempty string of ASCII letters, digits, underscores."""
    if type(value) is not str:
        raise TypeError(f'{role} must be a string')
    if not _NAME.fullmatch(value):
        raise ValueError(
            f'{role} {value!r} must use only ASCII letters, digits and underscores')


def _check_condition(value: object) -> None:
    if value is not None:
        _check_name(value, 'condition')


def _check_label(value: object) -> None:
    if type(value) is not str:
        raise TypeError('label must be a string')
    if not _LABEL.fullmatch(value):
        raise ValueError(
            f'label {value!r} must be printable ASCII without spaces or parentheses')


def _check_ports(value: object, role: str) -> None:
    if type(value) is not tuple or not all(isinstance(port, Port) for port in value):
        raise TypeError(f'{role} must be a tuple of Port values')
    names = [port.name for port in value]
    if len(set(names)) != len(names):
        raise ValueError(f'{role} must not repeat a name')


# Records. Each validates its own fields; the rules that relate records to
# one another are checked by check_stream.

@dataclass(frozen=True, slots=True)
class Port:
    """A name in a START, END or REQUEST list, marked quantum or classical."""

    kind: str
    name: str

    def __post_init__(self) -> None:
        if self.kind not in _KIND_WORDS:
            raise ValueError("port kind must be 'q' (quantum) or 'c' (classical)")
        _check_name(self.name, 'port name')


@dataclass(frozen=True, slots=True)
class Phase:
    """PHASE k: multiply by exp(i*pi*k/4), with no wire operand."""

    exponent: int

    def __post_init__(self) -> None:
        if type(self.exponent) is not int:
            raise TypeError('phase exponent must be an integer (not a boolean)')
        if not 0 <= self.exponent < 8:
            raise ValueError('phase exponent must be in range(8)')


@dataclass(frozen=True, slots=True)
class CliffordGate:
    """CLIF k q: the exact single-qubit Clifford Clif(k, phase=0).

    Frame k denotes the matrix product P[k % 4] R[k // 4], with
    P = (I, X, Y, Z) and R = (I, H, S, HS, SH, HSH), as for Clif.
    """

    frame: int
    qubit: str
    condition: str | None = None

    def __post_init__(self) -> None:
        if type(self.frame) is not int:
            raise TypeError('frame must be an integer (not a boolean)')
        if not 0 <= self.frame < 24:
            raise ValueError('frame must be in range(24)')
        _check_name(self.qubit, 'qubit')
        _check_condition(self.condition)


@dataclass(frozen=True, slots=True)
class TGate:
    """T q, applied only when the optional condition is 1."""

    qubit: str
    condition: str | None = None

    def __post_init__(self) -> None:
        _check_name(self.qubit, 'qubit')
        _check_condition(self.condition)


@dataclass(frozen=True, slots=True)
class CZGate:
    """CZ a b on two distinct qubits, applied only when the optional condition is 1."""

    first: str
    second: str
    condition: str | None = None

    def __post_init__(self) -> None:
        _check_name(self.first, 'qubit')
        _check_name(self.second, 'qubit')
        if self.first == self.second:
            raise ValueError('CZ needs two distinct qubits')
        _check_condition(self.condition)


@dataclass(frozen=True, slots=True)
class Prepare:
    """PREP q: prepare |0> under a new name."""

    qubit: str

    def __post_init__(self) -> None:
        _check_name(self.qubit, 'qubit')


@dataclass(frozen=True, slots=True)
class Measure:
    """MEAS q: measure in the computational basis; q then names the outcome."""

    qubit: str

    def __post_init__(self) -> None:
        _check_name(self.qubit, 'qubit')


@dataclass(frozen=True, slots=True)
class ClassicalOp:
    """XOR a b -> c, AND a b -> c or NOT a -> c, written to a new name c."""

    operator: str
    operands: tuple[str, ...]
    result: str

    def __post_init__(self) -> None:
        if self.operator not in _CLASSICAL_ARITY:
            raise ValueError("operator must be 'XOR', 'AND' or 'NOT'")
        if type(self.operands) is not tuple:
            raise TypeError('operands must be a tuple of names')
        arity = _CLASSICAL_ARITY[self.operator]
        if len(self.operands) != arity:
            raise ValueError(f'{self.operator} takes {arity} operand(s)')
        for operand in self.operands:
            _check_name(operand, 'operand')
        _check_name(self.result, 'result')
        if self.result in self.operands:
            raise ValueError('a classical operation writes a new name, not an operand')


@dataclass(frozen=True, slots=True)
class Discard:
    """DISCARD c: end a classical name without returning its value."""

    name: str

    def __post_init__(self) -> None:
        _check_name(self.name, 'name')


@dataclass(frozen=True, slots=True)
class Report:
    """REPORT c: end a classical name and return its value. Root only."""

    name: str

    def __post_init__(self) -> None:
        _check_name(self.name, 'name')


@dataclass(frozen=True, slots=True)
class Start:
    """START d (names): open definition d, binding its ordered input ports."""

    label: str
    ports: tuple[Port, ...]

    def __post_init__(self) -> None:
        _check_label(self.label)
        _check_ports(self.ports, 'START list')


@dataclass(frozen=True, slots=True)
class End:
    """END d (names): close definition d, binding its ordered output ports."""

    label: str
    ports: tuple[Port, ...]

    def __post_init__(self) -> None:
        _check_label(self.label)
        _check_ports(self.ports, 'END list')


@dataclass(frozen=True, slots=True)
class Request:
    """REQUEST d (ins) (outs): use a definition that has already ended."""

    label: str
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]

    def __post_init__(self) -> None:
        _check_label(self.label)
        _check_ports(self.inputs, 'REQUEST input list')
        _check_ports(self.outputs, 'REQUEST output list')


Record = (
    Phase | CliffordGate | TGate | CZGate | Prepare | Measure | ClassicalOp
    | Discard | Report | Start | End | Request
)
_RECORD_TYPES = (
    Phase, CliffordGate, TGate, CZGate, Prepare, Measure, ClassicalOp,
    Discard, Report, Start, End, Request,
)
_CONDITIONAL_GATES = (CliffordGate, TGate, CZGate)


def _as_records(records: Iterable[Record]) -> tuple[Record, ...]:
    records = tuple(records)
    for record in records:
        if not isinstance(record, _RECORD_TYPES):
            raise TypeError(f'not a stream record: {record!r}')
    return records


# Text.

def _format_names(ports: tuple[Port, ...]) -> str:
    return ' '.join(f'{port.kind}:{port.name}' for port in ports)


def _condition_suffix(condition: str | None) -> str:
    return '' if condition is None else f' if {condition}'


def _format_record(record: Record) -> str:
    """One line of stream text, without its line feed."""
    if isinstance(record, Phase):
        return f'PHASE {record.exponent}'
    if isinstance(record, CliffordGate):
        return (f'CLIF {record.frame} {record.qubit}'
                f'{_condition_suffix(record.condition)}')
    if isinstance(record, TGate):
        return f'T {record.qubit}{_condition_suffix(record.condition)}'
    if isinstance(record, CZGate):
        return (f'CZ {record.first} {record.second}'
                f'{_condition_suffix(record.condition)}')
    if isinstance(record, Prepare):
        return f'PREP {record.qubit}'
    if isinstance(record, Measure):
        return f'MEAS {record.qubit}'
    if isinstance(record, ClassicalOp):
        return f'{record.operator} {" ".join(record.operands)} -> {record.result}'
    if isinstance(record, Discard):
        return f'DISCARD {record.name}'
    if isinstance(record, Report):
        return f'REPORT {record.name}'
    if isinstance(record, Start):
        return f'START {record.label} ({_format_names(record.ports)})'
    if isinstance(record, End):
        return f'END {record.label} ({_format_names(record.ports)})'
    if isinstance(record, Request):
        return (f'REQUEST {record.label} ({_format_names(record.inputs)})'
                f' ({_format_names(record.outputs)})')
    raise TypeError(f'not a stream record: {record!r}')


def format_stream(records: Iterable[Record]) -> str:
    """Write records as stream text: one line each, each ending with a line feed."""
    return ''.join(_format_record(record) + '\n' for record in _as_records(records))


_START_OR_END = re.compile(r'(START|END) (\S+) \(([^()]*)\)')
_REQUEST = re.compile(r'REQUEST (\S+) \(([^()]*)\) \(([^()]*)\)')
_ONE_NAME_RECORDS = {
    'PREP': Prepare, 'MEAS': Measure, 'DISCARD': Discard, 'REPORT': Report,
}
_GATE_QUBIT_COUNTS = {'CLIF': 1, 'T': 1, 'CZ': 2}


def _parse_names(text: str) -> tuple[Port, ...]:
    if text == '':
        return ()
    ports = []
    for entry in text.split(' '):
        kind, colon, name = entry.partition(':')
        if not colon:
            raise ValueError(f'list entry {entry!r} must be q:name or c:name')
        ports.append(Port(kind, name))
    return tuple(ports)


def _parse_gate(fields: list[str]) -> Record:
    keyword = fields[0]
    # CLIF has a frame field before its qubit.
    field_count = 1 + (keyword == 'CLIF') + _GATE_QUBIT_COUNTS[keyword]
    condition = None
    if len(fields) == field_count + 2 and fields[field_count] == 'if':
        condition = fields[-1]
        fields = fields[:field_count]
    if len(fields) != field_count:
        raise ValueError(
            f'{keyword} takes {field_count - 1} field(s) and an optional "if name"')
    if keyword == 'CLIF':
        if not _FRAME_NUMBER.fullmatch(fields[1]):
            raise ValueError(
                'CLIF frame must be a decimal integer without leading zeros')
        return CliffordGate(int(fields[1]), fields[2], condition)
    if keyword == 'T':
        return TGate(fields[1], condition)
    return CZGate(fields[1], fields[2], condition)


def _parse_classical(fields: list[str]) -> ClassicalOp:
    keyword = fields[0]
    arity = _CLASSICAL_ARITY[keyword]
    if len(fields) != arity + 3 or fields[arity + 1] != '->':
        operand_text = 'a b' if arity == 2 else 'a'
        raise ValueError(
            f'{keyword} must be written {keyword} {operand_text} -> result')
    return ClassicalOp(keyword, tuple(fields[1:arity + 1]), fields[-1])


def _parse_record(line: str) -> Record:
    if line == '':
        raise ValueError('a blank line is not a record')
    keyword = line.split(' ', 1)[0]
    if keyword in ('START', 'END'):
        match = _START_OR_END.fullmatch(line)
        if match is None:
            raise ValueError(f'{keyword} must be written {keyword} label (names)')
        record_type = Start if keyword == 'START' else End
        return record_type(match[2], _parse_names(match[3]))
    if keyword == 'REQUEST':
        match = _REQUEST.fullmatch(line)
        if match is None:
            raise ValueError('REQUEST must be written REQUEST label (names) (names)')
        return Request(match[1], _parse_names(match[2]), _parse_names(match[3]))
    fields = line.split(' ')
    if '' in fields:
        raise ValueError('fields must be separated by single spaces')
    if keyword == 'PHASE':
        if (len(fields) != 2 or len(fields[1]) != 1
                or fields[1] not in '01234567'):
            raise ValueError('PHASE takes one exponent from 0 to 7')
        return Phase(int(fields[1]))
    if keyword in _GATE_QUBIT_COUNTS:
        return _parse_gate(fields)
    if keyword in _CLASSICAL_ARITY:
        return _parse_classical(fields)
    if keyword in _ONE_NAME_RECORDS:
        if len(fields) != 2:
            raise ValueError(f'{keyword} takes one name')
        return _ONE_NAME_RECORDS[keyword](fields[1])
    raise ValueError(f'unknown record {keyword!r}')


def parse_stream(text: str) -> tuple[Record, ...]:
    """Parse stream text into records. This checks the format, not the rules."""
    if type(text) is not str:
        raise TypeError('stream text must be a string')
    for position, character in enumerate(text):
        if character != '\n' and not ' ' <= character <= '~':
            line_number = text.count('\n', 0, position) + 1
            raise StreamError(
                f'line {line_number}: {character!r} is not printable 7-bit ASCII')
    if text and not text.endswith('\n'):
        raise StreamError('the last record must end with a line feed')
    records = []
    # Every line ends with a line feed, so the final split piece is empty.
    for line_number, line in enumerate(text.split('\n')[:-1], start=1):
        try:
            records.append(_parse_record(line))
        except (TypeError, ValueError) as error:
            raise StreamError(f'line {line_number}: {error}') from None
    return tuple(records)


# Canonical form and digests.

def _rename_operation(record: Record, rename: Callable[[str], str]) -> Record:
    """Copy an operation record with every name passed through rename."""
    def condition(name: str | None) -> str | None:
        return None if name is None else rename(name)

    if isinstance(record, Phase):
        return record
    if isinstance(record, CliffordGate):
        return CliffordGate(record.frame, rename(record.qubit),
                            condition(record.condition))
    if isinstance(record, TGate):
        return TGate(rename(record.qubit), condition(record.condition))
    if isinstance(record, CZGate):
        return CZGate(rename(record.first), rename(record.second),
                      condition(record.condition))
    if isinstance(record, Prepare):
        return Prepare(rename(record.qubit))
    if isinstance(record, Measure):
        return Measure(rename(record.qubit))
    if isinstance(record, ClassicalOp):
        return ClassicalOp(record.operator,
                           tuple(rename(operand) for operand in record.operands),
                           rename(record.result))
    if isinstance(record, Discard):
        return Discard(rename(record.name))
    if isinstance(record, Report):
        return Report(rename(record.name))
    raise TypeError(f'not an operation record: {record!r}')


def _introduced_name(record: Record) -> str | None:
    """The name an operation record introduces, if it introduces one."""
    if isinstance(record, Prepare):
        return record.qubit
    if isinstance(record, ClassicalOp):
        return record.result
    return None


def _digest(inputs: tuple[Port, ...], body: Iterable[Record],
            outputs: tuple[Port, ...]) -> str:
    """'sha256:' and the SHA-256 of a canonical definition's records.

    The definition's own START and END omit its label, which would
    otherwise be part of what it hashes.
    """
    lines = [f'START ({_format_names(inputs)})']
    lines.extend(_format_record(record) for record in body)
    lines.append(f'END ({_format_names(outputs)})')
    text = ''.join(line + '\n' for line in lines)
    return 'sha256:' + hashlib.sha256(text.encode('ascii')).hexdigest()


@dataclass(frozen=True, slots=True)
class Definition:
    """A checked definition in canonical form.

    START names are 0, 1, 2, ... in list order; names the definition
    introduces continue the count. A nested first use appears as the
    REQUEST record for that use. The digest hashes exactly this form.
    """

    digest: str
    inputs: tuple[Port, ...]
    body: tuple[Record, ...]
    outputs: tuple[Port, ...]


@dataclass(frozen=True, slots=True)
class Program:
    """A checked stream: its definitions in the order they end, root last."""

    definitions: tuple[Definition, ...]

    @property
    def root(self) -> Definition:
        return self.definitions[-1]


# The checker.

@dataclass
class _Frame:
    """An open definition while the checker reads its records.

    live maps each name the definition holds to its current kind.
    canonical maps every name the definition has ever held to its canonical
    name. canonical only grows, so its size numbers the next new name.
    """

    label: str
    inputs: tuple[Port, ...]
    live: dict[str, str]
    canonical: dict[str, str]
    body: list[Record]

    @classmethod
    def open(cls, start: Start) -> _Frame:
        return cls(
            start.label,
            start.ports,
            {port.name: port.kind for port in start.ports},
            {port.name: str(index) for index, port in enumerate(start.ports)},
            [],
        )

    def add_name(self, name: str, kind: str) -> None:
        self.live[name] = kind
        self.canonical[name] = str(len(self.canonical))

    def rename(self, name: str) -> str:
        return self.canonical[name]

    def rename_ports(self, ports: tuple[Port, ...]) -> tuple[Port, ...]:
        return tuple(Port(port.kind, self.canonical[port.name]) for port in ports)


def _check_signature(given: tuple[Port, ...], expected: tuple[Port, ...],
                     role: str) -> None:
    if len(given) != len(expected):
        raise StreamError(
            f'{len(given)} {role}s given; the definition has {len(expected)}')
    for index, (port, definition_port) in enumerate(zip(given, expected)):
        if port.kind != definition_port.kind:
            raise StreamError(
                f'{role} {index} is {_KIND_WORDS[port.kind]}; the definition '
                f'expects {_KIND_WORDS[definition_port.kind]}')


class _Checker:
    """Reads records once, enforcing the rules in DESIGN.md.

    With verify_labels, each label must be its definition's digest. Without
    it, labels are placeholders, and digests records the digest each stands for.
    """

    def __init__(self, verify_labels: bool) -> None:
        self.verify_labels = verify_labels
        self.stack: list[_Frame] = []
        self.introduced: set[str] = set()    # every name introduced so far
        self.opened: set[str] = set()        # every label that has had a START
        self.definitions: dict[str, Definition] = {}  # keyed by label as written
        self.digests: dict[str, str] = {}    # label as written -> digest
        self.known_digests: set[str] = set()
        self.finished = False

    def read(self, records: tuple[Record, ...]) -> Program:
        for index, record in enumerate(records, start=1):
            try:
                self.read_record(record)
            except StreamError as error:
                raise StreamError(
                    f'record {index} ({_format_record(record)}): {error}') from None
        if not records:
            raise StreamError('a stream needs a root START and END')
        if not self.finished:
            raise StreamError(f'the stream ends inside {self.stack[-1].label}')
        return Program(tuple(self.definitions.values()))

    def read_record(self, record: Record) -> None:
        if self.finished:
            raise StreamError('the root has already ended')
        if not self.stack and not isinstance(record, Start):
            raise StreamError('a stream begins with the root START')
        if isinstance(record, Start):
            self.read_start(record)
        elif isinstance(record, End):
            self.read_end(record)
        elif isinstance(record, Request):
            self.read_request(record)
        else:
            self.read_operation(record)

    def require(self, name: str, kind: str) -> None:
        """Check that the open definition holds name with the given kind."""
        live = self.stack[-1].live
        if name not in live:
            raise StreamError(f'{name} is not live in this definition')
        if live[name] != kind:
            raise StreamError(
                f'{name} is {_KIND_WORDS[live[name]]}, not {_KIND_WORDS[kind]}')

    def require_new(self, name: str) -> None:
        """Enforce single assignment: a name is introduced once per stream."""
        if name in self.introduced:
            raise StreamError(f'{name} has already been introduced')
        self.introduced.add(name)

    def read_start(self, record: Start) -> None:
        if record.label in self.opened:
            raise StreamError(f'{record.label} has already been opened')
        if self.stack:
            # A first use inline: the caller lends these names to the block.
            for port in record.ports:
                self.require(port.name, port.kind)
        else:
            for port in record.ports:
                self.require_new(port.name)
        self.opened.add(record.label)
        self.stack.append(_Frame.open(record))

    def read_end(self, record: End) -> None:
        frame = self.stack[-1]
        if record.label != frame.label:
            raise StreamError(f'END {record.label} does not close {frame.label}')
        for port in record.ports:
            self.require(port.name, port.kind)
        unlisted = sorted(set(frame.live) - {port.name for port in record.ports})
        if unlisted:
            raise StreamError(
                'names still live must be listed or ended first: '
                + ', '.join(unlisted))
        inputs = frame.rename_ports(frame.inputs)
        outputs = frame.rename_ports(record.ports)
        digest = _digest(inputs, frame.body, outputs)
        if self.verify_labels and record.label != digest:
            raise StreamError(f'the label is not the digest {digest}')
        if digest in self.known_digests:
            raise StreamError(
                'this definition repeats an earlier one; '
                'later uses must be REQUEST records')
        definition = Definition(digest, inputs, tuple(frame.body), outputs)
        self.definitions[record.label] = definition
        self.digests[record.label] = digest
        self.known_digests.add(digest)
        self.stack.pop()
        if self.stack:
            self.apply_use(definition, frame.inputs, record.ports)
        else:
            self.finished = True

    def read_request(self, record: Request) -> None:
        label = record.label
        if label not in self.definitions:
            if label in self.opened:
                raise StreamError(
                    f'{label} has not ended; a definition cannot use itself')
            raise StreamError(f'{label} has no definition earlier in the stream')
        definition = self.definitions[label]
        _check_signature(record.inputs, definition.inputs, 'input')
        _check_signature(record.outputs, definition.outputs, 'output')
        for port in record.inputs:
            self.require(port.name, port.kind)
        input_positions = {port.name: index for index, port in enumerate(record.inputs)}
        for output_index, port in enumerate(record.outputs):
            if port.name in input_positions:
                # A continuing name: the definition must return the input it
                # received at that position, which in canonical form means
                # the same canonical name.
                input_index = input_positions[port.name]
                returned = definition.outputs[output_index].name
                if returned != definition.inputs[input_index].name:
                    raise StreamError(
                        f'{port.name} is input {input_index} and output '
                        f'{output_index}, '
                        'but the definition does not return that input there')
            else:
                self.require_new(port.name)
        self.apply_use(definition, record.inputs, record.outputs)

    def apply_use(self, definition: Definition, inputs: tuple[Port, ...],
                  outputs: tuple[Port, ...]) -> None:
        """Update the caller for a use and record it as a canonical REQUEST.

        A name in both lists continues, possibly with a new kind. A name only
        in the input list ends. A name only in the output list is new to the
        caller.
        """
        caller = self.stack[-1]
        canonical_inputs = caller.rename_ports(inputs)
        output_names = {port.name for port in outputs}
        for port in inputs:
            if port.name not in output_names:
                del caller.live[port.name]
        for port in outputs:
            if port.name in caller.live:
                caller.live[port.name] = port.kind
            else:
                caller.add_name(port.name, port.kind)
        canonical_outputs = caller.rename_ports(outputs)
        caller.body.append(
            Request(definition.digest, canonical_inputs, canonical_outputs))

    def read_operation(self, record: Record) -> None:
        frame = self.stack[-1]
        if isinstance(record, (CliffordGate, TGate)):
            self.require(record.qubit, QUANTUM)
        elif isinstance(record, CZGate):
            self.require(record.first, QUANTUM)
            self.require(record.second, QUANTUM)
        elif isinstance(record, Prepare):
            self.require_new(record.qubit)
            frame.add_name(record.qubit, QUANTUM)
        elif isinstance(record, Measure):
            self.require(record.qubit, QUANTUM)
            frame.live[record.qubit] = CLASSICAL
        elif isinstance(record, ClassicalOp):
            for operand in record.operands:
                self.require(operand, CLASSICAL)
            self.require_new(record.result)
            frame.add_name(record.result, CLASSICAL)
        elif isinstance(record, (Discard, Report)):
            if isinstance(record, Report) and len(self.stack) > 1:
                raise StreamError('only the root may REPORT')
            self.require(record.name, CLASSICAL)
            del frame.live[record.name]
        if isinstance(record, _CONDITIONAL_GATES) and record.condition is not None:
            self.require(record.condition, CLASSICAL)
        # A name that ended is no longer live but keeps its canonical name.
        frame.body.append(_rename_operation(record, frame.rename))


def check_stream(records: Iterable[Record]) -> Program:
    """Check every rule in DESIGN.md, including that each label is its digest."""
    return _Checker(verify_labels=True).read(_as_records(records))


def _relabel(record: Record, digests: dict[str, str]) -> Record:
    if isinstance(record, Start):
        return Start(digests[record.label], record.ports)
    if isinstance(record, End):
        return End(digests[record.label], record.ports)
    if isinstance(record, Request):
        return Request(digests[record.label], record.inputs, record.outputs)
    return record


def assign_digests(records: Iterable[Record]) -> tuple[Record, ...]:
    """Replace placeholder labels with digests, checking every other rule.

    A placeholder is any label. START, END and REQUEST records that share a
    placeholder refer to the same definition.
    """
    records = _as_records(records)
    checker = _Checker(verify_labels=False)
    checker.read(records)
    return tuple(_relabel(record, checker.digests) for record in records)


# The meaning.

@dataclass(frozen=True, slots=True)
class FlatCircuit:
    """A checked stream with every use expanded: operation records only.

    Names are 0, 1, 2, ...: the root's START names first, then each new name
    in order of introduction, fresh for every expansion of a definition.
    """

    inputs: tuple[Port, ...]
    operations: tuple[Record, ...]
    outputs: tuple[Port, ...]


def expand(program: Program) -> FlatCircuit:
    """Replace every use by its definition's body: the stream's meaning.

    The result holds every operation of the expanded circuit. It is the
    reference meaning, not a traversal for large circuits.
    """
    if not isinstance(program, Program):
        raise TypeError('expand takes the Program that check_stream returns')
    definitions = {definition.digest: definition for definition in program.definitions}
    root = program.root
    fresh_numbers = itertools.count(len(root.inputs))
    operations: list[Record] = []

    def inline(definition: Definition, binding: dict[str, str]) -> None:
        # binding maps the definition's canonical names to flat names. Each
        # call has its own binding, so each expansion gets fresh internal names.
        for record in definition.body:
            if isinstance(record, Request):
                child = definitions[record.label]
                child_binding = {
                    port.name: binding[argument.name]
                    for port, argument in zip(child.inputs, record.inputs)
                }
                inline(child, child_binding)
                for port, result in zip(child.outputs, record.outputs):
                    binding[result.name] = child_binding[port.name]
            else:
                new_name = _introduced_name(record)
                if new_name is not None:
                    binding[new_name] = str(next(fresh_numbers))
                operations.append(_rename_operation(record, binding.__getitem__))

    root_binding = {port.name: port.name for port in root.inputs}
    inline(root, root_binding)
    outputs = tuple(Port(port.kind, root_binding[port.name]) for port in root.outputs)
    return FlatCircuit(root.inputs, tuple(operations), outputs)
