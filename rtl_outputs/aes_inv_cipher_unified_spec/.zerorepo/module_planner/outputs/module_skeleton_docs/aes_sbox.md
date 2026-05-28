# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_sbox
- file_path: rtl/aes_sbox.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_sbox
  - repo_skeleton_ref: repo_skeleton_v1::aes_sbox
  - spec_ref: aes_sbox.md
- planning_note: Purely combinational leaf module; a 256×8 lookup table (ROM/LUT) provides the substitution. No clock, no reset, no registered objects.

## 1. Module Frame
```verilog
module aes_sbox (
    input [7:0] a,
    output [7:0] b
);

// <block: decl_lookup_table>
// <block: comb_substitution>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_lookup_table
- block_kind: decl
- required: true
- purpose: Declare the 256×8 pre‑computed AES S‑Box values as a constant resource.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: 256×8 lookup table constant declaration
// Contains all S‑Box output values; no registers, no clock
```
- must_appear:
  - the complete 256‑entry S‑Box constant array
- may_appear:
  - implementation pragmas or attributes for ROM/LUT inference
- retrieval_focus:
  - S‑Box table definition

### Block
- block_id: B2
- block_label: comb_substitution
- block_kind: comb
- required: true
- purpose: Drive output b using the table entry indexed by input a.
- code_shape: combinational assignment
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational lookup: b = table[a]
// Purely combinational; input a directly addresses the table
```
- must_appear:
  - output b assigned from the lookup table
- may_appear:
  - nothing else
- retrieval_focus:
  - output b generation

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - DIRECT_LOOKUP: output b reflects the pre‑computed substitution of input a immediately; no internal modes.
- state_model:
  - object: no_registered_state
    storage_kind: none
    representation: not_applicable
    notes: The module is purely combinational with no clock or state.
- global_invariants:
  - Output b is a pure function of input a.
  - Output updates immediately after input changes, following the table mapping.
- open_semantic_questions:
  - None; the spec fully defines the function and corner cases (0x00→0x63, 0xFF→0x16).

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide the constant 256×8 S‑Box lookup table.
- timing_semantics:
  - Static declaration; no timing dependencies beyond standard elaboration.
- touched_objects:
  - sbox_table (the 256×8 constant)
- coupling_rules:
  - B2 must read this table; no other module state is involved.
- forbidden_drift:
  - Do not introduce clocked or registered storage; do not alter the standard AES S‑Box values.

- block_id: B2
- responsibilities:
  - Continuously drive output b with the table entry pointed to by a.
- timing_semantics:
  - Purely combinational; output changes immediately with a.
- touched_objects:
  - sbox_table (read), input a, output b
- coupling_rules:
  - None; no downstream control dependencies inside this module.
- forbidden_drift:
  - Do not add pipeline stages, enable signals, or registered outputs.
  - Do not introduce any additional ports or internal signals.

## 4. Decision Ledger
### Chosen Decision
- topic: Structural decomposition
- decision: Separate the lookup table declaration (B1) from the readout mapping (B2) to clearly expose the resource and its usage.
- reason: Matches the purely combinational spec and allows easy local retrieval of the table definition.

### Deferred Decision
- items:
  - Concrete Verilog coding style for the 256×8 table: ROM inference, case statement, or readmemh‑based initialization. The choice is left open to suit target tools and device characteristics.

### Structural Risk
- items:
  - None; a leaf combinational module with one resource and one readout poses minimal structural risk.

### Behavioral Risk
- items:
  - None; the function is fully specified and corner cases are explicitly validated in the spec.