# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_inv_cipher_top
- file_path: rtl/aes_inv_cipher_top.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_inv_cipher_top
  - repo_skeleton_ref: repo_skeleton_v1::aes_inv_cipher_top
  - spec_ref: aes_inv_cipher_top.md
- planning_note: Organize the module around declared state, submodule instances, a combinational round transform network, and a sequential FSM with register updates.

## 1. Module Frame
```verilog
module aes_inv_cipher_top (
    // port list placeholder: clk, rst, kld, ld, done, key, text_in, text_out
);

// <block: decl_state_and_signals>
// <block: inst_submodules>
// <block: round_transform_comb>
// <block: seq_control_fsm>

endmodule
```

## 2. Structural Skeleton

### Block
- block_id: B1
- block_label: decl_state_and_signals
- block_kind: decl
- required: true
- purpose: Declare all module registers (text_in_r, sa[0:3][0:3], dcnt, kb[10:0], kcnt, ld_r, text_out) and internal combinational wires (state, next_state, go, sa_ark, sa_next, sbox_out, mixcol_out, output_map, shift_out, round_key_sel, kb_ld, etc.).
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster
// registers: text_in_r[127:0], sa[0:3][0:3] (8-bit each), dcnt[3:0], kb[10:0][127:0], kcnt[3:0], ld_r, text_out[127:0]
// internal wires: state, next_state, go, sa_ark[127:0], sa_next[127:0], shift_out[127:0], sbox_out[127:0], mixcol_out[127:0], output_map[127:0], round_key_sel[127:0], kb_ld
// state and control signals as needed
```
- must_appear:
  - all spec-required registers (text_in_r, sa, dcnt, kb, kcnt, ld_r, text_out)
- may_appear:
  - intermediate combinational sizing/structuring signals
- retrieval_focus:
  - interface
  - state/register description

### Block
- block_id: B2
- block_label: inst_submodules
- block_kind: inst
- required: true
- purpose: Instantiate aes_key_expand_128 (one instance) and aes_inv_sbox (16 instances named us00–us33) with appropriate connections.
- code_shape: instance cluster
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: submodule instance region
// aes_key_expand_128 instance: u_ke (clk, kld, key, wo_0, wo_1, wo_2, wo_3)
// aes_inv_sbox instances: us00..us33 (a = state_byte, b = substituted_byte)
```
- must_appear:
  - exactly one aes_key_expand_128
  - exactly 16 aes_inv_sbox instances with names us00 through us33
- may_appear:
  - internal wire fan-out for sbox inputs/outputs
- retrieval_focus:
  - instance names and module boundaries

### Block
- block_id: B3
- block_label: round_transform_comb
- block_kind: comb
- required: true
- purpose: Compute inverse round transformations combinationaly: InvShiftRows, InvSubBytes (via B2 sbox instances), AddRoundKey (XOR with selected round key from kb[dcnt]), and InvMixColumns (except final round). Also produce final output mapping candidate (sa_ark → column-major 128-bit vector).
- code_shape: combinational network
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: combinational round transformation
// region: InvShiftRows (cyclic right shifts per row)
// region: InvSubBytes (16 combinational paths through us00..us33)
// region: AddRoundKey (select round_key_sel from kb[dcnt], XOR with shift/sub results → sa_ark)
// region: InvMixColumns (GF(2^8) matrix multiply per column, using pmul_e/b/d/9 functions → sa_next)
//   bypass MixColumns when final_round control is active
// region: output_mapping (map sa_ark to output_map candidate in column-major order)
```
- must_appear:
  - shift logic, sbox connection, key selection, InvMixColumns (conditional), output mapping
- may_appear:
  - helper functions for GF multiplications (pmul_e, pmul_b, pmul_d, pmul_9)
- retrieval_focus:
  - datapath transformation chain
  - combinational path structure

### Block
- block_id: B4
- block_label: seq_control_fsm
- block_kind: seq
- required: true
- purpose: Implement the FSM (IDLE, KeyLoad, KeyExpansion, KeyStored, InitialRound, StandardRound, FinalRound, Done) and all registered updates on clock edge. Manage counters (dcnt, kcnt), control signals (go, ld_r, kb_ld, done), and register assignments for text_in_r, sa, kb, kcnt, dcnt, ld_r, text_out.
- code_shape: sequential always blocks
- depends_on: [B1, B3]
- placeholder:
```verilog
// skeleton only: sequential control and register update
// always block(s) for state machine
//   state transitions based on kld, ld, kcnt==0, dcnt==11, etc.
//   produce control signals: go, kb_ld, ld_r_next, done, final_round flag
// always block(s) for register updates
//   text_in_r capture on ld & appropriate state
//   sa update: from load mapping (text_in_r + kb[10]) or sa_next
//   dcnt: reset=0, set=1 on data load, increment while go and not final
//   kcnt: reset=10, decrement during key expansion storage
//   kb buffer: capture wk3..wk0 into kb[kcnt] when key expansion active
//   text_out: capture output_map on Done state
```
- must_appear:
  - state register and next-state logic
  - counter update rules per spec
  - key buffer write logic
  - done signal assertion logic
- may_appear:
  - internal control signal intermediate assignments
- retrieval_focus:
  - FSM structure
  - register update timings

## 3. Behavioral Overlay

### Module-Level Behavioral Summary
- control_style: explicit_fsm
- semantic_modes:
  - key_load_phase: Load key, expand, store round keys in reverse order (kb[10]←initial, kb[0]←last).
  - decryption_phase: Process text_in through initial round, 9 standard rounds, final round (no InvMixColumns), output plaintext.
- state_model:
  - object: state (registered, enumerated values)
    storage_kind: registered
    representation: states IDLE, KeyLoad, KeyExpansion, KeyStored, InitialRound, StandardRound, FinalRound, Done
    notes: state transitions per spec; reset initializes to IDLE.
  - object: dcnt (round counter)
    storage_kind: registered
    representation: 4-bit, reset 0, set to 1 on data load, increments during operation, finish when 11 and not loading.
  - object: kcnt (key buffer counter)
    storage_kind: registered
    representation: 4-bit, reset 10, decrements to 0 during key expansion storage.
  - object: sa (state matrix), kb, text_in_r, text_out, ld_r
    storage_kind: registered
    representation: widths as spec; updated on clock edge.
- global_invariants:
  - Key schedule must be entirely loaded (kcnt==0 in KeyStored) before data processing can start.
  - Final round applies all transformations except InvMixColumns.
  - Output plaintext is held stable until next data load or reset.
  - No combinational feedback into state matrix; update only from registered sa_next.
- open_semantic_questions:
  - Exact reset timing (synchronous / asynchronous) not specified; assumption may be needed.
  - Behaviour when kld and ld are asserted simultaneously (both 1) at IDLE – spec does not define priority; must be resolved in local generation.

### Block Behavioral Overlay

- block_id: B1
- responsibilities:
  - Provide shared declared objects (registers and wires) used by all other blocks.
- timing_semantics:
  - None (declaration only).
- touched_objects:
  - All registers and combinational signals defined in the module.
- coupling_rules:
  - B2, B3, B4 depend on these declarations for signal names, widths, and register existence.
- forbidden_drift:
  - Do not add new top-level ports or registers not mentioned in the spec.
  - Do not pre-assign constants or implement logic inside this block.

- block_id: B2
- responsibilities:
  - Instantiate aes_key_expand_128 and connect its ports (clk, kld, key → wo_0‑3).
  - Instantiate 16 aes_inv_sbox (us00–us33) and connect their a inputs and b outputs to the state bytes.
- timing_semantics:
  - Submodule combinational paths are purely combinational (aes_inv_sbox); aes_key_expand_128 may have sequential internal logic but its interface is treated as given.
- touched_objects:
  - wk0..wk3 signals from key expansion; sbox input/output wiring.
- coupling_rules:
  - sbox outputs are consumed by B3.
  - key expand outputs are consumed by B4 (for kb loading).
- forbidden_drift:
  - Do not add extra instances beyond spec (one key expand, exactly 16 sboxes).
  - Do not alter instance naming conventions.

- block_id: B3
- responsibilities:
  - Implement InvShiftRows as a purely combinational cyclic right shift per row.
  - Route the shifted bytes to the appropriate sbox inputs (usxy); sbox outputs provide InvSubBytes result.
  - Combine with AddRoundKey: select the current round key from kb[dcnt] and XOR bytewise with the sbox output, producing sa_ark.
  - Apply InvMixColumns (GF(2^8) matrix multiplication per column using pmul functions) to sa_ark, producing sa_next.
  - Skip InvMixColumns when `final_round` control flag (from B4) is active; in that case sa_next is not used.
  - Generate output_map candidate from sa_ark in column-major order for final output.
- timing_semantics:
  - Entirely combinational; all paths complete within one clock cycle (critical path includes sbox + ark + mixcol).
- touched_objects:
  - state matrix sa (read), kb (read), dcnt (read, for key selection), sbox_outputs (from B2).
  - produces: sa_ark, sa_next, output_map.
- coupling_rules:
  - sa_next is registered into sa in B4.
  - output_map is registered into text_out in B4 during Done state.
  - The control signal `final_round` is driven by B4 and must be stable before this combinational block evaluates.
- forbidden_drift:
  - Do not add pipeline registers or sequential elements inside this block.
  - Do not change the transformation order relative to the spec.

- block_id: B4
- responsibilities:
  - Maintain the registered FSM state and produce next-state logic per spec transitions (IDLE→KeyLoad on kld|ld, KeyExpansion→KeyStored when kcnt==0, KeyStored→InitialRound on ld, FinalRound→Done when dcnt==11, Done→IDLE next cycle).
  - Drive control signals: go (set on data load, cleared on completion), ld_r flag, kb_ld (enable key buffer write during KeyExpansion), final_round flag, done output.
  - Manage counters:
    - dcnt: reset to 0; set to 1 on data load; increment each clock while go is true and not in final state; used to detect when dcnt==11.
    - kcnt: reset to 10; decrement each clock during KeyExpansion storage; used to detect completion (0).
  - Update registers on rising clock edge:
    - text_in_r: capture text_in when ld is asserted in appropriate state.
    - sa: for initial round, map text_in_r into column-major order and XOR with kb[10]; for subsequent rounds, capture sa_next from B3.
    - kb[10:0]: when key expansion is active, store the wk3..wk0 values into kb indexed by kcnt.
    - text_out: capture output_map from B3 during Done state; hold until next load or reset.
    - ld_r: set on data load, cleared otherwise.
- timing_semantics:
  - All updates are synchronous to rising edge of clk; reset behavior aligns with spec’s implicit active-high reset (rst).
- touched_objects:
  - All registers (text_in_r, sa, dcnt, kb, kcnt, ld_r, text_out, state).
  - Control outputs: go, kb_ld, done, final_round flag.
- coupling_rules:
  - Uses sa_next and output_map from B3.
  - Provides dcnt, kb, state, and control flags to B3.
  - Reads external inputs kld, ld, and drives done.
- forbidden_drift:
  - Do not perform combinational arithmetic or GF operations inside B4; restrict to state transitions and register load/store.
  - Do not add extra states or transitions beyond the eight named states.

## 4. Decision Ledger

### Chosen Decision
- topic: module decomposition
- decision: Partition into declarations (B1), submodule instances (B2), combinational round transform (B3), and explicit FSM/sequential updates (B4).
- reason: Matches the explicit FSM and combinational datapath described in the spec; keeps concerns separated for later code generation and debugging.

### Chosen Decision
- topic: control style
- decision: explicit_fsm with enumerated states (IDLE, KeyLoad, KeyExpansion, KeyStored, InitialRound, StandardRound, FinalRound, Done).
- reason: Spec provides a detailed state transition diagram and naming; explicit FSM is the most direct mapping.

### Deferred Decision
- items:
  - Implementation form of helper functions pmul_e, pmul_b, pmul_d, pmul_9 (LUT, case, or function) – left to local generation within B3.
  - FSM state encoding (one-hot, binary, gray) – not forced by spec; can be chosen at code generation.
  - Exact cycle-level handling of key expansion loop (kcnt decrement, simultaneous kb write) – spec implies one write per clock, but detailed timing may be refined.

### Structural Risk
- items:
  - B3 (round_transform_comb) will contain multiple sub-transformations; if not partitioned carefully inside the block, it could become monolithic. However, the spec clearly separates the sub-operations, mitigating risk.

### Behavioral Risk
- items:
  - Simultaneous assertion of kld and ld at IDLE could lead to ambiguous sequencing (spec says “waiting for the key load signal (kld) or data load signal (ld) to start”, but does not prioritize one over the other). Local generation must define a rule (e.g., give kld priority) to avoid deadlock or incorrect operation.
  - Unspecified reset timing (synchronous vs asynchronous) and the exact reset value of state/unused registers may cause mismatches if not clarified.