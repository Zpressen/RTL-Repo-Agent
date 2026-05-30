# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_crc_7
- file_path: rtl/sd_crc_7.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_crc_7
  - repo_skeleton_ref: repo_skeleton_v1::sd_crc_7
  - spec_ref: sd_crc_7.md
- planning_note: Leaf stateful module computing a 7‑bit CRC with asynchronous reset and enable‑controlled update. Organised around declaration, combinational pre‑computation, and sequential register update.

## 1. Module Frame
```verilog
module sd_crc_7 (
    // port list placeholder – concrete ports defined by spec/contract
);

// <block: decl_core_objects>
// <block: comb_inv_compute>
// <block: seq_crc_update>

endmodule
```

## 2. Structural Skeleton

### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare the 7‑bit CRC register and any internal stored or derived objects.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration of CRC register (width 7) and supporting storage/wires
```
- must_appear:
  - CRC register (width 7)
- may_appear:
  - combinational wire for inv (if not local to a later block)
- retrieval_focus:
  - register width, reset value, update condition

### Block
- block_id: B2
- block_label: comb_inv_compute
- block_kind: comb
- required: true
- purpose: Combine BITVAL and CRC[6] to produce inv combinationally.
- code_shape: continuous assignment or combinational always block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational compute of inv = BITVAL ^ CRC[6]
```
- must_appear:
  - expression for inv using BITVAL and CRC[6]
- may_appear:
  - no other objects or logic
- retrieval_focus:
  - XOR input path, dependency on CRC[6]

### Block
- block_id: B3
- block_label: seq_crc_update
- block_kind: seq
- required: true
- purpose: Asynchronously reset or enable‑updated CRC register using inv and current state.
- code_shape: synchronous always block with asynchronous reset
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: sequential update of CRC register
// asynchronous reset (RST) takes precedence
// enable‑gated update shifts CRC bits and inserts inv at LSB,
// with XOR on CRC[3] path
```
- must_appear:
  - asynchronous reset to 0
  - enable‑gated update of CRC[0] <= inv, CRC[3] <= CRC[2] ^ inv, CRC[i>0,i!=3] <= CRC[i-1]
  - hold behaviour when Enable is low
- may_appear:
  - local assignment to simplify shift‑XOR mapping
- retrieval_focus:
  - shift‑XOR update pattern, reset priority

## 3. Behavioral Overlay

### Module-Level Behavioral Summary
- control_style: flag_driven
- semantic_modes:
  - RESET: RST asserted – CRC forced to 0 irrespective of Enable
  - HOLD: Enable deasserted, RST inactive – CRC retains current value
  - UPDATE: Enable asserted, RST inactive – CRC advances according to shift‑XOR rule
- state_model:
  - object: CRC (output register)
    storage_kind: registered
    representation: 7‑bit vector
    notes: Output directly driven by register; no additional output stage
- global_invariants:
  - CRC is always a valid 7‑bit value
  - inv is purely combinational and appears only as a next‑state input
  - RST overrides any Enable activity (reset priority)
- open_semantic_questions:
  - None – spec fully defines update equations and corner cases.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide the CRC register and any global‑scope storage for use by other blocks.
- timing_semantics:
  - purely declarative; no timing constraints
- touched_objects:
  - CRC
- coupling_rules:
  - B2 reads CRC[6]; B3 reads the full register and drives it
- forbidden_drift:
  - do not add extra state registers or delayed versions of CRC

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - Compute inv as BITVAL XOR CRC[6] combinationally.
- timing_semantics:
  - zero‑delay combinational; must be stable before the active clock edge
- touched_objects:
  - BITVAL (input), CRC[6] (read from B1)
- coupling_rules:
  - feeds inv signal to B3; must recompute on any change of BITVAL or CRC[6]
- forbidden_drift:
  - do not register inv; do not create sequential dependencies here

### Block Behavioral Overlay
- block_id: B3
- responsibilities:
  - Implement the asynchronous reset, enable‑gated shift‑XOR register update.
- timing_semantics:
  - asynchronous reset: CRC <= 0 when RST high
  - synchronous update on rising CLK: if Enable high, apply shift‑XOR rule; otherwise hold
- touched_objects:
  - CRC (driven), RST, Enable, CLK, BITVAL (indirectly via inv)
- coupling_rules:
  - consumes inv from B2; reads current value of CRC from B1 for shift
- forbidden_drift:
  - do not soften the reset priority (RST overrides Enable)
  - do not add pipelining or extra clocked stages

## 4. Decision Ledger

### Chosen Decision
- topic: block decomposition
- decision: Separate declaration, combinational pre‑computation (inv), and sequential update into distinct blocks.
- reason: Keeps retrieval straightforward and allows local reasoning about each concern; matches the explicit spec separation of inv and register update.

### Deferred Decision
- items:
  - exact coding style for the sequential block (single always vs. separate reset/update) – not forced by spec, left for generation.

### Structural Risk
- items:
  - None; the decomposition is minimal and naturally follows the design.

### Behavioral Risk
- items:
  - None; all corner cases (Enable deassertion, simultaneous RST/Enable) are explicitly defined and must be enforced in generation.