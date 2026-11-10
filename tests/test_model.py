from dataclasses import FrozenInstanceError
from itertools import permutations
import random
import unittest

from quantum_circuits import (
    CCZ, CZ, WireSegment, Intersection, Apply, H, I, Wire, S, Seq, Clif,
    T, X, Y, Z, op, gate, seq,
)
from tests.reference import apply, evaluate


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.t = map(Wire, ('a', 'b', 't'))

    def test_named_qubit_identity_hash_and_repr(self):
        self.assertEqual(self.a, Wire('a'))
        self.assertEqual(hash(self.a), hash(Wire('a')))
        self.assertNotEqual(self.a, self.b)
        for name in ('a', 'a\nb', "q'0", 'q"1', 'α'):
            self.assertEqual(repr(Wire(name)), f'Wire({name!r})')
        with self.assertRaises(TypeError):
            Wire(4)

    def test_immutable_values(self):
        values = (
            (self.a, 'name', 'other'),
            (Apply(H, self.a), 'op', X),
            (gate(T, self.a), 'targ', self.b),
            (CZ(self.a, self.b), 'a', self.t),
            (CCZ(self.a, self.b, self.t), 'a', self.t),
            (WireSegment(self.a), 'source', 0),
            (Intersection('CZ', (WireSegment(self.a), WireSegment(self.b))), 'kind', 'CCZ'),
            (seq(Apply(H, self.a), Apply(S, self.b)), 'outputs', ()),
        )
        for value, field, new in values:
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, field, new)
            hash(value)

    def test_gate_repr_and_qubits(self):
        c = Apply(H, self.a)
        self.assertEqual(repr(c), "Apply(op=WireOp(phase=0, rep=1, pauli=0, axes=''), targ=Wire('a'))")
        self.assertEqual(c.qubits, frozenset((self.a,)))

    def test_symmetric_gate_operands(self):
        cz = CZ(self.a, self.b)
        self.assertEqual(cz, CZ(self.b, self.a))
        self.assertEqual(hash(cz), hash(CZ(self.b, self.a)))
        self.assertEqual(cz.qubits, frozenset((self.a, self.b)))
        expected = CCZ(self.a, self.b, self.t)
        for wires in permutations((self.a, self.b, self.t)):
            self.assertEqual(CCZ(*wires), expected)
            self.assertEqual(hash(CCZ(*wires)), hash(expected))
        self.assertEqual(expected.qubits, frozenset((self.a, self.b, self.t)))
        self.assertEqual(gate(T, self.t).qubits, frozenset((self.t,)))

    def test_symmetric_ports_use_natural_name_order(self):
        ordered = ['', '9', '10', 'a', 'a9', 'a9b', 'a10', 'a10a', 'b', 'q02', 'q2', 'q10', 'q٣']
        for i, low in enumerate(ordered):
            for high in ordered[i + 1:]:
                first, second = Wire(low), Wire(high)
                with self.subTest(low=low, high=high):
                    for cz in (CZ(first, second), CZ(second, first)):
                        self.assertEqual((cz.a, cz.b), (first, second))
                    vertex = Intersection('CZ', (WireSegment(second), WireSegment(first)))
                    self.assertEqual(tuple(e.wire for e in vertex.inputs), (first, second))
        register = [Wire(f'r{i}') for i in range(12)]
        ccz = CCZ(register[11], register[9], register[10])
        self.assertEqual((ccz.a, ccz.b, ccz.c), tuple(register[9:12]))
        self.assertEqual(seq(*(CZ(b, a) for a, b in zip(register, register[1:]))).wires,
                         tuple(register))

    def test_invalid_gate_operands(self):
        for make in (
            lambda: Apply('H', self.a), lambda: Apply(H, 'a'),
            lambda: gate(T, 'a'), lambda: CZ(self.a, 'b'),
        ):
            with self.assertRaises(TypeError):
                make()
        for make in (
            lambda: CZ(self.a, Wire('a')),
            lambda: CCZ(self.a, self.b, self.a),
        ):
            with self.assertRaises(ValueError):
                make()

    def test_entangling_gates_validate_every_operand(self):
        for cls, wires in (
            (CZ, (self.a, self.b)),
            (CCZ, (self.a, self.b, self.t)),
        ):
            for i in range(len(wires)):
                for invalid in ('q', None, 1, Apply(H, wires[i])):
                    args = list(wires)
                    args[i] = invalid
                    with self.subTest(gate=cls.__name__, position=i, invalid=invalid):
                        with self.assertRaises(TypeError):
                            cls(*args)
                for j in range(i):
                    args = list(wires)
                    args[i] = Wire(wires[j].name)
                    with self.subTest(gate=cls.__name__, repeated=(j, i)):
                        with self.assertRaises(ValueError):
                            cls(*args)

    def test_empty_and_singleton(self):
        self.assertEqual(seq(), Seq((), (), ()))
        self.assertEqual(seq(Apply(H, self.a)), Seq((self.a,), (), (WireSegment(self.a, None, H),)))
        self.assertEqual(seq(Apply(I, self.a)), seq(wires=(self.a,)))
        wires = (self.t, self.b, self.a)
        identity = seq(wires=wires)
        self.assertEqual(identity, Seq(wires, (), tuple(WireSegment(q) for q in wires)))
        self.assertEqual(identity.qubits, frozenset(wires))
        self.assertEqual(seq(seq(), identity, seq()), identity)

    def test_wire_labels_follow_execution_order_and_preserve_phase(self):
        q = self.t
        self.assertNotEqual(S @ H, H @ S)
        self.assertEqual(seq(gate(H, q), gate(S, q)).outputs, (WireSegment(q, None, S @ H),))
        self.assertEqual(seq(*(gate(x, q) for x in 'HTH')), seq(gate('HTH', q)))
        self.assertEqual(seq(*(gate(T, q) for _ in range(8))), seq(wires=(q,)))
        scalar = op(phase=1)
        self.assertEqual(seq(*(gate(x, q) for x in (S, H, S, H, S, H))),
                         seq(wires=(q,), phase=1))
        self.assertEqual(seq(gate(scalar, q), gate(op(phase=7), q)), seq(wires=(q,)))
        with self.assertRaises(TypeError):
            gate(Clif(0), q)

    def test_long_runs_and_independent_wires(self):
        q = self.t
        raw = [gate(x, q) for x in 'HT' * 10000]
        self.assertEqual(seq(*raw), seq(gate('HT' * 10000, q)))
        first, second = gate(H, self.a), gate(S, self.b)
        wires = (self.a, self.b)
        self.assertEqual(seq(first, second, wires=wires), seq(second, first, wires=wires))

    def test_input_ports_parallel_edges_and_output_ports(self):
        a, b, c = self.a, self.b, self.t
        body = seq(gate(H, a), CZ(b, a), gate(T, b), gate(S, c), CCZ(c, a, b))
        self.assertEqual(body.vertices, (
            Intersection('CZ', (WireSegment(a, None, H), WireSegment(b))),
            Intersection('CCZ', (WireSegment(a, 0), WireSegment(b, 0, T), WireSegment(c, None, S))),
        ))
        self.assertEqual(body.outputs, (WireSegment(a, 1), WireSegment(b, 1), WireSegment(c, 1)))

    def test_only_the_participating_wires_end_their_segments(self):
        spectator = Wire('spectator')
        for interaction in (CZ(self.a, self.t), CCZ(self.a, self.b, self.t)):
            for wire in (*interaction.qubits, spectator):
                h = gate(H, wire)
                body = seq(h, interaction, h)
                self.assertEqual(len(body.vertices), 1)
                inputs = {e.wire: e.op for e in body.vertices[0].inputs}
                outputs = {e.wire: e for e in body.outputs}
                if wire == spectator:
                    self.assertEqual(outputs[wire], WireSegment(wire))
                else:
                    self.assertEqual(inputs[wire], H)
                    self.assertEqual(outputs[wire], WireSegment(wire, 0, H))

    def test_construction_reduces_identity_separated_pairs(self):
        for interaction in (CZ(self.a, self.t), CCZ(self.a, self.b, self.t)):
            body = seq(interaction, gate(H, self.t), gate(H, self.t), interaction)
            self.assertEqual(body, seq(wires=body.wires))
            body = seq(interaction, gate(T, self.t), interaction)
            self.assertEqual(len(body.vertices), 2)
            self.assertIn(WireSegment(self.t, 0, T), body.vertices[1].inputs)

    def test_compose_graphs_by_name_and_preserve_declared_order(self):
        a, b, c = self.a, self.b, self.t
        idle = Wire('idle')
        wires = (c, idle, a, b)
        left = (CZ(a, b), gate(H, a), gate(T, b))
        right = (gate(S, a), CCZ(c, b, a), CZ(c, a), gate(X, a))
        tail = (gate(S, b), gate(T, c))
        # The child interface order differs from the caller's, and includes an idle port.
        child = seq(*right, wires=(b, c, a, idle))
        expected = seq(*left, *right, *tail, wires=wires)
        self.assertEqual(seq(seq(*left), child, seq(*tail), wires=wires), expected)
        self.assertEqual(seq(*left, seq(child, *tail), wires=wires), expected)
        self.assertEqual(expected.outputs[1], WireSegment(idle))
        self.assertEqual(seq(child).wires, child.wires)
        self.assertEqual(seq(child, wires=wires).wires, wires)

    def test_graph_rejects_invalid_boundaries_and_wiring(self):
        a, b, c = self.a, self.b, self.t
        first = Intersection('CZ', (WireSegment(a), WireSegment(b)))
        with self.assertRaises(ValueError):
            seq(CZ(a, b), wires=(a,))
        with self.assertRaises(ValueError):
            seq(seq(wires=(b,)), wires=(a,))
        with self.assertRaises(ValueError):
            seq(wires=(a, a))
        with self.assertRaises(TypeError):
            seq(wires=('a',))
        for invalid in (None, 'H', [gate(H, a)]):
            with self.assertRaises(TypeError):
                seq(invalid)
        with self.assertRaises(ValueError):
            Intersection('CCZ', first.inputs)
        with self.assertRaises(ValueError):
            Intersection('CZ', (WireSegment(a), WireSegment(a)))
        with self.assertRaises(TypeError):
            WireSegment(a, False)
        for body in (
            ((a, b), (first,), (WireSegment(b, 0), WireSegment(a, 0))),  # crossed outputs
            ((a, b), (first,), (WireSegment(a, 0),)),              # missing output
            ((a, b), (first,), (WireSegment(a), WireSegment(b, 0))),      # reused boundary port
            ((a, b), (Intersection('CZ', (WireSegment(a, 0), WireSegment(b))),), (WireSegment(a, 0), WireSegment(b, 0))),
            ((a, b, c), (first, Intersection('CZ', (WireSegment(a, 0), WireSegment(c, 0)))),
             (WireSegment(a, 1), WireSegment(b, 0), WireSegment(c, 1))),         # c is absent from vertex 0
            ((a, b), (first, first), (WireSegment(a, 1), WireSegment(b, 1))),  # fork from boundary
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                Seq(*body)

    def test_raw_graph_requires_pair_normal_form(self):
        for kind, wires in (('CZ', (self.a, self.b)), ('CCZ', (self.a, self.b, self.t))):
            first = Intersection(kind, tuple(WireSegment(w) for w in wires))
            second = Intersection(kind, tuple(WireSegment(w, 0) for w in wires))
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'cancellable'):
                Seq(wires, (first, second), tuple(WireSegment(w, 1) for w in wires))

    def test_equivalent_normalised_sequences_hash_equally(self):
        a = seq(Apply(op('HXH'), self.a), gate(T, self.b))
        b = seq(Apply(Z, Wire('a')), gate(T, Wire('b')))
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_random_normalisation_preserves_complete_three_qubit_matrices(self):
        rng = random.Random(812)
        wires = (self.a, self.b, self.t)
        for _ in range(200):
            raw = []
            for _ in range(rng.randrange(30)):
                choice = rng.randrange(6)
                if choice < 3:
                    raw.append(Apply(op(Clif(rng.randrange(24), rng.randrange(8)), ''.join(rng.choices('HST', k=8))), rng.choice(wires)))
                elif choice == 3:
                    raw.append(gate(T, rng.choice(wires)))
                elif choice == 4:
                    raw.append(CZ(*rng.sample(wires, 2)))
                else:
                    raw.append(CCZ(*rng.sample(wires, 3)))
            result = seq(*raw)
            self.assertEqual(seq(result), result)
            cut = rng.randrange(len(raw) + 1)
            self.assertEqual(seq(seq(*raw[:cut]), seq(*raw[cut:])), result)
            for basis in range(8):
                expected = apply(raw, wires, basis)
                actual = evaluate(result, wires, basis)
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-12)

    def test_cnot_and_toffoli_recipes(self):
        for controls in ((self.a,), (self.a, self.b)):
            wires = (*controls, self.t)
            central = CZ(*wires) if len(controls) == 1 else CCZ(*wires)
            circuit = seq(Apply(H, self.t), central, Apply(H, self.t))
            for basis in range(1 << len(wires)):
                mask = (1 << len(controls)) - 1
                target = basis ^ (1 << len(controls)) if basis & mask == mask else basis
                expected = [0j] * (1 << len(wires))
                expected[target] = 1
                actual = evaluate(circuit, wires, basis)
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-12)

    def test_t_adjoint_recipe(self):
        circuit = seq(Apply(S.inverse(), self.t), gate(T, self.t))
        from tests.reference import OMEGA
        self.assertAlmostEqual(evaluate(circuit, (self.t,), 1)[1], OMEGA.conjugate())


if __name__ == '__main__':
    unittest.main()
