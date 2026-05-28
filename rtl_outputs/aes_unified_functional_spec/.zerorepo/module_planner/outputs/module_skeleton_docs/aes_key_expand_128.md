# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_key_expand_128
- file_path: rtl/aes_key_expand_128.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_key_expand_128
  - repo_skeleton_ref: repo_skeleton_v1::aes_key_expand_128
  - spec_ref: aes_key_expand_128.md
- planning_note: Organize the module around key word registers, child instances, combinational round-key calculation, and a synchronous update block controlled by the kld flag.

## 1. Module Frame
```verilog
module aes_key_expand_128 (
    // clk, kld, key[127:0], wo_0[31:0], wo_1[31:0], wo_2[31:0], wo_3[31:0]
);

// <block: decl_round_key_registers>
// <block: inst_aes_rcon>
// <block: inst_aes_sbox_x4>
// <block: comb_new_round_words>
// <block: seq_register_update>
// <block: comb_output_assignment>

endmodule
```

## 2. Structural Skeleton

### Block
- block_id: B1
- block_label: decl_round_key_registers
- block_kind: decl
- required: true
- purpose: Declare storage for the four 32-bit round-key words (r0, r1, r2, r3).
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration of four 32-bit round-key registers (r0-r3)
```
- must_appear:
  - four 32-bit key-word registers per spec
- may_appear:
  - no other objects unless required by child instantiation wiring
- retrieval_focus:
  - central storage for current round key
  - used by output block and by expansion logic

### Block
- block_id: B2
- block_label: inst_aes_rcon
- block_kind: inst
- required: true
- purpose: Instantiate the round constant generator (aes_rcon) that produces a 32-bit round constant updated each cycle.
- code_shape: module instantiation
- depends_on: []
- placeholder:
```verilog
// skeleton only: aes_rcon instance
//   .clk(clk), .kld(kld), .out(rcon_out)
```
- must_appear:
  - one instance of aes_rcon
- may_appear:
  - internal connecting signals
- retrieval_focus:
  - delivers rcon_out to the combinational expansion block

### Block
- block_id: B3
- block_label: inst_aes_sbox_x4
- block_kind: inst
- required: true
- purpose: Instantiate four S-box modules for parallel byte substitution in SubWord.
- code_shape: block of four module instantiation statements
- depends_on: []
- placeholder:
```verilog
// skeleton only: four aes_sbox instances
//   .a(sbox_in_byte[0:3]), .b(sbox_out_byte[0:3])
```
- must_appear:
  - exactly four aes_sbox instances
- may_appear:
  - wiring of byte-level input/output signals
- retrieval_focus:
  - S-box outputs feed into the combinational expansion block

### Block
- block_id: B4
- block_label: comb_new_round_words
- block_kind: comb
- required: true
- purpose: Compute RotWord on r3, feed S-box inputs, form T = SubWord(RotWord) XOR rcon_out, then calculate next-round words (nxt_r0..nxt_r3) according to the spec’s XOR sequence.
- code_shape: combinational always block or continuous assignments
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// skeleton only: combinational network for round-word generation
//   apply RotWord to current r3
//   route each byte to an aes_sbox input
//   collect SubWord result
//   compute T = SubWord XOR rcon_out
//   generate nxt_r0..nxt_r3 using the spec-described XOR rules:
//       nxt_r0 = current_r0 XOR T
//       nxt_r1 = current_r1 XOR nxt_r0 XOR T (or equivalent per spec)
//       nxt_r2 = current_r2 XOR nxt_r0 XOR nxt_r1 XOR T (per spec)
//       nxt_r3 = current_r3 XOR nxt_r0 XOR nxt_r1 XOR nxt_r2 XOR T (per spec)
```
- must_appear:
  - RotWord transformation on r3
  - S-box input mapping for four bytes
  - rcon_out incorporation
  - equations for all four next-round words
- may_appear:
  - intermediate signal names
- retrieval_focus:
  - new‑round datapath; must be consistent with the spec’s multi‑XOR wording

### Block
- block_id: B5
- block_label: seq_register_update
- block_kind: seq
- required: true
- purpose: On every clock rising edge, if kld is active load key words from the input port; otherwise update the four registers with the computed next-round words.
- code_shape: sequential always block
- depends_on: [B1, B4]
- placeholder:
```verilog
// skeleton only: synchronous load / update of r0–r3
//   if (kld) begin
//       r0 <= key[127:96];
//       r1 <= key[ 95:64];
//       r2 <= key[ 63:32];
//       r3 <= key[ 31: 0];
//   end else begin
//       r0 <= nxt_r0;
//       r1 <= nxt_r1;
//       r2 <= nxt_r2;
//       r3 <= nxt_r3;
//   end
```
- must_appear:
  - kld‑gated synchronous load from key
  - synchronous update from B4’s outputs when kld is inactive
- may_appear:
  - reset handling if later determined, but spec is silent
- retrieval_focus:
  - the single register‐update rule; registers change only on clk rising edge

### Block
- block_id: B6
- block_label: comb_output_assignment
- block_kind: comb
- required: true
- purpose: Continuously drive wo_0..wo_3 with the current register values.
- code_shape: combinational assignment block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: assign wo_0 = r0; wo_1 = r1; wo_2 = r2; wo_3 = r3;
```
- must_appear:
  - output ports tied directly to r0–r3
- may_appear:
  - nothing else
- retrieval_focus:
  - ensures outputs immediately follow loading or expansion

## 3. Behavioral Overlay

### Module-Level Behavioral Summary
- control_style: flag_driven
- semantic_modes:
  - LOAD: kld active → synchronously load key words from the key bus into r0–r3; outputs reflect the loaded first round key.
  - EXPAND: kld inactive → every clock cycle compute a new round key using the expansion formula and update r0–r3; outputs advance to the next round key.
- state_model:
  - object: r0–r3 (four 32‑bit registers)
    storage_kind: registered
    representation: implementation‑open
    notes: four registers hold the current 128‑bit round key; all update simultaneously
- global_invariants:
  - wo_0..wo_3 always equal the current r0..r3 (no buffering delay)
  - the expansion sequence does not stop automatically; the external controller re‑asserts kld to restart the sequence
- open_semantic_questions:
  - reset behaviour is not specified; the skeleton defers any reset handling to later local generation
  - total number of expansion cycles is not enforced inside the module

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide the four 32‑bit storage elements that hold the working round key
- timing_semantics:
  - registers are updated on every rising clock edge; no combinatorial read glitches
- touched_objects:
  - r0, r1, r2, r3
- coupling_rules:
  - B5 is the sole updater of these registers
  - B4 reads r3 and all registers for next‑word calculation
  - B6 reads all registers
- forbidden_drift:
  - do not introduce extra shadow registers or non‑synchronous load paths

- block_id: B2
- responsibilities:
  - supply a 32‑bit round constant (rcon_out) that increments each cycle when kld is low
- timing_semantics:
  - rcon_out is updated by aes_rcon internally; its value must be valid before the expansion computation latches
- touched_objects:
  - rcon_out (internal wire)
- coupling_rules:
  - B4 is the only consumer of rcon_out
- forbidden_drift:
  - do not replicate rcon logic inside this module; always delegate to aes_rcon instance

- block_id: B3
- responsibilities:
  - map the rotated word bytes into four S‑box lookups and collect the SubWord result
- timing_semantics:
  - S‑box outputs are combinationally derived from their inputs; no internal register
- touched_objects:
  - sbox inputs/outputs (internal wires)
- coupling_rules:
  - B4 drives the S‑box inputs and reads the outputs
- forbidden_drift:
  - do not bypass or merge the four S‑box instantiations; exactly four discrete aes_sbox instances must appear

- block_id: B4
- responsibilities:
  - perform RotWord on the current r3
  - feed the rotated bytes to the S‑box instances
  - XOR the SubWord result with rcon_out to form T
  - compute next‑round words nxt_r0..nxt_r3 according to the spec’s explicit XOR chain
- timing_semantics:
  - purely combinational; must settle within one clock cycle to meet timing constraints
- touched_objects:
  - r3 (read only), rcon_out, sbox inputs/outputs, nxt_r0..nxt_r3
- coupling_rules:
  - depends on B1 (r3), B2 (rcon_out), B3 (sbox outputs)
  - provides new values to B5
- forbidden_drift:
  - do not reorder the XOR sequence arbitrarily; follow the spec’s wording (first word XOR, second word XOR with first and transformation, etc.) unless the specification is later clarified

- block_id: B5
- responsibilities:
  - on kld asserted → load r0–r3 from key bus slices
  - on kld de‑asserted → load r0–r3 from B4’s nxt_r0..nxt_r3
- timing_semantics:
  - synchronous on rising clock edge; no intermediate buffering
- touched_objects:
  - r0..r3 (modify)
  - key bus, nxt_r0..nxt_r3 (read)
- coupling_rules:
  - must not duplicate loading logic; all register writes pass through this block
  - the loading slice mappings are dictated by the spec: key[127:96]→r0, key[95:64]→r1, etc.
- forbidden_drift:
  - do not introduce asynchronous set or partial updates

- block_id: B6
- responsibilities:
  - provide continuous output drive of wo_0..wo_3 from r0..r3
- timing_semantics:
  - purely combinational; no register between internal registers and output ports
- touched_objects:
  - r0..r3 (read only)
  - wo_0..wo_3 (drive)
- coupling_rules:
  - must reflect r0..r3 immediately after any register update
- forbidden_drift:
  - do not insert latches, additional enable gates, or any combinatorial delay that would desynchronize the outputs from the internal state

## 4. Decision Ledger

### Chosen Decision
- topic: skeletal decomposition strategy
- decision: Separate the module into six blocks: declaration, two child instance blocks, combinational expansion network, sequential register update, and output assignment.
- reason: This matches the spec’s clear separation of storage, sub‑modules, expansion arithmetic, and the kld‑controlled load/update mechanism. It keeps retrieval and later code generation predictable.

### Deferred Decision
- items:
  - exact logical form of the multi‑XOR equations for nxt_r1–nxt_r3 (as spec wording may be simplified or re‑interpreted during code generation)
  - optional reset handling (not required by current spec)
  - internal naming of S‑box byte wires

### Structural Risk
- items:
  - B4 (comb_new_round_words) may become a large combinational blob if all round‑word equations and routing are placed there without internal structure; careful partitioning may be needed during fragment generation.
  - The dependency path from r3 through RotWord → S‑boxes → XOR chain and back to register inputs may create timing pressure; floorplanning awareness is required but not yet captured.

### Behavioral Risk
- items:
  - The spec’s description of the second/third/fourth word XOR sequences contains possible redundancy (apparent repeated XOR of the transformation result) that could lead to behavioral divergence from standard AES‑128. Later clarification or correction may be needed before RTL generation.
  - Absence of an explicit expansion‑end signal means the external integrator must know the correct round count; this module will continue expanding indefinitely if kld stays low.