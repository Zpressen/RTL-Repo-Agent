# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_sbox
- file_path: rtl/aes_sbox.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_sbox
  - repo_skeleton_ref: repo_skeleton_v1::aes_sbox
  - spec_ref: aes_sbox Design Specification
- planning_note: Pure combinational leaf module implementing the AES forward S-box via a 256×8 lookup table. No clocks, resets, or state machines required.

## 1. Module Frame
```verilog
module aes_sbox (
    // <port: a> input [7:0]
    // <port: b> output [7:0]
);

// <block: decl_interface_and_consts>
// <block: comb_lookup_assignment>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_interface_and_consts
- block_kind: decl
- required: true
- purpose: Declare module ports and the 256×8 constant storage for the forward S-box lookup table.
- code_shape: port declaration group + constant table definition cluster
- depends_on: []
- placeholder:
```verilog
// skeleton only: port declarations for a and b
// skeleton only: 256x8 constant table definition placeholder
```
- must_appear:
  - input a [7:0]
  - output b [7:0]
  - 256-entry constant array/table aligned with spec Sec 4
- may_appear:
  - synthesis-directed attributes for ROM/LUT inference
- retrieval_focus:
  - interface specification
  - constant storage layout

### Block
- block_id: B2
- block_label: comb_lookup_assignment
- block_kind: comb
- required: true
- purpose: Map input byte `a` to output byte `b` using the declared S-box table.
- code_shape: continuous assignment region
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational index-based lookup assignment
// skeleton only: corner-case validation markers for 0x00 and 0xFF
```
- must_appear:
  - direct mapping from a to b via table
  - adherence to spec corner cases (0x00→0x63, 0xFF→0x16)
- may_appear:
  - inline table indexing syntax
- retrieval_focus:
  - lookup operation principle
  - corner case handling

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - BYTE_SUB: continuous, zero-latency byte substitution
- state_model:
  - object: none
    storage_kind: none
    representation: none
    notes: combinational leaf with no registered state
- global_invariants:
  - b = SBOX[a] for all a ∈ [0:255]
  - output updates immediately upon input change (no registered delay)
- open_semantic_questions:
  - exact synthesis target (ROM vs distributed LUT) is implementation-dependent but functionally equivalent per spec Sec 6

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - establish external interface contract
  - define immutable 256×8 lookup constant
- timing_semantics:
  - static declaration; no timing dependencies
- touched_objects:
  - port a
  - port b
  - SBOX_TABLE
- coupling_rules:
  - downstream combinational logic must read from this table
  - table values must exactly match standard AES forward S-box specification
- forbidden_drift:
  - do not introduce clocks, resets, or sequential storage
  - do not modify port widths or directions

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - perform index-based table read
  - enforce spec corner-case outputs
- timing_semantics:
  - pure combinational propagation; output b tracks input a continuously
- touched_objects:
  - port a
  - port b
  - SBOX_TABLE
- coupling_rules:
  - must directly reference B1's table without intermediate registered stages
  - must not add pipelining or buffering
- forbidden_drift:
  - do not implement mathematical GF(2^8) inverse unless explicitly overriding lookup approach (spec prefers lookup)
  - do not introduce conditional gating that breaks combinational transparency

## 4. Subtask Plan
### Subtask
- subtask_id: ST1
- implements_blocks: [B1]
- generation_goal: Emit port declarations and 256×8 S-box constant storage.
- required_spec_sections:
  - 3. Interface
  - 4.1 Basic Principle (lookup table mandate)
  - 6. Constraints (ROM/LUT storage requirement)
- optional_spec_sections:
  - 4.2 Mathematical Derivation (for cross-verification if needed)
- output_contract: Defines `a`, `b`, and `SBOX_TABLE` with correct widths and static initialization shape.
- merge_contract: Provides immutable constants and port signatures for B2 to consume.

### Subtask
- subtask_id: ST2
- implements_blocks: [B2]
- generation_goal: Generate combinational assignment mapping `a` to `b` via the declared table.
- required_spec_sections:
  - 4.1 Basic Principle
  - 5. Corner Cases (0x00, 0xFF validation)
  - 6. Constraints (combinational timing rule)
- optional_spec_sections:
  - 4.2 Affine Transformation (for mathematical fallback validation)
- output_contract: Continuous assignment `b = SBOX_TABLE[a]` with verified corner-case entries.
- merge_contract: Connects table output to module port `b`; completes combinational data path for integration with `aes_key_expand_128`.

## 5. Decision Ledger
### Chosen Decision
- topic: implementation method for S-box transformation
- decision: Use a 256×8 lookup table rather than on-the-fly GF(2^8) inverse + affine math.
- reason: Explicitly mandated in spec Sec 4.1 ("In this design, we uses a lookup table to store all the S-box outputs values") and aligns with repo skeleton note "Pure combinational ROM lookup".

### Deferred Decision
- items:
  - exact Verilog constant declaration syntax (e.g., `parameter`, `localparam`, or `function`-based initialization)
  - synthesis-directed attributes for ROM vs LUT inference (left to tool/local generator)

### Structural Risk
- items:
  - minimal; leaf combinational structure is flat and well-bounded
  - risk of table initialization bloat in generated code if not carefully formatted

### Behavioral Risk
- items:
  - incorrect S-box constant values will break downstream cipher rounds; strict cross-check against standard AES forward S-box table is required
  - synthesis tools may introduce unintended buffering if combinational paths are not explicitly marked as pure assignment