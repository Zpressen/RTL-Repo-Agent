# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_rcon
- file_path: rtl/aes_rcon.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_rcon
  - repo_skeleton_ref: repo_skeleton_v1::aes_rcon
  - spec_ref: aes_rcon.md
- planning_note: Leaf-level counter-driven round constant generator. Structure revolves around a registered counter, combinational next-state logic (including GF multiplication), and a synchronous register update block. No submodules.

## 1. Module Frame
```verilog
module aes_rcon (
    // input  clk,
    // input  kld,
    // output [31:0] out
);

// <block: decl_regs_and_wires>
// <block: comb_next_gen>
// <block: seq_update>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_regs_and_wires
- block_kind: decl
- required: true
- purpose: Declare registered objects (rcnt, out) and any intermediate next-state wires used by combinational and sequential blocks.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration of rcnt register, out register, and possibly next_rcnt / next_out wires
```
- must_appear:
  - rcnt (4-bit round counter, registered)
  - out (32-bit constant output, registered)
- may_appear:
  - next_rcnt, next_out (combinational pre‑values, optional but recommended for structural clarity)
- retrieval_focus:
  - interface
  - storage width / alignment constraints

### Block
- block_id: B2
- block_label: comb_next_gen
- block_kind: comb
- required: true
- purpose: Pure combinational logic that computes next_rcnt and next_out from current kld and rcnt. Does not contain sequential elements.
- code_shape: assign‑like or always_comb block skeleton
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational next-state and output logic
//   - next_rcnt = (kld) ? 0 : rcnt + 1
//   - next_out = (kld) ? 32'h01_00_00_00
//                : (rcnt > 9) ? 32'h0
//                : gf_mult_by_02_sequence(rcnt, ...)   // or lookup table approximation
```
- must_appear:
  - derivation for next_rcnt (counter increment / reset)
  - derivation for next_out (initial constant, overflow‑zero, or GF‑multiplied constant)
- may_appear:
  - helper encoding for the recursive GF(2⁸) multiplication, if not flattened
- retrieval_focus:
  - constraint: lower 24 bits of out must be zero in all cases
  - combinational path detail for later implementation choice

### Block
- block_id: B3
- block_label: seq_update
- block_kind: seq
- required: true
- purpose: Sequential always block triggered by posedge clk. Updates rcnt and out using next_rcnt and next_out from B2. Synchronous load/reset through kld is expressed inside this block.
- code_shape: sequential always block skeleton
- depends_on: [B2, B1]
- placeholder:
```verilog
// skeleton only: sequential register update on posedge clk
//   - rcnt <= next_rcnt
//   - out  <= next_out
```
- must_appear:
  - rcnt register assignment
  - out register assignment
- may_appear:
  - any necessary clock‑domain clarifications
- retrieval_focus:
  - update edge (rising)
  - synchronous behaviour of kld

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: counter_driven
- semantic_modes:
  - KEY_LOAD: kld=1 → rcnt=0, out=0x01000000 on next rising edge
  - NORMAL_COUNT: kld=0, rcnt≤9 → rcnt increments, out issues round constant for current rcnt
  - OVERFLOW_ZERO: kld=0, rcnt>9 → out=0x00000000, rcnt continues to increment
- state_model:
  - object: rcnt
    storage_kind: registered
    representation: 4‑bit counter (count range 0–9 used; above 9 allowed but output forced zero)
    notes: resets to 0 when kld synchronous; increments without explicit limit except width wraparound
  - object: out
    storage_kind: registered
    representation: 32‑bit bus, only MSByte changes per round constant; lower 24 bits are permanently zero
    notes: updates synchronously with rcnt; initial value 32’h01_00_00_00
- global_invariants:
  - out changes only on the rising edge of clk
  - when kld is asserted, out assumes 0x01000000 after the next clock edge
  - for rcnt values 0–9, out reflects the AES round constant sequence (01,02,04,…) in the most significant byte
  - for rcnt>9, out = 32’h0
  - counter (rcnt) is never stalled; it increments or resets every cycle
- open_semantic_questions:
  - post‑overflow wrap‑around behaviour (rcnt rolls from 15 back to 0) is not explicitly defined; specification only addresses rcnt up to 9 and overflow >9 without describing re‑entry into the 0–9 range

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide shared, typed declarations for rcnt and out, as well as any intermediate wires needed by B2 and B3
- timing_semantics:
  - all declared objects are synchronous; no combinatorial propagation assumptions are made at this block level
- touched_objects:
  - rcnt (register)
  - out (register)
  - (if present) next_rcnt, next_out (wires)
- coupling_rules:
  - B2 and B3 depend on these declarations; their behaviour must be consistent with widths and types defined here
- forbidden_drift:
  - do not add extra storage (e.g. an internal state machine register) not described in the spec

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - derive next_rcnt from current rcnt and kld
  - derive next_out from current rcnt, kld, and the recursive GF(2⁸) multiplication sequence
- timing_semantics:
  - purely combinational; must compute stable next values before the next rising clock edge
- touched_objects:
  - next_rcnt (if declared in B1)
  - next_out (if declared in B1)
  - reads rcnt and kld (external inputs, registered elsewhere)
- coupling_rules:
  - next_rcnt must equal 0 when kld=1, else rcnt+1 (4‑bit)
  - next_out must equal 0x01000000 when kld=1, else 0x00000000 when rcnt>9, else { RC[rcnt] , 24’h0 }
  - the RC constant for a given rcnt must match the spec‑derived sequence (01,02,04,08,10,20,40,80,1B,36)
- forbidden_drift:
  - do not invent asynchronous paths or bypass the registered output update
  - do not allow any non‑zero value in the lower 24 bits of next_out

### Block Behavioral Overlay
- block_id: B3
- responsibilities:
  - on rising edge of clk, assign next_rcnt to rcnt and next_out to out
  - this block is the sole writer of rcnt and out
- timing_semantics:
  - synchronous update on clk posedge; no other edge‑sensitive behaviour
- touched_objects:
  - rcnt (register write)
  - out (register write)
  - reads next_rcnt, next_out (from B2, via B1)
- coupling_rules:
  - must use the same next values produced by B2
  - must not alter rcnt or out under any other condition
- forbidden_drift:
  - do not introduce asynchrony, glitching, or additional reset logic not described in the spec

## 4. Decision Ledger
### Chosen Decision
- topic: structural decomposition
- decision: Organize the module into declaration (B1), combinational next‑state generation (B2), and sequential update (B3). This separates concerns and allows each block to be retrieved and reasoned about independently.
- reason: Fits the spec’s clear separation between the counter, the constant computation, and the synchronous output. Supports later substitution of GF multiplier vs. lookup table without touching the other blocks.

### Deferred Decision
- items:
  - Whether the constant‑generation path in B2 uses a hardcoded lookup table (rcnt → MSByte) or an explicit GF(2⁸) multiply‑by‑02 circuit. The spec allows either; this choice is deferred to local generation.
  - Exact naming and structure of intermediate wires (e.g., next_rcnt, next_out) – the skeleton only requires that they exist and are connected consistently.

### Structural Risk
- items:
  - rcnt is a 4‑bit counter; after reset (kld) it restarts at 0. If rcnt is allowed to count past 15 and wraps back to 0 while kld=0, it will re‑enter the valid 0‑9 range and could re‑issue round constants unintentionally. The spec does not define protection against this, but a downstream instantiation (aes_key_expand_128) is expected to manage kld before overflow occurs.
  - The module has no global asynchronous reset; all reset/initialization behaviour relies solely on kld. Systems that need a full hardware reset may need external handling.

### Behavioral Risk
- items:
  - The spec states “kld rising edge must synchronize with clk for key loading”. This implies that kld should be treated as a synchronous signal; any path where kld could be metastable or violate setup/hold is outside the scope of this module and may need external synchronisation.
  - The GF(2⁸) reduction rule for constants > 0x80 (1B, 36) must be accurately implemented. A deviation from the specified polynomial m(x) = x⁸+x⁴+x³+x+1 would break key expansion entirely. The skeleton does not resolve the implementation, so any local generation must verify correctness against the documented sequence.