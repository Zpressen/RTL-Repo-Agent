# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_fifo_rx_filler
- file_path: rtl/sd_fifo_rx_filler.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_fifo_rx_filler
  - repo_skeleton_ref: repo_skeleton_v1::sd_fifo_rx_filler
  - spec_ref: sd_fifo_rx_filler.md
- planning_note: Organize around FIFO interface, Wishbone master control, and offset tracking. Maintain clear separation between combinational output generation and sequential control.

## 1. Module Frame
```verilog
module sd_fifo_rx_filler (
    input  wire          clk,
    input  wire          rst,
    input  wire          en,
    input  wire [31:0]   adr,
    input  wire [SD_BUS_W-1:0] dat_i,
    input  wire          wr,
    input  wire          sd_clk,
    output wire          full,
    output wire          empty,
    output wire [31:0]   m_wb_adr_o,
    output wire          m_wb_we_o,
    output wire [31:0]   m_wb_dat_o,
    output wire          m_wb_cyc_o,
    output wire          m_wb_stb_o,
    output wire [2:0]    m_wb_cti_o,
    output wire [1:0]    m_wb_bte_o,
    input  wire          m_wb_ack_i
);

// <block: decl_main_objects>
// <block: inst_sd_rx_fifo>
// <block: comb_wishbone_outputs>
// <block: seq_control_fsm>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_main_objects
- block_kind: decl
- required: true
- purpose: Declare all registers, wires, parameters, and constants required by the module.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster
//   parameter  MEM_OFFSET = ...             // address increment (defined externally)
//   reg  [8:0]           offset;            // address offset register
//   reg                  wb_free;           // Wishbone bus availability flag
//   reg                  reset_rx_fifo;     // RX FIFO reset control
//   reg                  rd;                // read enable for RX FIFO
//   reg  [FSM_STATE_BITS-1:0] state;        // FSM state register
//   wire [31:0]          fifo_q;            // FIFO output data
//   wire                  fifo_full;         // FIFO full flag
//   wire                  fifo_empty;        // FIFO empty flag
//   wire [1:0]            fifo_mem_empt;     // (unused if not needed)
```
- must_appear:
  - offset register (9‑bit)
  - wb_free, reset_rx_fifo, rd registers (1‑bit each)
  - MEM_OFFSET parameter
  - wire for sd_rx_fifo q output (32‑bit)
  - full/empty connection wires
- may_appear:
  - state register encoding and localparam for state values
- retrieval_focus:
  - interface to submodule and Wishbone signals
  - register set that defines the module’s state

### Block
- block_id: B2
- block_label: inst_sd_rx_fifo
- block_kind: inst
- required: true
- purpose: Instantiate the sd_rx_fifo submodule and connect its ports.
- depends_on: [B1]
- code_shape: single‑instance block
- placeholder:
```verilog
// skeleton only: sd_rx_fifo instance
//  sd_rx_fifo #( .DEPTH(…) ) u_rx_fifo (
//    .d        (dat_i),
//    .wr       (wr),
//    .wclk     (sd_clk),
//    .q        (fifo_q),
//    .rd       (rd),
//    .full     (fifo_full),
//    .empty    (fifo_empty),
//    .mem_empt (fifo_mem_empt),   // optionally tied or left open
//    .rclk     (clk),
//    .rst      (reset_rx_fifo)    // controlled by our register
//  );
```
- must_appear:
  - connection of dat_i, wr, sd_clk, fifo_q, rd, fifo_full, fifo_empty, clk, reset_rx_fifo
- may_appear:
  - tie‑off of mem_empt if unused
- retrieval_focus:
  - complete FIFO‑to‑host data path
  - explicit instance name u_rx_fifo

### Block
- block_id: B3
- block_label: comb_wishbone_outputs
- block_kind: comb
- required: true
- purpose: Generate all Wishbone master outputs combinationally from current state.
- depends_on: [B1, B2]
- code_shape: combinational `assign`/always‑comb group
- placeholder:
```verilog
// skeleton only: combinational Wishbone output generation
//   assign m_wb_adr_o = adr + { {23{1'b0}}, offset };
//   assign m_wb_dat_o = fifo_q;
//   assign m_wb_we_o  = wb_request_active;
//   assign m_wb_cyc_o = wb_request_active;
//   assign m_wb_stb_o = wb_request_active;
//   assign m_wb_cti_o = CONSTANT_CTI;
//   assign m_wb_bte_o = CONSTANT_BTE;
//   assign full       = fifo_full;
//   assign empty      = fifo_empty;
```
- must_appear:
  - m_wb_adr_o = adr + offset
  - passthrough fifo_q to m_wb_dat_o
  - output enables driven by wb_request_active from control
  - full/empty tied to FIFO flags
- may_appear:
  - constant assignments for cti_o, bte_o
- retrieval_focus:
  - combinational Wishbone master signal generation
  - clear separation from sequential state

### Block
- block_id: B4
- block_label: seq_control_fsm
- block_kind: seq
- required: true
- purpose: Implement the main control FSM for FIFO reads, Wishbone handshake, and offset update.
- depends_on: [B1, B3]
- code_shape: single clocked `always` block with asynchronous reset
- placeholder:
```verilog
// skeleton only: sequential control FSM
//   always @(posedge clk or posedge rst) begin
//     if (rst) begin
//       // reset all registers: offset=0, wb_free=1, reset_rx_fifo=1, rd=0, state=IDLE
//     end else if (!en) begin
//       // disabled behaviour: hold fifo reset, stop reads, free bus, zero offset
//     end else begin
//       case (state)
//         IDLE: begin
//           // release fifo reset (reset_rx_fifo <= 0)
//           // if ~empty & wb_free => rd<=1, wb_free<=0, state<=ACTIVE
//         end
//         ACTIVE: begin
//           // wait for m_wb_ack_i == 1
//           // on ack: rd<=0, offset <= offset + MEM_OFFSET, wb_free<=1, state<=IDLE
//         end
//       endcase
//     end
//   end
//
//   // wb_request_active = (state == ACTIVE);
```
- must_appear:
  - asynchronous reset with registers set to known state
  - disabled mode (en=0) forces reset_rx_fifo=1, rd=0, offset=0, wb_free=1, state=IDLE
  - FSM states IDLE and ACTIVE
  - transition IDLE→ACTIVE when ~empty & wb_free
  - ACTIVE state waits for m_wb_ack_i
  - offset update only on ack during ACTIVE
  - generation of wb_request_active signal for B3
- may_appear:
  - additional intermediate state if needed (but two‑state is primary)
- retrieval_focus:
  - entire FSM logic, register updates, and handshake sequencing

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: explicit_fsm
- semantic_modes:
  - DISABLED: (en=0) RX FIFO held in reset, offset zeroed, Wishbone bus idle, no reads.
  - TX: (en=1) actively transfers data from FIFO to Wishbone memory in single‑word bursts.
- state_model:
  - object: state
    storage_kind: registered
    representation: two‑state (IDLE, ACTIVE) – exact bit encoding deferred
  - object: offset
    storage_kind: registered
    representation: 9‑bit counter incremented by MEM_OFFSET on completion
  - object: wb_free
    storage_kind: registered
    role: Wishbone bus ownership flag (1 = free, 0 = busy)
  - object: reset_rx_fifo
    storage_kind: registered
    role: controls reset input of sd_rx_fifo; set high in reset/disabling, cleared when entering normal operation
  - object: rd
    storage_kind: registered
    role: read‑enable to sd_rx_fifo; asserted during a transfer
- global_invariants:
  - m_wb_cyc_o and m_wb_stb_o are never asserted when wb_free is asserted
  - rd is never asserted while reset_rx_fifo is asserted
  - offset only changes on a Wishbone ack during ACTIVE state
- open_semantic_questions:
  - MEM_OFFSET supplied externally; exact value unknown at this planning stage
  - FIFO depth sufficiency and overflow behaviour outside scope of this module
  - usage of mem_empt output (unused in spec)
  - no Wishbone timeout or error handling
  - edge specification (rising/falling) for clk and sd_clk not stated, assume posedge clk for control logic and posedge sd_clk for FIFO write

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide all declared storage and wire objects for downstream blocks
  - define MEM_OFFSET parameter
- timing_semantics: none (declarative)
- touched_objects:
  - offset, wb_free, reset_rx_fifo, rd, state (registers)
  - fifo_q, fifo_full, fifo_empty (wires)
- coupling_rules:
  - all following blocks reference only objects declared here
- forbidden_drift:
  - do not add unsupported persistent registers (e.g., burst counters)

- block_id: B2
- responsibilities:
  - instantiate sd_rx_fifo and connect its interface
  - ensure write‑side is driven by sd_clk, read‑side by clk
- timing_semantics:
  - FIFO write domain: asynchronous to clk, uses sd_clk
  - FIFO read domain: synchronous to clk
- touched_objects:
  - dat_i, wr, sd_clk, fifo_q, rd, fifo_full, fifo_empty, reset_rx_fifo
- coupling_rules:
  - feeds fifo_q to B3, receives rd from B4, drives full/empty to B3 and B4
  - reset controlled by reset_rx_fifo from B4
- forbidden_drift:
  - do not alter internal FIFO behavior (depth, width) beyond what the instance allows
  - do not create additional pipeline stages on FIFO data path

- block_id: B3
- responsibilities:
  - compute and drive all Wishbone master outputs combinationally
  - reflect FIFO full/empty to top‑level ports without delay
- timing_semantics: pure combinational; outputs are functions of current state and inputs
- touched_objects:
  - adr, offset, fifo_q, wb_request_active (from B4)
  - m_wb_adr_o, m_wb_dat_o, m_wb_we_o, m_wb_cyc_o, m_wb_stb_o, m_wb_cti_o, m_wb_bte_o, full, empty
- coupling_rules:
  - receives wb_request_active from B4 to qualify bus outputs
  - must not introduce registers on Wishbone outputs
- forbidden_drift:
  - do not include registered pipeline stages in the Wishbone data path

- block_id: B4
- responsibilities:
  - execute the explicit FSM controlling the transaction flow
  - manage reset, disable, and enable transitions
  - update offset, wb_free, rd, reset_rx_fifo, state according to spec
  - generate wb_request_active signal for B3
- timing_semantics:
  - all updates occur on rising edge of clk; reset is asynchronous (posedge rst)
- touched_objects:
  - offset, wb_free, reset_rx_fifo, rd, state (registers)
  - derived wb_request_active (combinational from state)
  - inputs: en, fifo_empty, m_wb_ack_i
- coupling_rules:
  - wb_request_active decoded from state and used by B3
  - rd asserted during ACTIVE after FIFO is first read
  - reset_rx_fifo cleared upon entering IDLE after reset/disable
  - ensures wb_free deasserted before wishbone signals become active
- forbidden_drift:
  - do not implement pending‑request queues, retry counters, or burst logic not in spec
  - do not add synchronous reset paths or multi‑cycle delays that alter the two‑state handshake

## 4. Decision Ledger
### Chosen Decision
- topic: control architecture
- decision: Use an explicit two‑state FSM (IDLE/ACTIVE) for single‑word transfers from FIFO to Wishbone.
- reason: Matches the stepwise operation in the spec and expected simple handshake; keeps future RTL generation straightforward.

### Deferred Decision
- items:
  - exact bit width and encoding of state register
  - concrete value of MEM_OFFSET (external parameter)
  - tie‑off or usage of sd_rx_fifo’s mem_empt output
  - exact timing of rd assertion relative to FIFO read pipeline (spec leaves open)
  - Wishbone cti_o / bte_o constant values (likely classic single‑cycle)

### Structural Risk
- items:
  - Only one data word transferred per FSM cycle; no burst‑mode support may limit throughput if large transfers needed.
  - The sd_rx_fifo depth is not constrained here; external mismatch could cause overflow if producer outpaces consumer.

### Behavioral Risk
- items:
  - No timeout for m_wb_ack_i; the module stalls indefinitely if the slave is unresponsive (matching spec constraint but a system risk).
  - reset_rx_fifo control: spec says “release FIFO from reset” then later implies active during disabled state; need to verify exact expected behavior during active transfer (current plan assumes low after IDLE entry).