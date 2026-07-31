# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_inv_cipher_top
- file_path: rtl/aes_inv_cipher_top.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_inv_cipher_top
  - repo_skeleton_ref: repo_skeleton_v1::aes_inv_cipher_top
  - spec_ref: aes_inv_cipher_system_hard.md
- planning_note: The module integrates key expansion and inverse S‑box instances, owns the state matrix, round‑key buffer, round counter, and control FSM. All inverse cipher transformations (InvShiftRows, InvSubBytes via child instance, AddRoundKey, InvMixColumns) except SubBytes substitution are performed internally.

## 1. Module Frame
```verilog
module aes_inv_cipher_top (
    // ports: clk, rst, kld, ld, done, key, text_in, text_out
);

// <block: decl_core_state>
// <block: inst_child_modules>
// <block: comb_round_network>
// <block: seq_control>
// <block: final_output>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_state
- block_kind: decl
- required: true
- purpose: Declare all persistent storage: state matrix, round‑key buffer, round counter, FSM state register, and optional auxiliary registered objects.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: core state and register declarations
```
- must_appear:
  - state_matrix (4×4 bytes)
  - round_key_buffer (depth to hold 11 round keys)
  - round_counter (dcnt)
  - fsm_state (encoding for operational phases)
- may_appear:
  - auxiliary control flags (e.g., start or done flags)
- retrieval_focus:
  - interface (port list)
  - persistent state layout

### Block
- block_id: B2
- block_label: inst_child_modules
- block_kind: inst
- required: true
- purpose: Instantiate aes_key_expand and aes_inv_sbox as sub‑modules.
- code_shape: module instantiation group
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: aes_key_expand inst_key_expand ( ... );
// skeleton only: aes_inv_sbox  inst_inv_sbox  ( ... );
```
- must_appear:
  - one instance of aes_key_expand
  - one instance of aes_inv_sbox
- may_appear:
  - connection glue declarations (internal wires) if needed
- retrieval_focus:
  - sub‑module interface mapping
  - clock/rst connectivity

### Block
- block_id: B3
- block_label: comb_round_network
- block_kind: comb
- required: true
- purpose: Compute the next state matrix candidate through InvShiftRows, AddRoundKey, InvMixColumns, and InvSubBytes (via the inv_sbox instance).
- code_shape: large combinational network with helper sub‑blocks for each transformation
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: combinational datapath:
//   read current state from B1, round key from B1, invoke inv_sbox via B2,
//   produce next_state_comb per byte
```
- must_appear:
  - InvShiftRows byte rearrangement logic
  - AddRoundKey XOR network
  - InvMixColumns GF(2⁸) network
- may_appear:
  - helper functions/expressions for GF multiplications
- retrieval_focus:
  - datapath transformation order
  - combinational cone from state/key to next_state_comb

### Block
- block_id: B4
- block_label: seq_control
- block_kind: seq
- required: true
- purpose: Implement the multi‑phase control FSM, load external stimuli (key, text_in), drive the key expansion instance, update the state matrix and round counter, and orchestrate transitions.
- code_shape: always block with reset and posedge clk, containing case over fsm_state and counter updates
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// skeleton only: sequential control always block
//   clocked update of fsm_state, dcnt, state_matrix, round_key_buffer load
```
- must_appear:
  - state machine with phases: IDLE, KeyLoad, KeyExpansion, KeyStored, InitialRound, StandardRound, FinalRound, Done
  - round counter increment logic
  - state matrix commit using next_state_comb from B3
  - key_buffer load from key_expand outputs
- may_appear:
  - flags for key_expand start / done management
  - text_in load during KeyLoad
- retrieval_focus:
  - FSM encoding and phase transitions
  - state matrix update timing

### Block
- block_id: B5
- block_label: final_output
- block_kind: seq
- required: true
- purpose: Register the final text_out value and the done output signal at the appropriate phase.
- code_shape: registered output update on posedge clk, conditioned on FSM state being Done or FinalRound transition
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: output register update
//   text_out <= final_state_matrix;
//   done     <= 1'b1 when fsm_state == PH_DONE;
```
- must_appear:
  - registered text_out
  - registered done
- may_appear:
  - synchronous reset of done
- retrieval_focus:
  - output port mapping and timing of done assertion

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - IDLE: initial reset state, waiting for kld or ld
  - KeyLoad: key loading state, preparing key expansion
  - KeyExpansion: executing key expansion to generate round keys
  - KeyStored: round keys ready, waiting for data load
  - InitialRound: performs initial AddRoundKey and increments round counter
  - StandardRound: full inverse round (ShiftRows, SubBytes, AddRoundKey, MixColumns)
  - FinalRound: final inverse round without MixColumns
  - Done: decryption complete, output plaintext
- state_model:
  - object: state_matrix
    storage_kind: registered
    representation: 4×4 bytes, column‑major order
    notes: updated once per round in Standard / Final phases, stored in B1
  - object: round_key_buffer
    storage_kind: registered
    representation: 11×128‑bit (rk10 down to rk0)
    notes: filled from key_expand during KeyExpansion; read during round computations
  - object: round_counter (dcnt)
    storage_kind: registered
    representation: counter tracking round number
    notes: used for round key selection and condition for FinalRound
  - object: fsm_state
    storage_kind: registered
    representation: encoding of the operational phase
    notes: controls all sequential transitions and output gating
  - object: done_out
    storage_kind: registered
    representation: single bit
    notes: asserted in Done phase; de‑asserted on reset or new start
- global_invariants:
  - Only the FinalRound excludes InvMixColumns.
  - Round keys are applied in reverse order (rk10 .. rk0).
  - Output text_out and done are registered and free of glitches.
  - The inverse S‑box is accessed via combinational interface of aes_inv_sbox instance.
- open_semantic_questions:
  - Exact handshake mechanism for key expansion done signal (e.g., kcnt==0) is deferred to the instance interface of aes_key_expand.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide all persistent storage objects used by other blocks.
- timing_semantics:
  - Registers are updated elsewhere (B4/B5); B1 is a declaration region only.
- touched_objects:
  - state_matrix, round_key_buffer, round_counter, fsm_state, done_out
- coupling_rules:
  - Downstream blocks read these declared objects.
  - B4 has sole write access to state_matrix, round_counter, fsm_state, and round_key_buffer.
  - B5 has sole write access to done_out and the final text_out register.
- forbidden_drift:
  - Do not add extra registered resources not implied by the operational phases.

- block_id: B2
- responsibilities:
  - Instantiate aes_key_expand and aes_inv_sbox; route clk, rst, and data connections.
- timing_semantics:
  - aes_key_expand provides registered round keys visible on POST_EDGE.
  - aes_inv_sbox is purely combinational.
- touched_objects:
  - key input port, text_in port, initial_key signals, inv_sbox request/response combinational paths
- coupling_rules:
  - Round‑key outputs from key_expand are captured into round_key_buffer in B4.
  - The combinational path from B3 through inv_sbox must not be double‑registered outside B2.
- forbidden_drift:
  - Do not replicate or bypass the sub‑module logic; all S‑box operations happen through the instance.

- block_id: B3
- responsibilities:
  - Accept current state and round key from B1, issue byte requests to inv_sbox instance (via B2), and compute the next state candidate after InvShiftRows, InvSubBytes, AddRoundKey, and InvMixColumns.
- timing_semantics:
  - Purely combinational – settled within the clock period; no latches or flip‑flops.
- touched_objects:
  - current state matrix (read‑only), round key (read‑only), inv_sbox_request/response combinational nets
- coupling_rules:
  - The produced next_state_comb is used exclusively by B4’s sequential update.
  - Must not drive any registered output directly.
  - Must respect that FinalRound phase does not apply InvMixColumns; the omission is controlled by the selected next‑state path inside B3, relying on round_counter from B1.
- forbidden_drift:
  - Do not introduce pipelining or storage; keep the network fully combinational.

- block_id: B4
- responsibilities:
  - Implement the multi‑phase FSM: handle kld, ld, initiate key expansion, detect key_expand done, transition through rounds, increment round counter, commit next_state_comb into state_matrix, and manage start/stop of the key expansion instance.
- timing_semantics:
  - All updates occur on positive edge of clk, subject to synchronous reset (rst active high).
  - Initial key is sampled PRE_EDGE during KeyLoad phase, consistent with key_expand input timing.
  - State matrix is updated in the cycle following the round’s combinational evaluation (1‑cycle round latency).
- touched_objects:
  - fsm_state, round_counter, state_matrix, round_key_buffer, key_expand instance control signals
- coupling_rules:
  - Reads round_key from B1, writes new values during KeyExpansion phase.
  - Uses next_state_comb from B3 for state matrix updates.
  - Must coordinate with key_expand done signal to transition out of KeyExpansion.
  - Must ensure state matrix is not updated during IDLE/KeyLoad/KeyStored.
- forbidden_drift:
  - Do not implement any combinational transformation; leave that to B3.
  - Do not bypass the FSM phases or skip key expansion sequencing.

- block_id: B5
- responsibilities:
  - Register the final plaintext text_out and the done flag.
- timing_semantics:
  - Registered on posedge clk; text_out is written upon entering Done (or on the FinalRound commit), done is asserted in Done phase and cleared on reset.
- touched_objects:
  - state_matrix (read snapshot after FinalRound), done_out register, text_out register
- coupling_rules:
  - Output values are derived solely from state_matrix and fsm_state stored in B1.
  - No combinational path from text_out back into the round loop.
- forbidden_drift:
  - Do not create intermediate registered stages that delay output beyond the specified Done cycle.

## 4. Decision Ledger
### Chosen Decision
- topic: decomposition principle
- decision: Partition the design into declaration, instance, combinational datapath, sequential control, and output‑registration blocks, exactly reflecting the top‑level responsibilities inferred from the spec and architecture timing contracts.
- reason: This mapping keeps retrieval clean and matches the known structure of AES decryption engines while respecting child‑module boundaries.

### Deferred Decision
- items:
  - Exact internal wire widths (e.g., next_state_comb width) will be determined during concrete RTL generation, constrained by the state matrix size.
  - FSM state encoding (binary, one‑hot) is not yet chosen; any functional encoding is acceptable.

### Structural Risk
- items:
  - B3 may become a very large combinational cloud, causing synthesis challenges; hierarchical grouping or helper functions can mitigate this.

### Behavioral Risk
- items:
  - The handshake with aes_key_expand (how key_expand signals completion) is currently inferred; if the generated sub‑module uses a different protocol, B4 must be adjusted. This risk is bounded because aes_key_expand is already generated and its interface is known at merge time.