# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_rx_fifo
- file_path: rtl/sd_rx_fifo.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_rx_fifo
  - repo_skeleton_ref: repo_skeleton_v1::sd_rx_fifo
  - spec_ref: sd_rx_fifo.md
- planning_note: Organize the module into dual‑clock domain code regions: write‑side nibble accumulation and RAM write, read‑side RAM read and address update, pointer synchronization and flag generation, and output logic.

## 1. Module Frame
```verilog
module sd_rx_fifo (
    // <port list placeholder>
);

// <block: decl_parameters_and_registers>
// <block: seq_write_domain>
// <block: seq_read_domain>
// <block: seq_flag_synchronization>
// <block: comb_data_and_space_output>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_parameters_and_registers
- block_kind: decl
- required: true
- purpose: Declare FIFO depth/address parameters, RAM storage, pointer registers, nibble accumulation registers, and byte‑enable register.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: parameter declarations (FIFO_RX_MEM_DEPTH, FIFO_RX_MEM_ADR_SIZE)
// skeleton only: RAM array declaration (ram)
// skeleton only: write pointer register (adr_i)
// skeleton only: read pointer register (adr_o)
// skeleton only: nibble accumulator register (tmp)
// skeleton only: byte write enable register (we)
// skeleton only: data written flag register (ft)
// skeleton only: any pointer‑width extension bits for wrap‑around detection
```
- must_appear:
  - RAM storage array
  - adr_i, adr_o, tmp, we, ft registers
  - FIFO_RX_MEM_DEPTH, FIFO_RX_MEM_ADR_SIZE parameters
- may_appear:
  - Gray‑coded pointer variants
  - synchronizer stages
- retrieval_focus:
  - storage objects
  - state‑holding registers
  - parameterisation

### Block
- block_id: B2
- block_label: seq_write_domain
- block_kind: seq
- required: true
- purpose: On wclk rising edge, accumulate 4‑bit data into tmp, shift byte‑write enables, and when a full word is ready write to ram[adr_i] and increment adr_i.
- code_shape: clocked sequential region (wclk)
- depends_on: [B1]
- placeholder:
```verilog
// <block: seq_write_domain>
// synchronous to wclk, active on wr
// tmp reg update (nibble placement governed by we)
// we shift/update logic
// write to ram when word accumulation complete
// adr_i increment on successful write, with wrap‑around
// ft flag update
```
- must_appear:
  - tmp accumulation logic
  - we shift mechanism
  - ram write enable condition
  - adr_i increment with wrap‑around
- may_appear:
  - nibble‑packing order spec‑implied detail
- retrieval_focus:
  - write clock domain update path

### Block
- block_id: B3
- block_label: seq_read_domain
- block_kind: seq
- required: true
- purpose: On rclk rising edge, update read pointer adr_o when a valid read occurs; keep read data available on q (combinational or registered) and ensure empty‑condition hold.
- code_shape: clocked sequential region (rclk) with optional direct output assignment
- depends_on: [B1, B4]
- placeholder:
```verilog
// <block: seq_read_domain>
// synchronous to rclk
// adr_o increment on read condition (rd & ~empty)
// adr_o wrap‑around handling
// present ram[adr_o] to q (combinational or registered)
// hold q when empty (present last‑read ram location data)
```
- must_appear:
  - adr_o update condition
  - wrap‑around logic
  - output data mapping to q
- may_appear:
  - output register stage
- retrieval_focus:
  - read clock domain update path
  - output generation

### Block
- block_id: B4
- block_label: seq_flag_synchronization
- block_kind: seq
- required: true
- purpose: Generate full, empty, and mem_empt flags by synchronizing and comparing write‑side and read‑side pointers. Must safely cross clock domains.
- code_shape: mixed sequential (synchroniser registers) and combinational comparison
- depends_on: [B1, B2, B3]
- placeholder:
```verilog
// <block: seq_flag_synchronization>
// synchronize write pointer into rclk domain (register stages)
// synchronize read pointer into wclk domain (register stages)
// combinational full/empty logic using synchronized pointers (including high‑bit comparison)
// combinational mem_empt generation from pointer difference
// ensure flags stable outside their native domains
```
- must_appear:
  - synchronizer chains (min 2‑stage)
  - pointer comparison logic for full
  - pointer comparison logic for empty
  - mem_empt calculation
- may_appear:
  - Gray encoding converters
- retrieval_focus:
  - cross‑clock safety
  - flag generation

### Block
- block_id: B5
- block_label: comb_data_and_space_output
- block_kind: comb
- required: false
- purpose: (Optional) If the preceding read‑domain block does not directly drive q and mem_empt, provide a dedicated combinational block that extracts these outputs from ram and pointer state.
- code_shape: purely combinational region
- depends_on: [B1, B3, B4]
- placeholder:
```verilog
// <block: comb_data_and_space_output>
// continuous assignments from ram and pointer state
// q = ram[adr_o] (if not already assigned in read block)
// mem_empt = combinatorial space count from pointer difference
```
- must_appear:
  - none (can be merged into other blocks)
- may_appear:
  - explicit mux or assignment
- retrieval_focus:
  - final output mapping

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - NORMAL: independent write‑side nibble accumulation and read‑side word retrieval
- state_model:
  - object: tmp
    storage_kind: registered (wclk domain)
    representation: 32‑bit shift/accumulator
    notes: accumulates 4‑bit nibbles; placement governed by we bits; reset to 0
  - object: we
    storage_kind: registered (wclk domain)
    representation: 8‑bit, one‑hot or rotating mask
    notes: initialised to 8’h1 at reset; shifts to track written nibbles; full word triggers write
  - object: ft
    storage_kind: registered (wclk domain)
    representation: 1‑bit flag
    notes: indicates a complete word has been written since last RAM write; used to qualify write
  - object: adr_i
    storage_kind: registered (wclk domain)
    representation: FIFO_RX_MEM_ADR_SIZE + extra wrap‑around bit
    notes: write pointer; increments on successful RAM write; wraps with high‑bit toggle
  - object: adr_o
    storage_kind: registered (rclk domain)
    representation: FIFO_RX_MEM_ADR_SIZE + extra wrap‑around bit
    notes: read pointer; increments after a read while not empty; wraps with high‑bit toggle; after reset points to RAM location that will be output on subsequent reads when empty
- global_invariants:
  - Write operation only updates state when wr is active.
  - Read operation only alters read pointer when rd is active and FIFO not empty.
  - Full/empty flags must be stable and glitch‑free in the consuming domains.
  - mem_empt reflects available space in words, not nibbles.
- open_semantic_questions:
  - Whether q output is registered or purely combinational.
  - Exact byte‑packing order of nibbles into tmp (spec only says “accumulated”, not nibble‑position mapping).
  - Preferred synchronisation method (2‑stage DFF or Gray‑code pointer) is not specified.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide parameter constants and all state‑holding declarations.
- timing_semantics:
  - Asynchronous reset (rst) clears all registers declared here.
- touched_objects:
  - ram, adr_i, adr_o, we, tmp, ft, and any pointer‑width extension bits
- coupling_rules:
  - All other blocks depend on these declarations; no write‑domain block may modify rclk‑side registers, and vice‑versa, except through synchronised paths in B4.
- forbidden_drift:
  - Do not create additional asynchronous storage or un‑clocked registers.

- block_id: B2
- responsibilities:
  - Implement nibble accumulation, byte‑enable shifting, RAM write, and write‑pointer management.
- timing_semantics:
  - Fully synchronous to wclk; outputs to RAM (ram[adr_i]) and pointer updates are registered.
  - The RAM write occurs on the rising edge when a full word is ready; data must be committed to RAM before the pointer increments.
- touched_objects:
  - tmp, we, ft, ram, adr_i
- coupling_rules:
  - Must respect we reset value (8’h1) and wrap‑around pointer behaviour.
  - Must signal word‑ready to read side only through the synchronised pointer in B4.
- forbidden_drift:
  - Do not presume the width of the wrap‑around extension bit beyond what is necessary for full/empty distinction.
  - Do not add speculative writes without wr.

- block_id: B3
- responsibilities:
  - Update read pointer when rd is active and FIFO not empty; provide q output.
- timing_semantics:
  - adr_o update on rclk rising edge; q may be combinational from ram[adr_o] or registered. If registered, care must be taken to meet external read‑data hold timing.
- touched_objects:
  - adr_o, q (if assigned here), ram (read access)
- coupling_rules:
  - Must not update adr_o when empty signal (from B4) is asserted.
  - When empty, must hold the data from the last valid read address on q (as per spec empty behaviour).
- forbidden_drift:
  - Do not produce q from any source other than ram[adr_o] (or a registered version of it).
  - Do not assume rd handshake extends beyond the current clock cycle.

- block_id: B4
- responsibilities:
  - Safely synchronise write‑ and read‑side pointers, generate full, empty, and mem_empt.
- timing_semantics:
  - Synchroniser chains run on their respective clocks; flag outputs are potentially delayed by 2–3 clock cycles, which is inherent to asynchronous FIFO design.
  - Flag combinational logic produces glitch‑free outputs only after synchronisers have settled.
- touched_objects:
  - full, empty, mem_empt outputs; internal synchronised versions of adr_i, adr_o
- coupling_rules:
  - Must use the same pointer width and wrap‑around extension as declared in B1.
  - Empty/full determination uses the high‑bit comparison technique implied by the spec wrap‑around test.
  - mem_empt computes available words (e.g., pointer difference masked to FIFO depth).
- forbidden_drift:
  - Do not infer handshake signals or additional control paths beyond the static flags.
  - Do not bypass synchroniser stages except when explicitly justified by a known safe user constraint.

- block_id: B5
- responsibilities:
  - If q or mem_empt are not directly driven in their originating blocks, provide terminal combinational assignments from the synchronised state.
- timing_semantics:
  - Purely combinational; timing is determined by input arrival from upstream blocks.
- touched_objects:
  - q, mem_empt (may also set them in B3/B4)
- coupling_rules:
  - Outputs must match the behaviour specified in the interface contract.
- forbidden_drift:
  - Do not introduce new logic that changes the meaning of mem_empt (only 2‑bit word space).

## 4. Decision Ledger
### Chosen Decision
- topic: structural decomposition
- decision: Split the module into five blocks: parameter/register declaration, write‑domain sequencer, read‑domain sequencer, flag synchronisation, and optional output‑only block. Aligns with spec’s explicit dual‑clock FIFO structure and pointer comparison requirements.
- reason: Separate clock domains and cross‑clock logic are the main complexity; this decomposition keeps retrieval and future code merge manageable while honouring every spec line.

### Deferred Decision
- items:
  - Exact byte‑packing order of nibbles into tmp (which bit position for which nibble) – deferred until local generation; will use a straightforward right‑to‑left accumulation unless later spec clarification forces otherwise.
  - Whether to register q output – deferred to timing closure requirements; skeleton allows both.
  - Use of Gray‑coded pointers versus 2‑stage DFF synchronisers for pointer crossing – deferred; both satisfy "high‑bit flips" test but have different area/latency trade‑offs.

### Structural Risk
- items:
  - B4 (flag synchronisation) concentrates all cross‑clock logic and may become a maintenance burden if future specs add more flags.
  - B2 and B3 are tightly coupled to B1 register widths; parameter changes must be reflected in all pointer logic.

### Behavioral Risk
- items:
  - If q is not registered, the read output may glitch when adr_o changes; consuming logic must guarantee rd/empty handshake to avoid capturing invalid data.
  - Cross‑clock path latency may cause full/empty to lag; host must tolerate conservative flag timing (inherent in asynchronous FIFO).