# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_key_expand_128
- file_path: rtl/aes_key_expand_128.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_key_expand_128
  - repo_skeleton_ref: repo_skeleton_v1::aes_key_expand_128
  - spec_ref: aes_key_expand_128.md
- planning_note: Organize the module around key word registers, child instantiations (aes_rcon, aes_sbox×4), a combinational expansion network, and a sequential load/update block driven by kld flag.

## 1. Module Frame
```verilog
module aes_key_expand_128 (
    // port list: clk, kld, key[127:0], wo_0[31:0], wo_1[31:0], wo_2[31:0], wo_3[31:0]
);

// <block: decl_key_storage_and_signals>
// <block: inst_submodules>
// <block: comb_expansion_network>
// <block: seq_load_update>
// <block: output_assignment>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_key_storage_and_signals
- block_kind: decl
- required: true
- purpose: Declare the four 32-bit key word registers and all internal wires (intermediate transformation results, rcon output, sbox outputs).
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster
// - four 32-bit registers: w0, w1, w2, w3
// - wires for combinational network intermediates: rot_word, sub_word[31:0], T_word, next_w0..3
// - wires for rcon output: rcon_out[31:0]
// - wires for sbox outputs: sb0_out[7:0], sb1_out[7:0], sb2_out[7:0], sb3_out[7:0]
```
- must_appear:
  - the four key word registers (spec‑required)
- may_appear:
  - auxiliary combinational intermediate wires
- retrieval_focus:
  - state element declarations
  - interface for downstream blocks

### Block
- block_id: B2
- block_label: inst_submodules
- block_kind: inst
- required: true
- purpose: Instantiate one aes_rcon and four aes_sbox modules.
- code_shape: instance group
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: submodule instances
// aes_rcon u_rcon (.clk, .kld, .out(rcon_out));
// aes_sbox u_sbox0 (.a( <rot byte1> ), .b(sb0_out));
// aes_sbox u_sbox1 (.a( <rot byte2> ), .b(sb1_out));
// aes_sbox u_sbox2 (.a( <rot byte3> ), .b(sb2_out));
// aes_sbox u_sbox3 (.a( <rot byte4> ), .b(sb3_out));
```
- must_appear:
  - 1× aes_rcon
  - 4× aes_sbox
- may_appear:
  - connection details deferred
- retrieval_focus:
  - library/child hierarchy
  - signal routing anchors

### Block
- block_id: B3
- block_label: seq_load_update
- block_kind: seq
- required: true
- purpose: Synchronous load of initial key when kld=1; otherwise update the four registers with the next expanded round key words computed by the combinational network.
- code_shape: always @(posedge clk)
- depends_on: [B1, B4]
- placeholder:
```verilog
// skeleton only: sequential load/update process
// always @(posedge clk) begin
//   if (kld) begin
//     // load w0..w3 from key[127:96], [95:64], [63:32], [31:0]
//   end else begin
//     // update w0..w3 with next_w0..next_w3 from combinational network
//   end
// end
```
- must_appear:
  - kld‑controlled register load/update logic
- may_appear:
  - no reset logic unless spec eventually requires it
- retrieval_focus:
  - the sole state‑update arc
  - timing‑critical synchronous path

### Block
- block_id: B4
- block_label: comb_expansion_network
- block_kind: comb
- required: true
- purpose: Compute SubWord(RotWord(w3)) using sbox instances, XOR with rcon_out to form T_word, then compute next_w0, next_w1, next_w2, next_w3 from current w0..w3 and T_word.
- code_shape: combinational assign / wire networks
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: combinational key‑expansion network
// assign rot_word = { w3[23:0], w3[31:24] };
// assign sub_word = { sb0_out, sb1_out, sb2_out, sb3_out };
// assign T_word = sub_word ^ rcon_out;
// assign next_w0 = w0 ^ T_word;
// assign next_w1 = w1 ^ next_w0;   // (derived from w1 ^ w0 ^ T_word)
// assign next_w2 = w2 ^ next_w1;   // (derived from w2 ^ w1 ^ next_w0)
// assign next_w3 = w3 ^ next_w2;   // (derived from w3 ^ w2 ^ next_w1)
```
- must_appear:
  - RotWord, SubWord, T_word computation
  - next‑round word equations as per AES‑128 spec
- may_appear:
  - algebraic simplification if allowed later
- retrieval_focus:
  - combinational datapath core
  - anchor for SubWord/RotWord and XOR tree

### Block
- block_id: B5
- block_label: output_assignment
- block_kind: comb
- required: true
- purpose: Drive the module’s 32‑bit output ports directly from the internal register set.
- code_shape: continuous assignment group
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: output assignments
// assign wo_0 = w0;
// assign wo_1 = w1;
// assign wo_2 = w2;
// assign wo_3 = w3;
```
- must_appear:
  - wo_0..wo_3 tied to the four key word registers
- may_appear:
  - (no additional logic)
- retrieval_focus:
  - output interface binding

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: flag_driven
- semantic_modes:
  - KEY_LOAD: kld=1 → synchronous load of input key into registers; outputs follow immediately.
  - EXPANSION: kld=0 → each clock cycle the combinational network computes the next round key and the registers update; outputs reflect the newly expanded round key.
- state_model:
  - object: w0, w1, w2, w3
    storage_kind: registered (32‑bit each)
    representation: implementation‑open (flattened into four separate registers)
    notes: directly drive output ports; updated on rising clk
- global_invariants:
  - wo_0…wo_3 always equal current register values
  - expansion begins immediately after kld de‑assertion, producing one full round key per cycle
  - all S‑box lookups and rcon constant are purely combinational or self‑contained in submodules
- open_semantic_questions:
  - No explicit reset signal; behaviour at power‑up or after unspecified reset is undefined.
  - The spec does not define a “done” indicator or a limit on the number of expansion rounds; the module may keep expanding indefinitely.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide the storage objects (w0..w3) and all necessary combinational wires for the rest of the design
- timing_semantics:
  - purely declarative; does not itself enforce timing
- touched_objects:
  - w0, w1, w2, w3
  - all internal combinational wires
- coupling_rules:
  - blocks B3, B4, B5 must reference exactly these declarations
- forbidden_drift:
  - do not add extra registers, counters, or state machines not mentioned in the spec

- block_id: B2
- responsibilities:
  - incorporate the aes_rcon and four aes_sbox instances, making their outputs available to the combinational network
- timing_semantics:
  - rcon is clocked and synchronous, sboxes are combinational
- touched_objects:
  - rcon_out, sb0_out…sb3_out
- coupling_rules:
  - rcon’s kld must be connected to the module’s kld signal (reset of round constant)
  - sbox inputs must be driven by the rotated bytes from w3
- forbidden_drift:
  - do not instantiate extra rcon or sbox beyond 1× rcon and 4× sbox

- block_id: B3
- responsibilities:
  - implement the only synchronous update path; load initial key or capture expanded round key words
- timing_semantics:
  - posedge clk, kld sampled to select load vs. update
- touched_objects:
  - w0..w3
  - input key, kld
  - next_w0..next_w3 from B4
- coupling_rules:
  - must use the exact combinational network outputs provided by B4
- forbidden_drift:
  - do not insert a reset or an extra state machine; kld alone controls the mode

- block_id: B4
- responsibilities:
  - deliver the next round key words to B3 through pure combinational logic
- timing_semantics:
  - all outputs must settle within one clock period; no sequential elements
- touched_objects:
  - current w0..w3 (read)
  - rcon_out, sbox outputs
  - T_word, rot_word, sub_word
  - next_w0…next_w3
- coupling_rules:
  - must respect the exact byte‑order and XOR scheme from the AES key expansion spec
- forbidden_drift:
  - do not add pipelining registers or change the round key generation algorithm

- block_id: B5
- responsibilities:
  - continuously drive the output ports from the current register values
- timing_semantics:
  - purely combinational, no added latency
- touched_objects:
  - wo_0…wo_3, w0…w3
- coupling_rules:
  - no other block should directly assign wo_*
- forbidden_drift:
  - do not gate the outputs or add output registers

## 4. Decision Ledger
### Chosen Decision
- topic: block organisation for key‑expansion datapath
- decision: Separate combinational expansion network (B4) from sequential register update (B3) to clarify timing boundaries and reuse the pure‑combinational core for verification.
- reason: The spec describes distinct combinatorial transformations (RotWord, SubWord, XOR) and a synchronous load/update; reflecting this in blocks simplifies later code generation and retrieval.

### Chosen Decision
- topic: control style
- decision: Use a flag‑driven control (kld) with no explicit FSM.
- reason: The module’s only operational distinction is load vs. expand; no state transitions beyond this are required by the spec.

### Deferred Decision
- items:
  - Whether to include a round‑count limiter or a “done” flag – the spec is silent on this, so it is left for later elaboration when the consuming environment (aes_cipher_top) is fully defined.
  - Exact power‑on/reset state of registers; if a reset signal is later required, it will be added as an optional port.

### Structural Risk
- items:
  - The combinational expansion network (B4) may grow complex, but the separation into its own block prevents it from interleaving with sequential logic.
  - If the rcon submodule’s internal behaviour differs from the described round‑constant update, the inter‑block coupling will need adjustment.

### Behavioral Risk
- items:
  - If aes_cipher_top expects precisely 11 round keys and then stops advancing, the absence of an explicit round counter in aes_key_expand_128 may lead to over‑expansion if not externally gated. This must be clarified during top‑level integration.