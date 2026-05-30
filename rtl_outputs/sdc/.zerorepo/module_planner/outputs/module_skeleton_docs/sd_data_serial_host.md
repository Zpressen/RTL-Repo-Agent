# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_data_serial_host
- file_path: rtl/sd_data_serial_host.v
- source_refs:
  - module_contract_ref: extracted_facts::sd_data_serial_host.interface_contract
  - repo_skeleton_ref: repo_skeleton_v1::sd_data_serial_host
  - spec_ref: sd_data_serial_host.md
- planning_note: Decompose the module into a declaration group, a CRC sub‑module instantiation block, and the five internal processing blocks described in the spec (ACK_SYNC, START_SYNC, FSM_COMBO, FSM_SEQ, FSM_OUT). Each block carries a clear purpose and is placed sequentially after declarations.

## 1. Module Frame
```verilog
module sd_data_serial_host (
    // port list: sd_clk, rst, data_in, start_dat, ack_transfer, DAR_dat_i,
    //           rd, data_out, we, DAT_oe_o, DAT_dat_o, busy_n, transm_complete, crc_ok
);

// <block: B1_decl_core_objects>
// <block: B2_inst_CRC16_gen>
// <block: B3_seq_ACK_SYNC>
// <block: B4_seq_START_SYNC>
// <block: B5_comb_FSM_COMBO>
// <block: B6_seq_FSM_SEQ>
// <block: B7_seq_FSM_OUT>

endmodule
```

## 2. Structural Skeleton

### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare all registers, wires, and parameters used by the module, including state, counters, buffer registers, CRC control signals, synchronized versions of inputs, and intermediate status registers.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster for all internal objects
// registers: state, next_state, transf_cnt, crc_c, out_buff_ptr, in_buff_ptr,
//   data_send_index, write_buf_0, write_buf_1, sd_data_out, last_din,
//   crc_in, crc_en, crc_rst, crc_status, busy_int, ack_transfer_int, ack_q,
//   q_start_bit, crc_s, temp_in
// wires: crc_out (array of 16‑bit vectors), combinational next_state signals
// parameter re‑use: SD_BUS_W, BIT_BLOCK, CRC_OFF, BIT_BLOCK_REC, BIT_CRC_CYCLE,
//   LITLE_ENDIAN, BIG_ENDIAN, SD_BUS_WIDTH_1, SD_BUS_WIDTH_4 from sd_defines.v
```
- must_appear:
  - state and next_state FSM registers
  - transf_cnt, crc_c
  - write_buf_0, write_buf_1, sd_data_out, out_buff_ptr, last_din, data_send_index
  - crc_in, crc_en, crc_rst, crc_status, crc_s
  - busy_int, ack_transfer_int, ack_q, q_start_bit
  - output registers for DAT_oe_o, DAT_dat_o, rd, we, data_out, transm_complete, crc_ok, busy_n
- may_appear:
  - temporary combinational helper wires if needed for next_state computation
- retrieval_focus:
  - interface and all registered objects used across multiple blocks

### Block
- block_id: B2
- block_label: inst_CRC16_gen
- block_kind: inst
- required: true
- purpose: Generate one sd_crc_16 instance per data line (SD_BUS_W instances), connecting the module’s crc_in, crc_en, crc_rst ports and collecting crc_out.
- code_shape: generate loop instantiation
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: generate block instantiating sd_crc_16 for each i in 0..SD_BUS_W-1
// connections:
//   .CLK(sd_clk), .RST(crc_rst), .BITVAL(crc_in[i]), .Enable(crc_en),
//   .CRC(crc_out[i*16 +: 16])
```
- must_appear:
  - sd_crc_16 instance per data line
  - crc_out vector
- may_appear:
  - local wire indexing helpers
- retrieval_focus:
  - sub‑module instantiation and CRC pipeline

### Block
- block_id: B3
- block_label: seq_ACK_SYNC
- block_kind: seq
- required: true
- purpose: Two‑stage synchronizer for the ack_transfer input, producing ack_transfer_int.
- code_shape: sequential always block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: two‑flip‑flop synchronizer on sd_clk rising edge
// first stage: ack_q <= ack_transfer
// second stage: ack_transfer_int <= ack_q
// reset: both cleared asynchronously
```
- must_appear:
  - ack_q, ack_transfer_int
- may_appear:
  - none
- retrieval_focus:
  - synchronization of external handshake signal

### Block
- block_id: B4
- block_label: seq_START_SYNC
- block_kind: seq
- required: true
- purpose: Synchronize start‑bit detection for read operations by sampling DAT_dat_i[0] only when state == READ_WAIT.
- code_shape: sequential always block
- depends_on: [B1, B5, B6]
- placeholder:
```verilog
// skeleton only: on rising sd_clk, if state == READ_WAIT and DAT_dat_i[0] == 0,
//   q_start_bit <= 0; else q_start_bit <= 1.
// reset: q_start_bit <= 1
```
- must_appear:
  - q_start_bit register
- may_appear:
  - none
- retrieval_focus:
  - read start‑bit qualification

### Block
- block_id: B5
- block_label: comb_FSM_COMBO
- block_kind: comb
- required: true
- purpose: Combinational logic that computes next_state from current state and inputs (start_dat, transf_cnt, crc_status, busy_int, DAT_dat_i, etc.) according to the state transition table.
- code_shape: combinational always block or continuous assignment block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational next_state calculation
// uses case(current_state):
//   IDLE:    next_state = (start_dat==WRITE_CMD)? WRITE_DAT : (start_dat==READ_CMD)? READ_WAIT : IDLE;
//   WRITE_DAT: next_state = (transf_cnt==SD_BUS_W)? WRITE_CRC : WRITE_DAT;
//   WRITE_CRC:next_state = (crc_status==OK)? WRITE_BUSY : WRITE_CRC;
//   WRITE_BUSY:next_state = (busy_int==0)? IDLE : WRITE_BUSY;
//   READ_WAIT: next_state = (DAT_dat_i[0]==0)? READ_DAT : (DAT_dat_i[0]==1)? IDLE : READ_WAIT;
//   READ_DAT: next_state = (transf_cnt==SD_BUS_W)? IDLE : READ_DAT;
//   default: next_state = IDLE;
```
- must_appear:
  - full transition logic covering all 6 states + default
- may_appear:
  - local combinational control flags if required for readability
- retrieval_focus:
  - state machine next‑state logic

### Block
- block_id: B6
- block_label: seq_FSM_SEQ
- block_kind: seq
- required: true
- purpose: Sequential update of state register (state <= next_state) on each rising edge of sd_clk, with asynchronous reset to IDLE.
- code_shape: sequential always block
- depends_on: [B1, B5]
- placeholder:
```verilog
// skeleton only: state register update
// always @(posedge sd_clk or posedge rst) begin
//   if (rst) state <= IDLE;
//   else     state <= next_state;
// end
```
- must_appear:
  - state register update
- may_appear:
  - none
- retrieval_focus:
  - state register

### Block
- block_id: B7
- block_label: seq_FSM_OUT
- block_kind: seq
- required: true
- purpose: Control all output signals, data buffers, counters, and CRC control lines according to the current state. Implements the per‑state behaviour described in the spec: buffer loading, data output multiplexing, start/stop bit insertion, CRC management, counter increments, transfer completion signalling, busy polling, and CRC verification.
- code_shape: sequential always block (possibly one large always block, or a few sub‑blocks) sensitive to posedge sd_clk (and maybe posedge rst for reset)
- depends_on: [B1, B2, B3, B4, B6]
- placeholder:
```verilog
// skeleton only: main output and control logic
// Reset block sets all registers listed in spec reset table.
// Non‑reset behaviour driven by state:
//   IDLE:        reset CRC, clear counters
//   WRITE_DAT:   load write buffers from data_in, manage sd_data_out selection,
//                output start bit, then data bits via last_din, increment transf_cnt,
//                toggle buffer pointers, control crc_en/crc_rst
//   WRITE_CRC:   capture CRC response token (crc_s) over 7 cycles via crc_c,
//                advance to WRITE_BUSY when done
//   WRITE_BUSY:  assert transm_complete, poll DAT_dat_i[0] for busy_int=0,
//                set crc_ok based on crc_s
//   READ_WAIT:   enable CRC, disable output driver
//   READ_DAT:    latch DAR_dat_i into data_out, we, crc_in; increment transf_cnt;
//                after 512B data, receive CRC bits, compare with crc_out,
//                set crc_ok and transm_complete; deassert busy_n
// All output registers (DAT_oe_o, DAT_dat_o, rd, we, data_out, transm_complete,
//   crc_ok, busy_n) are managed here.
```
- must_appear:
  - write_buf_0, write_buf_1 loading logic
  - sd_data_out, out_buff_ptr, data_send_index management
  - last_din delay path to DAT_dat_o
  - transf_cnt update
  - crc_control: crc_en, crc_rst, crc_in gating
  - CRC response capture (crc_c, crc_s, crc_status)
  - busy polling (busy_int)
  - read data capture and storage (data_out, we)
  - CRC comparison logic (crc_ok)
  - transm_complete assertion
  - reset condition for all listed signals as in spec reset table
- may_appear:
  - auxiliary combinational logic for multiplexing, but if complex may be split in the future
- retrieval_focus:
  - all datapath and output controls; this block is the behavioural heart of the module

## 3. Behavioral Overlay

### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - WRITE_MODE: triggered by start_dat == WRITE_CMD; follows IDLE → WRITE_DAT → WRITE_CRC → WRITE_BUSY → IDLE
  - READ_MODE: triggered by start_dat == READ_CMD; follows IDLE → READ_WAIT → READ_DAT → IDLE
- state_model:
  - object: state
    storage_kind: registered (6‑bit)
    representation: enumerated values IDLE, WRITE_DAT, WRITE_CRC, WRITE_BUSY, READ_WAIT, READ_DAT
    notes: updated on sd_clk rising edge from next_state; reset asynchronously to IDLE
- global_invariants:
  - CRC is computed per data bit/group and appended/verified according to SD protocol
  - DAT_dat_o output is one cycle delayed relative to CRC input to match card timing
  - Data output enable (DAT_oe_o) is only asserted during write transfers and after start bit
  - Busy sampling and start‑bit detection use synchronised low‑speed path where needed
  - transm_complete is held until acknowledged by ack_transfer
- open_semantic_questions:
  - Reset type is not explicitly stated (described as independent of clock, so likely asynchronous); implementation should follow that interpretation.
  - Exact timing of busy_n deassertion relative to transm_complete is unspecified; may be refined during debugging.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide all declared objects for use in subsequent blocks
- timing_semantics:
  - purely structural; no process logic
- touched_objects:
  - all internal registers and wires listed in the spec
- coupling_rules:
  - every other block references these declarations
- forbidden_drift:
  - do not add undocumented registers; do not change widths from spec

- block_id: B2
- responsibilities:
  - Instantiate per‑data‑line CRC‑16 generators; expose crc_out vector
- timing_semantics:
  - Each `sd_crc_16` instance updates its CRC on each posedge sd_clk when Enable is high; combinatorial path from BITVAL/crc_in to CRC
- touched_objects:
  - crc_in, crc_en, crc_rst, crc_out (produced)
- coupling_rules:
  - crc_in bits must be stable at clock edge when crc_en is high; crc_out is used in FSM_OUT for CRC response check
- forbidden_drift:
  - do not change CRC instance count; do not use a different CRC width

- block_id: B3
- responsibilities:
  - Synchronize external ack_transfer into ack_transfer_int (two‑stage flip‑flop)
- timing_semantics:
  - On each rising sd_clk, ack_q <= ack_transfer, then ack_transfer_int <= ack_q. Reset clears both.
- touched_objects:
  - ack_q, ack_transfer_int
- coupling_rules:
  - FSM_OUT uses ack_transfer_int to deassert transm_complete after handshake
- forbidden_drift:
  - do not change synchronizer depth; do not poll ack_transfer directly

- block_id: B4
- responsibilities:
  - Provide q_start_bit indicator based on DAT_dat_i[0] and READ_WAIT state
- timing_semantics:
  - Combinational condition sampled on sd_clk edge; q_start_bit updated at same edge. Reset sets q_start_bit to 1.
- touched_objects:
  - q_start_bit
- coupling_rules:
  - FSM_COMBO may use q_start_bit to decide state transition? Actually spec uses DAT_dat_i[0] directly, but q_start_bit is a registered start‑bit indicator; used in FSM_OUT for timing of read data capture. Ensure FSM_OUT reads q_start_bit.
- forbidden_drift:
  - do not sample DAT_dat_i outside of READ_WAIT; do not mask start bit with other states

- block_id: B5
- responsibilities:
  - Implement combinational next_state logic for the FSM (state transition table)
- timing_semantics:
  - Completely combinatorial, producing next_state based on current state and inputs; no clock edge here.
- touched_objects:
  - next_state (combinational output)
- coupling_rules:
  - B6 registers next_state into state
- forbidden_drift:
  - do not insert sequential logic here; do not invent additional states or transitions not in the spec

- block_id: B6
- responsibilities:
  - Register next_state into state
- timing_semantics:
  - On each posedge sd_clk, state <= next_state; asynchronous reset to IDLE
- touched_objects:
  - state register
- coupling_rules:
  - B7 (FSM_OUT) and B5 (FSM_COMBO) depend on state
- forbidden_drift:
  - do not add extra clock‑enable or glitch filtering here

- block_id: B7
- responsibilities:
  - Drive all output and control signals according to state; manage data buffer pointers, serialisation, CRC control, counters, and completion handshake.
- timing_semantics:
  - All registers updated on posedge sd_clk (some may be reset asynchronously). Outputs like DAT_dat_o are driven one cycle after data enters CRC pipeline (via last_din). Write buffers are filled from data_in under command of local logic. CRC response token captured over multiple cycles.
- touched_objects:
  - write_buf_0, write_buf_1, sd_data_out, out_buff_ptr, data_send_index,
    last_din, DAT_dat_o, DAT_oe_o,
    crc_en, crc_rst, crc_in, crc_status, crc_c, crc_s,
    transf_cnt, busy_int, transm_complete, crc_ok, busy_n,
    rd, we, data_out
- coupling_rules:
  - Reads state from B6; reads crc_out from B2; reads ack_transfer_int from B3; may use q_start_bit from B4. Drives output ports directly.
- forbidden_drift:
  - do not implement state transition logic (belongs to B5)
  - do not duplicate synchronizers (ACK_SYNC and START_SYNC are separate)
  - do not deviate from the per‑state behaviour detailed in the spec’s narrative and reset table
  - do not infer additional counters or phases beyond those listed

## 4. Decision Ledger

### Chosen Decision
- topic: Module decomposition
- decision: Split into the six‑block scheme listed in the spec (CRC_16_gen, ACK_SYNC, FSM_COMBO, START_SYNC, FSM_SEQ, FSM_OUT) plus a separate declaration block.
- reason: Matches the spec’s explicit description and provides clear retrieval boundaries for later code generation and debugging.

### Deferred Decision
- items:
  - Whether to combine FSM_COMBO and FSM_OUT into a single always block for efficiency, or keep them separate as the spec logically implies. The current skeleton keeps them separate to honor the spec’s block count, but final implementation may merge if synthesis‑friendly.
  - Exact reset polarity and type (asynchronous vs synchronous) – spec suggests asynchronous, but repo constraints may impose synchronous. Currently deferred as asynchronous per spec.

### Structural Risk
- items:
  - FSM_OUT block is very large and may become a monolithic always block that is hard to debug. Future versions may need to split it into sub‑blocks per state, but the spec treats it as one block.
  - Some signals (e.g., crc_en, crc_rst) are described as registers but they may be purely combinational in certain states; the skeleton reflects them as registers for safety, but the final form may be hybrid.

### Behavioral Risk
- items:
  - CRC comparison in READ_DAT for multi‑line (SD_BUS_WIDTH_4) is explicit in the spec but exact timing of crc_ok assertion and CRC receive window remains underspecified; placeholder must guard against off‑by‑one errors.
  - The spec mentions a CRC check bypass in simulation mode; its mechanism is not defined. This bypass must not be implemented unless explicitly confirmed by surrounding code.
  - The start_dat encoding “11” for Stop is listed in port description but no Stop state is described in the FSM; this must be resolved during local generation or debug. Currently the skeleton ignores Stop (treats unknown encoding as IDLE), but risk remains.