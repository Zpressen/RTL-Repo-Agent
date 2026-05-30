# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_tx_fifo
- file_path: rtl/sd_tx_fifo.v
- source_refs:
  - module_contract_ref: module_contracts_v1::sd_tx_fifo
  - repo_skeleton_ref: repo_skeleton_v1::sd_tx_fifo
  - spec_ref: sd_tx_fifo.md
- planning_note: Dual‑clock FIFO with separate write (wclk) and read (rclk) domains, pointer‑based address management, and cross‑clock domain flag generation.

## 1. Module Frame
```verilog
module sd_tx_fifo #(
    // parameter: FIFO_TX_MEM_DEPTH (RAM depth)
    // parameter: FIFO_RX_MEM_ADR_SIZE (pointer width)
) (
    // input  [31:0] d,
    // input         wr,
    // input         wclk,
    // output [31:0] q,
    // input         rd,
    // output        full,
    // output        empty,
    // output [ 5:0] mem_empt,
    // input         rclk,
    // input         rst
);

// <block: decl_core_objects>
// <block: write_pointer_update>
// <block: read_pointer_update>
// <block: status_flag_gen_sync>
// <block: data_output>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare RAM storage, write pointer (adr_i), read pointer (adr_o), and any synchronization registers needed by status_flag_gen_sync.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster for ram, adr_i (wclk domain), adr_o (rclk domain), synchronization registers
```
- must_appear:
  - ram as 32‑bit × FIFO_TX_MEM_DEPTH storage
  - adr_i of width FIFO_RX_MEM_ADR_SIZE
  - adr_o of width FIFO_RX_MEM_ADR_SIZE
  - (if needed) synchronizer registers for cross‑clock pointer transfer
- may_appear:
  - internal wires for synchronized pointer values
- retrieval_focus:
  - interface
  - state/storage description

### Block
- block_id: B2
- block_label: write_pointer_update
- block_kind: seq
- required: true
- purpose: On rising edge of wclk, when not full and wr is high, write d into ram[adr_i] and increment adr_i with wrap‑around.
- code_shape: sequential always block (wclk domain)
- depends_on: ['B1', 'B4']
- placeholder:
```verilog
// wclk domain sequential process:
//   - on reset: reset adr_i
//   - else if wr and not full: write d to ram[adr_i]; increment adr_i with wrap‑around
```
- must_appear:
  - write to ram
  - adr_i increment and wrap‑around
- may_appear:
  - reset of adr_i and possibly RAM
- retrieval_focus:
  - write‑domain sequence

### Block
- block_id: B3
- block_label: read_pointer_update
- block_kind: seq
- required: true
- purpose: On rising edge of rclk, when not empty and rd is high, increment adr_o with wrap‑around; possibly update any registered output.
- code_shape: sequential always block (rclk domain)
- depends_on: ['B1', 'B4']
- placeholder:
```verilog
// rclk domain sequential process:
//   - on reset: reset adr_o
//   - else if rd and not empty: increment adr_o with wrap‑around
```
- must_appear:
  - adr_o increment and wrap‑around
- may_appear:
  - reset of adr_o
- retrieval_focus:
  - read‑domain sequence

### Block
- block_id: B4
- block_label: status_flag_gen_sync
- block_kind: helper
- required: true
- purpose: Synchronize write pointer to read clock domain and read pointer to write clock domain; derive full, empty, and mem_empt flags from the resulting synchronised pointer values according to the spec.
- code_shape: combination of synchronizer registers (in respective clock domains) and combinational logic for flag computation
- depends_on: ['B1']
- placeholder:
```verilog
// cross‑clock pointer synchronization and flag generation
//   - synchronize adr_i to rclk domain (e.g., gray‑encode + two‑flop synchronizer)
//   - synchronize adr_o to wclk domain (similar)
//   - derive full flag in wclk domain using synchronized read pointer
//   - derive empty flag in rclk domain using synchronized write pointer
//   - derive mem_empt occupancy value (adr_i minus adr_o with wrap handling)
```
- must_appear:
  - generation of full, empty, mem_empt as described in spec (pointer comparisons with wrap‑around awareness)
  - safe cross‑clock transfer of multi‑bit pointers
- may_appear:
  - explicit synchronizer instances or structures
  - internal synchronised pointer wires
- retrieval_focus:
  - flag generation cross‑domain coupling

### Block
- block_id: B5
- block_label: data_output
- block_kind: comb
- required: true
- purpose: Drive output q from the FIFO RAM, using the read pointer.
- code_shape: combinational assignment or registered output (see Deferred Decision)
- depends_on: ['B1', 'B3']
- placeholder:
```verilog
// output data path
//   - drive q from ram[adr_o] (combinational or registered, per deferred decision)
```
- must_appear:
  - q output connected to ram content addressed by adr_o
- may_appear:
  - registration of q (if chosen)
- retrieval_focus:
  - output data path

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - RESET: pointers set to 0; empty high, full low; RAM content undefined or cleared
  - NORMAL: independent write and read operations governed by wr/full and rd/empty; pointers advance and wrap; occupancy updated
- state_model:
  - object: adr_i
    storage_kind: registered
    representation: binary counter (width FIFO_RX_MEM_ADR_SIZE) in wclk domain
    notes: incremented on successful write; wrap‑around at FIFO_TX_MEM_DEPTH-1 → 0
  - object: adr_o
    storage_kind: registered
    representation: binary counter (width FIFO_RX_MEM_ADR_SIZE) in rclk domain
    notes: incremented on successful read; wrap‑around at FIFO_TX_MEM_DEPTH-1 → 0
  - object: ram
    storage_kind: inferred memory (32‑bit × FIFO_TX_MEM_DEPTH)
    notes: written in wclk domain, read in rclk domain (or combinationally for q)
- global_invariants:
  - After reset, empty is high and full is low.
  - Writing when full does not alter ram or adr_i.
  - Reading when empty does not alter adr_o and q holds the last‑read (or last‑addressed) value.
  - Pointer wrap‑around preserves correct flag generation.
- open_semantic_questions:
  - Exact synchronisation methodology for full/empty generation (gray code vs. multi‑flop) is left open by spec; must be safe for asynchronous clocks.
  - Whether q output is registered on rclk edge (committed) or purely combinational (latched by consumer) is not stated; both are permissible but must be decided.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide shared declarations for ram, write pointer, read pointer, and any synchronizer registers required by B4.
- timing_semantics:
  - No timing obligation beyond lexical declaration; actual assignment occurs in B2/B3/B4.
- touched_objects:
  - ram, adr_i, adr_o, (optional) sync_wptr, sync_rptr
- coupling_rules:
  - B2 exclusively updates adr_i and ram (write side) on wclk.
  - B3 exclusively updates adr_o on rclk.
  - B4 reads raw adr_i/adr_o and produces full, empty, mem_empt.
  - B5 reads ram and adr_o (or registered version) to produce q.
- forbidden_drift:
  - Do not add extra registered objects that violate the dual‑clock simplicity (e.g., no explicit state machine).

- block_id: B2
- responsibilities:
  - Execute write transaction under wclk: when wr high and full low, store d into ram[adr_i] and increment adr_i with proper wrap.
  - Handle reset: set adr_i to 0 (and optionally clear RAM content if required by reset spec, though not explicitly mandated).
- timing_semantics:
  - Entire block is synchronous to rising edge of wclk; adr_i and ram updates occur after clock edge.
- touched_objects:
  - ram (wclk domain write), adr_i
- coupling_rules:
  - Uses full flag from B4; B4 must present full such that glitches or metastability do not cause false writes (synchronization must guarantee safe full generation).
  - Must not interfere with read side (B3/B5).
- forbidden_drift:
  - Do not gate the clock or use latches; implement straightforward clocked process.

- block_id: B3
- responsibilities:
  - On rising edge of rclk, when rd high and empty low, increment adr_o with wrap‑around.
  - Handle reset: set adr_o to 0.
- timing_semantics:
  - Entire block is synchronous to rclk; adr_o updates after clock edge.
- touched_objects:
  - adr_o
- coupling_rules:
  - Uses empty flag from B4; B4 must deliver safe empty to prevent spurious reads.
  - Must not modify ram or adr_i.
- forbidden_drift:
  - Do not add additional state on the read side beyond adr_o (except possibly a q register if decided).

- block_id: B4
- responsibilities:
  - Transfer multi‑bit pointers across asynchronous clock domains safely (e.g., gray‑encode + 2‑flop synchronizer).
  - Generate full flag (in wclk domain) from synchronised read pointer and current write pointer.
  - Generate empty flag (in rclk domain) from synchronised write pointer and current read pointer.
  - Generate mem_empt occupancy value (likely in rclk or common domain) as adr_i minus adr_o (with wrap‑around handling).
- timing_semantics:
  - Synchronizer registers in both clock domains add latency; flags will lag pointer changes but this is safe for FIFO operation.
  - mem_empt may change a few cycles after pointer changes; its exact update edge is not critical as long as it does not glitch.
- touched_objects:
  - raw adr_i (wclk domain), raw adr_o (rclk domain), internal synchronised pointers, full (output), empty (output), mem_empt (output)
- coupling_rules:
  - B2 depends on full; B3 depends on empty. B4 must ensure those flags are derived from a synchronised version of the opposite pointer to avoid metastability.
  - If mem_empt is used by external logic, it must also be derived from synchronised pointers (typically a common domain).
- forbidden_drift:
  - Do not attempt to compare raw pointers directly across clock domains without synchronisation.
  - Do not invent extra status flags beyond full, empty, mem_empt.

- block_id: B5
- responsibilities:
  - Provide the data output q corresponding to the current read pointer adr_o.
- timing_semantics:
  - If combinational: q changes after adr_o or ram content changes (subject to read‑side timing).
  - If registered: q updates on rclk rising edge when rd is high (or every cycle) depending on choice.
- touched_objects:
  - q (output port)
- coupling_rules:
  - Must read ram with address adr_o; adr_o is managed by B3.
  - Must not infer a write‑enable side effect on the read port (read‑only).
- forbidden_drift:
  - Do not add mux or transformation on output data that is not described in the spec.

## 4. Decision Ledger
### Chosen Decision
- topic: Block decomposition strategy
- decision: Separate write‑domain pointer update, read‑domain pointer update, status flag generation with synchronisation, and data output into distinct structural blocks.
- reason: This mirrors the natural dual‑clock FIFO architecture, simplifies retrieval of domain‑coupled logic, and keeps synchronisation concerns localised to one block.

- topic: Pointer widths
- decision: Use `FIFO_RX_MEM_ADR_SIZE` for both adr_i and adr_o as stated in the spec’s register table (despite the “RX” naming).
- reason: The spec table explicitly lists both addresses with `FIFO_RX_MEM_ADR_SIZE`; this appears to be a copy‑over from the rx_fifo document but is the current normative source.

### Deferred Decision
- items:
  - Determination of whether q output is combinatorial or registered on rclk (both are viable, spec is silent; later generator must pick one and document).
  - Exact synchronisation method for pointers (gray encoding, binary + multi‑flop, vendor‑specific synchroniser primitives) – to be resolved during local RTL generation while respecting asynchronous clock safety.
  - Whether RAM content is cleared on reset (spec does not mandate, but may be pragmatically included; to be decided during generation).
  - Width of mem_empt: spec states 6 bits, but this may depend on FIFO_TX_MEM_DEPTH; if depth exceeds 64, width may need adjustment. This is not determined by current spec and must be resolved when parameter values are fixed.

### Structural Risk
- items:
  - Block B4 (status_flag_gen_sync) combines cross‑clock synchronisation and combinatorial flag logic; if the implementation becomes complex, it may need to be split into synchroniser instances and flag derivation. The current skeleton groups them for simplicity; during local generation the block may be expanded.
  - The index `FIFO_RX_MEM_ADR_SIZE` may be inconsistently defined (e.g., derived from `FIFO_TX_MEM_DEPTH`). If the actual depth requires a different address width, the spec’s use of `FIFO_RX_MEM_ADR_SIZE` could cause misalignment.

### Behavioral Risk
- items:
  - Unspecified timing of q and flag updates relative to respective clocks could lead to glitch‑sensitive downstream logic. The skeleton does not force a decision, so a later stage must ensure consistent choice.
  - Cross‑clock synchronisation can introduce metastability if not designed with proper timing constraints; the deferral of the method leaves a concrete safety obligation for local generation.
  - The occupancy signal `mem_empt` computed as `adr_i – adr_o` requires both pointers in a common domain; spec does not state which domain is used. An incorrect choice could yield an occupancy value that is not monotonically usable (e.g., rapid changes). This must be cross‑checked during generation.