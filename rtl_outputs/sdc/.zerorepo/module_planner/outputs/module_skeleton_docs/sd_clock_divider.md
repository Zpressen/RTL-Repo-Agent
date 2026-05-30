# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_clock_divider
- file_path: rtl/sd_clock_divider.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_clock_divider
  - repo_skeleton_ref: repo_skeleton_v1::sd_clock_divider
  - spec_ref: sd_clock_divider.md
- planning_note: Organize the module around internal counter, divided‑clock generation, and compile‑time output binding.

## 1. Module Frame
```verilog
module sd_clock_divider (
    // port list placeholder
);

// <block: decl_core_objects>
// <block: seq_clock_division>
// <block: comb_output_path>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare internal division counter and intermediate divided‑clock signal SD_CLK_O.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: counter and sd_clk_o declarations
```
- must_appear:
  - counter register (width ≥ needed for max division)
  - sd_clk_o signal
- may_appear:
  - any internal enable or pre‑scaled signals
- retrieval_focus:
  - state/register description
  - internal timing signals

### Block
- block_id: B2
- block_label: seq_clock_division
- block_kind: seq
- required: true
- purpose: Implement clock‑division behaviour: counter update on CLK, toggling of SD_CLK_O, and asynchronous reset.
- code_shape: sequential process(es) sensitive to CLK and RST
- depends_on: [B1]
- placeholder:
```verilog
// skeleton: sequential division process
// <asynchronous reset: counter ← 0, sd_clk_o ← 0>
// <counter increment logic based on DIVIDER>
// <sd_clk_o toggling logic>
```
- must_appear:
  - counter update
  - sd_clk_o generation
- may_appear:
  - intermediate toggling enable
- retrieval_focus:
  - division ratio implementation
  - reset behaviour

### Block
- block_id: B3
- block_label: comb_output_path
- block_kind: comb
- required: true
- purpose: Map SD_CLK_O to the top‑level SD_CLK output according to synthesis/simulation defines (SYN, SIM, ACTEL).
- code_shape: combinational assignment with conditional compilation directives
- depends_on: [B1]
- placeholder:
```verilog
// skeleton: output path
//`ifdef SYN
//    // synthesis connection
//`elsif SIM
//    // direct connection: assign SD_CLK = sd_clk_o;
//`elsif ACTEL
//    // clock buffer instantiation (SD_CLK_O as output, SD_CLK as CLKINT input)
//`endif
```
- must_appear:
  - output signal SD_CLK
- may_appear:
  - none
- retrieval_focus:
  - target‑specific output routing

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: counter_driven
- semantic_modes:
  - clock_division: constantly produces SD_CLK at frequency CLK/(DIVIDER+1)
- state_model:
  - object: counter
    storage_kind: registered
    representation: implementation‑open (width not explicitly bounded but minimum 8)
    notes: holds current count for division; reset to 0
  - object: sd_clk_o
    storage_kind: registered
    representation: 1‑bit
    notes: toggled to produce intermediate divided waveform; reset to 0
- global_invariants:
  - SD_CLK output is 0 immediately after asynchronous reset
  - division ratio is fixed by DIVIDER input (not self‑changing)
- open_semantic_questions:
  - exact duty cycle of SD_CLK not specified
  - precise timing of SD_CLK edges relative to CLK edges not given
  - SYN synthesis path not detailed

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide shared declared objects (counter, sd_clk_o) for downstream blocks
- timing_semantics:
  - objects are synchronous to CLK; no independent timing
- touched_objects:
  - counter
  - sd_clk_o
- coupling_rules:
  - B2 reads and writes these objects
- forbidden_drift:
  - do not add extra state that implies additional division modes

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - update counter every rising CLK edge
  - toggle sd_clk_o at the correct rate defined by DIVIDER
  - asynchronous reset: force counter and sd_clk_o to 0, directly driving SD_CLK low through B3
- timing_semantics:
  - synchronous update on rising edge of CLK
  - reset is asynchronous, exits immediately; no metastability mitigation required in this block
- touched_objects:
  - counter
  - sd_clk_o
- coupling_rules:
  - B3 reads sd_clk_o (through B1 declaration)
- forbidden_drift:
  - do not alter the division formula (1/(DIVIDER+1))
  - do not introduce glitch‑filtering or clock‑gating that changes the semantic behaviour

### Block Behavioral Overlay
- block_id: B3
- responsibilities:
  - map sd_clk_o to top‑level SD_CLK under active compile‑time constraint
  - in SIM mode connect directly; in ACTEL mode route through the appropriate clock buffer; SYN mode remains unspecified
- timing_semantics:
  - no additional sequential elements; pure combinational mapping
  - must not add timing delay that alters the intended SD_CLK waveform
- touched_objects:
  - SD_CLK
  - sd_clk_o
- coupling_rules:
  - depends on sd_clk_o from B1
- forbidden_drift:
  - do not change the division timing or introduce an extra clock domain
  - do not reinterpret sd_clk_o as a different logical function

## 4. Decision Ledger
### Chosen Decision
- topic: internal signal for divided clock
- decision: Use an intermediate signal SD_CLK_O before output selection.
- reason: Required by SIM/ACTEL constraints; keeps division logic separate from output routing.

### Deferred Decision
- items:
  - exact counter width and toggle threshold expression
  - duty‑cycle choice (50% or otherwise) left open until further specification
  - exact `ifdef` structure for SYN/SIM/ACTEL (only placeholders used)

### Structural Risk
- items:
  - B2 and B3 must coordinate such that sd_clk_o transitions do not create glitches on SD_CLK through combination with output mapping; placeholder structure assumes B3 is pure wire‑level assignment
  - Any additional SYN path not described may require its own clock buffer instance not captured here

### Behavioral Risk
- items:
  - Undefined duty cycle may cause SD protocol timing violations in downstream modules (sd_cmd_serial_host, sd_data_serial_host)
  - Lack of timing precision between CLK and SD_CLK may affect setup/hold in the rest of the controller; must be addressed during generation or integration