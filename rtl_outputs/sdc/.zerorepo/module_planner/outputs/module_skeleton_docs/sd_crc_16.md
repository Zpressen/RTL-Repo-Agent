# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_crc_16
- file_path: rtl/sd_crc_16.v
- source_refs:
  - spec_ref: sd_crc_16 design specification
  - extracted_facts_ref: modules.json::sd_crc_16
  - repo_skeleton_ref: repo_skeleton.json::sd_crc_16
- planning_note: Organise the module around the 16-bit CRC register, its combinational input `inv`, and the sequential update logic with asynchronous reset.

## 1. Module Frame
```verilog
module sd_crc_16 (
    // port list placeholder
);

// <block: decl_core_objects>
// <block: comb_inv_logic>
// <block: seq_crc_update>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare the 16-bit CRC register and the combinational intermediate `inv`.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster for CRC register and inv wire
```
- must_appear:
  - CRC output register (16 bits)
  - inv (1 bit)
- may_appear:
  - nothing else
- retrieval_focus:
  - state storage
  - combinational intermediate

### Block
- block_id: B2
- block_label: comb_inv_logic
- block_kind: comb
- required: true
- purpose: Compute `inv = BITVAL XOR CRC[15]` combinational.
- code_shape: combinational assignment block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational logic for inv
```
- must_appear:
  - combinational expression for `inv`
- may_appear:
  - nothing else
- retrieval_focus:
  - combinational path from BITVAL and CRC[15]

### Block
- block_id: B3
- block_label: seq_crc_update
- block_kind: seq
- required: true
- purpose: Update the CRC register on rising edge of CLK or asynchronous RST, with Enable gating and shift‑and‑XOR update pattern.
- code_shape: sequential always block
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: sequential CRC update logic with async RST and Enable
```
- must_appear:
  - asynchronous reset (RST high → CRC = 0)
  - enable‑controlled shift‑and‑XOR update:
    - CRC[12] <= CRC[11] ^ inv
    - CRC[5] <= CRC[4] ^ inv
    - CRC[0] <= inv
    - remaining bits shift from CRC[i-1]
- may_appear:
  - nothing else
- retrieval_focus:
  - registered update rules
  - reset behaviour
  - enable gating

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - CRC_UPDATE: Enable is high, CRC is shifted and updated
  - HOLD: Enable is low, CRC holds its value
- state_model:
  - object: CRC
    storage_kind: registered
    representation: 16-bit vector
    notes: asynchronously cleared to 0 by RST; updated on posedge CLK when Enable = 1
- global_invariants:
  - `CRC` output always reflects the current value of the internal CRC register
  - `inv` is a pure combinational function of BITVAL and CRC[15] and never registered
- open_semantic_questions: []

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide the declared CRC register and `inv` wire for use by B2 and B3
- timing_semantics:
  - none (pure declaration)
- touched_objects:
  - CRC (register)
  - inv (net)
- coupling_rules:
  - B2 writes `inv`; B3 reads `inv` and updates CRC register
- forbidden_drift:
  - do not add extra declared registers or signals beyond CRC and inv

- block_id: B2
- responsibilities:
  - drive `inv` with `BITVAL ^ CRC[15]` continuously
- timing_semantics:
  - combinational; updates immediately when BITVAL or CRC[15] changes
- touched_objects:
  - inv
- coupling_rules:
  - depends on CRC[15] from B1
  - output used by B3
- forbidden_drift:
  - do not introduce sequential delay or additional gating on `inv`

- block_id: B3
- responsibilities:
  - handle asynchronous reset: when RST is high, set CRC to 0 immediately
  - on rising edge of CLK, if Enable is high, update CRC by left‑shifting and applying `inv` at specified bit positions; if Enable is low, hold CRC
- timing_semantics:
  - sequential, sensitive to posedge CLK and posedge RST (async)
- touched_objects:
  - CRC (register)
  - reads `inv` from B2
- coupling_rules:
  - must instantiate the exact shift‑and‑XOR pattern from the spec
  - must not alter CRC when Enable is low
- forbidden_drift:
  - do not add extra pipeline stages or bypass the enable gate
  - do not change the XOR tapping positions (12, 5)

## 4. Decision Ledger
### Chosen Decision
- topic: block decomposition
- decision: Split into declarations, combinational `inv`, and sequential CRC update block to reflect the spec’s separate combinational/sequential descriptions.
- reason: Keeps responsibilities minimal and aligns with explicit spec structure.

### Deferred Decision
- items: []

### Structural Risk
- items: []

### Behavioral Risk
- items: []