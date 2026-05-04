# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_sbox
- file_path: rtl/aes_sbox.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_sbox
  - repo_skeleton_ref: repo_skeleton_v1::aes_sbox
  - spec_ref: aes_sbox.md
- planning_note: Pure combinational byte substitution via a 256-entry lookup table; no clock, reset, or registered objects.

## 1. Module Frame
```verilog
module aes_sbox (
    // port list placeholder: input [7:0] a, output [7:0] b
);

// <block: decl_sbox_table>
// <block: comb_lookup_output>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_sbox_table
- block_kind: decl
- required: true
- purpose: Declare the fixed 256-entry 8-bit substitution table (ROM/LUT) holding the AES S-box values.
- code_shape: declaration group (e.g., localparam array, case construct, inferred ROM)
- depends_on: []
- placeholder:
```verilog
// skeleton only: S-box table declaration (256 x 8 entries)
```
- must_appear:
  - exactly 256 constant 8-bit values matching the AES forward S-box
- may_appear:
  - compiler directives for ROM/LUT inference guidance
- retrieval_focus:
  - S-box table structure and content source

### Block
- block_id: B2
- block_label: comb_lookup_output
- block_kind: comb
- required: true
- purpose: Continuously drive output byte b from the table entry selected by input byte a.
- code_shape: combinational assignment or always_comb case block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational output b = sbox_table[a]
```
- must_appear:
  - output b driven purely as a combinational function of a
- may_appear:
  - nothing else
- retrieval_focus:
  - lookup logic and output net

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - SBOX_LOOKUP: forward byte substitution only
- state_model: none (no internal state)
- global_invariants:
  - b is a deterministic, purely combinational function of a
  - no side effects, no internal memory, no retained state
- open_semantic_questions: none

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide the hardwired 256-entry 8-bit substitution array
  - serve as a read-only constant ROM/LUT resource
- timing_semantics:
  - static; no timing dependency on a or any other signal
- touched_objects:
  - internal sbox_table (array, localparam, or memory)
- coupling_rules:
  - only B2 may read the table; all external paths see content only through B2
  - table contents are immutable and defined at elaboration time
- forbidden_drift:
  - do not add writability, clocking, or reset sensitivity
  - do not alter the standard AES forward S-box values

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - decode input a as an index into the S-box table
  - drive output b with the selected byte
  - implement continuous, unregistered lookup
- timing_semantics:
  - propagation delay only; b tracks a without clocked sampling
  - setup/hold considerations are external to the module
- touched_objects:
  - input a, output b, sbox_table (from B1)
- coupling_rules:
  - depends on B1 for table content; must not replicate or bypass it
  - output b is directly exposed at the module port; no internal buffering
- forbidden_drift:
  - do not introduce pipelining or registered stages
  - do not speculate on additional control or qualification of the output

## 4. Decision Ledger
### Chosen Decision
- topic: internal organisation
- decision: Separate the table declaration (B1) from the lookup logic (B2) to allow clear retrieval and possible future substitution of implementation style.
- reason: The spec allows ROM/LUT implementation flexibility; splitting the concerns avoids mixing storage and logic, and supports local retrieval for later code generation.

### Deferred Decision
- items:
  - Physical implementation style of the S-box table (e.g., localparam array, case statement, block RAM, distributed LUT) will be resolved during synthesis or technology mapping, as explicitly noted in the design constraints.

### Structural Risk
- items:
  - If a single large table is inferred as distributed memory, it may consume significant LUT resources; this is a synthesis concern, not a skeleton structural risk.

### Behavioral Risk
- items:
  - None; the combinational behaviour is unambiguous and fully specified.