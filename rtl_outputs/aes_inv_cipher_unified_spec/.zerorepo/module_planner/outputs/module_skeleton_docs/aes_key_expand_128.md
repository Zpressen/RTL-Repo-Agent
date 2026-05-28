# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: aes_key_expand_128
- file_path: rtl/aes_key_expand_128.v
- source_refs:
  - module_contract_ref: module_contracts_v1::aes_key_expand_128
  - repo_skeleton_ref: repo_skeleton_v1::aes_key_expand_128
  - spec_ref: aes_key_expand_128.md
- planning_note: Organize the module into register declarations, submodule instances, combinational key expansion logic, synchronous state update, and output assignments.

## 1. Module Frame
```verilog
module aes_key_expand_128 (
    input clk,
    input kld,
    input [127:0] key,
    output [31:0] wo_0,
    output [31:0] wo_1,
    output [31:0] wo_2,
    output [31:0] wo_3
);

// <block: decl_regs_wires>
// <block: inst_submodules>
// <block: comb_rotword_subword_rcon>
// <block: comb_key_next>
// <block: seq_reg_update>
// <block: output_assign>

endmodule
```

## 2. Structural Skeleton

### Block
- block_id: B1
- block_label: decl_regs_wires
- block_kind: decl
- required: true
- purpose: Declare the four 32-bit round key registers and intermediate wires needed for combinational expansion.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: register and wire declarations
// register: rk0, rk1, rk2, rk3 (32-bit each)
// wire: T_word (32-bit), rk0_next, rk1_next, rk2_next, rk3_next (32-bit)
// wire: rcon_out (32-bit)
// wire: rot_word (32-bit) from RotWord of rk3
// wire: sbox_byte0, sbox_byte1, sbox_byte2, sbox_byte3 (8-bit each)
```
- must_appear:
  - rk0, rk1, rk2, rk3 (32-bit registers)
  - next-round-key intermediate signals (rk0_next, rk1_next, rk2_next, rk3_next)
- may_appear:
  - auxiliary combinational signal declarations (rot_word, sbox_byte*, T_word, rcon_out)
- retrieval_focus:
  - interface to downstream blocks

### Block
- block_id: B2
- block_label: inst_submodules
- block_kind: inst
- required: true
- purpose: Instantiate one aes_rcon and four aes_sbox submodules.
- code_shape: module instantiations
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: submodule instances
// aes_rcon rcon_inst (.clk(clk), .kld(kld), .out(rcon_out));
// aes_sbox sbox_inst0 (.a(rot_word[31:24]), .b(sbox_byte0));
// aes_sbox sbox_inst1 (.a(rot_word[23:16]), .b(sbox_byte1));
// aes_sbox sbox_inst2 (.a(rot_word[15:8]),  .b(sbox_byte2));
// aes_sbox sbox_inst3 (.a(rot_word[7:0]),   .b(sbox_byte3));
```
- must_appear:
  - aes_rcon instance
  - four aes_sbox instances
- may_appear:
  - connection notes (exact port mapping deferred)
- retrieval_focus:
  - submodule connectivity

### Block
- block_id: B3
- block_label: comb_rotword_subword_rcon
- block_kind: comb
- required: true
- purpose: Compute RotWord, SubWord, and XOR with round constant to produce T_word.
- code_shape: combinational assignment group
- depends_on: [B1, B2]
- placeholder:
```verilog
// skeleton only: RotWord, SubWord, Rcon XOR
// rot_word = {rk3[23:0], rk3[31:24]};
// sub_word = {sbox_byte0, sbox_byte1, sbox_byte2, sbox_byte3};
// T_word = sub_word ^ rcon_out;
```
- must_appear:
  - RotWord function
  - SubWord assembly
  - T_word (SubWord XOR rcon_out)
- may_appear:
  - nothing else
- retrieval_focus:
  - transformation key word

### Block
- block_id: B4
- block_label: comb_key_next
- block_kind: comb
- required: true
- purpose: Compute next round key words using current registers and T_word according to the AES key expansion recurrence.
- code_shape: combinational assignment group
- depends_on: [B1, B3]
- placeholder:
```verilog
// skeleton only: next round key word computation
// rk0_next = rk0 ^ T_word;
// rk1_next = rk1 ^ rk0_next;
// rk2_next = rk2 ^ rk1_next;
// rk3_next = rk3 ^ rk2_next;
```
- must_appear:
  - rk0_next, rk1_next, rk2_next, rk3_next equations
- may_appear:
  - nothing else
- retrieval_focus:
  - key expansion arithmetic

### Block
- block_id: B5
- block_label: seq_reg_update
- block_kind: seq
- required: true
- purpose: On each rising clock edge, load the initial key (when kld=1) or update with computed next round key words (when kld=0).
- code_shape: always_ff with synchronous mux
- depends_on: [B1, B4]
- placeholder:
```verilog
// skeleton only: register update process
// always @(posedge clk) begin
//   if (kld) begin
//     rk0 <= key[127:96];
//     rk1 <= key[95:64];
//     rk2 <= key[63:32];
//     rk3 <= key[31:0];
//   end else begin
//     rk0 <= rk0_next;
//     rk1 <= rk1_next;
//     rk2 <= rk2_next;
//     rk3 <= rk3_next;
//   end
// end
```
- must_appear:
  - kld-controlled mux
  - synchronous update of rk0..rk3
- may_appear:
  - no reset handling (none specified)
- retrieval_focus:
  - state transition logic

### Block
- block_id: B6
- block_label: output_assign
- block_kind: comb
- required: true
- purpose: Assign output ports directly from the current register values.
- code_shape: continuous assignment group
- depends_on: [B1]
- placeholder:
```verilog
// skeleton only: output assignments
// assign wo_0 = rk0;
// assign wo_1 = rk1;
// assign wo_2 = rk2;
// assign wo_3 = rk3;
```
- must_appear:
  - wo_0, wo_1, wo_2, wo_3 assignments
- may_appear:
  - nothing else
- retrieval_focus:
  - output connectivity

## 3. Behavioral Overlay

### Module-Level Behavioral Summary
- control_style: flag_driven
- semantic_modes:
  - MODE_LOAD: kld=1; load 128-bit input key into rk0..rk3; aes_rcon is reset; outputs reflect loaded values.
  - MODE_EXPAND: kld=0; each clock cycle compute next round key and update registers; outputs reflect new round key.
- state_model:
  - object: rk0..rk3 (four 32-bit registers)
    storage_kind: registered
    representation: 32-bit words, most significant bits correspond to higher byte indices
    notes: updated synchronously on posedge clk; initial state after power-up is undefined; first kld load defines the initial round key.
  - object: rcon internal state (managed by aes_rcon)
- global_invariants:
  - When kld=1, wo_0..wo_3 equal the input key portions.
  - When kld=0, wo_0..wo_3 present the current round key, updated once per clock cycle.
  - All combinational paths (RotWord, SubWord, XOR) are purely combinational and must meet timing between registers.
- open_semantic_questions:
  - Exact cycle relationship between kld deassertion and first expanded key output not explicitly specified; code assumes immediate one-cycle update.
  - Stable kld deassertion relative to clk edge for expansion start not fully detailed; no extra synchronization described.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide register declarations and intermediate signal containers.
- timing_semantics: none (declaration only)
- touched_objects: rk0..rk3, all next-wires, rot_word, sbox_byte*, rcon_out, T_word
- coupling_rules:
  - All downstream blocks reference these declared objects.
- forbidden_drift:
  - Do not introduce extra storage beyond the four 32-bit registers.

- block_id: B2
- responsibilities:
  - Instantiate aes_rcon and aes_sbox and connect them to declared wires.
- timing_semantics:
  - aes_sbox instances: purely combinational, output valid after propagation delay.
  - aes_rcon: synchronously updates output on clk edge; rcon_out treated as wire.
- touched_objects: rcon_out, rot_word, sbox_byte*
- coupling_rules:
  - rcon_out from aes_rcon drives B3.
  - rot_word from B3 drives sbox byte inputs.
- forbidden_drift:
  - Do not instantiate more than 4 sbox or more than 1 rcon; do not add extra control into submodules.

- block_id: B3
- responsibilities:
  - Compute RotWord, SubWord, and XOR with rcon to produce T_word.
- timing_semantics:
  - purely combinational; must settle within one clock period.
- touched_objects: rot_word, sbox_byte*, rcon_out, T_word
- coupling_rules:
  - Depends on rk3 (from B1/B5) and sbox outputs (from B2).
  - T_word is read by B4.
- forbidden_drift:
  - Do not add sequential state; do not reorder bytes incorrectly (must be one-byte left rotate of rk3).

- block_id: B4
- responsibilities:
  - Compute rk0_next, rk1_next, rk2_next, rk3_next from current registers and T_word.
- timing_semantics:
  - purely combinational.
- touched_objects: rk0_next, rk1_next, rk2_next, rk3_next
- coupling_rules:
  - Depends on rk0..rk3 and T_word (from B1, B3).
  - Produces next words for B5.
- forbidden_drift:
  - Do not alter the recurrence order; do not add extra terms.

- block_id: B5
- responsibilities:
  - Implement synchronous load/update of round key registers.
- timing_semantics:
  - On rising clk edge: if kld=1, load key portion; else load next words.
  - No asynchronous reset.
- touched_objects: rk0, rk1, rk2, rk3
- coupling_rules:
  - Reads key input and next words from B4.
  - Writes to rk* which feed back to B3, B4, B6.
- forbidden_drift:
  - Do not add hidden state or counters; do not introduce a reset signal; do not add extra clock edges.

- block_id: B6
- responsibilities:
  - Drive output ports with current register values.
- timing_semantics:
  - continuous assignment, purely combinational.
- touched_objects: wo_0, wo_1, wo_2, wo_3
- coupling_rules:
  - Depends on rk* from B1/B5.
- forbidden_drift:
  - Do not gate or delay outputs; always reflect current rk*.

## 4. Decision Ledger

### Chosen Decision
- topic: module structure decomposition
- decision: Separate design into declaration, instantiation, combinational transformation, combinational key expansion, sequential register update, and output assignment blocks.
- reason: Aligns blocks with well-defined design roles, eases future retrieval and merge.

### Deferred Decision
- items:
  - Exact port mapping names for submodule instances (e.g., sbox_inst0..inst3) – deferred to implementation.
  - Timing assumption that combinational S-box propagation completes within one clock cycle – must be verified physically.
  - Whether to use explicit wire names for each sbox output or a vector – deferred to local generation.
  - Handling of undefined register values before first kld – not required by top-level usage; left unspecified.

### Structural Risk
- items:
  - The purely combinational expansion chain (B3→B4→B5) may create a long critical path if not pipelined; spec does not mention pipelining, so risk accepted.
  - The sequential block (B5) combines load and expand logic; no explicit load sequencing counter matches spec but may cause confusion if used incorrectly in top-level.

### Behavioral Risk
- items:
  - Initial register state after power-up is undefined; top-level must assert kld to load initial key before relying on outputs.
  - The exact round constant value when kld=1 depends on aes_rcon’s reset behavior; must match expected first expansion constant (e.g., 0x01000000) as required by the AES standard.
  - Undocumented cycle-level timing between kld deassertion and first expanded key output could lead to off-by-one errors if not handled by the integrator.