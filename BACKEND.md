# The backend team's tools

This document describes the tools that will consume this library's circuits.
It then says what the library should offer them. [DESIGN.md](DESIGN.md)
explains the library itself.

The backend team builds Rottnest. Rottnest is a set of programs that
estimate what a circuit costs to run on a fault-tolerant quantum computer.
The estimate is a number of physical qubits and a run time.

Claude wrote this document on 16 November 2026 from the team's public code
and papers. None of the code was run. The [sources](#sources) are listed at
the end.

[How their machine runs a circuit](#how-their-machine-runs-a-circuit) ·
[Their pipeline](#their-pipeline) ·
[What Cabaliser does](#what-cabaliser-does) ·
[What the library offers](#what-the-library-offers) ·
[Details of their code](#details-of-their-code) ·
[What this means for the library](#what-this-means-for-the-library) ·
[What is not established](#what-is-not-established) ·
[Questions for the backend team](#questions-for-the-backend-team) ·
[Sources](#sources)

## How their machine runs a circuit

Their model of the machine does not apply a circuit gate by gate. It
prepares a graph state and then measures it, one qubit at a time.

A graph state is defined by a graph. Each vertex of the graph is a qubit in
the state |+>. Each edge is a CZ between its two qubits.

Figure 1 of [Saadatmand et al.](https://arxiv.org/abs/2406.06015) shows the
machine. A register of logical qubits holds the graph state. A bus of helper
qubits prepares it by measurement. Factories supply T states, and the
measurements of the graph use them up.

## Their pipeline

A circuit passes through six stages.

1. **Read.** Rottnest reads a circuit written with Cirq, Google's circuit
   library. It keeps H, S, the Pauli gates, CNOT, CZ, T, rotations about one
   axis, measurement and reset. It breaks other gates down into these.
2. **Cut.** Rottnest cuts the circuit into pieces that fit the machine's
   register. It calls a piece a widget. A companion tool called Pandora can
   do the cutting. Pandora keeps circuits in a database and reuses a piece
   it has already processed
   ([Moflic et al.](https://arxiv.org/abs/2507.20677)).
3. **Compile.** Cabaliser turns each widget into a graph state and a list of
   measurements. The next section explains how.
4. **Place and schedule.** Later tools place each graph on the register and
   schedule the measurements that prepare it. They replace each rotation
   with a sequence of H, S and T gates. They route T states from the
   factories to the measurements that need them.
5. **Choose the code distance.** The tools pick the smallest surface-code
   distance that meets the error budget.
6. **Report.** They report the space-time volume, the run time, the code
   distance and the number of physical qubits.

Section V of [Nguyen et al.](https://arxiv.org/abs/2509.13546) works through
one run of this pipeline.

## What Cabaliser does

[Cabaliser](https://github.com/QSI-BAQS/cabaliser) rewrites a widget as a
graph state and a list of measurements. It works in three steps.

1. **It gives each T gate and each rotation a fresh qubit.** One CNOT joins
   the wire to the fresh qubit, and the wire continues there. The old qubit
   is measured later, and that measurement performs the rotation. A circuit
   of Clifford gates remains, followed by measurements of single qubits.
2. **It reduces the Clifford circuit to a graph state.** It tracks the
   circuit as a stabiliser state. Every stabiliser state can be written as a
   graph state with one Clifford gate on each qubit.
3. **It reports the result.** The report holds the graph and the Clifford
   gate on each qubit. It names the rotation that each measurement performs.
   It gives an order for the measurements, and it says which qubits are
   outputs.

The two-qubit gates of the widget do not run as gates. They become edges of
the graph.

This library targets the input to Cabaliser, which is a list of gates. The
later stages read Cabaliser's output. Handing the backend team anything
later than a list of gates would mean writing a second graph-state compiler.

## What the library offers

The library keeps its own representation. It offers the backend team one
thing, which is a walk over a subcircuit. The walk yields the subcircuit's
entries in the order they run. The backend team writes an adapter that
consumes the walk. The library does not call Cabaliser and does not depend
on it.

### A subcircuit

A subcircuit has a key, a number of wires and a list of entries. The key is
the subcircuit's hash. The wires are numbered from zero. An entry is one of
two things.

- **A gate** on some of the wires. The gates today are H, S, T and CZ. A
  rotation and a measurement will follow.
- **A call** to another subcircuit. The call gives the other subcircuit's
  key. It also lists the wires of this subcircuit that the other one acts
  on.

### An example

Here are two subcircuits. The names `ccz` and `two` stand for their hashes.

```text
ccz   3 wires   34 entries
    H 2
    CZ 1 2
    H 2   S 2   S 2   S 2   T 2   H 2
    CZ 0 2
    H 2   T 2   H 2
    CZ 1 2
    H 2   S 2   S 2   S 2   T 2   H 2
    CZ 0 2
    T 1   H 1
    CZ 0 1
    T 0   H 1   S 1   S 1   S 1   T 1   H 1
    CZ 0 1
    H 1   H 2   T 2

two   5 wires   3 entries
    call ccz (0, 1, 2)
    H 3
    call ccz (2, 3, 4)

root   two
```

`ccz` builds the three-qubit gate CCZ from six CZ gates and seven T gates.
`two` applies CCZ to wires 0, 1 and 2. It then applies H to wire 3 and CCZ
to wires 2, 3 and 4. Its second call attaches wires 0, 1 and 2 of `ccz` to
wires 2, 3 and 4 of `two`.

`two` has three entries and stands for 69 gates. `ccz` is stored once.

The `ccz` list comes from the data in `tests/test_ccz.py`. That file holds
six CZ gates and 15 operators on single qubits, one for each stretch of
wire. A walk over that data gives the list above. On 16 November 2026 a
floating-point simulation checked both lists. The `ccz` list equals CCZ. The
`two` list equals CCZ, H and CCZ applied directly.

### The adapter

The backend team's adapter is one loop that calls itself. For a gate entry
it emits one instruction. For a call entry it looks at the key. If the key
is new, it compiles that subcircuit. If the key has been seen, it reuses the
stored result.

Rottnest already has a second source of instructions besides Cirq. It is the
class `PandoraSequencer` in rottnest_py.

### The format

The backend team chooses how to store what the walk yields. Two of their
tools already read lists of gates. Rottnest builds lists of Cabaliser
instructions, which the next section describes. The tool in Saadatmand et
al. reads subcircuits written in OpenQASM 2.0. Its gate set is the Clifford
gates, T, the inverse of T, and rotations about Z.

### What stays with the backend team

Three decisions stay with them, because their code makes them. Their code
decides where a widget ends. It decides how a widget receives its inputs. It
decides which sequence of H, S and T performs a rotation.

### Qualtran

Qualtran is a second target for this library. It serves gate counts and cost
models, as DESIGN.md explains. Rottnest reads a Qualtran bloq only after the
bloq has been wrapped as a Cirq gate.

## Details of their code

### What Cabaliser reads

The file names in this section are in the Cabaliser repository under
`c_lib/`.

- **An instruction is 12 bytes.** The first byte is the operation code.
  Three unused bytes follow. Then come two unsigned 32-bit numbers
  (`lib/instruction_table.h`). In Python,
  `struct.pack('<B3xII', code, a, b)` writes one instruction.
- **These codes are for input.**
  - `0x20` to `0x26` are I, X, Y, Z, H, S and the inverse of S. Each takes
    one qubit.
  - `0x40` is CNOT and `0x41` is CZ. Each takes two qubits.
  - `0x80` is RZ, a rotation about Z. It takes one qubit and a tag. A tag is
    a number that stands for a rotation angle.
  - `0xC0` is MEAS. It measures one qubit.
  - `0xC1` to `0xC3` measure the first qubit. They then apply X, Y or Z to
    the second qubit, depending on the outcome.
- **Other codes are for output.** Codes `0x27` to `0x37` name the other 17
  Clifford gates on one qubit. Cabaliser writes them in its report. It
  cannot read them, because its lookup table has rows for seven gates only
  (`lib/instructions.h`).
- **Qubits are numbered from zero inside one widget.** The caller keeps the
  map from its own names to these numbers. Rottnest numbers qubits in the
  order they first appear.
- **Cabaliser merges Clifford gates itself.** It keeps one byte for each
  qubit and updates the byte from a table (`src/input_stream.c`).
- **Each RZ adds one qubit to the graph.** Cabaliser stores the tag on that
  qubit and does not interpret it (`src/input_stream.c`). Tag 0 means no
  rotation. Tag `0x0fffffff` marks a qubit that was measured.

### What Rottnest adds

The file names in this section are in rottnest_py under `src/rottnest/`,
except where t_scheduler is named.

- **A table maps each tag to an angle.** The angle is in units of pi, so T
  has the angle 0.25. One precision applies to a whole run. The table also
  records a tolerance for each tag, and Rottnest does not use it
  (`input_parsers/rz_tag_tracker.py`).
- **A rotation is expanded where it is measured.** The T scheduler turns a
  tag into a sequence of H, S, T, X and Z gates on that one graph qubit. It
  gets the sequence from a decomposer (t_scheduler,
  `rottnest_interface/rz_decomposer.py`). The default decomposer runs
  GridSynth as a separate program. Rottnest's README says other decomposers
  can replace it.
- **Rottnest sizes a widget by counting graph qubits.** It counts two for
  each circuit qubit the widget touches and one for each RZ. The layout of
  the machine sets the limit (`input_parsers/cirq_parser.py`,
  `compute_units/sequencer.py`).
- **Markers signal reuse.** Rottnest puts markers in its stream of
  instructions. START and END surround a subcircuit the first time it is
  compiled. Rottnest stores the cost of everything between them under the
  subcircuit's key. REQUEST stands for a later use. Rottnest then adds the
  stored cost again and compiles nothing
  (`architecture_interface/rottnest_composer.py`). Each marker lists the
  wires of that use. The key can be any value that works as a Python
  dictionary key.
- **A call ends a widget.** Rottnest closes the current widget at each
  marker (`compute_units/sequencer.py`).
- **Classical control is ignored.** Some gates depend on a measurement
  outcome. Rottnest applies such a gate whatever the outcome
  (`input_parsers/cirq_parser.py`).
- **T is the only magic state.** Rottnest breaks CCX down into T gates. It
  does the same to Qualtran's `And`.

## What this means for the library

1. **Hand over a rotation as a rotation.** The walk should yield a rotation
   as one entry with an angle and a tolerance. T is the rotation by pi/4.
   Suppose the library first turned a rotation into a sequence of T gates.
   Cabaliser would then add one graph qubit for each T. A rotation handed
   over whole adds one graph qubit.
2. **The library's gridsynth has two uses.** It gives T counts for the
   library's own cost estimates. It could also replace the backend team's
   decomposer. Their decomposer is built with Quipper, and their README
   recommends version 8.6.5 of the GHC compiler for it.
3. **The fixed form of a Clifford gate serves the hash.** Cabaliser merges
   Clifford gates whatever it is given. The walk writes a Clifford gate as a
   sequence of H and S, which `WireOp.iter_gates` already produces.
   Cabaliser's Clifford gates carry no overall phase, so the walk can drop
   it.
4. **An entry needs wire numbers.** Two equal subcircuits yield equal walks
   only if their wires are numbered the same way. So the content of a
   subcircuit must fix the numbering. This is open question 3 in DESIGN.md.
5. **The choice of calls changes the reported cost.** A call ends a widget,
   and a widget receives each input through two graph qubits. By Rottnest's
   count, `ccz` as its own widget is 2 × 3 + 7 = 13 graph qubits. The tree
   may hold more subcircuits than the walk reports as calls. The walk can
   write the gates of a small subcircuit in place.
6. **Measurement has a place.** MEAS exists, and so do Pauli gates that
   depend on a measurement. A CZ that depends on a measurement does not
   exist. Rottnest would count it as a plain CZ.

## What is not established

- **None of the code was run.**
- **The adapter is untested.** Their layout and scheduling tools may not
  accept instructions that come from outside their own parser.
- **Some code was not read.** The team has private repositories. Eight of
  the 18 public repositories in their GitHub organisation were not read.
  Pandora's source was not read.
- **Tolerances may be ignored.** The team may not honour a separate
  tolerance for each rotation.

## Questions for the backend team

1. Will you consume a walk of gates and calls, with a hash for each
   subcircuit, in place of a Cirq circuit?
2. A call ends a widget. How large must a subcircuit be to be worth a call?
3. Will you take a rotation as an angle and a tolerance? Will you honour a
   separate tolerance for each rotation?
4. Would you use a decomposer from this library in place of GridSynth?
5. How should a CZ that depends on a measurement be passed?

## Sources

Code, with the commit that was read.

- Cabaliser, commit `9bc6ed1`. <https://github.com/QSI-BAQS/cabaliser>
- rottnest_py, commit `0109b89`. <https://github.com/QSI-BAQS/rottnest_py>
- t_scheduler, commit `5af6a31`. <https://github.com/QSI-BAQS/t_scheduler>
- rottnest_example_executables, commit `289b3dc`.
  <https://github.com/QSI-BAQS/rottnest_example_executables>

Papers.

- Nguyen et al., Section V. <https://arxiv.org/abs/2509.13546>
- Moflic et al. <https://arxiv.org/abs/2507.20677>
- Saadatmand et al., Figure 1 and Section II.
  <https://arxiv.org/abs/2406.06015>
