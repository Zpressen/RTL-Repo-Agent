# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_sbox
- file_path: rtl/aes_sbox.v
- source_refs:
  - module_contract_ref: modules::aes_sbox
  - repo_skeleton_ref: repo_skeleton_v1::aes_sbox
  - spec_ref: aes_sbox.md
- planning_note: This is a purely combinational leaf module; its internal structure is a single lookup‑table block. No clock, no reset, no registered objects.

## 1. Module Frame
```verilog
module aes_sbox (
    input  [7:0] a,
    output [7:0] b
);

// <block: lookup_table_substitution>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: lookup_table_substitution
- block_kind: comb
- required: true
- purpose: Implement the 8‑bit forward S‑box substitution using a lookup table.
- code_shape: combinational lookup (ROM or case‑like selection)
- depends_on: []
- placeholder:
```verilog
// skeleton only: forward S‑box substitution table
//   input  a : 8‑bit address
//   output b : 8‑bit byte from S‑box table
//   corner‑case coverage:
//     0x00 → 0x63
//     0xFF → 0x16
//   table content from AES specification
```
- must_appear:
  - correct S‑box substitution values for all 256 input bytes
- may_appear:
  - implementation‑flexible mapping (ROM, packaged case, or LUT cascade)
- retrieval_focus:
  - the lookup table contents and corner‑case validation

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - NORMAL: Input a directly selects output b through the lookup table.
- state_model: []
- global_invariants:
  - Output b updates immediately after input a changes.
  - 0x00 always maps to 0x63; 0xFF always maps to 0x16.
- open_semantic_questions:
  - None – substitution is fully specified.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Convert the 8‑bit input byte a into the 8‑bit output byte b by applying the forward S‑box substitution.
  - Guarantee corner cases 0x00→0x63 and 0xFF→0x16.
- timing_semantics:
  - Output appears after combinational propagation delay; no clock or pipelining.
- touched_objects: []
- coupling_rules:
  - Downstream logic may sample b combinatorially; external setup/hold must be respected.
- forbidden_drift:
  - Do not add any internal state, clock, reset, or sequential element.
  - Do not alter the S‑box mapping from the AES forward table.

## 4. Decision Ledger
### Chosen Decision
- topic: Implementation method for substitution
- decision: Use a lookup table (256×8 stored values) as the sole substitution mechanism, consistent with the spec’s preferred actual realization.
- reason: Simplest and matches spec guidance; no mathematical inverse or affine logic needed explicitly.

### Deferred Decision
- items:
  - Exact implementation form (ROM, inferred LUT RAM, combinatorial case) remains open for a specific target technology.
  - No external pipelining helpers are defined inside this module; external modules may add registers as needed.

### Structural Risk
- items:
  - None – the single‑block combinational structure is unambiguous and appropriate for a leaf S‑box.

### Behavioral Risk
- items:
  - None – corner cases are explicitly specified and embedded in the lookup table.