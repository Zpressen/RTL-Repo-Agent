# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_key_expand
- file_path: rtl/aes_key_expand.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_key_expand
  - repo_skeleton_ref: repo_skeleton_v1::aes_key_expand
  - spec_ref: aes_key_expand internal from system spec (S003, S004, S005, S006, S007, S008)
- planning_note: Module generates outer‑round keys sequentially using a 4‑word working register and an internal round counter (rcnt), instantiaties aes_sbox for SubWord, and exports each completed 128‑bit round key on a registered output.

## 1. Module Frame
```verilog
module aes_key_expand (
    // clock and reset
    // key load control (kld)
    // 128‑bit initial key input
    // 128‑bit round key output
);

// <block: decl_state_and_regs>
// <block: inst_sbox>
// <block: comb_round_const_gen>
// <block: comb_key_expand_next>
// <block: seq_update>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_state_and_regs
- block_kind: decl
- required: true
- purpose: Declare the round counter (rcnt), the four 32‑bit working registers that hold the current round key words, and any associated control flags.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// declaration cluster: rcnt, working keyword registers (w0..w3 or equivalent), expansion‑active flag if needed
```
- must_appear:
  - rcnt (round counter, 0‑9)
  - four 32‑bit registers holding the current round key words
- may_appear:
  - explicit round‑constant register (if not purely combinational)
  - enable/status flags
- retrieval_focus:
  - state register description
  - counter width / range

### Block
- block_id: B2
- block_label: inst_sbox
- block_kind: inst
- required: true
- purpose: Instantiate the aes_sbox child module to perform byte‑level SubWord substitution during key expansion.
- code_shape: module instantiation
- depends_on: []
- placeholder:
```verilog
// aes_sbox instance: 8‑bit in → 8‑bit out, purely combinational
```
- must_appear:
  - one aes_sbox instance
  - combinational byte‑in/byte‑out connectivity
- may_appear:
  - multiple instantiations if repeated per byte (but for clarity a single instance expected)
- retrieval_focus:
  - S‑box bounding box
  - SubWord byte routing

### Block
- block_id: B3
- block_label: comb_round_const_gen
- block_kind: comb
- required: true
- purpose: Compute the current round constant (Rcon) from rcnt using a small lookup or shift‑based mechanism, as required by the key expansion algorithm.
- code_shape: combinational function
- depends_on: [B1]
- placeholder:
```verilog
// combinationally derive round constant (e.g. LUT or shift polynomial) from rcnt
```
- must_appear:
  - 8‑bit round constant value updated cycle‑by‑cycle according to rcnt
- may_appear:
  - a small ROM / wire‑based LUT
- retrieval_focus:
  - Rcon derivation logic
  - dependency on rcnt

### Block
- block_id: B4
- block_label: comb_key_expand_next
- block_kind: comb
- required: true
- purpose: Compute the next set of four 32‑bit words from the current working registers (B1), the S‑box response (B2), and the round constant (B3), implementing the AES‑128 key expansion equations (RotWord, SubWord, Rcon XOR, and sequential word chaining).
- code_shape: combinational network
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// combinational derivation of next_w0, next_w1, next_w2, next_w3
// uses: current w3, w2, w1, w0, sbox output applied to rotated w3,
//       round constant XOR, and intra‑round XOR chaining
```
- must_appear:
  - RotWord of w3 feeding S‑box input
  - XOR of SubWord result with Rcon
  - four computed next‑word values according to AES‑128 key schedule
- may_appear:
  - per‑byte S‑box multiplexing (if single sbox reused)
- retrieval_focus:
  - key expansion datapath
  - algorithmic structure

### Block
- block_id: B5
- block_label: seq_update
- block_kind: seq
- required: true
- purpose: On each rising clock edge, when expansion is active, load the next words into the working registers, increment rcnt, and drive the registered round_key output; on kld assertion load the initial key into the working registers and reset rcnt.
- code_shape: always block (sequential)
- depends_on: [B1, B4]
- placeholder:
```verilog
// sequential update process:
//   kld asserted:
//     load initial_key into w0..w3, clear rcnt
//   kld deasserted and expansion still needed:
//     assign w0..w3 <= {next_w0, next_w1, next_w2, next_w3}
//     increment rcnt
//   registered output round_key <= {w0, w1, w2, w3} after update
```
- must_appear:
  - posedge clk sensitivity
  - synchronous reset / initialisation (rst)
  - state transitions described above
- may_appear:
  - expansion‑done flag (e.g. rcnt == 9 stop) if needed for top‑level handshake
- retrieval_focus:
  - register update timing
  - output driving
  - control signal handling

## 3. Behavioral Overlay

### Module-Level Behavioral Summary
- control_style: counter_driven
- semantic_modes:
  - KEY_LOAD: kld asserted → reset rcnt, capture initial_key into working registers
  - KEY_EXPANSION: kld deasserted → increment rcnt each cycle, compute next round key, output registered round_key
- state_model:
  - object: rcnt
    storage_kind: registered, 4‑bit
    representation: count 0‑9 (rollover or stop at 9)
    notes: reset on kld assertion
  - object: working_key_words (w0‑w3)
    storage_kind: four 32‑bit registered words
    representation: current round key being updated
    notes: loaded with initial_key on kld, updated each expansion cycle
- global_invariants:
  - round_key output is updated on the clock edge where key expansion is active, reflecting the newly computed 128‑bit round key.
  - rcnt value directly determines the round constant used and the expansion progress.
- open_semantic_questions:
  - Whether the module explicitly signals “expansion done” to the top level, or the top counts via kcnt.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - hold the module’s sequential state (rcnt, working registers) visible to other blocks.
- timing_semantics:
  - registers are updated on posedge clk (via B5); they are read combinationally by B3 and B4.
- touched_objects:
  - rcnt
  - w0, w1, w2, w3
- coupling_rules:
  - B3 reads rcnt only; B4 reads all four words; B5 updates them based on B4’s outputs.
- forbidden_drift:
  - Do not create additional persistent registers not implied by the spec (e.g. a separate round‑constant register if B3 is purely combinational from rcnt).

- block_id: B2
- responsibilities:
  - provide byte‑level SubWord substitution to the key expansion datapath.
- timing_semantics:
  - combinational: output responds immediately to input byte.
- touched_objects:
  - sbox input, sbox output (combinational signals)
- coupling_rules:
  - fed by part of the rotated w3 word; its output is consumed in B4.
  - must not alter or buffer the S‑box result; purely pass‑through instantiation.
- forbidden_drift:
  - Do not embed the S‑box inside any sequential wrapper inside this module; keep as leaf inst.

- block_id: B3
- responsibilities:
  - generate the round constant used in the AES key schedule from the round counter.
- timing_semantics:
  - purely combinational from rcnt; stable within the expansion cycle.
- touched_objects:
  - rcnt (read‑only)
  - rcon_byte (output word)
- coupling_rules:
  - read rcnt from B1; provide rcon_byte to B4.
- forbidden_drift:
  - Do not add extra sequential delay on rcon generation; keep it synchronous with the current rcnt.

- block_id: B4
- responsibilities:
  - encode the full AES‑128 key expansion algorithm (RotWord, SubWord, Rcon, and the word‑chaining XOR equations) as combinational logic.
- timing_semantics:
  - combinational; the path includes RotWord → S‑box lookup → XOR with rcon → XOR chain to produce next words.
- touched_objects:
  - w0–w3 (from B1, read‑only)
  - sbox_response (from B2)
  - rcon_byte (from B3)
  - next_w0, next_w1, next_w2, next_w3 (outputs to B5)
- coupling_rules:
  - must not store any intermediate values; all computation is feed‑forward.
  - if a single S‑box instance is shared, multiplex the appropriate byte of w3 into it.
- forbidden_drift:
  - Do not re‑implement S‑box functionality locally; always use B2’s instantiation.
  - Do not introduce non‑standard round constants or word ordering.

- block_id: B5
- responsibilities:
  - sequence the key expansion across clock cycles: load initial key on kld, then each cycle commit the next words computed by B4, increment rcnt, and drive the registered round_key output.
- timing_semantics:
  - registered: all state updates occur on posedge clk (rst synchronous).
  - round_key output is captured in a register updated at the same edge, visible post‑edge.
- touched_objects:
  - rcnt (write)
  - w0–w3 (write)
  - next_w0–next_w3 (from B4, read)
  - round_key output port (write)
- coupling_rules:
  - follows the enable signal derived from kld and expansion‑active condition.
  - must not bypass B4’s computations.
- forbidden_drift:
  - Do not generate round_key combinationally from working registers; it must be registered as specified by the architecture timing obligations (XFER_ROUND_KEY, POST_EDGE visibility).

## 4. Decision Ledger
### Chosen Decision
- topic: Organizing principle for key expansion logic
- decision: Split into combinatorial round constant / next‑word derivation and sequential state update, with a single child S‑box instance.
- reason: Aligns with module spec responsibilities and architecture contract (combinational S‑box access, registered round key output).

### Deferred Decision
- items:
  - Exact implementation of round constant generation (explicit LUT vs. shift‑with‑polynomial), left as implementation choice.
  - Whether an explicit “done” signal is exported from aes_key_expand or the top exclusively drives completion detection via kcnt.
  - Sharing strategy for a single S‑box instance across the four bytes of the rotated word (time‑multiplex vs. four parallel instances) — spec is ambiguous; defer to generation.

### Structural Risk
- items:
  - If the chosen round constant generation method is not aligned with timing (e.g., deep LUT may slow combinational path), critical path may need pipeline; currently assumed doable in one cycle.
  - The heavy combinational block B4 (SubWord, XOR chain) might cross timing closure boundaries if not carefully partitioned.

### Behavioral Risk
- items:
  - The precise handshake with aes_inv_cipher_top (e.g., how top knows key expansion is done) is underspecified; could lead to mismatched control sequencing during later integration.
  - Potential mismatch between rcnt range and the number of actually needed round keys if the top‑level kcnt counting scheme deviates from the internal rcnt logic.