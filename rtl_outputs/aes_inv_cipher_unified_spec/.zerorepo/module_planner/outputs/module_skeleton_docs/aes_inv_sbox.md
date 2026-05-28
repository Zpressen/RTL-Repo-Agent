# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_inv_sbox
- file_path: rtl/aes_inv_sbox.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_inv_sbox
  - repo_skeleton_ref: repo_skeleton_v1::aes_inv_sbox
  - spec_ref: aes_inv_sbox Design Specification (inside unified spec)
- planning_note: Purely combinational lookup module. Organise around a constant 256×8 inverse S‑box table and a direct output assignment block.

## 1. Module Frame
```verilog
module aes_inv_sbox (
    // port list: a (input [7:0]), b (output [7:0])
);

// <block: decl_inv_sbox_table>
// <block: comb_output_assignment>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_inv_sbox_table
- block_kind: decl
- required: true
- purpose: Declare the 256‑entry inverse S‑box constant table (ROM).
- code_shape: declaration group (256×8‑bit constant array)
- depends_on: []
- placeholder:
```verilog
// skeleton: constant inv_sbox_table[0:255] with predefined inverse S‑box values
```
- must_appear:
  - the complete inverse S‑box mapping (all 256 entries)
- may_appear:
  - nothing else
- retrieval_focus:
  - table content and addressing

### Block
- block_id: B2
- block_label: comb_output_assignment
- block_kind: comb
- required: true
- purpose: Drive output b from the inverse S‑box table using input a as address.
- code_shape: combinational assignment (continuous, no clocking)
- depends_on: [B1]
- placeholder:
```verilog
// skeleton: b driven by inv_sbox_table[a] without any sequential elements
```
- must_appear:
  - connection from input a to table address
  - connection from table output to output b
- may_appear:
  - internal combinational wires (optional)
- retrieval_focus:
  - address-to-output mapping, combinational path

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: purely_combinational
- semantic_modes:
  - SINGLE_MODE: continuous byte substitution
- state_model:
  - object: N/A
    storage_kind: N/A
    representation: purely combinational
    notes: No clocked registers or state elements; behaviour is entirely memoryless
- global_invariants:
  - Output b always equals inv_sbox_table[a]
  - No internal state, no clock, no reset
- open_semantic_questions:
  - none

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide fixed inverse S‑box mapping values as a constant (ROM) for all 256 inputs.
- timing_semantics:
  - Not applicable (static values)
- touched_objects:
  - inv_sbox_table (internal constant)
- coupling_rules:
  - B2 reads this table; any generated table must match the standard AES inverse S‑box exactly.
- forbidden_drift:
  - Do not alter table values; must be the correct inverse S‑box mapping.

- block_id: B2
- responsibilities:
  - Continuously compute output b = inv_sbox_table[a] without any clocked logic.
- timing_semantics:
  - Propagation delay only; b updates combinatorially after a changes.
- touched_objects:
  - a (input), b (output), inv_sbox_table
- coupling_rules:
  - Depends on B1 for table content; must not assume any pipelining or registered stages.
- forbidden_drift:
  - Do not add clock, reset, enable, or any sequential elements; do not add logic that modifies the output beyond direct table lookup.

## 4. Decision Ledger
### Chosen Decision
- topic: module organization
- decision: Split into a declaration block for the constant table and a combinational assignment block for the output.
- reason: Clear separation of data and access logic aids retrieval, verification, and matches the intended ROM‑based implementation.

### Deferred Decision
- items:
  - exact RTL representation of the 256×8 table (e.g., initialised `reg` array vs. localparam constant vs. synthesis‑directed ROM)
  - final mapping to target device resources (ROM block vs. distributed LUT)

### Structural Risk
- items:
  - none (simple combinational leaf module)

### Behavioral Risk
- items:
  - none (behaviour is exhaustively specified by the lookup table)