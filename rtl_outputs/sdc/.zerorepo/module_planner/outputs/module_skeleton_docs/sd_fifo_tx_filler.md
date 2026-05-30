# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_fifo_tx_filler
- file_path: rtl/sd_fifo_tx_filler.v
- source_refs:
  - module_contract_ref: interface_contract_v1::sd_fifo_tx_filler
  - repo_skeleton_ref: repo_skeleton_v1::sd_fifo_tx_filler
  - spec_ref: sd_fifo_tx_filler.md
- planning_note: Organize module around Wishbone master read engine, address/offset control, and TX FIFO instance. The core sequential logic uses flags (ackd, delay, first) to manage bus transactions and coordinate FIFO writes.

## 1. Module Frame
```verilog
module sd_fifo_tx_filler (
    // port list placeholder
);

// <block: decl_registers_and_wires>
// <block: inst_sd_tx_fifo>
// <block: comb_address_and_static_wb>
// <block: seq_wishbone_control>
// <block: comb_output_assign>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_registers_and_wires
- block_kind: decl
- required: true
- purpose: Declare all registers (offset, we, din, wr_tx, reset_tx_fifo, first, ackd, delay) and any necessary combinational wires or intermediate signals required by other blocks.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: register/wire declarations
// may include: offset, we, din, wr_tx, reset_tx_fifo, first, ackd, delay
```
- must_appear:
  - offset (9 bits)
  - we (9 bits)
  - din (32 bits)
  - wr_tx
  - reset_tx_fifo
  - first
  - ackd
  - delay
  - any internal wires needed for Wishbone control glue
- may_appear:
  - temporary signals for flow control
- retrieval_focus:
  - state/register description
  - internal control interface

### Block
- block_id: B2
- block_label: inst_sd_tx_fifo
- block_kind: inst
- required: true
- purpose: Instantiate the dual-clock domain sd_tx_fifo.
- code_shape: single module instance
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: sd_tx_fifo instance
// ports: d(din), wr(wr_tx), wclk(clk), q(dat_o), rd(rd), full(fe), empty(empty), mem_empt(...), rclk(sd_clk), rst(reset_tx_fifo or combined reset)
```
- must_appear:
  - connection of din, wr_tx, dat_o, fe, empty, rd, clk, sd_clk, reset control
- may_appear:
  - buffered full/empty flags if needed
- retrieval_focus:
  - submodule integration
  - dual‑clock domain interface

### Block
- block_id: B3
- block_label: comb_address_and_static_wb
- block_kind: comb
- required: true
- purpose: Generate Wishbone master address and static control signals.
- code_shape: combinational assignments
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: m_wb_adr_o = adr + offset;
// m_wb_we_o = 1'b0; (only reads)
// m_wb_cti_o = 3'b000; // classic cycle
// m_wb_bte_o = 2'b00;  // linear burst
```
- must_appear:
  - continuous address addition (adr + offset)
  - fixed Write Enable = 0
  - fixed Cycle Type Identifier and Burst Type Extension to match spec (only master read)
- may_appear:
  - nothing extra
- retrieval_focus:
  - address path
  - Wishbone output constants

### Block
- block_id: B4
- block_label: seq_wishbone_control
- block_kind: seq
- required: true
- purpose: Implement the sequential Wishbone read engine, including start conditions, acknowledge handling, flag updates, address offset increment, and disable/reset overrides.
- code_shape: sequential always block (exact style deferred)
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// skeleton only: sequential block on clk, async reset rst
// manages: m_wb_cyc_o, m_wb_stb_o, wr_tx, ackd, delay, first, offset, we, reset_tx_fifo
// start condition: en && !fe && ackd && !m_wb_ack_i
// on m_wb_ack_i: din <= m_wb_dat_i; wr_tx <= 1; m_wb_cyc_o/stb_o <= 0; delay <= 1;
// on delay: offset <= offset + MEM_OFFSET; ackd <= ~ackd; wr_tx <= 0; ...
// disable (en==0): reset_tx_fifo <= 1; offset <= 0; m_wb_cyc_o/stb_o <= 0; maybe reset other control
```
- must_appear:
  - logic for start condition based on fe, ackd, m_wb_ack_i, en
  - capture of m_wb_dat_i into din on ack
  - assertion/deassertion of m_wb_cyc_o, m_wb_stb_o
  - write strobe (wr_tx) control
  - delay flag set/clear sequence
  - ackd toggle after delay
  - address offset increment by MEM_OFFSET
  - reset and en=0 handling (reset_tx_fifo, offset reset, bus inactive)
- may_appear:
  - handling of first flag for initial ackd state
  - we counter increment on each completed word
  - internal synchronization aids if needed
- retrieval_focus:
  - main control sequence
  - flag-based handshaking
  - transaction state machine (flag_driven)

### Block
- block_id: B5
- block_label: comb_output_assign
- block_kind: comb
- required: true
- purpose: Connect FIFO outputs to module pins.
- code_shape: continuous assignments
- depends_on: [B2]
- placeholder:
```verilog
// skeleton only:
// assign dat_o   = sd_tx_fifo_q;
// assign empty   = sd_tx_fifo_empty;
// assign fe      = sd_tx_fifo_full;
```
- must_appear:
  - dat_o driven by FIFO read data (q)
  - empty driven by FIFO empty
  - fe driven by FIFO full
- may_appear:
  - nothing
- retrieval_focus:
  - output port forwarding
  - interface bridging

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: flag_driven
- semantic_modes:
  - NORMAL_TRANSFER: en=1, read bursts fill FIFO periodically.
  - DISABLED: en=0, FIFO reset, Wishbone interface quiesced.
- state_model:
  - object: ackd
    storage_kind: registered
    representation: toggling flag
    notes: determines permission to start next transaction; toggles after each completed bus cycle.
  - object: delay
    storage_kind: registered
    representation: one‑cycle pulse
    notes: used to defer offset increment and ackd toggle by one clock.
  - object: first
    storage_kind: registered
    representation: internal initialisation flag
    notes: exact usage underspecified; likely governs initial ackd state after enable.
  - object: offset
    storage_kind: registered
    representation: 9‑bit address offset
    notes: incremented by MEM_OFFSET after each word; reset to 0 on disable/reset.
  - object: we
    storage_kind: registered
    representation: 9‑bit counter
    notes: role as write‑enable counter not fully detailed in spec; may count words written or serve as burst length.
- global_invariants:
  - m_wb_cyc_o and m_wb_stb_o are never asserted while en=0 or during reset.
  - A new Wishbone read is only started when FIFO is not full, ackd=1, and no outstanding transaction.
  - wr_tx is only asserted on the exact cycle that m_wb_ack_i is sampled high, capturing the read data.
  - Address offset does not change during an active bus transaction.
- open_semantic_questions:
  - Exact role and synchronisation of first flag (initial state of ackd after enable).
  - Detailed operation of we counter (only incremented on completed writes? used to limit burst size?).
  - Cross‑domain aspects of empty/full flags from sd_clk to clk domain; assumed safe as‑is from dual‑clock FIFO.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide all registered storage and any intermediate combinational wires that serve as communication points between control and datapath.
- timing_semantics: purely structural; no timing behaviour.
- touched_objects: offset, we, din, wr_tx, reset_tx_fifo, first, ackd, delay
- coupling_rules: all sequential updates to these objects must be performed only inside block B4.
- forbidden_drift: do not introduce additional registers or state not mentioned in the specification.

- block_id: B2
- responsibilities:
  - instantiate sd_tx_fifo with correct clock and reset connections.
- timing_semantics: FIFO write side operated by clk, read side by sd_clk; internal dual‑clock synchronisation is handled by the submodule.
- touched_objects: din, wr_tx, dat_o, fe, empty, rd, reset
- coupling_rules: wr_tx is driven by B4; din is captured and presented from B4/B1; read side inputs (rd, sd_clk) come from top‑level and are only passed through.
- forbidden_drift: do not add extra buffering or logic that modifies the FIFO’s own flags or data between ports.

- block_id: B3
- responsibilities:
  - compute m_wb_adr_o combinationally from adr and offset; provide constant values for unused Wishbone master control signals.
- timing_semantics: purely combinational; address updates propagate immediately with offset changes.
- touched_objects: m_wb_adr_o, m_wb_we_o, m_wb_cti_o, m_wb_bte_o
- coupling_rules: offset is maintained by B4; any glitch on address due to offset update is acceptable because bus transaction is inactive at that time.
- forbidden_drift: do not introduce registered address pipeline that would interfere with the one‑cycle offset update schedule.

- block_id: B4
- responsibilities:
  - implement the full Wishbone master read handshake sequence and offset management.
- timing_semantics:
  - On every clk rising edge (after async reset release), evaluate start condition; if true, assert m_wb_cyc_o and m_wb_stb_o.
  - When m_wb_ack_i sampled high, capture m_wb_dat_i into din, assert wr_tx, deassert bus control, set delay.
  - One clock later (delay==1), increment offset, toggle ackd, deassert wr_tx, clean up any transient flags.
  - When en=0 or during reset, override all bus outputs to inactive, reset offset, set reset_tx_fifo.
- touched_objects: m_wb_cyc_o, m_wb_stb_o, din, wr_tx, ackd, delay, first, offset, we, reset_tx_fifo
- coupling_rules: must read fe (from B2) and m_wb_ack_i; must not interfere with B3’s combinational address path.
- forbidden_drift:
  - do not invent multi‑cycle burst modes or Wishbone retry mechanisms beyond the described single‑word read loop.
  - do not add additional wait states unrelated to the spec.

- block_id: B5
- responsibilities:
  - wire FIFO data and status outputs directly to top‑level ports.
- timing_semantics: combinational; dat_o follows FIFO q, empty/full follow FIFO internal flags.
- touched_objects: dat_o, empty, fe
- coupling_rules: no sequential updates; relies solely on B2 instance outputs.
- forbidden_drift: do not gate or sample these signals inside this block; leave timing handling to external components.

## 4. Decision Ledger
### Chosen Decision
- topic: primary control decomposition
- decision: Separate static combinational address generation and output forwarding from the sequential Wishbone engine, keeping the control block (B4) focused on the flag‑driven handshake sequence.
- reason: The spec describes a simple flag‑driven protocol with no complex arbitration. Partitioning in this way avoids large monolithic always blocks and makes later localisation manageable.

### Deferred Decision
- items:
  - Exact behaviour and initialisation of the `first` flag (needed to set initial ackd state after enable).
  - Operation of the `we` counter: whether it counts every completed word, resets on certain conditions, or interacts with burst limits.
  - Resolution of MEM_OFFSET constant value and offset width justification.
  - Choice of raw flag‑driven logic versus a small explicit FSM to encode the start/ack/next‑cycle sequence; the skeleton preserves either by grouping all control in one sequential block.

### Structural Risk
- items:
  - The seq_wishbone_control block (B4) may accumulate many responsibilities (start, ack, delay, increment, disable) if not further subdivided later; can become difficult to debug locally.
  - Coupling between B3 address generation and B4 offset update timing is tight; a change in offset update scheduling could break combinational address stability.

### Behavioral Risk
- items:
  - Underspecified synchronization of `ackd` toggle with the Wishbone handshake could lead to missed transactions if `m_wb_ack_i` persists or if the bus reports an error.
  - The `first` flag’s role is unclear, risking an unsynchronised initial transaction or deadlock if the flag is not properly integrated with reset/enable.
  - Cross‑clock domain flags (fe, empty) are assumed to be safe for use in clk domain without additional synchronisation; any metastability issues will need to be addressed at the system level.