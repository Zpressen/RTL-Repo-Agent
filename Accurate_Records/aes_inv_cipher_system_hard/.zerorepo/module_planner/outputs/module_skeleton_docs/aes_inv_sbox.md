# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_inv_sbox
- file_path: rtl/aes_inv_sbox.v
- source_refs:
  - module_contract_ref: (not explicitly provided; derived from architecture timing slice)
  - repo_skeleton_ref: repo_skeleton_v1::aes_inv_sbox
  - spec_ref: aes_inv_cipher_system_hard.md (sections S004, S005, S006, S007, S008, S009)
- planning_note: Pure combinational leaf module implementing the AES inverse S-box via a 256x8 lookup table. No clock, reset, or persistent state.

## 1. Module Frame
```verilog
module aes_inv_sbox (
    // port list placeholder
);

// <block: decl_lookup_table>
// <block: comb_table_lookup>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_lookup_table
- block_kind: decl
- required: true
- purpose: Define the constant inverse S-box mapping table (256 x 8-bit ROM/LUT).
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: constant 256x8 inverse S-box table declaration
```
- must_appear:
  - full 256-entry lookup table with standard AES inverse S-box values
- may_appear:
  - nothing else
- retrieval_focus:
  - ROM/constant table representation
  - table content specification

### Block
- block_id: B2
- block_label: comb_table_lookup
- block_kind: comb
- required: true
- purpose: Combine the byte‑in address with the declared table to drive byte_out.
- code_shape: combinational assignment
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational read from inverse S-box table
```
- must_appear:
  - address → data lookup path using the table from B1
- may_appear:
  - nothing else
- retrieval_focus:
  - read‑only combinational path
  - address‑data mapping

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - NORMAL: continuous byte substitution for all input values (0x00–0xFF)
- state_model:
  - object: byte_out
    storage_kind: combinational
    representation: 8-bit vector
    notes: output derived from byte_in and the constant lookup table; no registers
- global_invariants:
  - byte_out must equal the AES inverse S-box standard value for the current byte_in
  - output responds to input changes within a single simulation delta
- open_semantic_questions:
  - none (the standard mathematical definition of the inverse S-box is authoritative)

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - hold the complete 256x8 inverse S-box table as a read‑only data resource
- timing_semantics:
  - table values are fixed at elaboration time, no timing dependency
- touched_objects:
  - none (combinational constants)
- coupling_rules:
  - provides the lookup data to B2
- forbidden_drift:
  - do not introduce registered storage
  - do not change table size (must be exactly 256 entries of 8 bits)
  - do not use algorithmic computation in place of a declared table (spec requires lookup table)

- block_id: B2
- responsibilities:
  - read byte_in and drive byte_out by indexing into the constant table from B1
- timing_semantics:
  - purely combinational; delay is the read path of the table
- touched_objects:
  - byte_in
  - byte_out
- coupling_rules:
  - must use the table declared in B1
  - must not bypass or shadow the table
- forbidden_drift:
  - do not add a clock or reset signal
  - do not insert sequential elements (flops, latches)
  - do not use external sub‑modules or state machines

## 4. Decision Ledger
### Chosen Decision
- topic: implementation primitive
- decision: Lookup table (256x8 ROM/LUT) driven by a pure combinational read
- reason: The spec explicitly chooses the lookup table method (S005, S007) and the design is a leaf‑combinational block with no clock.

### Deferred Decision
- items:
  - Whether the table is expressed as a Verilog `case` statement, `readmemh` array, or other synthesizable ROM style. This is a backend synthesis choice.

### Structural Risk
- items:
  - None for a single‑block lookup; table size is small enough for any target.

### Behavioral Risk
- items:
  - The table values must exactly match the published AES inverse S‑box standard. Any deviation breaks the inverse relationship and violates S009 (S‑box(Inv_S‑box(x)) = x). Verification against the AES standard is required at generation time.