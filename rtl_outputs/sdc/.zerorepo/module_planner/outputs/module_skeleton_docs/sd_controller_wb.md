# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_controller_wb
- file_path: rtl/sd_controller_wb.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_controller_wb
  - repo_skeleton_ref: repo_skeleton_v1::sd_controller_wb
  - spec_ref: sd_controller_wb.md
- planning_note: Organize into declaration, combinational decode, clocked registers/FSM, and output port binding. All WISHBONE-visible outputs are registered per spec. Multi‑cycle BD write handled by a dedicated FSM.

## 1. Module Frame
```verilog
module sd_controller_wb (
    // WISHBONE slave interface
    input  wire             wb_clk_i,
    input  wire             wb_rst_i,
    input  wire [31:0]      wb_dat_i,
    output reg  [31:0]      wb_dat_o,
    input  wire [7:0]       wb_adr_i,
    input  wire [3:0]       wb_sel_i,
    input  wire             wb_we_i,
    input  wire             wb_cyc_i,
    input  wire             wb_stb_i,
    output reg              wb_ack_o,

    // Control outputs to other sub‑modules
    output reg              we_m_tx_bd,
    output reg              we_m_rx_bd,
    output reg              new_cmd,
    output reg              we_ack,
    output reg              int_ack,
    output reg              cmd_int_busy,
    output reg              int_busy,
    output reg              Bd_isr_reset,
    output reg              normal_isr_reset,
    output reg              error_isr_reset,

    // Data master interface
    input  wire             write_req_s,
    input  wire [15:0]      cmd_set_s,
    input  wire [31:0]      cmd_arg_s,

    // Configuration registers exposed as outputs
    output reg  [31:0]      argument_reg,
    output reg  [15:0]      cmd_setting_reg,
    output reg  [7:0]       software_reset_reg,
    output reg  [15:0]      time_out_reg,
    output reg  [15:0]      normal_int_signal_enable_reg,
    output reg  [15:0]      error_int_signal_enable_reg,
    output reg  [7:0]       clock_divider,
    output reg  [7:0]       Bd_isr_enable_reg,

    // Status/response inputs from rest of design
    input  wire [15:0]      status_reg,
    input  wire [31:0]      cmd_resp_1,
    input  wire [16:0]      normal_int_status_reg,
    input  wire [16:0]      error_int_status_reg,
    input  wire [16:0]      Bd_Status_reg,
    input  wire [7:0]       Bd_isr_reg,

    // BD data outputs to buffer descriptor blocks
    output reg  [RAM_MEM_WIDTH-1:0] dat_in_m_tx_bd,
    output reg  [RAM_MEM_WIDTH-1:0] dat_in_m_rx_bd
);

// <block: decl_core>
// <block: comb_decode_and_control>
// <block: seq_all_clocked>
// <block: port_assign>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core
- block_kind: decl
- required: true
- purpose: Declare all internal storage (register file for configuration registers, BD write FSM state, output register signals), internal wires for combinational logic, and constants.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster for:
//   - internal configuration register file (addressable registers per spec)
//   - BD write FSM state register
//   - registered output signals (wb_ack_o, wb_dat_o, we_m_tx_bd, ...)
//   - intermediate wires for combinational decode outputs
```
- must_appear:
  - register storage for all addressable registers: argument, cmd_setting, software_reset, timeout, normal_int_enable, error_int_enable, clock_divider, Bd_isr_enable
  - output registers for ports listed as outputs (argument_reg, etc. may be directly exposed from internal regfile)
  - BD FSM state (e.g., idle, waiting 1st word, waiting 2nd word)
  - internal acknowledge chain signals
- may_appear:
  - helper wires for next-state logic
  - constant definitions for register addresses and widths
- retrieval_focus:
  - state set
  - register file layout
  - FSM state enumeration

### Block
- block_id: B2
- block_label: comb_decode_and_control
- block_kind: comb
- required: true
- purpose: Combinational logic that decodes wb_adr_i for read mux, write enable target, BD write condition, reset‑pulse generation, and next‑state logic for the BD FSM; derives data sources for reads.
- code_shape: combinational netlist‑style block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinational decode block
//   - address decoder mapping wb_adr_i to specific register enable signals
//   - read data mux: select between internal regfile, status_reg, cmd_resp_1, …
//   - write enable decoding: generate write_strobes for each register, BD write triggers
//   - interrupt reset pulse generation: detect writes to normal_int_status_reg, error_int_status_reg, Bd_isr_reg
//   - BD FSM next state logic and control signal generation (int_ack, we_m_{t,r}x_bd, BD data selection)
//   - ﬂag logic for cmd_int_busy, int_busy, new_cmd, we_ack (based on cmd_set_s/cmd_arg_s, write_req_s, wb access)
```
- must_appear:
  - address decoder and read mux that covers all documented register addresses
  - write enable signals for each register
  - conditions for BD write multi‑cycle (depends on RAM_MEM_WIDTH)
  - generation of registered output values for output ports (driven from next‑state logic, e.g., wb_ack_o_next)
- may_appear:
  - helper functions for address comparison
  - pre‑decode of wb_adr_i into one‑hot
- retrieval_focus:
  - address decode
  - data path
  - FSM transition conditions

### Block
- block_id: B3
- block_label: seq_all_clocked
- block_kind: seq
- required: true
- purpose: All clocked processes: update internal register file, BD FSM state, all registered output ports (wb_ack_o, wb_dat_o, we_m_tx_bd, we_m_rx_bd, new_cmd, we_ack, int_ack, cmd_int_busy, int_busy, Bd_isr_reset, normal_isr_reset, error_isr_reset, and BD data ports). Reset sets default values per spec.
- code_shape: sequential always @(posedge wb_clk_i or posedge wb_rst_i) cluster
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: clocked process(es) for:
//   - if wb_rst_i: load reset values (int_ack=1, others 0 or spec defaults)
//   - else on posedge wb_clk_i:
//       * update configuration registers when write_strobe active
//       * BD FSM state transition
//       * output register update (wb_ack_o <= wb_ack_o_next, wb_dat_o <= read_data, …)
//       * special handling for BD write: capture wb_dat_i, manage BD data, handle we_m_xx_bd and int_ack transitions
```
- must_appear:
  - reset behavior exactly as spec: int_ack → 1, other variables → 0, configuration registers → documented default values
  - register write logic for all writable registers
  - BD multi‑cycle write handling (16‑bit RAM width case requires two writes)
  - registered output port updates aligned with combinational next‑state signals
- may_appear:
  - separate always blocks for BD FSM and general register/write logic if cleaner
- retrieval_focus:
  - reset sequencing
  - FSM state update
  - output register timing

### Block
- block_id: B4
- block_label: port_assign
- block_kind: meta
- required: true
- purpose: Direct assignments of internal register/stored values to module output ports. For outputs that are already registered in B3, this block may be trivial; for argument_reg, time_out_reg etc., it connects the internal storage to the output port (no extra logic).
- code_shape: continuous assignment or always_comb block
- depends_on: [B1, B3]
- placeholder:
```verilog
// skeleton only: port assignment block
//   - argument_reg <= internal argument_internal;
//   - dat_in_m_tx_bd <= tx_bd_data_internal;
//   - ...
```
- must_appear:
  - direct connections for all configuration register outputs (argument_reg, cmd_setting_reg, software_reset_reg, time_out_reg, …)
  - BD data output ports from internal BD data registers
- may_appear:
  - no extra logic
- retrieval_focus:
  - output port mapping

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - NORMAL_RW: simple Wishbone read/write to configuration registers
  - BD_WRITE: multi‑cycle write to BD RX or BD TX with int_ack handshake
- state_model:
  - object: bd_fsm_state
    storage_kind: registered
    representation: implementation-open (e.g., IDLE, WAIT_FIRST, WAIT_SECOND)
    notes: controls we_m_xx_bd, int_ack timing, and BD data capture
- global_invariants:
  - wb_ack_o is registered and only asserted in response to wb_cyc_i & wb_stb_i when int_ack is high
  - all outputs driven to the rest of sdc_controller are registered on wb_clk_i rising edge
- open_semantic_questions:
  - exact read data latency (1 cycle from address valid to wb_dat_o update) implied by registered output
  - BD write timing when RAM_MEM_WIDTH is 32 versus 16 – spec gives high‑level process

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide all storage that will be written/read by other blocks
- timing_semantics:
  - values are updated in B3 on rising edge
- touched_objects:
  - configuration register file
  - bd_fsm_state
  - output register bits
- coupling_rules:
  - B2 and B3 reference these declared objects
- forbidden_drift:
  - do not add extra state not implied by the spec

- block_id: B2
- responsibilities:
  - decode address, select read data
  - generate write strobes and BD control conditions
  - produce next‑state signals for all registered outputs and BD FSM
- timing_semantics:
  - purely combinational; must complete within one clock period
- touched_objects:
  - all declared registers (via next-state signals)
  - input ports (wb_adr_i, status_reg, etc.)
- coupling_rules:
  - next‑state signals feed B3
  - no feedback loops to B1
- forbidden_drift:
  - do not create asynchronous paths from inputs to outputs; outputs depend only on registered values from B3 and combinational logic

- block_id: B3
- responsibilities:
  - execute all state updates: register file writes, BD FSM transitions, output port registration
  - enforce reset values as per spec
- timing_semantics:
  - all updates occur at posedge wb_clk_i (or asynchronously reset when wb_rst_i asserted)
  - wb_ack_o is registered, meeting Wishbone B.3 requirements
- touched_objects:
  - all configuration registers, BD FSM state, all output port registers
- coupling_rules:
  - consumes next-state vectors from B2
  - drives internal values that B4 combines to ports
- forbidden_drift:
  - do not invent combinational paths from output registers to external ports except through B4

- block_id: B4
- responsibilities:
  - map internal signals to module ports, handling any trivial width conversions
- timing_semantics:
  - entirely combinatorial; must not introduce additional pipeline stages
- touched_objects:
  - output ports (argument_reg, dat_in_m_tx_bd, …)
- coupling_rules:
  - only simple wiring, no logic
- forbidden_drift:
  - do not add extra mux or gating

## 4. Decision Ledger
### Chosen Decision
- topic: overall structure
- decision: Decompose into declaration, combinational decode, clocked update, and port binding blocks.
- reason: Aligns with typical Wishbone register file designs and isolates BD write FSM handling.

- topic: output registration
- decision: All outputs (wb_ack_o, wb_dat_o, we_m_xx_bd, new_cmd, we_ack, int_ack, etc.) are registered inside B3.
- reason: Required by spec (“All WISHBONE output signals are registered at the rising edge of wb_clk_i.”)

- topic: BD write multi‑cycle
- decision: Implement a dedicated FSM (state explicit in B1, logic in B2, update in B3).
- reason: Necessary because BD writes may require two sequential writes when RAM_MEM_WIDTH is 16.

### Deferred Decision
- items:
  - Exact state encoding and transition conditions for BD FSM (will depend on final RAM_MEM_WIDTH logic)
  - How read path reacts to BD registers: they are write‑only; read may return 0 or undefined – spec unclear; may default to 0.
  - Whether normal_isr_reset / error_isr_reset / Bd_isr_reset are pulsed for one cycle or remain asserted while write is active; spec says “writing any value resets”, implying a pulse.

### Structural Risk
- items:
  - Large combinational decode block (B2) could become complex; might later need splitting into sub‑decode and data mux blocks if synthesis tools struggle.
  - Register file declaration (B1) may need explicit width‑parameterized arrays if many registers share similar coding patterns.

### Behavioral Risk
- items:
  - The exact timing relationship between write_req_s and we_ack is not fully captured; may require clarification during local generation.
  - The module outputs some registers directly (e.g., argument_reg) that are also part of the internal register file; if the spec expects these outputs to be updated immediately on write (same cycle), registered outputs satisfy that if output registers are directly connected to internal storage (the spec’s own statement that outputs are registered means a one‑cycle delay, which may be acceptable).