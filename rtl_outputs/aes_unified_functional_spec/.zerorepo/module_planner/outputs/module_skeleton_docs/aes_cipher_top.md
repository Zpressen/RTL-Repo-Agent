# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_cipher_top
- file_path: rtl/aes_cipher_top.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_cipher_top
  - repo_skeleton_ref: repo_skeleton_v1::aes_cipher_top
  - spec_ref: aes_cipher_top.md
- planning_note: Organize the module into a declaration block, an instantiation block for submodules, a MixColumns helper, a round datapath (SubBytes, ShiftRows, MixColumns bypass, AddRoundKey), a sequential FSM and counter manager, and a register-commit block that controls synchronous updates.

## 1. Module Frame
```verilog
module aes_cipher_top (
    // port list placeholder
);

// <block: decl_all>
// <block: inst_all>
// <block: mixcolumns_helper>
// <block: round_datapath>
// <block: fsm_sequencer>
// <block: register_commit>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_all
- block_kind: decl
- required: true
- purpose: Declare all storage elements (text_in_r, sa, dcnt, ld_r, text_out), internal combinational signals, and any control flags needed by later blocks.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster
// registers: text_in_r [127:0], sa[0:3][0:3] [7:0], dcnt [3:0], ld_r [0:0], text_out [127:0]
// internal signals: sbox_input_bus, sbox_output_bus, round_key_bus, next_state_matrix_columns, etc.
```
- must_appear:
  - text_in_r (128-bit)
  - sa[0:3][0:3] (4×4 8-bit)
  - dcnt (4-bit)
  - ld_r (1-bit)
  - text_out (128-bit)
- may_appear:
  - intermediate wires for sbox data, round keys, MixColumns partial products, FSM state encodings
- retrieval_focus:
  - interface
  - state/register description

### Block
- block_id: B2
- block_label: inst_all
- block_kind: inst
- required: true
- purpose: Instantiate 16 parallel aes_sbox modules and 1 aes_key_expand_128 module; provide wiring from state matrix to sbox inputs and from key inputs to key expand.
- code_shape: instance cluster
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: submodule instances
// 16 x aes_sbox instances, each connected to one byte of the state matrix
// 1 x aes_key_expand_128 instance connected to input key, providing four 32-bit round key words
```
- must_appear:
  - 16 aes_sbox instances (per spec)
  - 1 aes_key_expand_128 instance (per spec)
- may_appear:
  - connection buses to route sbox outputs to round datapath
- retrieval_focus:
  - submodule hierarchy
  - sbox/key expand interface mapping

### Block
- block_id: B3
- block_label: mixcolumns_helper
- block_kind: comb
- required: true
- purpose: Provide combinational MixColumns transformation for one column (or replicated for four columns) using GF(2^8) multiply-by-2 and XOR operations.
- code_shape: combinational logic function block (may be reused as a callable helper or explicitly duplicated)
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: MixColumns combinational helper
// input: four column bytes (8-bit each)
// output: four transformed column bytes
// internal: finite field multiply-by-2 combinational paths
```
- must_appear:
  - GF(2^8) multiply-by-2 paths
  - column byte mixing logic (×2, ×3 implemented as ×2 xor ×1)
- may_appear:
  - repeating the same logic four times for parallel processing
- retrieval_focus:
  - MixColumns datapath
  - finite field arithmetic

### Block
- block_id: B4
- block_label: round_datapath
- block_kind: comb
- required: true
- purpose: Compute the complete per-round transformation datapath: SubBytes (using sbox outputs from B2), ShiftRows (hardwired cyclic shifts), MixColumns (using B3 or inline columns), AddRoundKey (XOR with round key from B2). Provide a bypass path for the final round that skips MixColumns.
- code_shape: combinational network
- depends_on: [B2, B3]
- placeholder:
```verilog
// skeleton only: round datapath combinational network
// SubBytes: route each state byte through the corresponding sbox instance (outputs from B2)
// ShiftRows: hardwired reordering per row
// MixColumns: conditionally apply B3 outputs for each column
// AddRoundKey: XOR with round key slice (from key expand instance)
// final-round bypass: when dcnt==? or fsm_state==FINAL_ROUND, skip MixColumns
```
- must_appear:
  - SubBytes routing to 16 sbox results
  - ShiftRows wiring
  - MixColumns path (skip for final round)
  - AddRoundKey XOR with current round key
- may_appear:
  - multiplexers to select between intermediary states for initial AddRoundKey and subsequent rounds
- retrieval_focus:
  - round transformation datapath
  - key mixing

### Block
- block_id: B5
- block_label: fsm_sequencer
- block_kind: seq
- required: true
- purpose: Implement the finite state machine (IDLE, INIT_ROUND, ROUND_OP, FINAL_ROUND, DONE) and the round counter (dcnt) control. Generate next-state and load-enable conditions based on ld, dcnt, and current state.
- code_shape: sequential state machine and counter logic
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: FSM and counter sequence block
// state register: current_state (enum or encoded)
// next_state logic: transitions based on ld, dcnt value, and current state
// dcnt update: load with 0xB in INIT_ROUND, decrement in ROUND_OP, hold otherwise
// control outputs: flags for round stage, final round, completion
```
- must_appear:
  - FSM states: IDLE, INIT_ROUND, ROUND_OP, FINAL_ROUND, DONE
  - condition: IDLE → INIT_ROUND on ld=1
  - round counter initialisation to 11 (0xB) in INIT_ROUND
- may_appear:
  - exact decrement conditions and transition threshold (deferred)
- retrieval_focus:
  - control flow
  - state transition protocol

### Block
- block_id: B6
- block_label: register_commit
- block_kind: seq
- required: true
- purpose: On rising clock edge, update all registered objects (text_in_r, sa, dcnt, ld_r, text_out) according to FSM state and the round datapath output. Generate the done signal.
- code_shape: sequential update block (always_ff style placeholder)
- depends_on: [B4, B5]
- placeholder:
```verilog
// skeleton only: register commit block
// on positive clk edge or asynchronous reset (rst):
//   text_in_r, sa, dcnt, ld_r, text_out update as dictated by fsm_sequencer and round_datapath
//   done signal asserts in DONE state
//   reset clears all registers to 0
```
- must_appear:
  - synchronous or asynchronous reset to initialise all registers to zero
  - update of sa and text_out with final round result
  - done signal assertion
- may_appear:
  - pipeline staging if needed to meet timing (not indicated)
- retrieval_focus:
  - state writeback
  - output control

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: explicit_fsm
- semantic_modes:
  - IDLE: waiting for load signal
  - INIT_ROUND: load input data, initial AddRoundKey, set round counter
  - ROUND_OP: execute rounds 1-9 (SubBytes, ShiftRows, MixColumns, AddRoundKey)
  - FINAL_ROUND: execute round 10, skip MixColumns
  - DONE: output ciphertext, assert done
- state_model:
  - object: current_state
    storage_kind: registered
    representation: implementation-open
    notes: drives block enables, round stage selection, done signal; transitions per spec state diagram
  - object: dcnt
    storage_kind: registered
    representation: 4-bit down-counter
    notes: loaded with 11 in INIT_ROUND, decremented each round; transition from ROUND_OP to FINAL_ROUND depends on its value (exact threshold deferred)
  - object: text_in_r, sa, ld_r, text_out
    storage_kind: registered
    notes: synchronously updated per round; text_out latched in DONE
- global_invariants:
  - One round transformation completed per clock cycle
  - Output produced only after all rounds finished
  - Text_out mirrors state matrix column-major ordering
- open_semantic_questions:
  - Exact dcnt threshold that triggers FINAL_ROUND (e.g., dcnt==2 or dcnt==1) is not explicitly stated; must be resolved during generation.
  - Done signal hold duration after DONE is reached is unspecified.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide all declarations for registers and wires usable by downstream blocks
- timing_semantics:
  - None; purely declarative
- touched_objects:
  - text_in_r, sa, dcnt, ld_r, text_out, auxiliary signals
- coupling_rules:
  - All other blocks refer to objects declared here; no forward declarations allowed.
- forbidden_drift:
  - Do not add undeclared registers that affect the controller’s external contract.

- block_id: B2
- responsibilities:
  - Instantiate 16 aes_sbox and 1 aes_key_expand_128 with correct port connections.
  - Expose sbox outputs as combinational busses; provide round key words to the datapath.
- timing_semantics:
  - All outputs are combinational; key expand may have internal sequencing but its output is available in a synchronous manner.
- touched_objects:
  - sbox instance ports (a, b), key expand ports (clk, kld, key, wo_0..3)
- coupling_rules:
  - Key expand clock and control must align with aes_cipher_top clk and load sequence (kld signal must be driven appropriately by fsm_sequencer).
  - sbox inputs driven from current state matrix before SubBytes stage.
- forbidden_drift:
  - Do not instantiate more than 16 sbox or more than 1 key expand.

- block_id: B3
- responsibilities:
  - Compute MixColumns transformation for one column; may be replicated for four columns.
- timing_semantics:
  - Purely combinational; must complete within clock cycle along with other datapath logic.
- touched_objects:
  - column input bytes (from ShiftRows output), column output bytes
- coupling_rules:
  - Used by round_datapath (B4); must not incorporate any sequential elements.
- forbidden_drift:
  - Do not inadvertently include SubBytes or AddRoundKey inside this helper.

- block_id: B4
- responsibilities:
  - Assemble full round datapath: SubBytes routing, ShiftRows wiring, MixColumns (via B3), AddRoundKey XOR.
  - Implement final-round bypass (skip MixColumns) based on a control signal from fsm_sequencer.
- timing_semantics:
  - Purely combinational; critical path includes sbox lookup + MixColumns XORs.
- touched_objects:
  - sa current value (output from register_commit or previous stage), sbox outputs, round keys, MixColumns outputs, next-state matrix columns
- coupling_rules:
  - Must accept a control input to disable MixColumns for FINAL_ROUND.
  - Must output the next value for the state matrix to be latched in B6.
- forbidden_drift:
  - Do not embed FSM decisions or dcnt comparisons inside this block; only accept control flags.

- block_id: B5
- responsibilities:
  - Manage FSM state transitions and round counter decrement.
  - Generate load enable for key expand (kld) and control flags for B4 (e.g., skip MixColumns).
  - Detect completion and trigger transition to DONE state.
- timing_semantics:
  - Sequential block; registers updated on clock rising edge.
- touched_objects:
  - current_state, dcnt, ld_r (possibly), control flags to B4 and B6.
- coupling_rules:
  - Must sample ld synchronously and provide appropriate kld strobe for key expand loading.
  - Must not drive sa or text_out directly; only provide control signals.
- forbidden_drift:
  - Do not implement datapath operations; only control outputs.

- block_id: B6
- responsibilities:
  - On every clock rising edge, commit the currently selected next-state matrix to sa, update text_in_r and text_out as needed, and assert done signal.
  - Handle reset initialization.
- timing_semantics:
  - Sequential; registers updated on rising clock edge (and possibly asynchronously on rst).
- touched_objects:
  - sa, text_in_r, text_out, done, ld_r (as needed)
- coupling_rules:
  - Relies on B5 to provide valid state, and B4 to provide valid next-state matrix values.
  - Must ensure text_out holds final value only in DONE state.
- forbidden_drift:
  - Do not generate any combinational datapath outputs; only latch and drive.

## 4. Decision Ledger
### Chosen Decision
- topic: organizing principle
- decision: Decompose the module into six code-shaped blocks (declarations, submodules, MixColumns helper, combinational round datapath, sequential FSM, register commit) that align with the spec’s explicit stage requirements.
- reason: Enables clear separation of control, datapath, and instantiation, supporting focused retrieval and merge without mixing responsibilities.

### Deferred Decision
- items:
  - Exact reset polarity (active-high vs active-low) for rst signal; spec does not specify.
  - Precise dcnt threshold from ROUND_OP to FINAL_ROUND (e.g., dcnt==2 after 9 rounds or counter measures exactly 10 rounds including initial). Must be resolved during local generation.
  - Done signal hold duration (whether it remains asserted or deasserts after being acknowledged).
  - Whether the key expand kld signal is pulsed once in INIT_ROUND or held for multiple cycles; must match key expansion module interface.

### Structural Risk
- items:
  - The round_datapath (B4) may accumulate too many combinational paths; timing closure may require pipelining, but the spec mandates one round per clock without pipelining, so no structural adjustment anticipated.
  - The MixColumns helper (B3) is defined as separate block, but its logic could be replicated rather than shared; risk of duplication if not careful.

### Behavioral Risk
- items:
  - The correct sequencing of initial AddRoundKey with respect to key expand load and text_in_r latching is not fully detailed. If timing misalignment occurs (e.g., round key not ready), rounds may use wrong key.
  - The final round bypass must be applied after ShiftRows but before AddRoundKey; if ordering is accidentally swapped, output will be wrong.
  - Done signal may be sampled in the same cycle as the final round result, leading to possible off-by-one when integrated with higher-level controller.