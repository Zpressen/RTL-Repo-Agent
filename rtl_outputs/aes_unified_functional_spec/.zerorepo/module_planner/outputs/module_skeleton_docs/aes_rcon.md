# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_rcon
- file_path: rtl/aes_rcon.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_rcon
  - repo_skeleton_ref: repo_skeleton_v1::aes_rcon
  - spec_ref: aes_rcon.md
- planning_note: Organize around the 4‑bit round counter `rcnt`, a combinational constant‑lookup function, and a registered output `out`. Keep block separation strict to support later local retrieval and merge.

## 1. Module Frame
```verilog
module aes_rcon (
    input clk,
    input kld,
    output [31:0] out
);

// <block: decl_registers>
// <block: comb_rcon_lookup>
// <block: seq_update>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_registers
- block_kind: decl
- required: true
- purpose: Declare the internal 4‑bit counter `rcnt`, the output register `out`, and any wires needed for the next‑round‑constant value.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: register declarations + wire next_rcon
```
- must_appear:
  - `rcnt` (4‑bit register)
  - `out` (32‑bit register)
- may_appear:
  - wire `next_rcon` (32‑bit combinational result)
- retrieval_focus:
  - interface
  - state/register description

### Block
- block_id: B2
- block_label: comb_rcon_lookup
- block_kind: comb
- required: true
- purpose: Combinational mapping from `rcnt` to a 32‑bit round constant. Produces `next_rcon` where the most‑significant byte is the AES round constant byte and the lower 24 bits are zero. For `rcnt` values 0‑9 the byte follows the sequence (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x1B? Wait ‑ spec says 0x1B for RC[9]); for `rcnt > 9` the whole 32‑bit word is zero.
- code_shape: combinational `always_comb` or `assign` / case construct
- depends_on: [B1]
- placeholder:
```verilog
// combinational: use rcnt to select a pre‑computed 8‑bit constant, form {8'h??, 24'b0}
// explicit coverage for rcnt = 0..9, default zero for rcnt > 9
```
- must_appear:
  - explicit mapping for `rcnt = 0` through `rcnt = 9`
- may_appear:
  - default zero case
- retrieval_focus:
  - datapath constant generation
  - combinational helper

### Block
- block_id: B3
- block_label: seq_update
- block_kind: seq
- required: true
- purpose: Clock‑synchronous update of `rcnt` and `out`. On a rising edge of `clk`:
  * if `kld` is high, `rcnt` is set to 0 and `out` receives `next_rcon(0)` (which is 0x01_000000).
  * otherwise `rcnt` increments (wraps as a 4‑bit modulo‑16 counter) and `out` receives `next_rcon(rcnt)`.
- code_shape: sequential `always_ff` block
- depends_on: [B1, B2]
- placeholder:
```verilog
// sequential: posedge clk, rcnt <= (kld) ? 0 : rcnt + 1; out <= next_rcon
```
- must_appear:
  - `kld`‑driven reset/load of `rcnt`
  - `out` register update using `next_rcon`
- may_appear:
  - explicit handling of `rcnt` wrap (inherent in 4‑bit addition)
- retrieval_focus:
  - state update
  - registered output timing

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: counter_driven
- semantic_modes:
  - KEY_EXPANSION: generation of round‑constant sequence for rcnt 0‑9 and zero‑padding beyond.
- state_model:
  - object: rcnt
    storage_kind: registered
    representation: 4‑bit up‑counter (counter_driven)
    notes: value directly drives the combinational lookup; values 0‑9 produce valid constants, values 10‑15 yield output zero.
- global_invariants:
  - The lower 24 bits of `out` are always zero.
  - `out` changes only at the clock rising edge.
- open_semantic_questions:
  - Behaviour when `rcnt` wraps from 15 back to 0, if it ever occurs outside a key‑expansion sequence, is not defined in the spec; the lookup table would again produce valid constants.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide the declarations of `rcnt`, `out`, and the `next_rcon` wire that connects B2 to B3.
  - No logic or timing behaviour.
- timing_semantics: N/A
- touched_objects:
  - `rcnt` (register)
  - `out` (register)
  - `next_rcon` (wire)
- coupling_rules:
  - Both B2 and B3 depend on these declared objects.
- forbidden_drift:
  - Do not declare extra state, counters, or signals not explicitly required by the spec.

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - Compute `next_rcon` as a pure combinational function of `rcnt`.
  - For `rcnt = 0` → 8’h01, `rcnt = 1` → 8’h02, …, `rcnt = 9` → 8’h1B; pad with 24’h0.
  - For `rcnt > 9` → output 32’h0.
  - No clock or reset logic inside this block.
- timing_semantics: combinational path from `rcnt` to `next_rcon`; must settle within one clock period.
- touched_objects:
  - `next_rcon` (drive)
- coupling_rules:
  - Provides `next_rcon` to B3; must reflect the current `rcnt` value exactly.
- forbidden_drift:
  - Do not introduce registers, pipeline stages, or dynamic GF(2⁸) multiplication circuitry unless the spec later mandates it.
  - Do not output any value for `rcnt = 10` other than zero, despite the derivation example showing 0x36.

### Block Behavioral Overlay
- block_id: B3
- responsibilities:
  - Sequential update of `rcnt` and `out` on `posedge clk`.
  - If `kld` is high, `rcnt <= 0` and `out <= next_rcon(0)`.
  - Otherwise, `rcnt <= rcnt + 1` (4‑bit wrap) and `out <= next_rcon`.
- timing_semantics: Registered output; changes occur after the clock edge following the combinational evaluation.
- touched_objects:
  - `rcnt` (read and write)
  - `out` (write)
- coupling_rules:
  - Reads `next_rcon` from B2; the sequencing ensures that the `out` register captures the constant corresponding to the newly updated `rcnt` (or reset value).
- forbidden_drift:
  - Do not alter the reset action to use an external asynchronous reset; only `kld` synchronous reset/load is allowed.
  - Do not conditionally stall the counter unless a future spec adds a stall signal.

## 4. Decision Ledger
### Chosen Decision
- topic: Round constant generation method
- decision: Use a precomputed hardwired combinational look‑up table (mux/case) instead of dynamic GF(2⁸) multiplication.
- reason: Only ten constants are needed; a table is simpler, smaller, and avoids custom finite‑field arithmetic.

- topic: Internal code organisation
- decision: Partition into three blocks: declarations (B1), combinational constant table (B2), sequential update (B3).
- reason: Clear separation of concerns improves local retrieval, fragment generation, and later merging with the key‑expansion parent.

### Deferred Decision
- items:
  - None within the module; all choices are forced by the spec or deliberately settled.

### Structural Risk
- items:
  - No structural risks; the decomposition matches the spec’s simple register/counter/lookup structure.

### Behavioral Risk
- items:
  - The derivation section lists RC[10] = 0x36, but the implemented valid range (`rcnt` 0‑9) and the corner‑case rule (`rcnt > 9` ⇒ 0) exclude this value. If the key‑expansion module expects a tenth round constant 0x36, the parent integration will need adjustment (e.g., an extra constant or a wider counter). This should be flagged during integration of `aes_key_expand_128`.