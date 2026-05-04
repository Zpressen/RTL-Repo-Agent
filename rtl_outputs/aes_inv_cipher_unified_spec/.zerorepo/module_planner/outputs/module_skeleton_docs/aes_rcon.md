# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_rcon
- file_path: rtl/aes_rcon.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_rcon
  - repo_skeleton_ref: repo_skeleton_v1::aes_rcon
  - spec_ref: aes_rcon Design Specification
- planning_note: Leaf stateful module that generates AES round constants via a 4-bit synchronous counter and registered 32-bit output. Structured around counter control, GF(2^8) derived lookup, and output registration.

## 1. Module Frame
```verilog
module aes_rcon (
    // port list placeholder
);

// <block: B1_decl_objects>
// <block: B2_seq_rcnt_counter>
// <block: B3_comb_rcon_lookup>
// <block: B4_seq_out_register>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_objects
- block_kind: decl
- required: true
- purpose: Declare ports, internal 4-bit counter, 32-bit output register, and constant/placeholder storage for round sequence values.
- code_shape: declaration cluster
- depends_on: []
- placeholder:
```verilog
// skeleton only: port declarations, rcnt 4-bit register, out 32-bit register, constant placeholders
```
- must_appear:
  - clk, kld, out
  - rcnt (4-bit)
- may_appear:
  - internal constant array or case placeholders
- retrieval_focus:
  - interface
  - state/register description

### Block
- block_id: B2
- block_label: seq_rcnt_counter
- block_kind: seq
- required: true
- purpose: Manage rcnt state. Handles synchronous reset/load on kld, normal increment, and overflow continuation beyond 9.
- code_shape: sequential control block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: rcnt update logic on clk edge with kld sync reset and increment conditions
```
- must_appear:
  - rcnt
  - kld
- may_appear:
  - wrap/continue logic for rcnt > 9
- retrieval_focus:
  - counter rules
  - reset behavior
  - operation principle (counting)

### Block
- block_id: B3
- block_label: comb_rcon_lookup
- block_kind: comb
- required: true
- purpose: Map current rcnt value to the corresponding 32-bit round constant. Implements the GF(2^8) multiplication sequence via lookup/mux.
- code_shape: combinational mapping block
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: rcnt-to-rcon mapping logic with default zero for rcnt > 9
```
- must_appear:
  - rcnt
  - next_rcon_value
- may_appear:
  - explicit case/lookup entries for 0-9
  - fallback zero path
- retrieval_focus:
  - round constant sequence derivation
  - special value processing (GF(2^8) reduction)
  - corner cases (rcnt > 9)

### Block
- block_id: B4
- block_label: seq_out_register
- block_kind: seq
- required: true
- purpose: Register the mapped round constant onto the out port. Enforces kld synchronous load override to initial constant.
- code_shape: sequential output block
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// skeleton only: out register update on clk edge driven by next_rcon_value or kld load value
```
- must_appear:
  - out
  - next_rcon_value
  - kld
- may_appear:
  - timing alignment notes
- retrieval_focus:
  - output timing contract
  - corner cases (kld=1 behavior)

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: counter_driven
- semantic_modes:
  - MODE_RESET_LOAD: kld asserted, forces rcnt=0 and out=0x01000000
  - MODE_INCREMENT: kld deasserted, rcnt advances 0->9, then continues >9
  - MODE_OUTPUT_ZERO: rcnt > 9, out holds 0x00000000 regardless of counter progression
- state_model:
  - object: rcnt
    storage_kind: registered
    representation: 4-bit unsigned counter
    notes: counts 0-9 valid range, continues incrementing past 9 per spec
  - object: out
    storage_kind: registered
    representation: 32-bit constant vector
    notes: lower 24 bits always zero, upper 8 bits hold derived GF(2^8) value
- global_invariants:
  - out is always registered and updates one time unit after clk rising edge
  - kld synchronously overrides state and output to initial round constant
  - out lower 24 bits remain 0x000000 for all valid and overflow states
- open_semantic_questions:
  - exact synthesis optimization for lookup vs arithmetic GF(2^8) multiplier (spec provides precomputed values, favoring lookup)

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - establish all signal widths and reset/load semantics declarations
- timing_semantics:
  - static declarations, no timing behavior
- touched_objects:
  - clk, kld, out, rcnt
- coupling_rules:
  - provides typed objects for B2, B3, B4
- forbidden_drift:
  - do not introduce extra ports, parameters, or implicit reset signals

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - govern rcnt progression and synchronous reset/load boundary
- timing_semantics:
  - updates strictly on clk rising edge
- touched_objects:
  - rcnt, kld
- coupling_rules:
  - feeds rcnt to B3; must not directly drive out
- forbidden_drift:
  - do not cap counter at 9; spec explicitly requires continued incrementing

### Block Behavioral Overlay
- block_id: B3
- responsibilities:
  - translate rcnt index to 32-bit RCON value using spec-derived sequence
- timing_semantics:
  - purely combinational; output ready within same cycle as rcnt
- touched_objects:
  - rcnt, next_rcon_value
- coupling_rules:
  - must output 0x00000000 for rcnt > 9; must not depend on kld directly
- forbidden_drift:
  - do not compute GF(2^8) multiplication dynamically if precomputed lookup satisfies spec derivation table
  - do not alter lower 24 bits from zero

### Block Behavioral Overlay
- block_id: B4
- responsibilities:
  - register RCON value and enforce kld synchronous load priority
- timing_semantics:
  - registered on clk rising edge; one-cycle latency from combinatorial input
- touched_objects:
  - out, next_rcon_value, kld
- coupling_rules:
  - final driver of out port; must respect kld load value over next_rcon_value
- forbidden_drift:
  - do not introduce asynchronous reset or enable unless explicitly specified

## 4. Subtask Plan
### Subtask
- subtask_id: ST1
- implements_blocks: [B1]
- generation_goal: Build port list, internal signal declarations, and constant placeholders aligned with interface and register specs.
- required_spec_sections:
  - Section 3: Interface
  - Section 4: Register
  - Section 8: Constraints (Counter Size)
- optional_spec_sections:
  - Section 5.3.1: Basic Derivation Process
- output_contract: Declares clk, kld, out, rcnt(4), and out(32) with correct widths and directions.
- merge_contract: Exposes typed identifiers for B2, B3, B4 to reference.

### Subtask
- subtask_id: ST2
- implements_blocks: [B2]
- generation_goal: Implement synchronous counter logic for rcnt with kld reset and continuous increment rules.
- required_spec_sections:
  - Section 4: Register
  - Section 6.2: Normal Operation (Counting)
  - Section 7.2: Maximum Count
- optional_spec_sections:
  - Section 6.1: State Transition Diagram
- output_contract: Produces rcnt next-state logic driven by clk and kld.
- merge_contract: Provides rcnt value to B3; maintains 4-bit width invariant.

### Subtask
- subtask_id: ST3
- implements_blocks: [B3]
- generation_goal: Construct combinational mapping from rcnt to 32-bit round constant, including overflow zero case.
- required_spec_sections:
  - Section 5.2: Round Constant Generation Principle
  - Section 5.3.1: Basic Derivation Process
  - Section 5.3.2: Special Value Processing
  - Section 7.2: Maximum Count
- optional_spec_sections:
  - Section 8: Constraints (Output Format)
- output_contract: Generates next_rcon_value (32-bit) based on rcnt; lower 24 bits forced to 0.
- merge_contract: Supplies next_rcon_value to B4; guarantees deterministic combinational output.

### Subtask
- subtask_id: ST4
- implements_blocks: [B4]
- generation_goal: Implement output registration with kld synchronous load priority and timing compliance.
- required_spec_sections:
  - Section 6.2: Normal Operation (Reset & Counting)
  - Section 7.1: Key load
  - Section 8: Constraints (Output Format, Registered Output)
- optional_spec_sections:
  - Section 6.1: State Transition Diagram
- output_contract: Drives out port with registered value; enforces kld=1 -> out=0x01000000.
- merge_contract: Finalizes module output; matches timing contract for registered change on clk edge.

## 5. Decision Ledger
### Chosen Decision
- topic: constant generation method
- decision: Use precomputed lookup/mux mapping for round constants instead of runtime GF(2^8) multiplier.
- reason: Spec Section 5.3 explicitly derives and lists all 10 values; lookup reduces complexity and matches "counter-based lookup mechanism" description.

### Deferred Decision
- items:
  - exact synthesis pragma or optimization hints for the lookup structure (left to downstream implementation phase)
  - whether to implement rcnt>9 increment as free-running or clamped (spec says "continues to increment", so free-running is chosen structurally, but exact bit-width behavior beyond 15 is deferred to synthesis constraints)

### Structural Risk
- items:
  - B3 and B4 separation may introduce unnecessary intermediate signal if synthesis prefers direct registered lookup; will be resolved during merge/debug phase.
  - Counter overflow handling relies on 4-bit natural wrap; if spec intended exact 10-cycle stop, structural mismatch could occur (mitigated by explicit rcnt>9 combinatorial gate in B3).

### Behavioral Risk
- items:
  - Timing alignment of kld load vs normal increment must strictly follow "one time unit after clock's rising edge" phrasing; violation could cause off-by-one constant delivery.
  - Lower 24 bits zeroing constraint must be enforced across all paths; accidental propagation of undefined bits could violate interface contract.