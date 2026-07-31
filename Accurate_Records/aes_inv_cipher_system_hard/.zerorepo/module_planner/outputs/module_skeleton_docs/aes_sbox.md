# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_sbox
- file_path: rtl/aes_sbox.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_sbox
  - repo_skeleton_ref: repo_skeleton_v1::aes_sbox
  - spec_ref: aes_inv_cipher_system_hard.md (S001–S004)
- planning_note: Pure combinational forward S‑box; no clock, no state, no children.  

## 1. Module Frame
```verilog
module aes_sbox (
    // input  [7:0] sbox_byte_request,
    // output [7:0] sbox_byte_response
);

// <block: sbox_lut_decl>
// <block: sbox_output_comb>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: sbox_lut_decl
- block_kind: decl
- required: true
- purpose: Declare the constant lookup table (256×8 bits) that defines the forward S‑box.
- code_shape: constant-array or equivalent ROM‑inference region
- depends_on: []
- placeholder:
```verilog
// skeleton only: lookup table declaration
// 256-entry byte array containing S‑box substitution values
```
- must_appear:
  - 256‑byte constant table
- may_appear:
  - implementation‑specific pragmas for ROM/LUT mapping
- retrieval_focus:
  - data constant definition
  - table initialization values (derived from AES standard)

### Block
- block_id: B2
- block_label: sbox_output_comb
- block_kind: comb
- required: true
- purpose: Drive the output byte as a combinational function of the input byte using the declared lookup table.
- code_shape: combinational assignment or continuous‑assignment region
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: output drive region
// sbox_byte_response = table[ sbox_byte_request ]
```
- must_appear:
  - connection between input byte and table index
  - connection between table output and module output
- may_appear:
  - input‑width‑sensitive guards (e.g., full‑case warnings)
- retrieval_focus:
  - output‑to‑input mapping
  - index‑to‑data coupling

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - normal_lookup: one‑shot byte substitution via lookup table (default, no alternative modes)
- state_model:
  - object: none_no_state
    storage_kind: none
    representation: none
    notes: Module has no registered state; input payload drives combinational output only. All internal objects are constants or combinational nets.
- global_invariants:
  - output is always a deterministic function of the current input
  - no internal cycles, latches, or feedback paths exist
- open_semantic_questions:
  - none; the spec fully defines combinational lookup behaviour

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - hold the complete forward S‑box table as a compile‑time constant
  - be the single source of truth for substitution values
- timing_semantics:
  - declared constant, no timing dependencies
- touched_objects:
  - sbox_table[255:0]
- coupling_rules:
  - B2 must read from this table; no direct embedding of substitution logic in B2 without referencing B1
- forbidden_drift:
  - do not replace the table with on‑the‑fly Galois‑field computation unless the spec explicitly permits alternative implementations (the spec mandates a lookup table)

- block_id: B2
- responsibilities:
  - map input byte (sbox_byte_request) to output byte (sbox_byte_response) using the table from B1
  - maintain purely combinational behaviour: output follows input without delay beyond gate propagation
- timing_semantics:
  - combinational path; no clock‑edge sampling inside this module
  - output to be treated as stable only after input setup and propagation, as per external setup/hold constraints
- touched_objects:
  - sbox_byte_request (input)
  - sbox_byte_response (output)
  - sbox_table (constant from B1)
- coupling_rules:
  - depends on B1 for the table content
  - must not introduce local state or pipelining (that would shift timing requirements onto the parent)
- forbidden_drift:
  - do not add pipeline registers unless explicitly required by a later integration note and captured in a deferred decision
  - do not add alternative substitution methods that bypass the lookup table

## 4. Decision Ledger
### Chosen Decision
- topic: implementation form
- decision: Use a constant lookup table (ROM/LUT‑inferred) as specified by the module spec.
- reason: The spec mandates a 256×8 lookup table and prohibits alternative mathematical derivation inside this module. This aligns with the “pure combinational” constraint.

### Deferred Decision
- items:
  - Exact synthesis‑level coding style (e.g., Verilog case statement vs. array with readmemh) is left to later local generation.
  - If synthesis tools require particular ROM/LUT inference pragmas, they will be added in the final RTL without altering the architectural skeleton.

### Structural Risk
- items:
  - None; the module is a leaf combinational unit with a single well‑defined function.

### Behavioral Risk
- items:
  - Timing closure: propagation delay through the 256×8 table must meet the parent’s combinational‑path budget. This is a physical‑implementation concern, not a skeleton‑level ambiguity.
  - If future system constraints demand pipelining, that decision must be recorded as a deferred decision and reflected in a new block; the skeleton currently forbids internal pipelining.