"""Tests for the stream format, checker and expander (DESIGN.md, Stream)."""

import hashlib
import unittest

from quantum_circuits.stream import (
    CLASSICAL, QUANTUM, ClassicalOp, CliffordGate, CZGate, Discard, Measure,
    Phase, Port, Prepare, Report, Request, StreamError, TGate,
    assign_digests, check_stream, expand, format_stream, parse_stream,
)

# The example in DESIGN.md, with placeholder labels.
DESIGN_EXAMPLE = """\
START <root> (q:a q:b q:c q:t q:u)
START <undo> (q:a q:b q:t)
CLIF 4 t
MEAS t
CZ a b if t
DISCARD t
END <undo> (q:a q:b)
REQUEST <undo> (q:b q:c q:u) (q:b q:c)
END <root> (q:a q:b q:c)
"""

# The same root, with the first use on (b, c, u) and the REQUEST on (a, b, t).
SWAPPED_USES = """\
START <root> (q:a q:b q:c q:t q:u)
START <undo> (q:b q:c q:u)
CLIF 4 u
MEAS u
CZ b c if u
DISCARD u
END <undo> (q:b q:c)
REQUEST <undo> (q:a q:b q:t) (q:a q:b)
END <root> (q:a q:b q:c)
"""

# A definition that prepares a work qubit, used twice.
WORK_QUBIT = """\
START <root> (q:x)
START <work> (q:x)
PREP w
CZ x w
MEAS w
DISCARD w
END <work> (q:x)
REQUEST <work> (q:x) (q:x)
END <root> (q:x)
"""

# A definition that returns its measured input; classical operations and
# conditioned gates on the outcomes; reports at the root.
CLASSICAL_FLOW = """\
START <root> (q:x q:y)
START <measure> (q:x)
MEAS x
END <measure> (c:x)
REQUEST <measure> (q:y) (c:y)
XOR x y -> p
NOT p -> n
AND x n -> k
PREP z
CLIF 1 z if p
T z if k
MEAS z
REPORT x
DISCARD y
DISCARD p
DISCARD n
DISCARD k
REPORT z
END <root> ()
"""

# A definition that exchanges its two wires.
SWAP_THEN = """\
START <root> (q:x q:y)
START <swap> (q:x q:y)
END <swap> (q:y q:x)
"""


def q(name: str) -> Port:
    return Port(QUANTUM, name)


def c(name: str) -> Port:
    return Port(CLASSICAL, name)


def labelled(text: str):
    """Parse text whose labels are placeholders and give them their digests."""
    return assign_digests(parse_stream(text))


class TextTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        for text in (DESIGN_EXAMPLE, WORK_QUBIT, CLASSICAL_FLOW):
            with self.subTest(text=text.splitlines()[1]):
                self.assertEqual(format_stream(parse_stream(text)), text)

    def test_parses_each_record_form(self) -> None:
        cases = {
            'PHASE 3': Phase(3),
            'CLIF 4 t if m': CliffordGate(4, 't', 'm'),
            'T t': TGate('t'),
            'CZ a b if m': CZGate('a', 'b', 'm'),
            'PREP w': Prepare('w'),
            'MEAS w': Measure('w'),
            'XOR a b -> c': ClassicalOp('XOR', ('a', 'b'), 'c'),
            'NOT a -> c': ClassicalOp('NOT', ('a',), 'c'),
            'DISCARD m': Discard('m'),
            'REPORT m': Report('m'),
            'REQUEST d () (c:m)': Request('d', (), (c('m'),)),
        }
        for line, record in cases.items():
            with self.subTest(line=line):
                self.assertEqual(parse_stream(line + '\n'), (record,))

    def test_rejects_malformed_text(self) -> None:
        cases = {
            'phase out of range': 'PHASE 8\n',
            'negative phase': 'PHASE -1\n',
            'leading zero in phase': 'PHASE 01\n',
            'missing phase': 'PHASE\n',
            'conditional scalar': 'PHASE 1 if m\n',
            'non-ASCII character': 'T é\n',
            'tab': 'T\ta\n',
            'missing final line feed': 'T a',
            'double space': 'T  a\n',
            'blank line': '\n',
            'unknown record': 'SWAP a b\n',
            'frame out of range': 'CLIF 24 a\n',
            'leading zero in frame': 'CLIF 04 a\n',
            'CZ on one qubit': 'CZ a a\n',
            'condition without if': 'T a when b\n',
            'unknown port kind': 'START d (z:a)\n',
            'repeated name in a list': 'START d (q:a q:a)\n',
            'parenthesis in a label': 'START d( (q:a)\n',
            'classical result overwrites an operand': 'XOR a b -> a\n',
            'NOT with two operands': 'NOT a b -> c\n',
        }
        for description, text in cases.items():
            with self.subTest(description), self.assertRaises(StreamError):
                parse_stream(text)

    def test_records_reject_booleans_and_non_strings(self) -> None:
        with self.assertRaises(TypeError):
            Phase(True)
        with self.assertRaises(TypeError):
            Phase('1')
        for exponent in (-1, 8):
            with self.subTest(exponent=exponent), self.assertRaises(ValueError):
                Phase(exponent)
        with self.assertRaises(TypeError):
            CliffordGate(True, 'a')
        with self.assertRaises(TypeError):
            TGate(3)


class DigestTests(unittest.TestCase):
    def test_scalar_definition_digest_includes_phase(self) -> None:
        text = 'START scalar ()\nPHASE 3\nEND scalar ()\n'
        self.assertEqual(format_stream(parse_stream(text)), text)
        program = check_stream(labelled(text))
        canonical = 'START ()\nPHASE 3\nEND ()\n'
        expected = 'sha256:' + hashlib.sha256(canonical.encode('ascii')).hexdigest()
        self.assertEqual(program.root.digest, expected)
        changed = check_stream(labelled(text.replace('PHASE 3', 'PHASE 4')))
        self.assertNotEqual(program.root.digest, changed.root.digest)

    def test_digest_follows_design_encoding(self) -> None:
        # Written from DESIGN.md: START names become 0, 1, 2; the label is
        # omitted from the definition's own START and END.
        canonical_undo = (
            'START (q:0 q:1 q:2)\n'
            'CLIF 4 2\n'
            'MEAS 2\n'
            'CZ 0 1 if 2\n'
            'DISCARD 2\n'
            'END (q:0 q:1)\n'
        )
        expected = 'sha256:' + hashlib.sha256(
            canonical_undo.encode('ascii')).hexdigest()
        program = check_stream(labelled(DESIGN_EXAMPLE))
        self.assertEqual(program.definitions[0].digest, expected)

    def test_digest_ignores_caller_names(self) -> None:
        first = check_stream(labelled(DESIGN_EXAMPLE))
        second = check_stream(labelled(SWAPPED_USES))
        self.assertEqual(first.definitions[0].digest, second.definitions[0].digest)
        # The roots use undo on different positions, so they differ.
        self.assertNotEqual(first.root.digest, second.root.digest)

    def test_root_digest_ignores_root_names(self) -> None:
        renamed = (
            'START <root> (q:p q:r q:s q:v q:w)\n'
            'START <undo> (q:p q:r q:v)\n'
            'CLIF 4 v\n'
            'MEAS v\n'
            'CZ p r if v\n'
            'DISCARD v\n'
            'END <undo> (q:p q:r)\n'
            'REQUEST <undo> (q:r q:s q:w) (q:r q:s)\n'
            'END <root> (q:p q:r q:s)\n'
        )
        self.assertEqual(check_stream(labelled(renamed)).root.digest,
                         check_stream(labelled(DESIGN_EXAMPLE)).root.digest)

    def test_parent_digest_covers_child(self) -> None:
        changed = DESIGN_EXAMPLE.replace('CLIF 4 t', 'CLIF 5 t')
        self.assertNotEqual(check_stream(labelled(changed)).root.digest,
                            check_stream(labelled(DESIGN_EXAMPLE)).root.digest)

    def test_check_requires_digest_labels(self) -> None:
        with self.assertRaises(StreamError):
            check_stream(parse_stream(DESIGN_EXAMPLE))
        text = format_stream(labelled(DESIGN_EXAMPLE))
        last_digit = text.index(' (q:a q:b q:t)') - 1
        flipped = '0' if text[last_digit] != '0' else '1'
        tampered = text[:last_digit] + flipped + text[last_digit + 1:]
        with self.assertRaises(StreamError):
            check_stream(parse_stream(tampered))


class ExpandTests(unittest.TestCase):
    def test_phase_is_preserved_at_every_subcircuit_use(self) -> None:
        # A scalar definition has no wires. Both its inline first use and
        # its REQUEST contribute phase; expansion must not count it only once.
        text = (
            'START root ()\nSTART scalar ()\nPHASE 3\nEND scalar ()\n'
            'REQUEST scalar () ()\nPHASE 2\nEND root ()\n')
        program = check_stream(labelled(text))
        flat = expand(program)
        self.assertEqual(flat.inputs, ())
        self.assertEqual(flat.outputs, ())
        self.assertEqual(flat.operations, (Phase(3), Phase(3), Phase(2)))
        changed = check_stream(labelled(text.replace('PHASE 3', 'PHASE 4')))
        self.assertNotEqual(program.root.digest, changed.root.digest)

    def test_expands_design_example(self) -> None:
        flat = expand(check_stream(labelled(DESIGN_EXAMPLE)))
        self.assertEqual(flat.inputs, tuple(q(str(index)) for index in range(5)))
        self.assertEqual(flat.operations, (
            CliffordGate(4, '3'), Measure('3'), CZGate('0', '1', '3'), Discard('3'),
            CliffordGate(4, '4'), Measure('4'), CZGate('1', '2', '4'), Discard('4'),
        ))
        self.assertEqual(flat.outputs, (q('0'), q('1'), q('2')))

    def test_each_expansion_gets_fresh_names(self) -> None:
        flat = expand(check_stream(labelled(WORK_QUBIT)))
        self.assertEqual(flat.operations, (
            Prepare('1'), CZGate('0', '1'), Measure('1'), Discard('1'),
            Prepare('2'), CZGate('0', '2'), Measure('2'), Discard('2'),
        ))
        self.assertEqual(flat.outputs, (q('0'),))

    def test_classical_outputs_operations_and_reports(self) -> None:
        flat = expand(check_stream(labelled(CLASSICAL_FLOW)))
        self.assertEqual(flat.operations, (
            Measure('0'), Measure('1'),
            ClassicalOp('XOR', ('0', '1'), '2'),
            ClassicalOp('NOT', ('2',), '3'),
            ClassicalOp('AND', ('0', '3'), '4'),
            Prepare('5'), CliffordGate(1, '5', '2'), TGate('5', '4'), Measure('5'),
            Report('0'), Discard('1'), Discard('2'), Discard('3'), Discard('4'),
            Report('5'),
        ))
        self.assertEqual(flat.outputs, ())

    def test_continuing_names_follow_the_definition(self) -> None:
        text = SWAP_THEN + 'REQUEST <swap> (q:y q:x) (q:x q:y)\nEND <root> (q:x q:y)\n'
        flat = expand(check_stream(labelled(text)))
        self.assertEqual(flat.operations, ())
        self.assertEqual(flat.outputs, (q('0'), q('1')))

    def test_rejects_unchecked_input(self) -> None:
        with self.assertRaises(TypeError):
            expand(parse_stream(DESIGN_EXAMPLE))


class RuleTests(unittest.TestCase):
    """Each stream breaks one rule in DESIGN.md."""

    CASES = {
        'empty stream': '',
        'no root START': 'T a\n',
        'gate on a measured name': (
            'START r (q:a)\nMEAS a\nT a\nDISCARD a\nEND r ()\n'),
        'PREP of a held name': 'START r (q:a)\nPREP a\nEND r (q:a)\n',
        'name reused after it ends': (
            'START r (q:a)\nMEAS a\nDISCARD a\nPREP a\nMEAS a\nDISCARD a\nEND r ()\n'),
        'condition on a quantum name': 'START r (q:a q:b)\nT a if b\nEND r (q:a q:b)\n',
        'classical operation on a quantum name': (
            'START r (q:a)\nNOT a -> n\nEND r (q:a c:n)\n'),
        'DISCARD of a quantum name': 'START r (q:a)\nDISCARD a\nEND r ()\n',
        'live name missing from END': 'START r (q:a q:b)\nEND r (q:a)\n',
        'END lists an ended name': 'START r (q:a)\nMEAS a\nDISCARD a\nEND r (c:a)\n',
        'END gives the wrong kind': 'START r (q:a)\nMEAS a\nEND r (q:a)\n',
        'END closes the wrong definition': (
            'START r (q:a)\nSTART d (q:a)\nEND r (q:a)\nEND d (q:a)\n'),
        'block uses a name it was not given': (
            'START r (q:a q:b)\nSTART d (q:a)\nCZ a b\nEND d (q:a)\nEND r (q:a q:b)\n'),
        'definition uses itself': (
            'START r (q:a)\nSTART d (q:a)\nREQUEST d (q:a) (q:a)\nEND d (q:a)\n'
            'END r (q:a)\n'),
        'REQUEST of an unknown label': (
            'START r (q:a)\nREQUEST d (q:a) (q:a)\nEND r (q:a)\n'),
        'REQUEST with too many inputs': (
            'START r (q:a q:b)\nSTART d (q:a)\nEND d (q:a)\n'
            'REQUEST d (q:a q:b) (q:a)\nEND r (q:a q:b)\n'),
        'REQUEST with the wrong kind': (
            'START r (q:a q:b)\nMEAS b\nSTART d (q:a)\nT a\nEND d (q:a)\n'
            'REQUEST d (c:b) (c:b)\nEND r (q:a c:b)\n'),
        'REQUEST output reintroduces a name': (
            'START r (q:a q:b)\nSTART d (q:a)\nT a\nEND d (q:a)\n'
            'REQUEST d (q:a) (q:b)\nEND r (q:b)\n'),
        'continuing name at the wrong position': (
            SWAP_THEN + 'REQUEST <swap> (q:y q:x) (q:y q:x)\nEND <root> (q:y q:x)\n'),
        'REPORT inside a definition': (
            'START r (q:a)\nSTART d (q:a)\nMEAS a\nREPORT a\nEND d ()\nEND r ()\n'),
        'label opened twice': (
            'START r (q:a)\nSTART d (q:a)\nT a\nEND d (q:a)\n'
            'START d (q:a)\nCLIF 4 a\nEND d (q:a)\nEND r (q:a)\n'),
        'second inline copy of a definition': (
            'START r (q:a)\nSTART d (q:a)\nT a\nEND d (q:a)\n'
            'START e (q:a)\nT a\nEND e (q:a)\nEND r (q:a)\n'),
        'record after the root ends': 'START r (q:a)\nEND r (q:a)\nT a\n',
        'stream ends inside a definition': 'START r (q:a)\nT a\n',
    }

    def test_each_case_is_rejected(self) -> None:
        for description, text in self.CASES.items():
            with self.subTest(description), self.assertRaises(StreamError):
                assign_digests(parse_stream(text))


if __name__ == '__main__':
    unittest.main()
