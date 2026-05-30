# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_cmd_master
- file_path: rtl/sd_cmd_master.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_cmd_master
  - repo_skeleton_ref: repo_skeleton_v1::sd_cmd_master
  - spec_ref: sd_cmd_master.md
- planning_note: Organise around FSM with three explicit states, support logic, and output updates. All functional blocks (debounce, synchronisers, command assembly, status processing, watchdog) must be represented as distinct structural regions for retrieval purposes.

## 1. Module Frame
```verilog
module sd_cmd_master (
    // port list placeholder
);

// <block: B1 – main declarations>
// <block: B2 – combinational next-state logic>
// <block: B3 – sequential FSM state register>
// <block: B4 – combinational command/settings assembly>
// <block: B5 – sequential debounce logic>
// <block: B6 – sequential synchronisers for req_in/ack_in>
// <block: B7 – sequential per-state operations (output updates, watchdog, handshake, interrupts)>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: main_declarations
- block_kind: decl
- required: true
- purpose: Declare all internal storage, synchroniser stages, next-state combination signals, and locally used constants.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration space for:
// state register, next_state wire
// Watchdog_Cnt, debounce counter, card_present flag
// req_in_int, ack_in_int, req_q, ack_q
// complete, CRC_check_enable, index_check_enable
// response_size wire/reg, CICMD
// remaining output registers: RESP_1_REG, STATUS_REG, NORMAL_INT_REG, ERR_INT_REG
// combinational intermediate signals for cmd_out and settings computation
```
- must_appear:
  - state register and next_state signal
  - watchdog counter, debounce counter, card_present
  - synchroniser stages for req_in and ack_in
  - complete flag, check enable flags
  - response_size indicator
  - output register objects for settings, cmd_out, RESP_1_REG, STATUS_REG, interrupt registers
- may_appear:
  - local defines for small_rsp/big_rsp values
  - staging wires for combinational results
- retrieval_focus:
  - state enumeration and width
  - all synchronous objects required by spec

### Block
- block_id: B2
- block_label: comb_next_state
- block_kind: comb
- required: true
- purpose: Pure combinational logic to compute next state of the FSM based on current state, New_CMD, ack_in_int, and complete.
- code_shape: combinational block computing next_state
- depends_on: [B1]
- placeholder:
```verilog
always @(*) begin
    // skeleton only: next state calculation
    // case (state)
    //   IDLE: next_state = New_CMD ? SETUP : IDLE;
    //   SETUP: next_state = ack_in_int ? EXECUTE : SETUP;
    //   EXECUTE: next_state = complete ? IDLE : EXECUTE;
    //   default: next_state = IDLE;
end
```
- must_appear:
  - default return to IDLE for unlisted conditions
  - full sensitivity to state, New_CMD, ack_in_int, complete
- may_appear:
  - nothing else
- retrieval_focus:
  - transition conditions exactly as in spec

### Block
- block_id: B3
- block_label: seq_state_register
- block_kind: seq
- required: true
- purpose: Register the current state on posedge CLK_PAD_IO or asynchronous reset, resetting to IDLE.
- code_shape: sequential block with asynchronous reset
- depends_on: [B1, B2]
- placeholder:
```verilog
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        // state <= IDLE;
    end else begin
        // state <= next_state;
    end
end
```
- must_appear:
  - IDLE reset value
- may_appear:
  - encoded state representation
- retrieval_focus:
  - state register update exactly as per timing contract

### Block
- block_id: B4
- block_label: comb_cmd_settings_assembly
- block_kind: comb
- required: true
- purpose: Combinational logic used during SETUP to generate next_cmd_out and next_settings values from CMD_SET_REG, ARG_REG, data_read/data_write, and response_size.
- code_shape: combinational block computing next_cmd_out, next_settings, and response_size
- depends_on: [B1]
- placeholder:
```verilog
always @(*) begin
    // skeleton only: compute response_size from CMD_SET_REG[1:0]
    // compute next_cmd_out = {2'b01, CMD_SET_REG[13:8], ARG_REG[31:0]}
    // compute next_settings = {WORD_SELECT, data_read, data_write, delay_field, CRCE, response_size}
    // the above are raw next values, not assigned to ports directly
end
```
- must_appear:
  - response_size determination from RTS field
  - assembly of 40-bit cmd_out
  - assembly of 16-bit settings according to bit mapping
- may_appear:
  - combinational mux for response_size constants
- retrieval_focus:
  - exact bit-level mapping as in spec

### Block
- block_id: B5
- block_label: seq_debounce_logic
- block_kind: seq
- required: true
- purpose: Sequential debounce of card_detect signal; updates debounce counter and card_present flag on posedge CLK_PAD_IO or reset.
- code_shape: sequential block with asynchronous reset and counter logic
- depends_on: [B1]
- placeholder:
```verilog
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        // debounce <= 0; card_present <= 0;
    end else begin
        // if (!card_detect) begin
        //   debounce <= (debounce == 4'b1111) ? debounce : debounce + 1;
        // end else begin
        //   debounce <= 0;
        // end
        // card_present <= (debounce == 4'b1111);
    end
end
```
- must_appear:
  - debounce counter reaching 15 to set card_present
  - clearing counter when card_detect high
- may_appear:
  - nothing else
- retrieval_focus:
  - debounce timing and flag update

### Block
- block_id: B6
- block_label: seq_synchronisers
- block_kind: seq
- required: true
- purpose: Two-stage synchronisation of asynchronous req_in and ack_in inputs to generate req_in_int and ack_in_int.
- code_shape: sequential block with asynchronous reset, two flip-flop stages per signal
- depends_on: [B1]
- placeholder:
```verilog
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        // req_q <= 0; req_in_int <= 0;
        // ack_q <= 0; ack_in_int <= 0;
    end else begin
        // req_q <= req_in; req_in_int <= req_q;
        // ack_q <= ack_in; ack_in_int <= ack_q;
    end
end
```
- must_appear:
  - two-stage shift for each input
- may_appear:
  - nothing else
- retrieval_focus:
  - metastability mitigation

### Block
- block_id: B7
- block_label: seq_fsm_state_operations
- block_kind: seq
- required: true
- purpose: Main sequential block that updates per-state outputs, control signals, watchdog, status, response, and interrupts on posedge CLK_PAD_IO or reset.
- code_shape: sequential block with asynchronous reset, state-machine style case on state
- depends_on: [B1, B4, B5, B6]
- placeholder:
```verilog
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        // reset all module-maintained registers and outputs:
        //   cmd_out_reg <= 0; settings_reg <= 0; RESP_1_REG <= 0;
        //   STATUS_REG <= 0; NORMAL_INT_REG <= 0; ERR_INT_REG <= 0;
        //   complete <= 0; CRC_check_enable <= 0; index_check_enable <= 0;
        //   go_idle_o <= 0; req_out <= 0; ack_out <= 0; CICMD <= 0;
        //   Watchdog_Cnt <= 0;
    end else begin
        // default assignments for signals that are not state-modulated
        // NORMAL_INT_REG[1] <= card_present;   // card insertion indicator
        // NORMAL_INT_REG[2] <= ~card_present;  // card removal indicator

        // case (state)
        //   IDLE: begin
        //     go_idle_o <= 0; req_out <= 0; ack_out <= 0; CICMD <= 0;
        //     // if req_in_int, update status from serial_status, set ack_out
        //   end
        //   SETUP: begin
        //     // latch output registers with next values from comb assembly
        //     cmd_out_reg <= next_cmd_out;
        //     settings_reg <= next_settings;
        //     // clear interrupt registers, set check enables, reset watchdog
        //     NORMAL_INT_REG <= 0; ERR_INT_REG <= 0;
        //     index_check_enable <= CICE; CRC_check_enable <= CRCE;
        //     Watchdog_Cnt <= 0; CICMD <= 1;
        //   end
        //   EXECUTE: begin
        //     // increment watchdog, check timeout etc.
        //     // handshake: if ack_in_int -> req_out <= 1
        //     // else if req_in_int -> update status, ack_out <= 1
        //     // if dat_ava, complete logic, CRC/index checks, capture RESP_1_REG
        //   end
        // endcase
    end
end
```
- must_appear:
  - registered outputs for cmd_out and settings loaded only in SETUP
  - watchdog counter increment and timeout in EXECUTE
  - complete flag assertion logic
  - interrupt/status updates according to spec tables
  - response capture in EXECUTE
  - card_present reflected in NORMAL_INT_REG bit assignments (bits 1,2)
- may_appear:
  - internal status register bit 0 (CICMD) management
- retrieval_focus:
  - exact state-dependent operations as detailed in spec
  - interrupt and error condition handling

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: explicit_fsm
- semantic_modes:
  - IDLE: awaiting new command, monitoring serial status
  - SETUP: assembling command and settings, clearing interrupt registers, enabling checks, resetting watchdog
  - EXECUTE: transmitting command, managing handshake, processing responses, watchdog timeout enforcement
- state_model:
  - object: state
    storage_kind: registered
    representation: encoded 3‑bit one‑hot or binary
    notes: driven by next‑state combinational logic, reset to IDLE
- global_invariants:
  - cmd_out and settings outputs stable once set in SETUP and held through EXECUTE until next command
  - interrupt registers reflect the last known error/completion until explicitly cleared
- open_semantic_questions:
  - exact pulse width of req_out/ack_out handshake is not fully defined; may be edge‑driven or held
  - complete signal precise timing (level vs pulse) not specified

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide all shared declared objects needed by other blocks
- timing_semantics:
  - purely declarative, no active timing constraints
- touched_objects:
  - all registers, wires, combinational intermediates declared in B1
- coupling_rules:
  - every downstream block must reference objects declared here
- forbidden_drift:
  - do not pre‑assign functional role to any declared object beyond its spec‑defined purpose

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - purely combinational next‑state calculation
- timing_semantics:
  - zero‑delay combinational path from state and inputs to next_state
- touched_objects:
  - next_state, state, New_CMD, ack_in_int, complete
- coupling_rules:
  - drives next_state used by B3; must respond to combinational changes instantly
- forbidden_drift:
  - do not embed registered elements or side‑effects

### Block Behavioral Overlay
- block_id: B3
- responsibilities:
  - state register update
- timing_semantics:
  - synchronous positive‑edge update, asynchronous active‑high reset
- touched_objects:
  - state
- coupling_rules:
  - only source of state register update; consumes next_state from B2
- forbidden_drift:
  - do not modify state to anything other than IDLE on reset

### Block Behavioral Overlay
- block_id: B4
- responsibilities:
  - compute next_cmd_out, next_settings, response_size combinationally
- timing_semantics:
  - combinational output valid after inputs (CMD_SET_REG, ARG_REG, data_read, data_write) settle
- touched_objects:
  - next_cmd_out, next_settings, response_size, CMD_SET_REG, ARG_REG, data_read, data_write
- coupling_rules:
  - results sampled only during SETUP in B7
- forbidden_drift:
  - do not infer registered storage inside this block

### Block Behavioral Overlay
- block_id: B5
- responsibilities:
  - implement card_detect debounce
- timing_semantics:
  - updates debounce counter and card_present on each clock edge
- touched_objects:
  - debounce, card_present, card_detect
- coupling_rules:
  - card_present is used by B7 for NORMAL_INT_REG assignment; block operates independently of FSM state
- forbidden_drift:
  - do not interfere with FSM or handshake logic

### Block Behavioral Overlay
- block_id: B6
- responsibilities:
  - synchronise req_in and ack_in to internal clock domain
- timing_semantics:
  - two‑stage flip‑flop synchronisation; updates on each posedge
- touched_objects:
  - req_q, ack_q, req_in_int, ack_in_int
- coupling_rules:
  - req_in_int and ack_in_int used by B2 and B7; block independent of FSM state
- forbidden_drift:
  - do not add extra pipelining beyond two stages

### Block Behavioral Overlay
- block_id: B7
- responsibilities:
  - execute all state‑dependent outputs, control signal updates, watchdog, interrupt and status management, response capture
- timing_semantics:
  - sequential updates on posedge; defaults assigned then overwritten per state
- touched_objects:
  - cmd_out_reg, settings_reg, RESP_1_REG, STATUS_REG, NORMAL_INT_REG, ERR_INT_REG, complete, CRC_check_enable, index_check_enable, go_idle_o, req_out, ack_out, CICMD, Watchdog_Cnt
- coupling_rules:
  - consumes card_present (from B5), next_cmd_out/next_settings (from B4), req_in_int/ack_in_int (from B6), state (from B3)
  - writes all externally visible outputs
- forbidden_drift:
  - do not duplicate debounce, synchroniser, or next‑state logic
  - do not invent new states or output ports

## 4. Decision Ledger
### Chosen Decision
- topic: overall skeleton decomposition
- decision: Separate combinational next‑state, combinational output assembly, and sequential blocks for state register, debounce, synchronisers, and main per‑state operations. This mirrors the distinct functional blocks in the spec and simplifies later retrieval and change.
- reason: Spec explicitly describes these as separate functions; separation minimises block coupling and isolates timing concerns.

### Deferred Decision
- items:
  - exact encoding of `response_size` constants (small_rsp, big_rsp) and their bit patterns – left to code generation
  - precise handshake cycle behaviour (req_out/ack_out/req_in/ack_in) is not fully specified; block B7 must remain flexible to implement edge‑based or level‑based protocol as clarified later
  - encoding of `complete` (registered pulse vs level) – deferred until timing closure

### Structural Risk
- items:
  - Block B7 may become monolithic if state operations grow; future refactoring into per‑state sub‑blocks may be needed, but currently not justified.
  - Combinational block B4 may need to be combined with B7 if registered outputs require combinational path synchronous to latch, but current split preserves clarity.

### Behavioral Risk
- items:
  - Asynchronous reset timing and removal synchronisation not specified; actual implementation may need reset synchroniser.
  - Debounce threshold of 15 clocks is hard‑coded; any requirement to change it would touch block B5.