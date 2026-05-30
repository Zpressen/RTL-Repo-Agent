# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_cmd_serial_host
- file_path: rtl/sd_cmd_serial_host.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_cmd_serial_host
  - repo_skeleton_ref: repo_skeleton_v1::sd_cmd_serial_host
  - spec_ref: sd_cmd_serial_host.md
- planning_note: The module is built around a ten‑state explicit FSM that controls command transmission, response reception, CRC, and handshake. The internal code skeleton mirrors the six functional blocks described in the spec: FSM_COMBO, FSM_SEQ, REQ_SYNC, ACK_SYNC, COMMAND_DECODER, and FSM_OUT, plus an sd_crc_7 instantiation and a declaration region for all registers and parameters.

## 1. Module Frame
```verilog
module sd_cmd_serial_host (
    // port list placeholder (SD_CLK_IN, RST_IN, SETTING_IN, CMD_IN, REQ_IN, ACK_IN, cmd_dat_i, CMD_OUT, ACK_OUT, REQ_OUT, STATUS, cmd_oe_o, cmd_out_o, st_dat_t)
);

// <block: decl_core_objects>
// <block: inst_crc7>
// <block: sync_req>
// <block: sync_ack>
// <block: command_decoder>
// <block: fsm_combo>
// <block: fsm_seq_state_update>
// <block: fsm_out>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare all internal parameters, registers, wires, and submodule interface signals needed by the rest of the module.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster
// localparams: INIT_DELAY, NCR, SEND_SIZE, SIZE, CONTENT_SIZE, Read_Delay, EIGHT_PAD
// registers: state, next_state, Cmd_Cnt, Delay_Cnt, In_Buff, Out_Buff, Response_Size, Delay_Cycler, Write_Read, Write_Only, word_select_counter, CRC_RST, CRC_IN, CRC_Enable, CRC_OUT, CRC_Check_On, Crc_Buffering, CRC_Valid, block_write, block_read, word_select, FSM_ACK, DECODER_ACK, q, Req_internal_in, q1, Ack_internal_in
// wires: CRC_VAL (from sd_crc_7), Vector_Index (derived), Bit_Nr (derived)
```
- must_appear:
  - all registers listed in the planning facts that the spec explicitly describes
  - sd_crc_7 interface wires
  - FSM state constants (INIT, IDLE, …)
- may_appear:
  - additional local combinational indexing helpers
- retrieval_focus:
  - interface
  - state/register description
  - constant definitions

### Block
- block_id: B2
- block_label: inst_crc7
- block_kind: inst
- required: true
- purpose: Instantiate the sd_crc_7 submodule for 7‑bit CRC computation.
- code_shape: instantiation
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: sd_crc_7 instance
// .BITVAL(), .Enable(), .CLK(SD_CLK_IN), .RST(), .CRC(CRC_VAL)
```
- must_appear:
  - exactly one sd_crc_7 instance
- may_appear:
  - local wiring adaptors if needed
- retrieval_focus:
  - submodule interface
  - CRC computation availability

### Block
- block_id: B3
- block_label: sync_req
- block_kind: seq
- required: true
- purpose: Two‑flip‑flop synchronizer for REQ_IN → Req_internal_in.
- code_shape: edge‑triggered update
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: REQ synchronizer
// two‑stage flip‑flop chain clocked by SD_CLK_IN
// reset condition: RST_IN high clears both stages
```
- must_appear:
  - properly named synchronizer register stages (q, Req_internal_in)
- may_appear:
  - (none)
- retrieval_focus:
  - clock‑crossing synchronizer

### Block
- block_id: B4
- block_label: sync_ack
- block_kind: seq
- required: true
- purpose: Two‑flip‑flop synchronizer for ACK_IN → Ack_internal_in.
- code_shape: edge‑triggered update
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: ACK synchronizer
// two‑stage flip‑flop chain clocked by SD_CLK_IN
// reset condition: RST_IN high clears both stages
```
- must_appear:
  - properly named synchronizer register stages (q1, Ack_internal_in)
- may_appear:
  - (none)
- retrieval_focus:
  - clock‑crossing synchronizer

### Block
- block_id: B5
- block_label: command_decoder
- block_kind: seq
- required: true
- purpose: Decode SETTING_IN, load In_Buff and configuration registers (Response_Size, Delay_Cycler, flags, block_read, block_write, word_select), and manage Write_Read/Write_Only/DECODER_ACK.
- code_shape: single‑process sequential block
- depends_on: [B1, B3]
- placeholder:
```verilog
// skeleton only: COMMAND_DECODER
// on posedge SD_CLK_IN or synchronous reset (RST_IN)
//   if reset then clear all decoder registers and DECODER_ACK <= 1
//   else if (Req_internal_in) decode SETTING_IN, load In_Buff from CMD_IN, set Write_Read/Write_Only, set DECODER_ACK <= 0
//   else clear Write_Read/Write_Only, set DECODER_ACK <= 1
```
- must_appear:
  - decoding of all SETTING_IN bit fields per spec
  - In_Buff capture
  - Write_Read / Write_Only logic based on Response_Size > 0
  - DECODER_ACK management
- may_appear:
  - additional derived control bits if required
- retrieval_focus:
  - command setup logic
  - operation type determination

### Block
- block_id: B6
- block_label: fsm_combo
- block_kind: comb
- required: true
- purpose: Combinational next‑state logic for the main FSM.
- code_shape: combinational process
- depends_on: [B1, B3, B4, B5]
- placeholder:
```verilog
// skeleton only: FSM_COMBO
// always_comb
//   next_state = f(state, Cmd_Cnt, Delay_Cnt, Write_Read, Write_Only, Req_internal_in, Ack_internal_in, cmd_dat_i, Response_Size, Delay_Cycler, block_read, block_write)
//   transition logic per spec state table
```
- must_appear:
  - complete transition table covering INIT, IDLE, WRITE_WR, DLY_WR, READ_WR, DLY_READ, ACK_WR, WRITE_WO, DLY_WO, ACK_WO and a safe default
- may_appear:
  - grouping by operation path (write‑with‑read, write‑only) for readability
- retrieval_focus:
  - FSM control flow
  - transition conditions

### Block
- block_id: B7
- block_label: fsm_seq_state_update
- block_kind: seq
- required: true
- purpose: Register the current state of the FSM on each SD_CLK_IN edge.
- code_shape: single‑process sequential block
- depends_on: [B6]
- placeholder:
```verilog
// skeleton only: FSM_SEQ
// always_ff @(posedge SD_CLK_IN)
//   if (RST_IN) state <= INIT;
//   else        state <= next_state;
```
- must_appear:
  - assignment of state from next_state
- may_appear:
  - (none)
- retrieval_focus:
  - state register update

### Block
- block_id: B8
- block_label: fsm_out
- block_kind: seq
- required: true
- purpose: Generate all outputs (CMD_OUT, ACK_OUT, REQ_OUT, STATUS, cmd_oe_o, cmd_out_o, st_dat_t) and update internal counters and CRC control registers according to the current state.
- code_shape: single‑process sequential block with per‑state operations
- depends_on: [B1, B2, B7]
- placeholder:
```verilog
// skeleton only: FSM_OUT
// always_ff @(posedge SD_CLK_IN)
//   if (RST_IN) reset all output registers, counters, CRC controls and status per spec table
//   else
//     case (state)
//       INIT: increment Cmd_Cnt; hold cmd_oe_o, cmd_out_o high.
//       IDLE: deassert cmd_oe_o; reset Cmd_Cnt, Delay_Cnt, CRC controls, clear st_dat_t.
//       WRITE_WR: manage REQ_OUT/ACK_OUT handshake; enable CRC; serially transmit In_Buff bits using Crc_Buffering; update Cmd_Cnt, STATUS[3:0].
//       WRITE_WO: similar to WRITE_WR with write‑only STATUS and st_dat_t handling.
//       DLY_WR: manage REQ_OUT/ACK_OUT for delay; disable CRC; increment Delay_Cnt; hold cmd_oe_o low; update STATUS[3:0].
//       DLY_WO: manage REQ_OUT/ACK_OUT for delay; disable CRC; increment Delay_Cnt; hold cmd_oe_o low; update STATUS.
//       READ_WR: manage REQ_OUT/ACK_OUT; enable CRC; capture cmd_dat_i into Out_Buff per Cmd_Cnt; perform CRC validity check at end of response; update st_dat_t and STATUS; increment Cmd_Cnt.
//       DLY_READ: manage REQ_OUT/ACK_OUT for completion; assign CMD_OUT <= Out_Buff; update STATUS with CRC_Valid and Data Available; increment Delay_Cnt.
//       ACK_WO: assert FSM_ACK; deassert REQ_OUT if needed.
//       ACK_WR: assert FSM_ACK; deassert REQ_OUT.
//       default: safe idle behaviour
//     endcase
```
- must_appear:
  - correct per‑state handling of all outputs and internal registers as described in spec
  - usage of Crc_Buffering and Vector_Index/Bit_Nr for serial transmission
  - CRC enable/reset/input mapping
  - STATUS bit assignments per state
  - handshake sequencing (REQ_OUT/ACK_IN, internal ACK_OUT handling)
- may_appear:
  - helper indexing or bit‑selection combinational expressions (derived inside the block)
- retrieval_focus:
  - output and counter control
  - CRC interface
  - status update

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: explicit_fsm
- semantic_modes:
  - COMMAND_SETUP: new request triggers decoder to latch SETTING_IN and CMD_IN, determine Write_Read/Write_Only
  - TRANSMIT_WITH_RESPONSE: state path WRITE_WR → DLY_WR → READ_WR → DLY_READ → ACK_WR
  - TRANSMIT_WRITE_ONLY: state path WRITE_WO → DLY_WO → ACK_WO
- state_model:
  - object: state
    storage_kind: registered (10‑bit)
    representation: one‑hot or binary (as set by FSM designer)
    notes: next_state is computed combinatorially; state register updated on SD_CLK_IN posedge, reset to INIT
- global_invariants:
  - ACK_OUT is held low (request active) during the entire command cycle; SETTING_IN and CMD_IN must be stable while ACK_OUT is low
  - REQ_OUT pulses are used for handshake within certain states; ACK_IN must be monitored where required
  - Only one operation path (Write_Read xor Write_Only) is active at a time
- open_semantic_questions:
  - Exact reset synchronisation for synchronizer blocks (async assert, sync deassert?) is ambiguous between spec sections; downstream generation must resolve in alignment with the target technology and design rules

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide all shared parameter and register declarations for downstream blocks
- timing_semantics:
  - Not applicable; purely declarative
- touched_objects:
  - All registers, wires, constants
- coupling_rules:
  - All other blocks reference the objects declared here
- forbidden_drift:
  - Do not add registers or signals not required by the spec or the block interactions

- block_id: B2
- responsibilities:
  - Generate CRC_VAL for serial input data using sd_crc_7
- timing_semantics:
  - CRC update occurs on SD_CLK_IN; must be enabled only during applicable states (WRITE_WR, WRITE_WO, READ_WR)
- touched_objects:
  - CRC_IN, CRC_Enable, CRC_RST (drives) ; CRC_VAL (consumer)
- coupling_rules:
  - FSM_OUT controls Enable and RST; CRC_VAL is read by FSM_OUT for validation
- forbidden_drift:
  - Do not use additional CRC instances or alter the 7‑bit width

- block_id: B3
- responsibilities:
  - Synchronize REQ_IN to SD_CLK_IN domain to produce Req_internal_in
- timing_semantics:
  - Two‑stage flip‑flop; output is two SD_CLK_IN cycles delayed
- touched_objects:
  - q, Req_internal_in
- coupling_rules:
  - COMMAND_DECODER and FSM_COMBO consume Req_internal_in
- forbidden_drift:
  - Do not add metastability‑hardened circuits beyond the standard two‑stage synchronizer

- block_id: B4
- responsibilities:
  - Synchronize ACK_IN to SD_CLK_IN domain to produce Ack_internal_in
- timing_semantics:
  - Two‑stage flip‑flop; output is two SD_CLK_IN cycles delayed
- touched_objects:
  - q1, Ack_internal_in
- coupling_rules:
  - FSM_COMBO and FSM_OUT consume Ack_internal_in for handshake completion
- forbidden_drift:
  - Same as B3

- block_id: B5
- responsibilities:
  - Latch command settings and data on a synchronized request, set operation flags, and signal decoding completion (DECODER_ACK)
- timing_semantics:
  - Sequential block; outputs available one cycle after Req_internal_in assertion; flags cleared when Req_internal_in deasserts
- touched_objects:
  - Response_Size, Delay_Cycler, CRC_Check_On, block_write, block_read, word_select, In_Buff, Write_Read, Write_Only, DECODER_ACK
- coupling_rules:
  - FSM_OUT checks Write_Read/Write_Only to start the appropriate state path; may also read block_read/block_write for st_dat_t
  - DECODER_ACK indicates validity to the FSM; spec implies interaction with FSM_ACK in an overall handshake (the spec describes ACK_OUT control; skeleton holds this role in FSM_OUT)
- forbidden_drift:
  - Do not pre‑compute CRC or start transmission; only setup

- block_id: B6
- responsibilities:
  - Compute next_state from current state and all qualifying inputs
- timing_semantics:
  - Purely combinational; must be stable at each SD_CLK_IN posedge
- touched_objects:
  - all state inputs
- coupling_rules:
  - output next_state feeds B7 and is used by B8 for decision-making only indirectly (through state)
- forbidden_drift:
  - Do not embed output assignments or counter updates; only next_state

- block_id: B7
- responsibilities:
  - Register the FSM state
- timing_semantics:
  - Sequential; state updates on posedge SD_CLK_IN
- touched_objects:
  - state
- coupling_rules:
  - B8 reads state for output control
- forbidden_drift:
  - No bypass; always gated by reset priority

- block_id: B8
- responsibilities:
  - Drive all external outputs (CMD_OUT, ACK_OUT, REQ_OUT, STATUS, cmd_oe_o, cmd_out_o, st_dat_t) and update all internal counters and CRC control signals per the current FSM state.
- timing_semantics:
  - Sequential block; outputs and internal updates are registered on SD_CLK_IN.
  - Handshake signals (REQ_OUT, ACK_OUT) must align with spec timing: pulses and wait for Ack_internal_in.
- touched_objects:
  - Cmd_Cnt, Delay_Cnt, Out_Buff, CRC_RST, CRC_Enable, CRC_OUT, Crc_Buffering, CRC_Valid, word_select_counter, STATUS, FSM_ACK, CMD_OUT, REQ_OUT, ACK_OUT, cmd_oe_o, cmd_out_o, st_dat_t
- coupling_rules:
  - Uses sd_crc_7 signals, decoder flags, and synchronized handshake inputs.
  - Does not alter Write_Read, Write_Only, or next_state.
- forbidden_drift:
  - Do not bypass combinational next‑state logic; only read state.
  - Do not create hidden state variables beyond those explicitly listed.

## 4. Decision Ledger
### Chosen Decision
- topic: Top‑level decomposition
- decision: Map the six spec‑defined blocks (FSM_COMBO, FSM_SEQ, REQ_SYNC, ACK_SYNC, COMMAND_DECODER, FSM_OUT) plus a CRC instance and a central declaration block to the structural skeleton.
- reason: This directly captures the designer’s documented intent, keeps per‑block retrieval focused, and matches the module’s functional description.

- topic: Control style
- decision: Use explicit_fsm with a combinational next‑state block and a sequential state register.
- reason: The spec explicitly describes FSM_COMBO as combinational next‑state logic and FSM_SEQ as the state register; the module behaviour is entirely determined by this explicit FSM.

### Deferred Decision
- items:
  - Exact state encoding (one‑hot, binary, or gray) for the 10‑state FSM.
  - Whether the synchronizer flip‑flops use asynchronous or synchronous reset (spec contains conflicting descriptions; see Behavioral Risk).
  - Detailed bit‑order mapping for Vector_Index and Bit_Nr in serial transmission; currently derived from In_Buff and Cmd_Cnt, but exact realisation is left for generation.
  - Boundary between FSM_OUT combinational sub‑calculations and the registered outputs: currently FSM_OUT is a single sequential block; future refinement may split per‑state output logic into helper combinational functions.

### Structural Risk
- items:
  - Block B8 (FSM_OUT) is large and encompasses all output and counter logic for ten states. It may become hard to maintain or verify. If needed, it can be split into per‑state sub‑blocks or a combinational decode block plus a register‑update block, but such partitioning must preserve spec‑mandated per‑state functionality.
  - The COMMAND_DECODER (B5) and FSM_OUT (B8) both interact with DECODER_ACK and FSM_ACK; the spec describes a larger ACK_OUT/REQ_IN handshake that spans both blocks. The skeleton assumes FSM_OUT manages ACK_OUT directly while reading DECODER_ACK; verification must ensure the protocol is correctly implemented without deadlock.

### Behavioral Risk
- items:
  - Reset synchronisation conflict: the spec’s top‑level timing contract states synchronous reset; however the REQ_SYNC and ACK_SYNC sections describe “posedge SD_CLK_IN or posedge RST_IN”, implying asynchronous reset. The generated RTL must resolve this, potentially using asynchronous reset for the synchronizer chains and synchronous reset elsewhere, or adopting a single scheme with synchronised deassertion. This ambiguity affects metastability robustness.
  - CRC validation in READ_WR is described with a particular ordering of CRC_IN sampling relative to Cmd_Cnt; exact cycle alignment of CRC_IN bits and the calculation of CRC_VAL from the sd_crc_7 module may require careful scheduling. The skeleton does not resolve the internal latency of the CRC submodule—deferred to generation with test‑bench verification.
  - The st_dat_t output in WRITE_WO is described as depending on block_read, but the meaning of block_read during a write‑only operation is not fully clarified in the spec; generation should confirm with higher‑level documentation or testbenches.