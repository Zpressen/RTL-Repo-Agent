# E203 Instruction Fetch Unit System Design Specification

This specification describes the complete instruction fetch behavior required by the E203 processor. It covers program-counter generation, instruction-fetch flow control, pipeline flush and halt handling, instruction holding, preliminary instruction decoding, static branch prediction, memory-target selection, ICB transactions, instruction alignment, cross-lane assembly, error propagation, and the interface to the execution stage.

Internal design partitioning is intentionally unspecified. The behavioral sections below do not define internal RTL module names, module boundaries, submodule interfaces, instance relationships, instance counts, or ownership of responsibilities. State names and internal signal names retained from the original functional descriptions are symbolic terms used to specify sequencing and data dependencies only.

Only the top-level design-unit name `e203_ifu` and its external interface are fixed. An implementation may merge, split, or share the described behavior and may choose its own internal hierarchy, state encodings, storage organization, and internal handshakes, provided that the externally observable behavior remains equivalent.

---

## 1. System Context and Top-Level Interface

### 1.1 Introduction

The instruction fetch unit is the interface between the execution pipeline and the instruction storage targets of the E203 processor. It implements the complete instruction fetch pipeline, including the following main steps:

1. Generate the current fetch address and update the address of the next instruction according to reset, sequential execution, predicted control flow, or pipeline flush.
2. Route each fetch operation to ITCM or system memory according to the address region.
3. Receive storage responses and assemble complete 32-bit or 16-bit instructions, including instructions that cross a target lane boundary.
4. Hold the fetched instruction, its PC, preliminary register indices, prediction result, and error status until the execution stage accepts them.
5. Stop issuing new requests for a halt request and acknowledge the halt after outstanding instruction transactions are complete.

The unit supports the RV32C compressed instruction set. Consequently, valid instruction PCs are halfword aligned and sequential PC increments are either two or four bytes according to instruction length.

### 1.2 System and Clock Interface

| Signal Name | Direction | Bit Width | Description |
| --- | --- | --- | --- |
| `clk` | Input | 1 | System clock used for all synchronous IFU operations. |
| `rst_n` | Input | 1 | Asynchronous active-low reset. Assertion resets the applicable state; normal operation resumes after deassertion. |
| `inspect_pc` | Output | `E203_PC_SIZE` | Current PC value for inspection, debugging, or monitoring. |
| `ifu_active` | Output | 1 | IFU activity indication. The IFU is always active at block level and this output is tied high. |
| `itcm_nohold` | Input | 1 | Disables use of a previously held ITCM read lane when asserted. |
| `pc_rtvec` | Input | `E203_PC_SIZE` | Reset-vector address used for the first fetch after reset. |

### 1.3 Execution-Stage Interface

| Signal Name | Direction | Bit Width | Description |
| --- | --- | --- | --- |
| `ifu_o_ir` | Output | `E203_INSTR_SIZE` | Instruction register data presented to the execution stage. |
| `ifu_o_pc` | Output | `E203_PC_SIZE` | PC associated with the presented instruction. |
| `ifu_o_pc_vld` | Output | 1 | Indicates that the associated PC value is valid. |
| `ifu_o_misalgn` | Output | 1 | Instruction-fetch misalignment indication. It is always zero in the RV32C configuration. |
| `ifu_o_buserr` | Output | 1 | Bus error associated with the presented instruction. |
| `ifu_o_rs1idx` | Output | `E203_RFIDX_WIDTH` | Preliminary index of source register RS1. |
| `ifu_o_rs2idx` | Output | `E203_RFIDX_WIDTH` | Preliminary index of source register RS2. |
| `ifu_o_prdt_taken` | Output | 1 | Prediction indication associated with the instruction. |
| `ifu_o_muldiv_b2b` | Output | 1 | Indicates a recognized back-to-back multiply/divide sequence. |
| `ifu_o_valid` | Output | 1 | Output instruction and metadata are valid. |
| `ifu_o_ready` | Input | 1 | Execution stage is ready to accept the output instruction and metadata. |

The output transfer occurs when `ifu_o_valid && ifu_o_ready` is true. While `ifu_o_valid` is asserted and `ifu_o_ready` is low, the instruction and all metadata associated with it shall remain available and shall not be replaced by a later instruction.

### 1.4 Pipeline-Control Interface

| Signal Name | Direction | Bit Width | Description |
| --- | --- | --- | --- |
| `pipe_flush_req` | Input | 1 | Pipeline flush request. |
| `pipe_flush_ack` | Output | 1 | Flush acknowledgment. The supplied behavior accepts a flush immediately and keeps this output asserted. |
| `pipe_flush_add_op1` | Input | `E203_PC_SIZE` | First operand for flush-PC calculation when timing boost is not selected. |
| `pipe_flush_add_op2` | Input | `E203_PC_SIZE` | Second operand for flush-PC calculation when timing boost is not selected. |
| `pipe_flush_pc` | Input | `E203_PC_SIZE` | Direct flush PC, present when `E203_TIMING_BOOST` is defined. |

### 1.5 ITCM Interface

The following ports are present when `E203_HAS_ITCM` is defined.

| Signal Name | Direction | Bit Width | Description |
| --- | --- | --- | --- |
| `ifu2itcm_holdup` | Input | 1 | Indicates that the ITCM lane returned by the last IFU access remains held and has not been changed by another agent. |
| `itcm_region_indic` | Input | `E203_ADDR_SIZE` | ITCM address-region indication. |
| `ifu2itcm_icb_cmd_valid` | Output | 1 | ITCM command valid. |
| `ifu2itcm_icb_cmd_ready` | Input | 1 | ITCM command ready. |
| `ifu2itcm_icb_cmd_addr` | Output | `E203_ITCM_ADDR_WIDTH` | ITCM transaction address. |
| `ifu2itcm_icb_rsp_valid` | Input | 1 | ITCM response valid. |
| `ifu2itcm_icb_rsp_ready` | Output | 1 | IFU ready to accept the ITCM response. |
| `ifu2itcm_icb_rsp_err` | Input | 1 | ITCM response error. |
| `ifu2itcm_icb_rsp_rdata` | Input | `E203_ITCM_DATA_WIDTH` | Naturally aligned ITCM response data. |

### 1.6 System-Memory Interface

The following ports are present when `E203_HAS_MEM_ITF` is defined.

| Signal Name | Direction | Bit Width | Description |
| --- | --- | --- | --- |
| `ifu2biu_icb_cmd_valid` | Output | 1 | System-memory command valid. |
| `ifu2biu_icb_cmd_ready` | Input | 1 | System-memory command ready. |
| `ifu2biu_icb_cmd_addr` | Output | `E203_ADDR_SIZE` | System-memory transaction address. |
| `ifu2biu_icb_rsp_valid` | Input | 1 | System-memory response valid. |
| `ifu2biu_icb_rsp_ready` | Output | 1 | IFU ready to accept the system-memory response. |
| `ifu2biu_icb_rsp_err` | Input | 1 | System-memory response error. |
| `ifu2biu_icb_rsp_rdata` | Input | `E203_SYSMEM_DATA_WIDTH` | Naturally aligned system-memory response data. |

### 1.7 Halt and Dependency Inputs

| Signal Name | Direction | Bit Width | Description |
| --- | --- | --- | --- |
| `ifu_halt_req` | Input | 1 | Requests that instruction fetching stop. |
| `ifu_halt_ack` | Output | 1 | Indicates that no new fetch is being issued and the outstanding access has returned or is otherwise safe to quiesce. |
| `oitf_empty` | Input | 1 | Indicates that the outstanding-instruction tracking FIFO in the execution unit is empty. |
| `rf2ifu_x1` | Input | `E203_XLEN` | Current value of register x1. |
| `rf2ifu_rs1` | Input | `E203_XLEN` | Current value of the requested RS1 register. |
| `dec2ifu_rs1en` | Input | 1 | The instruction currently in the execution-facing IR stage uses RS1. |
| `dec2ifu_rden` | Input | 1 | The instruction currently in the execution-facing IR stage writes a destination register. |
| `dec2ifu_rdidx` | Input | `E203_RFIDX_WIDTH` | Destination-register index of the instruction in the IR stage. |
| `dec2ifu_mulhsu` | Input | 1 | Previous instruction is MULH, MULHU, or MULHSU. |
| `dec2ifu_div` | Input | 1 | Previous instruction is DIV. |
| `dec2ifu_rem` | Input | 1 | Previous instruction is REM. |
| `dec2ifu_divu` | Input | 1 | Previous instruction is DIVU. |
| `dec2ifu_remu` | Input | 1 | Previous instruction is REMU. |

### 1.8 Configuration Terms

| Name | Description |
| --- | --- |
| `E203_PC_SIZE` | Program-counter width. |
| `E203_ADDR_SIZE` | System address width. |
| `E203_INSTR_SIZE` | Instruction container width; 32 in the supplied configuration. |
| `E203_XLEN` | Integer data-path width; 32 in the supplied configuration. |
| `E203_RFIDX_WIDTH` | Integer register-index width. |
| `E203_HAS_ITCM` | Includes the ITCM target interface and ITCM address-region selection. |
| `E203_HAS_MEM_ITF` | Includes the system-memory target interface. |
| `E203_ITCM_ADDR_WIDTH` | Width of the ITCM-local address port. |
| `E203_ITCM_DATA_WIDTH` | ITCM read-lane width; supported descriptions cover 32 and 64 bits. |
| `E203_SYSMEM_DATA_WIDTH` | System-memory read-lane width; supported descriptions cover 32 and 64 bits. |
| `E203_TIMING_BOOST` | Selects direct `pipe_flush_pc` use for the flush critical path. |
| `E203_HAS_FPU` | Enables optional FPU-related preliminary register-index handling. When absent, all preliminary FPU indications are zero. |
| `E203_HAS_NICE` | May enable NICE decode connections in the shared instruction decoder; those outputs are unused by the IFU-specific preliminary decode behavior. |

At least one instruction-fetch target, ITCM or system memory, shall be present. ITCM and system-memory data widths described by this specification are 32 or 64 bits.

---

## 2. Handshake and Persistent-State Conventions

### 2.1 Ready/Valid Handshake

The system uses ready/valid handshaking throughout the request, response, and execution-output paths. A transfer is accepted only when valid and ready are both high in the same cycle.

The handshake protocol participates in four activities:

1. Issuing an instruction-fetch operation.
2. Accepting the corresponding storage response.
3. Presenting an instruction and its metadata to the execution stage.
4. Accepting and retaining a pipeline flush that cannot immediately produce a new storage request.

A producer shall hold valid and its associated payload stable until the handshake. A consumer may apply backpressure for an arbitrary number of cycles. The storage response is therefore not required to arrive in the cycle immediately following its command.

For the behavioral equations below, the following symbolic events are used:

- `fetch_req_hsked`: a system-level fetch request is accepted.
- `fetch_rsp_hsked`: a complete aligned instruction response is accepted by the PC/IR control behavior.
- `ir_o_hsked`: `ifu_o_valid && ifu_o_ready`.
- `pipe_flush_hsked`: `pipe_flush_req && pipe_flush_ack`.
- `icb_cmd_hsked`: a selected external ICB command is accepted.
- `icb_rsp_hsked`: the response of the selected external ICB target is accepted.

These names are behavioral notation and do not define internal ports.

### 2.2 Set/Clear State Convention

Several persistent conditions use a set/clear form. For a symbolic state `state_r`:

- `state_set` identifies the event that makes the condition active.
- `state_clr` identifies the event that clears it.
- `state_ena = state_set | state_clr`.
- `state_nxt = state_set | (~state_clr)`.

When set and clear occur in the same cycle, the set condition has priority. This rule is required for back-to-back activity and replaces the incorrect assumption that all corresponding set and clear events are mutually exclusive.

All resettable persistent state described below is reset by active-low `rst_n`. Storage that does not require a defined reset value shall not be observed as valid until its accompanying valid state has been established.

---

## 3. Reset, Halt, and Pipeline Flush Behavior

### 3.1 Reset Request and First Fetch

Reset handling generates a synchronized indication that the unit has just been reset. The reset indication is initialized active by reset and becomes inactive during normal clocked operation.

A pending reset fetch is set when the synchronized reset indication is active and no reset fetch is already pending. It is cleared when the reset fetch request is accepted. The resulting reset request remains asserted until the request handshake, preventing the first request from being lost under memory backpressure.

For a reset request:

- The PC adder base is `pc_rtvec`.
- The PC adder offset is zero.
- The generated address is halfword aligned.
- The request is marked non-sequential.
- The reset request may issue even though normal speculative fetching is inhibited during reset recovery.

This sequence ensures that the first instruction fetch after reset is directed to the reset vector and that normal sequential fetching resumes only after the reset operation has entered the normal request flow.

### 3.2 Halt Acknowledgment

When `ifu_halt_req` is asserted, no new ordinary fetch request is generated. An outstanding request is allowed to complete.

The halt acknowledgment is set when all of the following conditions hold:

1. `ifu_halt_req` is asserted.
2. `ifu_halt_ack` is not already asserted.
3. There is no outstanding request, or the outstanding response has returned and is visible as valid.

Treating a returned response as sufficient to quiesce avoids a deadlock in which a halt waits for an execution-stage handshake while the execution stage is itself waiting for the IFU to stop.

The acknowledgment remains asserted while the request remains asserted. It is cleared after `ifu_halt_req` is deasserted. Fetching resumes only after the halt request has been removed.

### 3.3 Immediate Flush Acknowledgment

`pipe_flush_ack` is asserted continuously. A pipeline flush is therefore accepted immediately and does not create a combinational ready path from the memory or execution system back into pipeline control.

Ideally, a flush would be acknowledged only when a new fetch request could be accepted or when an old response had returned. To cut that timing loop, the system always acknowledges the flush. If the fetch path cannot issue the redirected request in the same cycle, it records a delayed-flush indication.

### 3.4 Delayed Flush Retention

The delayed-flush indication is set when `pipe_flush_req` is asserted but a redirected fetch request is not accepted. It is cleared when the delayed redirected request is eventually accepted.

The real flush condition used throughout the fetch flow is the logical OR of the current external flush request and the delayed-flush indication. This behavior ensures that a flush operation is not lost when the instruction fetch path is temporarily unable to accept a new request.

Even if a delayed flush is already pending, a new external flush request may still be accepted. The PC update associated with the current flush is performed immediately; the delayed indication retains the need to issue a request from the already-updated redirected PC.

### 3.5 Flush Effects

A flush has the following effects:

1. It enables a PC update.
2. It clears any valid instruction currently held for the execution stage.
3. It causes any concurrently returned stale response to be accepted and discarded rather than installed as the next instruction.
4. It marks the redirected request as non-sequential.
5. It suppresses normal instruction installation until the real flush condition has cleared.

When `E203_TIMING_BOOST` is not defined, the flush target is calculated from `pipe_flush_add_op1 + pipe_flush_add_op2`, then forced to halfword alignment.

When `E203_TIMING_BOOST` is defined:

- A current flush selects `{pipe_flush_pc[E203_PC_SIZE-1:1], 1'b0}` directly.
- A delayed flush selects the already-updated and halfword-aligned current PC.
- Other PC sources continue to use the normal PC adder result.

---

## 4. Instruction Holding and Execution-Stage Flow

### 4.1 Instruction Validity

The instruction-valid state is set when a complete aligned fetch response handshakes and neither a real flush nor a replay condition applies.

Symbolically:

```text
ir_valid_set = fetch_rsp_hsked
             & ~pipe_flush_req_real
             & ~fetch_rsp_need_replay
```

The instruction-valid state is cleared when either:

- The execution stage accepts the current instruction, or
- A pipeline flush is accepted while an instruction is valid.

```text
ir_valid_clr = ir_o_hsked
             | (pipe_flush_hsked & ir_valid_r)
```

The valid state uses set priority when set and clear occur together. Therefore a back-to-back accepted response may replace an instruction that the execution stage accepts in the same cycle, provided no flush suppresses the new response.

`ifu_o_valid` reflects this persistent instruction-valid state.

### 4.2 Instruction-Input Readiness

The instruction holding position is ready to accept a new instruction when it is empty or when its current instruction is being cleared:

```text
ir_input_ready = ~ir_valid_r | ir_valid_clr
```

In normal operation, a complete fetch response is accepted only if:

1. The instruction holding position is ready.
2. The fetch-request path is ready to maintain the intended back-to-back flow.
3. Branch-prediction dependency handling is not waiting.

During a real pipeline flush, the response path is ready regardless of these normal conditions so that a stale response cannot block redirection.

### 4.3 PC Validity

The PC-valid state is managed separately from instruction validity because a newly selected PC may be pending before it is installed alongside a response.

The PC-valid state is set when:

- A new PC is pending.
- The instruction holding position is ready.
- No real flush is active.
- No replay is required.

```text
ir_pc_vld_set = pc_new_pending
              & ir_input_ready
              & ~pipe_flush_req_real
              & ~fetch_rsp_need_replay
```

It is cleared under the same conditions that clear instruction validity. `ifu_o_pc_vld` reflects this state.

### 4.4 Instruction Storage

The returned instruction is stored in two 16-bit portions:

- The low half, bits `[15:0]`, is updated whenever a new valid instruction is installed.
- The high half, bits `[31:16]`, is updated only when the incoming instruction is identified as a 32-bit instruction.

This segmented update reduces unnecessary switching for compressed 16-bit instructions. For a valid 16-bit instruction, only the low half is semantically relevant; the high half may retain its previous stored value.

### 4.5 Associated Metadata

The following values are captured when a new instruction is installed and remain associated with that instruction until replacement:

- Fetch error, from the aligned fetch response error.
- Static prediction result.
- Back-to-back multiply/divide indication.
- PC corresponding to the accepted fetch.
- Preliminary RS1 and RS2 register indices when their respective enable conditions apply.

`ifu_o_buserr`, `ifu_o_prdt_taken`, `ifu_o_muldiv_b2b`, `ifu_o_pc`, `ifu_o_rs1idx`, and `ifu_o_rs2idx` reflect these stored values.

The source-register index state changes only when needed. For a non-FPU instruction, RS1 is updated when the new instruction uses RS1 or when branch prediction explicitly requests a general RS1 register read. RS2 is updated when the new instruction uses RS2. When FPU support is absent, all preliminary FPU classifications and indices are treated as zero.

### 4.6 Misalignment and Bus Errors

Instruction-fetch misaligned exceptions are not possible for the supported RV32C configuration because the generated PC is always halfword aligned. Therefore:

```text
ifu_o_misalgn = 1'b0
```

A storage error is not reported as an unrelated global condition. It is captured with the instruction returned by the corresponding request and presented as `ifu_o_buserr` while that instruction is valid.

### 4.7 PC-Pending Tracking

A symbolic PC-pending condition records that the current PC has been updated but has not yet been loaded alongside an execution-facing instruction.

- It is set whenever the PC update enable is asserted.
- It is cleared when the PC is installed into the instruction holding state.
- If set and clear occur together, set has priority.

This condition keeps the PC metadata synchronized with response installation under backpressure and back-to-back operation.

---

## 5. Program-Counter and Fetch-Request Control

### 5.1 PC Update Enable

The current PC is updated when either a fetch request handshakes or a pipeline flush is accepted:

```text
pc_ena = fetch_req_hsked | pipe_flush_hsked
```

`inspect_pc` is the stored current PC. The address proposed for the next fetch is the selected and aligned next PC.

### 5.2 Sequential Increment

The sequential increment depends on the length of the instruction being decoded:

```text
pc_incr_offset = instruction_is_32bit ? 4 : 2
```

The request is marked sequential only when it is not caused by any of the following:

- A current or delayed pipeline flush.
- The reset-vector fetch.
- A replay request.
- A predicted taken branch or jump.

The request also carries the current PC as the last accessed PC and the preliminary 32-bit instruction-length indication. These behavioral attributes are used by the lane-reuse rules described later and do not prescribe an internal interface.

### 5.3 PC Adder Operand Selection

When timing boost is not enabled, the first PC-adder operand is selected with the following priority:

1. `pipe_flush_add_op1` for a current flush.
2. The current PC for a delayed flush.
3. The current PC for a replay.
4. The predicted base operand for a predicted taken branch or jump.
5. `pc_rtvec` for a reset fetch.
6. The current PC for ordinary sequential execution.

The second operand is selected with corresponding priority:

1. `pipe_flush_add_op2` for a current flush.
2. Zero for a delayed flush.
3. Zero for a replay.
4. The decoded branch/jump immediate for a predicted taken branch or jump.
5. Zero for a reset fetch.
6. The two- or four-byte sequential increment.

When timing boost is enabled, the direct flush target selection described in Section 3 replaces only the current-flush critical path. Replay, prediction, reset, and sequential selection retain the same relative priority.

The adder result is always forced to halfword alignment:

```text
pc_nxt = {pc_nxt_pre[E203_PC_SIZE-1:1], 1'b0}
```

### 5.4 Ordinary Request Generation

An ordinary new fetch may be generated only when:

1. Preliminary branch prediction is not waiting for a register dependency.
2. `ifu_halt_req` is not asserted.
3. Reset recovery is no longer actively suppressing ordinary speculation.
4. The current response does not require replay.

The combined request sources are:

- Ordinary new fetch.
- Pending reset-vector fetch.
- Current or delayed flush.
- Replay request, if replay is implemented.

The supplied behavior fixes both replay indications inactive and reserves them for future expansion.

### 5.5 Outstanding-Request Control

At most one system-level fetch request is outstanding.

- The outstanding condition is set when a new fetch request handshakes.
- It is cleared when the corresponding complete fetch response handshakes.
- If a new request and the previous response handshake in the same cycle, set has priority, permitting back-to-back fetch flow without losing the new outstanding state.

A new request may become valid when no request is outstanding or when the previous response is being accepted in the current cycle.

For halt detection, the system is treated as having no blocking outstanding work when the outstanding flag is clear or when the response has already returned as valid. This special rule avoids waiting for an execution handshake during halt.

### 5.6 Response Readiness

During a pipeline flush, the complete-response path is ready so that stale work can drain and be discarded.

Otherwise, complete-response readiness requires:

- The instruction holding position is ready.
- The request path is ready for the intended fetch sequencing.
- Branch prediction is not waiting.

The response must obey ready/valid flow control and may remain valid under backpressure. There is no fixed one-cycle response-latency requirement.

---

## 6. Preliminary Instruction Decoding

### 6.1 Purpose and Scope

The instruction fetch flow performs preliminary decoding of the fetched instruction before it is installed in the execution-facing instruction register. This decoding focuses on the information required by fetch control:

- Whether the instruction is 32 bits or 16 bits.
- Whether RS1 and RS2 are used, and their register indices.
- Whether the instruction is JAL, JALR, or a conditional branch.
- The branch/jump immediate and the JALR RS1 index.
- Whether the instruction is MULH-family, MUL, DIV, REM, DIVU, or REMU.

The behavior is combinational and has no clock-domain crossing. It does not require the IFU to expose a complete execution information bus, perform execution-stage legality reporting, or duplicate unrelated ALU, AGU, CSR, or custom-extension control.

### 6.2 Instruction Length

`dec_rv32` is high for a 32-bit instruction and low for a 16-bit compressed instruction. The decoded length controls:

1. The sequential PC increment, four bytes for a 32-bit instruction and two bytes for a compressed instruction.
2. Whether the high 16 bits of the execution-facing instruction storage are updated.
3. Lane-reuse address calculation for a sequential fetch.

The supported compressed encodings occupy RVC quadrants whose low two opcode bits are `00`, `01`, or `10`. Ordinary 32-bit instruction encodings use low opcode bits `11` within the supported RV32 instruction space.

### 6.3 RV32 Register Fields

For a 32-bit instruction:

| Bit Range | Field | Description |
| --- | --- | --- |
| `[31:25]` | `funct7` | Major operation extension. |
| `[24:20]` | `rs2` | Source register 2. |
| `[19:15]` | `rs1` | Source register 1. |
| `[14:12]` | `funct3` | Sub-operation. |
| `[11:7]` | `rd` | Destination register. |
| `[6:0]` | `opcode` | Major opcode. |

When a 32-bit instruction uses RS1 or RS2, the corresponding preliminary index is taken from these fields.

### 6.4 RV32 Branch and Jump Classification

The following encodings are relevant to fetch control:

| Instruction Class | Opcode | Additional Field | Preliminary Result |
| --- | --- | --- | --- |
| JAL | `1101111` | — | `dec_jal=1`, branch/jump indication set. |
| JALR | `1100111` | `funct3=000` for the standard instruction | `dec_jalr=1`, branch/jump indication set. |
| Conditional branch | `1100011` | `funct3` selects BEQ, BNE, BLT, BGE, BLTU, or BGEU | `dec_bxx=1`, branch/jump indication set. |

`dec_bjp` is the logical OR of the JAL, JALR, and conditional-branch classifications.

The preliminary decoder does not determine the actual outcome of a conditional branch. It supplies the instruction classification and immediate to the static prediction behavior.

### 6.5 RV32 Branch and Jump Immediates

For an SB-type conditional branch, the sign-extended immediate is assembled from:

| Immediate Bit | Instruction Source |
| --- | --- |
| `imm[12]` | instruction bit `[31]` |
| `imm[10:5]` | instruction bits `[30:25]` |
| `imm[4:1]` | instruction bits `[11:8]` |
| `imm[11]` | instruction bit `[7]` |
| `imm[0]` | `0` |

For JAL, the sign-extended UJ immediate is assembled from:

| Immediate Bit | Instruction Source |
| --- | --- |
| `imm[20]` | instruction bit `[31]` |
| `imm[10:1]` | instruction bits `[30:21]` |
| `imm[11]` | instruction bit `[20]` |
| `imm[19:12]` | instruction bits `[19:12]` |
| `imm[0]` | `0` |

For JALR, the branch/jump immediate is the sign extension of instruction bits `[31:20]`. The JALR source-register index is instruction bits `[19:15]`.

### 6.6 RV32 Multiply and Divide Classification

The following RV32M encodings are used for the back-to-back indication when `E203_SUPPORT_MULDIV` is enabled. All use opcode `0110011` and `funct7=0000001`.

| Instruction | `funct3` | Preliminary Result |
| --- | --- | --- |
| MUL | `000` | `dec_mul=1` |
| MULH | `001` | MULH-family indication set |
| MULHSU | `010` | MULH-family indication set |
| MULHU | `011` | MULH-family indication set |
| DIV | `100` | `dec_div=1` |
| DIVU | `101` | `dec_divu=1` |
| REM | `110` | `dec_rem=1` |
| REMU | `111` | `dec_remu=1` |

The MULH-family indication consumed from the previous execution-facing instruction is true for MULH, MULHSU, or MULHU.

### 6.7 Compressed Register Encoding

Compressed register fields marked with a prime select registers x8 through x15:

| RVC Field | `000` | `001` | `010` | `011` | `100` | `101` | `110` | `111` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Integer register | x8 | x9 | x10 | x11 | x12 | x13 | x14 | x15 |

Other compressed instruction formats use the full five-bit register fields defined by their encoding. The preliminary RS1 and RS2 outputs reflect the source registers actually used by the compressed instruction. An enable is not asserted merely because an instruction bit field happens to occupy the same bit positions.

### 6.8 Compressed Branch and Jump Classification

The following compressed instructions affect fetch prediction:

| Quadrant | `funct3` | Instruction | Preliminary Result |
| --- | --- | --- | --- |
| `01` | `001` | C.JAL | JAL classification |
| `01` | `101` | C.J | JAL classification |
| `01` | `110` | C.BEQZ | Conditional-branch classification |
| `01` | `111` | C.BNEZ | Conditional-branch classification |
| `10` | `100`, bit 12=`0`, bits `[6:2]=0`, rs1 nonzero | C.JR | JALR classification |
| `10` | `100`, bit 12=`1`, bits `[6:2]=0`, rs1 nonzero | C.JALR | JALR classification |

C.JR and C.JALR use the register in instruction bits `[11:7]` as the JALR source register. Their immediate is zero.

### 6.9 Compressed Jump Immediate

For C.J and C.JAL, the sign-extended jump immediate uses the encoded ordering:

```text
imm[11]   <- instr[12]
imm[4]    <- instr[11]
imm[9:8]  <- instr[10:9]
imm[10]   <- instr[8]
imm[6]    <- instr[7]
imm[7]    <- instr[6]
imm[3:1]  <- instr[5:3]
imm[5]    <- instr[2]
imm[0]    <- 0
```

For C.BEQZ and C.BNEZ, the sign-extended branch immediate uses:

```text
imm[8]    <- instr[12]
imm[4:3]  <- instr[11:10]
imm[7:6]  <- instr[6:5]
imm[2:1]  <- instr[4:3]
imm[5]    <- instr[2]
imm[0]    <- 0
```

### 6.10 Preliminary Decode Outputs

The preliminary decode behavior supplies the following symbolic results to the rest of the IFU behavior:

| Result | Meaning |
| --- | --- |
| `dec_rs1en` | Instruction requires integer source register 1. |
| `dec_rs2en` | Instruction requires integer source register 2. |
| `dec_rs1idx` | Decoded integer RS1 index. |
| `dec_rs2idx` | Decoded integer RS2 index. |
| `dec_mulhsu` | Instruction is MULH, MULHSU, or MULHU. |
| `dec_mul` | Instruction is MUL. |
| `dec_div` | Instruction is DIV. |
| `dec_rem` | Instruction is REM. |
| `dec_divu` | Instruction is DIVU. |
| `dec_remu` | Instruction is REMU. |
| `dec_rv32` | Instruction length is 32 bits. |
| `dec_bjp` | Instruction is a JAL, JALR, or conditional branch. |
| `dec_jal` | Instruction is JAL, C.JAL, or C.J. |
| `dec_jalr` | Instruction is JALR, C.JALR, or C.JR. |
| `dec_bxx` | Instruction is an RV32 branch, C.BEQZ, or C.BNEZ. |
| `dec_jalr_rs1idx` | Source register used to calculate a JALR target. |
| `dec_bjp_imm` | Sign-extended immediate for the classified branch or jump. |

Inputs unrelated to preliminary fetch decisions, including execution PC, prior prediction result, execution misalignment, execution bus error, and debug mode, do not alter these IFU-specific outputs.

### 6.11 Back-to-Back Multiply/Divide Recognition

The next instruction is marked as a supported back-to-back multiply/divide case when all of the following are true:

1. Its instruction class and the previous instruction class form one of these pairs:
   - Previous MULH/MULHU/MULHSU followed by current MUL.
   - Previous REM followed by current DIV.
   - Previous DIV followed by current REM.
   - Previous REMU followed by current DIVU.
   - Previous DIVU followed by current REMU.
2. The previous and current RS1 indices match.
3. The previous and current RS2 indices match.
4. Neither previous source-register index is equal to the previous destination-register index.

The result is captured with the new instruction and presented on `ifu_o_muldiv_b2b`.

---

## 7. Static Branch Prediction and Register Dependencies

### 7.1 Prediction Strategy

The branch prediction behavior uses a simple static strategy:

- JAL is an unconditional jump and is always predicted taken.
- JALR is an unconditional jump and is always predicted taken.
- A conditional branch with a negative offset, representing a backward branch, is predicted taken.
- A conditional branch with a nonnegative offset, representing a forward branch, is predicted not taken.

Symbolically:

```text
prdt_taken = dec_jal
           | dec_jalr
           | (dec_bxx & dec_bjp_imm[E203_XLEN-1])
```

### 7.2 Predicted Target Operands

The predicted PC is calculated from two operands.

The first operand is selected as follows:

1. For JAL or a conditional branch, use the current PC.
2. For JALR with `rs1=x0`, use zero.
3. For JALR with `rs1=x1`, use `rf2ifu_x1`.
4. For JALR with any other RS1, use `rf2ifu_rs1`.

The second operand is the low `E203_PC_SIZE` bits of the sign-extended decoded branch/jump immediate.

The final target passes through the common PC addition and halfword-alignment behavior.

### 7.3 JALR Source Classes

JALR source registers are divided into three classes:

- `rs1=x0`: the target base is known to be zero and has no register dependency.
- `rs1=x1`: the target base is supplied by the dedicated `rf2ifu_x1` input, but dependencies on pending instructions must be checked.
- `rs1=xn`, where xn is neither x0 nor x1: the general RS1 value must be obtained from `rf2ifu_rs1` after dependency conditions permit a read.

### 7.4 JALR x1 Dependency

A valid JALR using x1 is considered dependent when either:

1. `oitf_empty` is low, meaning the execution unit has an outstanding instruction that may update x1.
2. The current execution-facing instruction writes the same destination register as the JALR source register.

While this dependency exists, prediction asserts its wait condition and prevents a new fetch request. When the dependency is cleared, `rf2ifu_x1` may be used as the target base.

### 7.5 General JALR RS1 Dependency

A valid JALR using a register other than x0 or x1 is considered dependent when either the OITF is nonempty or the current execution-facing instruction is nonempty.

If only the IR-stage instruction creates the apparent dependency and `oitf_empty` is high, a general-register read may be initiated when:

- The IR instruction is being cleared, or
- The IR instruction does not use RS1.

This exception permits the read request to start; it does not remove the wait in that same cycle. The prediction waits during the read-request cycle so that `rf2ifu_rs1` is used only after the requested value is available.

### 7.6 General RS1 Read-State Management

A symbolic one-bit read state prevents repeated requests for the same JALR instruction.

The state is set when all of the following are true:

1. No general RS1 read is already active.
2. The decoded instruction is valid.
3. The instruction is JALR.
4. RS1 is neither x0 nor x1.
5. There is no dependency, or an IR-only dependency qualifies for the clearing exception above.

The state clears in the cycle after it is set. The set event produces the general RS1 read enable. Reset clears this state to zero.

### 7.7 Prediction Wait

The prediction wait indication is asserted when any of the following is true:

- A JALR x1 dependency exists.
- A general JALR RS1 dependency exists.
- A general RS1 read request is being initiated.

While prediction waits, the normal new-fetch condition is inhibited and the instruction response is not installed as a completed predicted instruction. This preserves the decoded instruction until the target base is safe to use.

### 7.8 Prediction Corner Cases

1. If the IR-stage instruction is being accepted in the same cycle, an IR-only dependency may be treated as clearing.
2. If the IR-stage instruction does not use RS1, it does not block the special general-JALR read once OITF is empty.
3. At most one general RS1 read is requested for a single held JALR instruction.
4. JAL and JALR classification are mutually exclusive for a valid instruction encoding.
5. The target address is always calculated when an instruction is predicted taken.

---

## 8. Fetch Targets, Lanes, and Instruction Assembly

### 8.1 Fetching Targets

A fetching target is an address region from which instructions may be read. The described targets are:

- ITCM, when present.
- System memory, when present.

ITCM and system-memory accesses are mutually exclusive for one command. If an address matches the configured ITCM region, the command is directed to ITCM. Otherwise, when the system-memory interface is present, the command is directed to system memory.

For ITCM selection, the high address region of the fetch address is compared with the corresponding high region of `itcm_region_indic`. The ITCM output address contains the low `E203_ITCM_ADDR_WIDTH` bits. The system-memory output retains the configured system address width.

The target selected for an accepted command is remembered until its response is consumed so that valid, data, and error are taken from the same target.

### 8.2 Definition of a Lane

A target lane is the naturally aligned quantity that a fetching target returns in one access.

- A 32-bit target reads one aligned 32-bit lane.
- A 64-bit target reads one aligned 64-bit lane.

A 32-bit instruction may begin at any halfword-aligned address. It may therefore be contained in one lane or may cross from the final halfword of one lane into the first halfword of the next lane.

### 8.3 Held Lane

A held lane is a previously returned lane that remains stable and can be reused without issuing another access.

ITCM may provide this behavior when `ifu2itcm_holdup` is asserted, the previous lane has not been changed by another agent, and `itcm_nohold` is low. System memory is assumed not to hold its previous response lane and is not reused through this mechanism.

### 8.4 Cross-Lane Detection

The current fetch crosses a lane boundary under the following target-specific conditions:

| Target lane width | Cross-lane condition |
| --- | --- |
| 32 bits | Fetch PC bit `[1]` is `1`. |
| 64 bits | Fetch PC bits `[2:1]` are `2'b11`. |

The condition is evaluated using the width of the selected target. ITCM width and system-memory width are handled independently.

### 8.5 Lane-Begin Detection

The current fetch begins at the first halfword of a lane under these conditions:

| Target lane width | Lane-begin condition |
| --- | --- |
| 32 bits | Fetch PC bit `[1]` is `0`. |
| 64 bits | Fetch PC bits `[2:1]` are `2'b00`. |

### 8.6 Same-Lane Sequential Reuse

A new fetch is treated as accessing the same previously accessed lane only for a sequential request.

- If the new request begins at a lane boundary, it is considered the same lane only when the previous sequential fetch crossed a boundary and therefore already accessed or prefetched the new lane.
- If the new request does not begin at the lane boundary, a sequential request is considered to use the same lane.
- Flush, reset, predicted branch/jump, and replay requests are non-sequential and are not treated as same-lane reuse cases.

### 8.7 Zero-, One-, and Two-Access Classification

The required number of external target accesses is classified from same-lane, crossing, and held-lane conditions.

**Zero-access case**:

```text
same lane & not cross lane & held lane
```

The instruction can be produced from the currently held target lane without issuing a new ICB command.

**Two-access case**:

```text
(same lane & cross lane & not held)
| (different lane & cross lane)
```

The current lane must be read to obtain its upper halfword, followed by a read of the next lane.

**One-access cases** include:

- A non-crossing request without reusable held data.
- A different-lane non-crossing request.
- A same-lane crossing request for which the current lane is held; the held upper halfword is saved and only the next lane is accessed.

### 8.8 Detailed Fetch Cases

#### 8.8.1 Same Lane, Crossing, Held

1. Save the upper 16 bits of the currently held lane as leftover data.
2. Issue one command for the next lane.
3. When the response returns, concatenate the next lane's low 16 bits above the leftover halfword.
4. Return the resulting 32-bit instruction.

#### 8.8.2 Same Lane, Crossing, Not Held

1. Issue a first command for the current lane.
2. Save the upper 16 bits of the first response and its error status.
3. Issue a second command for the next lane.
4. Concatenate the second response's low 16 bits above the saved halfword.
5. Merge the first and second response errors.

#### 8.8.3 Same Lane, Not Crossing, Held

1. Do not issue an external command.
2. Align the held lane according to the current PC.
3. Generate a complete internal response from the held data.

#### 8.8.4 Same Lane, Not Crossing, Not Held

1. Issue one command for the current lane.
2. Align the returned lane according to the request address.
3. Return the aligned instruction and response error.

#### 8.8.5 Different Lane, Crossing

1. Issue a first command for the lane containing the instruction's low halfword.
2. Save the upper 16 bits of that lane and its error indication.
3. Issue a second command for the next lane.
4. Concatenate the second lane's low 16 bits above the saved halfword.
5. Merge errors from both commands.

Held data from a different lane is not used to eliminate the first access.

#### 8.8.6 Different Lane, Not Crossing

1. Issue one command for the lane containing the fetch PC.
2. Align the returned data according to the PC.
3. Return the aligned instruction and error.

### 8.9 Request-Feature Retention

When a system-level fetch request handshakes, the following behavioral attributes are retained until the request completes:

- Whether it is the same-lane crossing case with reusable held data.
- Whether it requires two external accesses.
- Whether it requires zero external accesses.
- Whether the request crossed a lane boundary, for use by the next sequential fetch.

For each accepted external command, retain:

- The selected target.
- The address alignment bits required to select a 32-bit window from a 64-bit response.

These retained attributes ensure that backpressure or variable response latency cannot cause the request to be interpreted using attributes of a later PC.

### 8.10 Leftover Data

A 16-bit leftover value is loaded in either of two cases:

1. A same-lane crossing fetch reuses a held current lane. The held lane's upper 16 bits are saved when the system-level request is accepted.
2. A two-access fetch receives its first external response. The first lane's upper 16 bits are saved when that response handshakes.

The accompanying leftover error is:

- Zero for data taken from a valid held lane.
- The error indication of the first external access for a two-access fetch.

Leftover storage need not define a visible reset data value, but it shall only be used after one of these load events has made it valid for the active fetch.

### 8.11 Data Alignment

For a 32-bit target lane, the returned 32-bit lane is used directly for an ordinary one-access response. Cross-lane assembly uses the required 16-bit half as described above.

For a 64-bit target lane, select a 32-bit window according to the retained command address bits `[2:1]`:

| Address bits `[2:1]` | Selected 32-bit instruction window |
| --- | --- |
| `2'b00` | Response bits `[31:0]` |
| `2'b01` | Response bits `[47:16]` |
| `2'b10` | Response bits `[63:32]` |

The `2'b11` case is cross-lane and is completed using leftover assembly with the following lane.

ITCM and system-memory responses apply this rule using their own configured data width. The low 16 bits of the selected second-lane response are used as the upper half of a cross-lane 32-bit instruction:

```text
assembled_instruction = {second_lane_low16, leftover16}
```

### 8.12 Error Assembly

For an ordinary one-access instruction, the instruction error is the error returned by the selected target.

For an instruction assembled with leftover data:

```text
assembled_error = current_response_error | leftover_error
```

The selected target's valid, data, and error must remain associated. ITCM and system-memory response-valid signals are not treated as simultaneously valid responses to the same command.

---

## 9. External ICB Transaction Sequencing

### 9.1 Behavioral Phases

The following symbolic phases describe the required sequencing. Their state encoding and allocation to RTL design units are implementation choices.

| Phase | Description |
| --- | --- |
| `IDLE` | No outstanding translated fetch operation. |
| `FIRST` | First or only external command has been issued, or a zero-access response is being produced. |
| `WAIT_SECOND` | The first response of a two-access fetch has completed, but the next command has not yet been accepted. |
| `SECOND` | The second command has been issued and its complete instruction response is pending. |

### 9.2 IDLE Behavior

When a new system-level fetch request handshakes, retain its request classification and enter `FIRST`.

If the request is a zero-access held-lane case, no external command is issued; `FIRST` produces a synthetic valid response from held data.

Otherwise, the first external command is directed to the selected target.

### 9.3 FIRST Completion

For a two-access fetch, the first external response is always accepted into leftover storage. It does not yet produce a complete instruction response.

After that first response:

- If the second command can be accepted immediately, proceed to `SECOND`.
- If the command target is not ready, proceed to `WAIT_SECOND` and retain the second-command address and request context.

For a zero- or one-access fetch, `FIRST` completes only when the complete aligned response is accepted by the internal response holding path. If a new system-level request handshakes in the same completion cycle, begin its `FIRST` phase without returning to an idle bubble; otherwise return to `IDLE`.

### 9.4 WAIT_SECOND Behavior

Remain in `WAIT_SECOND` until the selected target accepts the second command. Then proceed to `SECOND`.

The second command remains valid and its address and target remain stable while ready is low.

### 9.5 SECOND Completion

The second external response is combined with leftover data and error status. The `SECOND` phase completes only when that complete instruction response is accepted by the response holding path.

If a new system-level request handshakes in the same completion cycle, begin its `FIRST` phase immediately; otherwise return to `IDLE`.

### 9.6 External Command Generation

An external command is valid in either of these cases:

1. A new system-level fetch request is available and it is not a zero-access held-lane case.
2. An active request requires two accesses and either:
   - Its first response is handshaking, allowing the second command to be presented, or
   - It is waiting in `WAIT_SECOND` for the target to accept the second command.

The selected target's command-valid output is asserted only for that target. Command-ready is the selected target's ready indication.

### 9.7 External Command Address

The external command address has three selection cases:

1. **Same-lane crossing with held data**: address the next aligned lane because the current lane's upper halfword is already available.
2. **Second command of a two-access fetch**: address the next lane after the first access.
3. **Ordinary first command**: use the current fetch PC.

The next-lane address calculation reuses the retained last PC. Its offset is selected as follows:

```text
next_lane_offset = second_command_of_two_access ? 2
                 : previous_sequential_instruction_was_32bit ? 6
                 : 4

next_lane_address = retained_last_pc + next_lane_offset
```

The two-byte offset advances from the first lane access to the immediately following lane for the second command. The four- or six-byte offset reaches the next required lane from the previous PC when a same-lane crossing request reuses a held lane. The resulting address shall not repeat or skip either half of a cross-lane instruction.

### 9.8 System-Level Request Ready

A new system-level fetch request can be accepted only when the required selected external command path is ready and one of the following sequencing conditions holds:

- No translated fetch is active.
- The active zero- or one-access fetch is completing its `FIRST` complete-response handshake.
- The active two-access fetch is completing its `SECOND` complete-response handshake.

This permits back-to-back operation while ensuring that request context for an incomplete fetch is not overwritten.

### 9.9 External Response Ready

When the first response of a two-access fetch is destined only for leftover storage, the response is always ready because the dedicated leftover position is reserved for that active request.

For a response that creates a complete instruction, external response ready follows the readiness of the complete-response holding path.

The ready signal is returned to both optional external interfaces, but only the response of the remembered selected target is interpreted as valid for the active command.

### 9.10 Direct System-Memory Command Path

The system-memory command address and valid indication are directly driven from the selected translated command behavior. No additional command pipeline stage is required by the supplied behavior. This direct path supports a zero-cycle response while the separate complete-response holding behavior prevents execution backpressure from deadlocking shared memory access.

---

## 10. Complete-Response Holding and Deadlock Avoidance

### 10.1 Purpose

The execution-stage ready signal may include timing-critical sources such as error checking. It applies backpressure to instruction fetch responses.

Without response decoupling, a memory response could remain blocked waiting for the execution-facing instruction position to clear. The execution stage may simultaneously need access to shared ITCM or system-memory resources and wait for the IFU to consume its earlier response. This creates a possible deadlock.

### 10.2 Required Behavior

The complete aligned response path provides one entry of elastic holding for the following 33-bit payload:

```text
{instruction_error, instruction[31:0]}
```

The behavior has these characteristics:

1. Depth is one complete instruction response.
2. When empty and the output consumer is ready, it may bypass an incoming response directly.
3. When the output consumer is not ready, it stores the accepted response and holds valid, instruction, and error stable.
4. It supports back-to-back transfers when an old entry leaves as a new entry arrives.
5. Reset clears its valid state.
6. The ready path is not cut by an additional registered stage in the supplied configuration.

This is a functional buffering requirement, not a requirement for a separately named RTL module.

### 10.3 Response Sources

A complete response may come from:

- A synthetic held-lane zero-access result.
- A selected and aligned one-access ICB response.
- A cross-lane result assembled from a current response and leftover data.

Exactly one complete response is generated for each accepted system-level fetch request.

---

## 11. Corner Cases and Constraints

### 11.1 Reset Timing

1. Active-low reset clears valid, outstanding, dependency-read, delayed-flush, error-valid, and response-holding state as applicable.
2. The reset-vector request remains pending until accepted.
3. No stale pre-reset instruction may appear valid after reset release.
4. Normal speculative requests are inhibited during the reset-recovery indication.

### 11.2 Instruction Alignment

1. All generated PCs are forced to two-byte alignment.
2. RV32C operation requires no stricter instruction-address alignment check, so the misalignment output remains zero.
3. A 32-bit instruction beginning at the final halfword of a target lane is assembled from two lanes.
4. ITCM and system-memory lane widths are evaluated independently.

### 11.3 Pipeline Flush Races

1. A flush clears a valid held instruction even if the execution stage has not accepted it.
2. A stale response arriving during a real flush is accepted and discarded.
3. A flush that cannot immediately issue its redirected request is retained through the delayed-flush condition.
4. Consecutive flushes shall not be lost; the PC reflects the most recently accepted immediate flush update while the delayed condition preserves the need to issue redirected fetching.
5. A flush and a response or output handshake may occur in the same cycle; flush suppression prevents stale instruction installation.

### 11.4 Halt Races

1. Assertion of halt prevents new ordinary fetches but does not discard an already outstanding response.
2. Halt acknowledgment waits until there is no blocking outstanding access.
3. A returned valid response is sufficient for halt quiescence even if execution backpressure prevents its immediate final handshake.
4. Halt acknowledgment remains asserted until the halt request is removed.

### 11.5 Branch Prediction Dependencies

1. A JALR x1 target is not used while OITF or a matching IR destination indicates a dependency.
2. A general JALR source waits for OITF and relevant IR dependencies to clear.
3. An IR-only dependency may be ignored when that instruction is clearing or does not use RS1.
4. The general RS1 read request is issued once per held JALR instruction.
5. Prediction wait inhibits normal new requests without losing the decoded control-flow instruction.

### 11.6 Backpressure

1. Request valid and address remain stable until the selected target accepts the command.
2. Response valid, data, and error remain stable until accepted.
3. Execution-facing instruction and metadata remain stable while `ifu_o_valid=1` and `ifu_o_ready=0`.
4. A first response written to leftover storage is consumed exactly once.
5. Complete-response holding must prevent shared-resource deadlock under execution backpressure.

### 11.7 Outstanding and Ordering

1. At most one system-level instruction fetch is outstanding.
2. A cross-lane fetch may contain two ordered ICB commands, but they belong to the same system-level fetch.
3. The second cross-lane command is not issued before the first response has supplied the leftover halfword.
4. A new system-level request may be accepted back-to-back only as the prior complete response is accepted.
5. Target selection and alignment context remain associated with the active command until its response.

### 11.8 Target and Configuration Constraints

1. At least one of ITCM or system memory is configured as a fetch target.
2. One command selects exactly one target.
3. ITCM region configuration shall not create an ambiguous target selection.
4. Target data width is configured consistently as 32 or 64 bits.
5. ITCM held-lane reuse is permitted only when `ifu2itcm_holdup && ~itcm_nohold` is true for the relevant prior access.
6. System memory is treated as not retaining reusable response-lane data.
7. Instruction, PC, XLEN, and register-index widths shall be defined consistently with the top-level interface.
8. Preliminary decode assumes a supported RISC-V instruction encoding. It supplies fetch-related classification but does not produce an IFU-visible illegal-instruction result.

### 11.9 Error Handling

1. A one-access instruction propagates the selected target error.
2. A two-access instruction reports an error if either access reports an error.
3. Error status is held with its instruction through response and execution backpressure.
4. Held ITCM data contributes no new error; a previously stored first-access error is retained in leftover error state.

### 11.10 Replay

The supplied fetch behavior fixes response-replay and fetch-replay requests low. Replay names are reserved for possible future expansion. No current request shall be repeated merely because the execution stage applies backpressure.

### 11.11 Signal Integrity

In non-FPGA verification configurations, fetch request valid shall never take an unknown value after reset is released. All ready/valid and target-selection behavior shall avoid combinational ambiguity between the optional targets.

---

## 12. System-Level Coordination and Architecture Inference

The detailed functional sections intentionally expose the relationships needed to infer a suitable RTL architecture without prescribing one.

The implementation shall account for the following interacting concerns:

1. PC state is updated by reset, sequential flow, prediction, and flush with defined priority.
2. Execution backpressure requires persistent instruction and metadata state.
3. Halt and flush interact with outstanding request tracking and response disposal.
4. Preliminary decoding feeds both PC increment and branch prediction.
5. JALR prediction depends on execution-state dependency inputs and a one-cycle general-register read sequence.
6. Memory routing must retain target and alignment context over variable response latency.
7. Cross-lane instructions require persistent first-half data and error state.
8. Complete-response elasticity prevents a shared-resource deadlock.

No behavioral section shall be interpreted as requiring a one-to-one RTL module. In particular, PC control, instruction holding, preliminary decode, prediction, target routing, transaction sequencing, alignment, leftover storage, and response holding may be merged, split, or shared in any manner.

The implementation chooses all internal module names, internal ports, state encodings, register primitives, and instance relationships. Only the top-level `e203_ifu` interface and the externally observable behavior specified above are mandatory.
