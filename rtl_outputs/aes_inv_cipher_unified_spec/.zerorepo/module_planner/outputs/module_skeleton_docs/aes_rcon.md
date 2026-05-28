# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_rcon
- file_path: rtl/aes_rcon.v
- source_refs:
  - module_contract_ref: extracted_facts::aes_rcon
  - repo_skeleton_ref: repo_skeleton::aes_rcon
  - spec_ref: aes_rcon Design Specification
- planning_note: The module is a leaf-level, counter-driven round constant generator with a 4-bit counter, a combinational constant lookup, and a registered 32-bit output. The skeleton focuses on declaration, combinational computation, and sequential update.

## 1. Module Frame
```verilog
module aes_rcon (
    // port list placeholder
);

// <block: decl_core_objects>
// <block: comb_round_constant_lookup>
// <block: seq_register_update>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare the round counter register, output register, and the constant lookup table (read-only map of round constants).
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster for rcnt (4-bit register), out_reg (32-bit register),
//               and a local constant array RC_TABLE[0:9] holding 8-bit round constants 01,02,04,...,36.
```
- must_appear:
  - rcnt (4-bit round counter)
  - out_reg (32-bit output register)
  - round constant table value set
- may_appear:
  - intermediate wire for combinational constant byte
- retrieval_focus:
  - register widths
  - constant table contents
  - reset/control signal connection points

### Block
- block_id: B2
- block_label: comb_round_constant_lookup
- block_kind: comb
- required: true
- purpose: Combinational logic to compute the next round constant byte from rcnt, kld, and the pre-defined table; handles forced values for kld=1 and rcnt>9.
- code_shape: combinatorial block
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: combinatorial derivation of next_rc_byte (8-bit)
//   select from RC_TABLE[rcnt] when valid; force to 0x01 when kld==1; force to 0x00 when rcnt > 9.
```
- must_appear:
  - a combinational path that reads rcnt and kld
  - a 8-bit intermediate representing the MSB of the output
- may_appear:
  - additional multiplexer structures
- retrieval_focus:
  - forced-value conditions (kld=1, rcnt > 9)
  - table indexing

### Block
- block_id: B3
- block_label: seq_register_update
- block_kind: seq
- required: true
- purpose: Synchronous update of rcnt and out_reg on the rising edge of clk, using the combinational result from B2.
- code_shape: sequential block
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: sequential always block
//   on posedge clk:
//     if (kld) rcnt <= 0;
//     else      rcnt <= rcnt + 1;
//     out_reg <= {next_rc_byte, 24'h00_00_00};
```
- must_appear:
  - clock edge sensitivity
  - rcnt update
  - out_reg update
- may_appear:
  - no additional logic
- retrieval_focus:
  - reset (kld) condition
  - counter increment condition
  - output formatting (lower 24 bits zero)

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: counter_driven
- semantic_modes:
  - KEY_LOAD: kld = 1; forces rcnt to 0 and out to 0x01000000.
  - INCREMENT: kld = 0; rcnt increments by 1 per cycle, out reflects the round constant for the new rcnt value.
  - OVERFLOW: rcnt > 9; out forced to 0x00000000 while rcnt continues incrementing.
- state_model:
  - object: rcnt
    storage_kind: registered
    representation: 4-bit counter
    notes: resets on kld; increments otherwise.
  - object: out_reg
    storage_kind: registered
    representation: 32-bit register; MSB from round constant, lower 24 bits fixed at zero.
    notes: updated synchronously every cycle.
- global_invariants:
  - out_reg[23:0] is always zero.
  - When kld=1, out_reg = 32'h01000000.
  - For rcnt=0..9 and kld=0, out_reg = {RC[rcnt], 24'h000000}.
  - For rcnt>9 and kld=0, out_reg = 32'h00000000.
- open_semantic_questions:
  - The precise behavioral effect of “one time unit after the clock’s rising edge” is left to RTL generation; no delay modeling needed.

### Block Behavioral Overlay
- block_id: B2
- responsibilities:
  - Compute a pure combinational value for the upper byte of out_reg.
  - Enforce forced outputs for kld assertion and rcnt overflow.
- timing_semantics:
  - purely combinational; must be stable before the rising clock edge.
- touched_objects:
  - rcnt (read)
  - kld (read)
  - RC_TABLE (read)
  - next_rc_byte (write)
- coupling_rules:
  - B3 consumes next_rc_byte; B2 must not create any registered paths.
- forbidden_drift:
  - Do not introduce registered signals inside this block.
  - Do not infer alternative GF multiplier circuits if the spec’s constant set is used directly.

- block_id: B3
- responsibilities:
  - Synchronously update rcnt and out_reg according to kld and rcnt state.
  - Ensure out_reg lower 24 bits are always zero.
- timing_semantics:
  - On every posedge clk, rcnt and out_reg capture their next values.
- touched_objects:
  - rcnt (read/write)
  - out_reg (write)
  - next_rc_byte (read from B2)
- coupling_rules:
  - Depends on B2 for the MSB computation.
  - Must apply kld-check before any counter increment.
- forbidden_drift:
  - Do not modify rcnt or out_reg outside this sequential block.
  - Do not add asynchronous reset paths; kld is synchronous.

## 4. Decision Ledger
### Chosen Decision
- topic: structural decomposition
- decision: Separate the constant lookup (combinational) from the register update (sequential) to keep responsibilities explicit and reuse-safe.
- reason: The spec defines a deterministic table of constants and forced outputs; isolating the combinational computation simplifies verification and avoids mixed-logic blocks.

### Chosen Decision
- topic: control_style
- decision: counter_driven
- reason: The module’s primary behavior is governed by a 4-bit counter (rcnt) with clear increment and reset rules; there is no finite-state machine beyond the counter.

### Deferred Decision
- items:
  - Whether the round constant table is implemented as a local read-only array, a parameterized lookup, or a const wire vector.
  - Exact encoding style for “rcnt > 9” condition (e.g., explicit comparison vs. rollover detection).

### Structural Risk
- items:
  - The single sequential block (B3) controls both the counter and output register; if later specification requires separate enable controls, the block may need splitting.

### Behavioral Risk
- items:
  - The “one time unit after the clock’s rising edge” language is purely descriptive and may cause confusion during timing closure; RTL generation must ignore it and treat the updates as standard synchronous flop behavior.