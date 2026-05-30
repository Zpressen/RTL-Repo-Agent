# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_data_master
- file_path: rtl/sd_data_master.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_data_master
  - repo_skeleton_ref: repo_skeleton_v1::sd_data_master
  - spec_ref: sd_data_master.md
- planning_note: FSM-based data transfer master for SD commands. Decomposed into parameter/register declarations, combinational next-state logic, sequential state and datapath update, and combinational output assignment.

## 1. Module Frame
```verilog
module sd_data_master (
    // input clk, rst
    // input dat_in_tx, ack_i_s_tx, free_tx_bd[BD_WIDTH-1:0]
    // input dat_in_rx, ack_i_s_rx, free_rx_bd[BD_WIDTH-1:0]
    // input cmd_busy, we_ack, cmd_tsf_err, card_status[4:0]
    // input tx_empt, tx_full, rx_full, busy_n, transm_complete, crc_ok
    // input Dat_Int_Status_rst, transfer_type[1:0]
    // output re_s_tx, a_cmp_tx, re_s_rx, a_cmp_rx
    // output we_req, d_write, d_read, cmd_arg[31:0], cmd_set[15:0]
    // output start_tx_fifo, start_rx_fifo, sys_adr[31:0]
    // output ack_transfer, Dat_Int_Status[7:0], CIDAT
);

// <block: param_decl>
// <block: decl_registers>
// <block: comb_fsm_ns>
// <block: seq_fsm_and_reg_update>
// <block: comb_output_assign>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: param_decl
- block_kind: decl
- required: true
- purpose: Declare all parameters, localparams, and conditional compile-time settings (READ_CYCLE, BD_EMPTY, bd_cnt width, state encoding).
- code_shape: parameter/localparam declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: parameter/localparam/conditional definitions
// includes CMD24, CMD17, CMD12, ACMD13, ACMD51, RESEND_MAX_CNT
// includes FSM state encoding (IDLE, GET_TX_BD, etc.) via parameter SIZE=9
// conditional: ifdef RAM_MEM_WIDTH_32 vs RAM_MEM_WIDTH_16 -> READ_CYCLE, BD_EMPTY, bd_cnt width
```
- must_appear:
  - spec-required parameters and FSM state one-hot encoding
- may_appear:
  - local helper parameters for bit indices
- retrieval_focus:
  - parameter names, widths, and conditional definitions

### Block
- block_id: B2
- block_label: decl_registers
- block_kind: decl
- required: true
- purpose: Declare all internal registers (state, next_state, flags, counters, address/data holding regs).
- code_shape: declaration group
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: register declarations
// state, next_state (9 bits)
// bd_cnt (2 or 3 bits, width from B1 conditional)
// tx_cycle, rx_cycle, send_done, rec_done, rec_failed, trans_done, trans_failed
// resend_try_cnt (3 bits)
// sys_adr (32 bits), cmd_arg (32 bits), cmd_set (16 bits)
// internal_transm_complete, transm_complete_q, CIDAT, Dat_Int_Status (8 bits)
```
- must_appear:
  - all registers listed in planning_facts
- may_appear:
  - edge-detect helper registers as needed
- retrieval_focus:
  - register interface and width

### Block
- block_id: B3
- block_label: comb_fsm_ns
- block_kind: comb
- required: true
- purpose: Combinational next-state logic (FSM_COMBO) that computes next_state from current state, inputs, and internal signals (bd_cnt, send_done, rec_done, rec_failed, trans_done, trans_failed, tx_full, free_tx_bd, free_rx_bd, transfer_type, etc.).
- code_shape: always_comb or assign block generating next_state
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: combinational next-state determination
// IDLE -> GET_TX_BD when free_tx_bd != BD_EMPTY
// IDLE -> GET_RX_BD when free_rx_bd != BD_EMPTY
// GET_TX_BD -> SEND_CMD when bd_cnt > READ_CYCLE-1 and tx_full == 1
// GET_RX_BD -> SEND_CMD when bd_cnt >= READ_CYCLE-1
// SEND_CMD -> RECIVE_CMD when send_done
// RECIVE_CMD -> DATA_TRANSFER when rec_done, -> SEND_CMD when rec_failed
// DATA_TRANSFER -> IDLE when trans_done, -> STOP when trans_failed
// STOP -> STOP_SEND unconditionally
// STOP_SEND -> IDLE when send_done
// default: stay in current state
```
- must_appear:
  - complete state transition mapping as per spec state table
- may_appear:
  - priority logic if TX BD checks have preference over RX BD
- retrieval_focus:
  - transition conditions and priority

### Block
- block_id: B4
- block_label: seq_fsm_and_reg_update
- block_kind: seq
- required: true
- purpose: Sequential process with asynchronous reset. Resets all internal registers to default values. On rising edge of clk: updates state <= next_state; updates all flags and datapath registers (bd_cnt, sys_adr, cmd_arg, cmd_set, tx_cycle, rx_cycle, send_done, rec_done, rec_failed, trans_done, trans_failed, resend_try_cnt, Dat_Int_Status, CIDAT, internal_transm_complete/transm_complete_q) according to current state, handshake signals, and conditions.
- code_shape: single always @(posedge clk or posedge rst) block
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// skeleton only: sequential update of state and all internal registers
// reset: state <= IDLE, flags <= 0, counters <= 0, address registers <= 0, Dat_Int_Status <= 0, CIDAT <= 0
// else:
//   state <= next_state
//   In IDLE: reset bd_cnt, clear temporary flags
//   In GET_TX_BD: if ack_i_s_tx: bd_cnt <= bd_cnt+1, load dat_in_tx into sys_adr/cmd_arg per READ_CYCLE, set tx_cycle
//   In GET_RX_BD: if ack_i_s_rx: bd_cnt <= bd_cnt+1, load dat_in_rx into sys_adr/cmd_arg, set rx_cycle, select cmd_set from transfer_type
//   In SEND_CMD: when we_ack received set send_done <= 1
//   In RECIVE_CMD: after cmd_busy deasserted check cmd_tsf_err and card_status, set rec_done or rec_failed
//   In DATA_TRANSFER: monitor tx_empt/rx_full/busy_n/transm_complete/crc_ok, set trans_done or trans_failed, free BD via a_cmp_tx/a_cmp_rx, assert ack_transfer on trans complete
//   In STOP: prepare command_set = CMD12, clear flags, start counters
//   In STOP_SEND: increment resend_try_cnt, send stop command via we_req handshake, on send_done transition
//   Dat_Int_Status updates: set error bits on resend limit, CRC fail, etc., reset on Dat_Int_Status_rst
//   CIDAT driven from data line status as needed
//   edge‑detect transm_complete using internal_transm_complete and transm_complete_q
```
- must_appear:
  - all registered objects from planning_facts must be updated here
  - all handshake-driven register loads (ack_i_s_tx, ack_i_s_rx, we_ack)
  - resend mechanism with resend_try_cnt and Dat_Int_Status[1]
- may_appear:
  - qualifying edge-detection logic for transm_complete
- retrieval_focus:
  - sequential responsibilities and update rules per state

### Block
- block_id: B5
- block_label: comb_output_assign
- block_kind: comb
- required: true
- purpose: Combinational assignment of all output ports based on current state, tx_cycle, rx_cycle, internal registers (cmd_arg, cmd_set, sys_adr, dat_int_status, CIDAT) and control flags. Derives re_s_tx, re_s_rx, we_req, d_write, d_read, start_tx_fifo, start_rx_fifo, ack_transfer, a_cmp_tx, a_cmp_rx, and passes through registered values for cmd_arg, cmd_set, sys_adr, Dat_Int_Status, CIDAT.
- code_shape: continuous assignments or always_comb
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: combinational output generation
// re_s_tx = (state == GET_TX_BD)
// re_s_rx = (state == GET_RX_BD)
// we_req = (state == SEND_CMD) && !cmd_busy
// d_write = (state == SEND_CMD) && tx_cycle
// d_read  = (state == SEND_CMD) && rx_cycle
// start_tx_fifo = asserted after TX BD load complete (in GET_TX_BD last cycle)
// start_rx_fifo = asserted in RECIVE_CMD when starting Rx duty
// ack_transfer = (state == DATA_TRANSFER) && internal_trans edge detected or similar
// a_cmp_tx = free BD in DATA_TRANSFER on Tx success
// a_cmp_rx = free BD in DATA_TRANSFER on Rx success
// sys_adr, cmd_arg, cmd_set, Dat_Int_Status, CIDAT driven directly from internal regs
// special: in STOP/STOP_SEND states, we_req and cmd_set assigned CMD12
```
- must_appear:
  - all output ports
  - state-driven enable for BD read and CMD handshake
- may_appear:
  - registered output assignments (if ports are reg) but behaviorally they reflect internal regs
- retrieval_focus:
  - output signal derivation mapping

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: explicit_fsm
- semantic_modes:
  - TX_MODE: active when free_tx_bd != BD_EMPTY, performs GET_TX_BD → SEND_CMD → RECIVE_CMD → DATA_TRANSFER → IDLE
  - RX_MODE: active when free_rx_bd != BD_EMPTY, performs GET_RX_BD → SEND_CMD → RECIVE_CMD → DATA_TRANSFER → IDLE
  - STOP_MODE: entered on DATA_TRANSFER failure, executes STOP → STOP_SEND → IDLE with retry
  - IDLE_MODE: waiting for buffer descriptors
- state_model:
  - object: state
    storage_kind: registered (9‑bit one‑hot)
    representation: one-hot encoded as per `IDLE`, `GET_TX_BD`, … parameters
    notes: transitions controlled by combinational next-state logic
  - object: bd_cnt
    storage_kind: registered (2 or 3 bits)
    representation: counter for BD word reads
    notes: width derived from RAM_MEM_WIDTH; incremented on ack_i_s_tx/ack_i_s_rx
  - object: sys_adr, cmd_arg, cmd_set
    storage_kind: registered
    representation: loaded from BD data words during GET_TX_BD/GET_RX_BD
    notes: cmd_set constant per command type
  - object: resend_try_cnt
    storage_kind: registered (3 bits)
    representation: retry counter, max RESEND_MAX_CNT
    notes: incremented only in STOP_SEND
- global_invariants:
  - Only one state active at a time.
  - Output signals reflect the current state and attached flags; no glitching into unintended FSM outputs during transitions.
  - BD read handshake must complete fully (ack_i_s_tx/ack_i_s_rx) before state transition from GET_TX_BD/GET_RX_BD.
  - Retry counter never exceeds RESEND_MAX_CNT; on limit, transfer marked failed via Dat_Int_Status[1].
- open_semantic_questions:
  - Exact priority between TX and RX BD availability in IDLE (spec implies sequential checking; no explicit priority rule).

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Define all project-wide constants required by the FSM.
- timing_semantics: purely compile-time; no dynamic timing.
- touched_objects:
  - READ_CYCLE, BD_EMPTY, bd_cnt width
- coupling_rules:
  - B2, B3, B4 depend on these definitions for widths and threshold comparisons.
- forbidden_drift:
  - Do not introduce extra parameters beyond those explicitly listed in the spec.

- block_id: B2
- responsibilities:
  - Declare all state and datapath storage elements.
- timing_semantics: register declarations only; timing governed by B4.
- touched_objects:
  - all registered objects listed in planning_facts.
- coupling_rules:
  - All other blocks reference these registers by name.
- forbidden_drift:
  - Do not add registers not explicitly required by the spec.

- block_id: B3
- responsibilities:
  - Compute next_state combinatorially from current state, inputs, and relevant flags.
- timing_semantics: purely combinational; must settle within one clock cycle.
- touched_objects:
  - state, free_tx_bd, free_rx_bd, tx_full, bd_cnt, READ_CYCLE, send_done, rec_done, rec_failed, trans_done, trans_failed, cmd_busy, we_ack, transfer_type (implicitly via GET_RX_BD command selection)
- coupling_rules:
  - Provides next_state to B4.
- forbidden_drift:
  - Do not implement output assignments or register updates; only next_state logic.
  - Do not add new transitions beyond the explicit state table.

- block_id: B4
- responsibilities:
  - Perform all synchronous updates on rising edge: state <= next_state; update all counters, flags, address, and command registers according to the state and handshake events.
  - Handle asynchronous reset clearing all registers to IDLE defaults.
- timing_semantics:
  - Asynchronous reset (rst high) clears all registers immediately.
  - Positive clock edge: all registers updated with next_state and state‑dependent update logic.
- touched_objects:
  - state, next_state, bd_cnt, tx_cycle, rx_cycle, send_done, rec_done, rec_failed, trans_done, trans_failed, sys_adr, cmd_arg, cmd_set, resend_try_cnt, internal_transm_complete, transm_complete_q, Dat_Int_Status, CIDAT.
- coupling_rules:
  - Depends on B3 for next_state; updates in GET_TX_BD/GET_RX_BD use ack_i_s_tx/rx; SEND_CMD/STOP_SEND use we_ack; DATA_TRANSFER uses crc_ok, transm_complete edge.
- forbidden_drift:
  - Do not use blocking assignments or combinational logic for register updates; keep sequential.
  - Do not invent new handshake or error conditions outside the spec.

- block_id: B5
- responsibilities:
  - Drive all output ports with values consistent with current state, tx/rx_cycle, and internal registers.
- timing_semantics:
  - Combinational, outputs may change combinatorially with state and internal regs.
- touched_objects:
  - re_s_tx, re_s_rx, we_req, d_write, d_read, start_tx_fifo, start_rx_fifo, ack_transfer, a_cmp_tx, a_cmp_rx, cmd_arg, cmd_set, sys_adr, Dat_Int_Status, CIDAT.
- coupling_rules:
  - re_s_tx/rx active only during BD‑read states; we_req active only in SEND_CMD and STOP_SEND when cmd_busy low; d_write/d_read reflect cycle type; ack_transfer asserted on completed DATA_TRANSFER.
- forbidden_drift:
  - Do not generate outputs that contradict the state‑defined behavior in the spec.

## 4. Decision Ledger
### Chosen Decision
- topic: structural decomposition
- decision: Decompose into param_decl, register decl, combinational NS logic, sequential state+datapath update, and combinational output assignment.
- reason: Mirrors the FSM_COMBO/FSM_SEQ/FSM_OUT pattern described in the spec; keeps responsibilities separated for later code generation.

### Deferred Decision
- items:
  - Exact edge‑detection mechanism for transm_complete (rising edge vs. level) deferred to implementation; skeleton provides a placeholder for a two‑stage synchronizer or qualifier.
  - Relative priority of TX vs. RX BD when both available in IDLE is unspecified and can be resolved as a simple if‑else order without further constraints.

### Structural Risk
- items:
  - The sequential block B4 aggregates many register updates; if too large, it could become monolithic, but the current FSM states are well-defined and manageable.
  - Conditional bd_cnt width based on RAM_MEM_WIDTH requires compile‑time `ifdef` handling, which is captured in B1.

### Behavioral Risk
- items:
  - The spec’s `STOP_RECEIVE_CMD` state description is briefly mentioned (“NOT request access to CMD registers”) but not integrated into the state table; it may require reinterpretation during generation to avoid a phantom state.
  - Unspecified handshake latencies (e.g., we_req to we_ack) could lead to infinite wait if not constrained; the skeleton assumes a handshake eventually completes, but a timeout mechanism is not mandated.