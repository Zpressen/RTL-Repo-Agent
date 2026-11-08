# E203 Execution ALU System Design Specification

## 1. System Context and Top-Level Interface

### 1.1 Introduction

The `e203_exu_alu` system is a key component of the E203 processor execution unit. It implements arithmetic and logic operations, branch and jump resolution, load/store address generation, atomic memory operations, and Control and Status Register (CSR) operations. When enabled by configuration, it also implements a shared multiplication/division function and handles Nuclei Instruction Custom Extension (NICE) operations.

The system receives an instruction that has already been decoded. The decode information identifies the instruction group and supplies group-specific control fields. According to this information, the system performs the required operation, communicates with the LSU or a custom accelerator when necessary, and coordinates the instruction's commit and write-back handshakes.

The behavior described here intentionally does not prescribe an internal module hierarchy. Implementations may divide the system into control, arithmetic, memory, iterative, and interface components as appropriate, provided that all externally visible behavior and ordering constraints in this specification are preserved.

### 1.2 Basic Interface

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Input | `i_valid` | 1 | Indicates that a valid decoded instruction and its operands are available. |
| Output | `i_ready` | 1 | Indicates that the current instruction can be accepted. |
| Output | `i_longpipe` | 1 | Indicates that the current instruction is issued as a long-pipeline instruction. |
| Output | `amo_wait` | 1 | Indicates that an atomic memory operation has started and must complete before the system becomes idle. |
| Input | `oitf_empty` | 1 | Indicates that the outstanding-instruction tracking FIFO is empty. |
| Input | `i_itag` | `E203_ITAG_WIDTH` | Instruction tag used to track an outstanding long-latency operation. |
| Input | `i_rs1` | `E203_XLEN` | First source operand. |
| Input | `i_rs2` | `E203_XLEN` | Second source operand. |
| Input | `i_imm` | `E203_XLEN` | Decoded immediate operand. |
| Input | `i_info` | `E203_DECINFO_WIDTH` | Decoded instruction information. |
| Input | `i_pc` | `E203_PC_SIZE` | Program counter of the instruction. |
| Input | `i_instr` | `E203_INSTR_SIZE` | Instruction word. |
| Input | `i_pc_vld` | 1 | Indicates that the program counter is valid for commit. |
| Input | `i_rdidx` | `E203_RFIDX_WIDTH` | Destination register index. |
| Input | `i_rdwen` | 1 | Indicates that the instruction writes a destination register. |
| Input | `i_ilegl` | 1 | Indicates an illegal instruction detected before execution. |
| Input | `i_buserr` | 1 | Indicates an instruction-fetch bus error. |
| Input | `i_misalgn` | 1 | Indicates an instruction-fetch misalignment exception. |
| Input | `flush_req` | 1 | Requests that a new memory operation be blocked while a flush is pending. |
| Input | `flush_pulse` | 1 | Flush pulse used to terminate cancellable iterative work and return its control state to idle. |
| Input | `mdv_nob2b` | 1 | Disables the multiplication/division back-to-back result-reuse optimization. |
| Input | `clk` | 1 | System clock. |
| Input | `rst_n` | 1 | Active-low reset. |

### 1.3 Commit Interface

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Output | `cmt_o_valid` | 1 | Commit handshake valid. |
| Input | `cmt_o_ready` | 1 | Commit handshake ready. |
| Output | `cmt_o_pc_vld` | 1 | Indicates that the commit PC is valid. |
| Output | `cmt_o_pc` | `E203_PC_SIZE` | Program counter associated with the instruction. |
| Output | `cmt_o_instr` | `E203_INSTR_SIZE` | Instruction associated with the commit. |
| Output | `cmt_o_imm` | `E203_XLEN` | Immediate associated with the commit. |
| Output | `cmt_o_rv32` | 1 | Indicates that the instruction is a 32-bit instruction rather than a 16-bit compressed instruction. |
| Output | `cmt_o_bjp` | 1 | Indicates a conditional branch or unconditional jump. |
| Output | `cmt_o_mret` | 1 | Indicates an MRET instruction. |
| Output | `cmt_o_dret` | 1 | Indicates a DRET instruction. |
| Output | `cmt_o_ecall` | 1 | Indicates an ECALL instruction. |
| Output | `cmt_o_ebreak` | 1 | Indicates an EBREAK instruction. |
| Output | `cmt_o_fencei` | 1 | Indicates a FENCE.I instruction. |
| Output | `cmt_o_wfi` | 1 | Indicates a WFI instruction. |
| Output | `cmt_o_ifu_misalgn` | 1 | Reports the incoming instruction-fetch misalignment indication. |
| Output | `cmt_o_ifu_buserr` | 1 | Reports the incoming instruction-fetch bus-error indication. |
| Output | `cmt_o_ifu_ilegl` | 1 | Reports an illegal instruction or illegal CSR access. |
| Output | `cmt_o_bjp_prdt` | 1 | Predicted taken/not-taken result supplied with a branch or jump. |
| Output | `cmt_o_bjp_rslv` | 1 | Resolved taken/not-taken result. |
| Output | `cmt_o_misalgn` | 1 | Reports a data-address misalignment exception. |
| Output | `cmt_o_ld` | 1 | Identifies an ordinary load commit. |
| Output | `cmt_o_stamo` | 1 | Identifies a store, atomic, or exclusive-memory commit. |
| Output | `cmt_o_buserr` | 1 | Reports a data-side bus error handled by this system. |
| Output | `cmt_o_badaddr` | `E203_ADDR_SIZE` | Address associated with a data-side exception. |

### 1.4 Register Write-Back Interface

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Output | `wbck_o_valid` | 1 | Register write-back handshake valid. |
| Input | `wbck_o_ready` | 1 | Register write-back handshake ready. |
| Output | `wbck_o_wdat` | `E203_XLEN` | Data written to the destination register. |
| Output | `wbck_o_rdidx` | `E203_RFIDX_WIDTH` | Destination register index. |

### 1.5 CSR Interface

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Output | `csr_ena` | 1 | Enables a normal CSR operation when its execution handshake completes. |
| Output | `csr_wr_en` | 1 | CSR write indication. |
| Output | `csr_rd_en` | 1 | CSR read indication. |
| Output | `csr_idx` | 12 | CSR address index. |
| Input | `nonflush_cmt_ena` | 1 | Present in the fixed top-level interface; it has no functional effect in the current implementation. |
| Input | `csr_access_ilgl` | 1 | Indicates that the CSR access is illegal. |
| Input | `read_csr_dat` | `E203_XLEN` | Data read from the selected normal CSR. |
| Output | `wbck_csr_dat` | `E203_XLEN` | New data calculated for a CSR write. |

### 1.6 LSU ICB Interface

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Output | `agu_icb_cmd_valid` | 1 | LSU ICB command valid. |
| Input | `agu_icb_cmd_ready` | 1 | LSU ICB command ready. |
| Output | `agu_icb_cmd_addr` | `E203_ADDR_SIZE` | Memory transaction start address. |
| Output | `agu_icb_cmd_read` | 1 | Read/write selection; high indicates a read. |
| Output | `agu_icb_cmd_wdata` | `E203_XLEN` | Naturally aligned store or atomic write data. |
| Output | `agu_icb_cmd_wmask` | `E203_XLEN/8` | Byte write mask. |
| Output | `agu_icb_cmd_lock` | 1 | Lock indication; asserted for the first request of an aligned atomic operation. |
| Output | `agu_icb_cmd_excl` | 1 | Exclusive-access indication. |
| Output | `agu_icb_cmd_size` | 2 | Access size: byte, halfword, or word. |
| Output | `agu_icb_cmd_back2agu` | 1 | Indicates that the LSU response must return to this system. |
| Output | `agu_icb_cmd_usign` | 1 | Unsigned-load indication. |
| Output | `agu_icb_cmd_itag` | `E203_ITAG_WIDTH` | Instruction tag associated with the memory transaction. |
| Input | `agu_icb_rsp_valid` | 1 | LSU ICB response valid. |
| Output | `agu_icb_rsp_ready` | 1 | LSU ICB response ready. |
| Input | `agu_icb_rsp_err` | 1 | LSU ICB response error. |
| Input | `agu_icb_rsp_excl_ok` | 1 | Exclusive-success input retained in the fixed interface; it has no functional effect in the current implementation. |
| Input | `agu_icb_rsp_rdata` | `E203_XLEN` | Naturally aligned LSU response data. |

### 1.7 Optional NICE CSR Interface

These ports are available when `E203_HAS_CSR_NICE` is defined. This option assumes that the NICE enable/status input is also available.

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Output | `nice_csr_valid` | 1 | NICE CSR request valid. |
| Input | `nice_csr_ready` | 1 | NICE CSR request ready. |
| Output | `nice_csr_addr` | 32 | NICE CSR address, formed from the 12-bit CSR index. |
| Output | `nice_csr_wr` | 1 | NICE CSR write indication. |
| Output | `nice_csr_wdata` | 32 | NICE CSR write data. |
| Input | `nice_csr_rdata` | 32 | NICE CSR read data. |

### 1.8 Optional NICE Instruction Interface

These ports are available when `E203_HAS_NICE` is defined.

| Direction | Port Name | Width | Description |
| --- | --- | --- | --- |
| Input | `nice_xs_off` | 1 | Disables NICE instruction and NICE CSR forwarding when asserted. |
| Output | `nice_req_valid` | 1 | Custom-instruction request valid. |
| Input | `nice_req_ready` | 1 | Custom-instruction request ready. |
| Output | `nice_req_instr` | `E203_XLEN` | Instruction forwarded to the custom accelerator. |
| Output | `nice_req_rs1` | `E203_XLEN` | First source operand forwarded to the custom accelerator. |
| Output | `nice_req_rs2` | `E203_XLEN` | Second source operand forwarded to the custom accelerator. |
| Input | `nice_rsp_multicyc_valid` | 1 | Indicates completion of a multi-cycle custom operation. |
| Output | `nice_rsp_multicyc_ready` | 1 | Indicates readiness to consume a multi-cycle completion. |
| Output | `nice_longp_wbck_valid` | 1 | Long-pipeline tag write-back valid. |
| Input | `nice_longp_wbck_ready` | 1 | Long-pipeline tag write-back ready. |
| Output | `nice_o_itag` | `E203_ITAG_WIDTH` | Instruction tag associated with the completed custom operation. |
| Input | `i_nice_cmt_off_ilgl` | 1 | Reports that a NICE instruction is illegal while the extension is disabled. |

### 1.9 Configuration Terms

- `E203_XLEN` is 32 for this implementation.
- `E203_SUPPORT_AMO` enables atomic memory operations.
- Hardware handling of unaligned load/store is not supported in the current implementation. Unaligned accesses are reported as exceptions.
- `E203_SUPPORT_MULDIV` enables the iterative multiplication/division implementation.
- `E203_SUPPORT_SHARE_MULDIV` integrates that implementation with the shared arithmetic datapath.
- `E203_HAS_NICE` enables the custom-instruction path.
- `E203_HAS_CSR_NICE` enables forwarding of the NICE CSR address range.

## 2. Instruction Dispatch, Handshake, and Result Coordination

### 2.1 Instruction Classification

The incoming decode information divides instructions into the following functional groups:

1. Regular arithmetic, logic, shift, comparison, immediate, and selected system instructions.
2. Load, store, exclusive, and atomic memory operations.
3. Conditional branch, jump, return, and instruction-fence operations.
4. CSR read, set, clear, and immediate forms.
5. Multiplication, division, and remainder operations when shared multiplication/division is configured.
6. Custom NICE instructions when the extension is configured.

An incoming instruction-fetch exception has priority over normal execution grouping. If `i_ilegl`, `i_buserr`, or `i_misalgn` is asserted, the instruction is treated as an exception operation rather than as an arithmetic, memory, branch, CSR, multiplication/division, or NICE operation.

### 2.2 Input Ready

Only the behavior selected by the current instruction group contributes to `i_ready`. A one-cycle combinational operation normally propagates downstream readiness to the input. A memory or iterative operation may delay readiness until its command, response, calculation, or final result phase allows the current instruction to complete.

The input handshake occurs when `i_valid` and `i_ready` are both high. All instruction information and operands used by that handshake must remain stable according to the ready/valid protocol.

### 2.3 Output Selection

The result associated with the current instruction group is selected for the common commit and write-back interfaces. The selected behavior supplies:

- Result-valid and ready propagation.
- Register write-back data and error status.
- Branch, jump, CSR, load/store, atomic, and system-instruction commit attributes.
- Data-address exception information.

Instruction-fetch exception inputs produce zero write-back data and an error result. They still proceed to the commit interface so that the architectural exception can be taken.

### 2.4 Commit and Write-Back Coupling

Every accepted instruction requires a commit handshake. A register write-back handshake is additionally required when all of the following are true:

- The instruction writes `rd`.
- The instruction is not marked as a long-pipeline operation.
- The selected execution result does not report an error.

When both commit and register write-back are required, the two valid signals are mutually qualified by the opposite interface's readiness. The instruction completes only when both destinations can accept it in the same transaction. When write-back is not required, commit can proceed independently.

`wbck_o_rdidx` is the incoming destination-register index. `cmt_o_instr`, `cmt_o_pc`, and `cmt_o_imm` preserve the incoming instruction metadata. `cmt_o_pc_vld` follows `i_pc_vld` and is interpreted only with a valid commit.

### 2.5 Long-Pipeline Classification

Aligned ordinary load/store operations are issued as long-pipeline instructions because their memory responses are handled outside this result path. An enabled NICE instruction is also marked as long-pipeline. The shared multiplication/division implementation is internally multi-cycle but does not assert `i_longpipe` in this system; it holds the normal execution path until its result is ready.

### 2.6 Flush Coordination

`flush_req` prevents a new memory operation from starting while memory control is idle. `flush_pulse` returns cancellable AMO and multiplication/division control phases to idle and invalidates their in-progress computation according to the behavior described in later sections.

An atomic operation that has already performed a memory update cannot be abandoned merely because a new interrupt or flush request is pending. `amo_wait` therefore remains asserted while the atomic read-modify-write sequence is active.

## 3. Regular Integer and Shared Datapath Operations

### 3.1 Valid-Ready Behavior

Regular integer operations are combinational. Their output valid follows the selected input valid, and their input ready follows the common output readiness.

### 3.2 Operation Information

The regular operation information supports the following calculations:

| Operation | Description |
| --- | --- |
| ADD | Adds the selected first and second operands. |
| SUB | Subtracts the second operand from the first operand. |
| XOR | Bitwise exclusive OR. |
| SLL | Logical left shift. |
| SRL | Logical right shift. |
| SRA | Arithmetic right shift. |
| OR | Bitwise OR. |
| AND | Bitwise AND. |
| SLT | Signed set-less-than. |
| SLTU | Unsigned set-less-than. |
| LUI | Returns the selected immediate operand. |

NOP is decoded as an ADDI operation. When the NOP indication is set, the add request is suppressed even though the ADD decode indication is present.

### 3.3 Operand Selection

The first operand is selected as follows:

- When the OP1-PC indication is high, use `i_pc`.
- Otherwise, use `i_rs1`.

The second operand is selected as follows:

- When the OP2-immediate indication is high, use `i_imm`.
- Otherwise, use `i_rs2`.

The selected result is returned as the regular register write-back data.

### 3.4 Special Instructions

The regular instruction information also carries ECALL, EBREAK, and WFI indications.

| Instruction | Commit behavior |
| --- | --- |
| ECALL | Assert `cmt_o_ecall`. |
| EBREAK | Assert `cmt_o_ebreak`. |
| WFI | Assert `cmt_o_wfi`. |

These instructions report an execution error for write-back selection so that no register-file result is written. Their architectural effect is communicated through the commit interface.

### 3.5 Shared Shift Behavior

Only regular integer operations use the shift behavior:

- SLL shifts the first operand left by `op2[4:0]`.
- SRL shifts the first operand right and fills the vacated upper bits with zero.
- SRA shifts the first operand right and fills the vacated upper bits with the original sign bit.

Only the low five bits of the shift amount are used for the 32-bit datapath.

### 3.6 Shared Addition and Comparison Behavior

Addition/subtraction behavior is shared by regular arithmetic, branch and jump processing, address generation, atomic calculations, and, when configured, multiplication/division intermediate steps.

The comparison behavior supports equality, inequality, signed less-than/greater-than, and unsigned less-than/greater-than. Signed and unsigned selection must follow the corresponding decoded operation. The same comparison results support SLT/SLTU, conditional branches, and atomic maximum/minimum selection.

### 3.7 Logical, Move, and Maximum/Minimum Results

- XOR, OR, and AND return the corresponding bitwise result.
- LUI and atomic swap return operand 2 directly.
- Signed MAX/MIN select operands using the signed comparison.
- Unsigned MAXU/MINU select operands using the unsigned comparison.
- SLT and SLTU return an XLEN-wide value of 1 when true and 0 when false.

### 3.8 Shared Working Storage

Two 33-bit working values hold intermediate AMO or multiplication/division data. AMO uses their low 32 bits. Shared multiplication/division uses all 33 bits.

These working values have load enables but no reset. Reset instead clears the control states that determine whether their contents are valid. The system must never consume an old working value unless the current operation has first loaded it.

## 4. Branch, Jump, Return, and Fence Behavior

### 4.1 Valid-Ready Behavior

Branch, jump, return, and fence processing is combinational. The selected input valid is passed to the common result-valid path, and common output readiness is passed back to the input.

### 4.2 Branch Information

The branch/jump information includes the following valid-high indications:

| Indication | Description |
| --- | --- |
| BEQ | Equality comparison. |
| BNE | Inequality comparison. |
| BLT | Signed less-than comparison. |
| BGT | Signed greater-than comparison used by the decoded internal form. |
| BLTU | Unsigned less-than comparison. |
| BGTU | Unsigned greater-than comparison used by the decoded internal form. |
| BXX | Any conditional branch. |
| JUMP | JAL or JALR. |
| MRET | Machine return. |
| DRET | Debug return. |
| FENCEI | Instruction-stream fence. |
| RV32 | The current instruction occupies 32 bits. |
| BPRDT | Predicted branch/jump result supplied by earlier instruction processing. |

The system does not generate a new branch prediction here. It forwards the supplied BPRDT value to `cmt_o_bjp_prdt` and independently computes the resolved result.

### 4.3 Operand Selection

For a conditional branch:

- Operand 1 is `i_rs1`.
- Operand 2 is `i_rs2`.
- The selected comparison operation determines whether the branch is resolved as taken.

For JAL or JALR link-value calculation:

- Operand 1 is `i_pc`.
- Operand 2 is 4 for a 32-bit instruction and 2 for a 16-bit compressed instruction.

The 4/2 choice refers to instruction length, not to an RV32-versus-RV64 processor mode.

### 4.4 Resolved Result

For an unconditional jump, the resolved result is always 1. For a conditional branch, the resolved result is the selected equality, inequality, signed comparison, or unsigned comparison result.

`cmt_o_bjp` is asserted for a conditional branch or unconditional jump. MRET, DRET, and FENCE.I are reported separately through `cmt_o_mret`, `cmt_o_dret`, and `cmt_o_fencei`.

### 4.5 Link Write-Back

The adder result is always presented as the branch/jump write-back data. It is architecturally used for JAL and JALR to write the address of the following instruction. Branch/jump processing does not generate a write-back error.

## 5. CSR Operations

### 5.1 CSR Information

The CSR information contains the following fields:

| Field | Description |
| --- | --- |
| CSRRW | CSR read/write instruction. |
| CSRRS | CSR read and set-bits instruction. |
| CSRRC | CSR read and clear-bits instruction. |
| RS1IMM | Selects the five-bit immediate rather than `i_rs1`. |
| RS1IS0 | Indicates that the source register is x0. |
| ZIMMM | Five-bit zero-extended immediate. |
| CSRIDX | Twelve-bit CSR address. |

### 5.2 Operand Selection

If RS1IMM is set, the five-bit immediate is zero-extended to XLEN and used as operand 1. Otherwise, `i_rs1` is used.

### 5.3 Read and Write Enables

`csr_rd_en` is asserted for a valid CSR instruction according to these rules:

- CSRRW reads the old CSR value only when the destination register is written.
- CSRRS and CSRRC always read the current CSR value.

`csr_wr_en` is asserted for a valid CSR instruction according to these rules:

- CSRRW always writes.
- CSRRS and CSRRC write only when the source is not x0.

`csr_idx` is the 12-bit decoded CSR index. A normal CSR operation asserts `csr_ena` only when the selected execution output handshake completes and the request is not routed to the NICE CSR range.

### 5.4 CSR Write Data

The calculated CSR write data is:

| Instruction | `wbck_csr_dat` |
| --- | --- |
| CSRRW | `csr_operand` |
| CSRRS | `csr_operand \| read_csr_dat` |
| CSRRC | `(~csr_operand) & read_csr_dat` |

The value read before modification is returned as the register write-back result.

### 5.5 Illegal CSR Access

When `csr_access_ilgl` is asserted, the CSR result reports a write-back error and `cmt_o_ifu_ilegl` is asserted for the committing instruction. The illegal access therefore cannot produce a normal register write-back.

### 5.6 Optional NICE CSR Range

When `E203_HAS_CSR_NICE` is configured, a CSR whose index has `csr_idx[11:8] == 4'hE` selects the NICE CSR range. Forwarding is active only when `nice_xs_off` is low.

For an enabled NICE CSR access:

- The execution output becomes valid only when `nice_csr_ready` is high.
- `nice_csr_valid` is asserted only when the CSR input is valid and the common execution output is ready.
- The input is ready only when both `nice_csr_ready` and common output readiness are high.
- `nice_csr_addr` receives the zero-extended CSR index.
- `nice_csr_wr` follows the calculated CSR write enable.
- `nice_csr_wdata` receives the calculated CSR write data.
- `nice_csr_rdata` supplies the register write-back result.

If the NICE extension is off, the same CSR index follows the normal CSR path rather than being forwarded.

## 6. Load/Store Address Generation and LSU Transactions

### 6.1 Memory Operation Information

The memory-operation information contains the following valid-high fields:

| Field | Description |
| --- | --- |
| LOAD | Ordinary load operation. |
| STORE | Ordinary store operation. |
| AMO | Atomic read-modify-write operation. |
| SIZE | Access size: `00` byte, `01` halfword, `10` word. |
| USIGN | Selects unsigned load-data extension. |
| EXCL | Identifies an exclusive memory access. |
| AMOSWAP | Atomic swap. |
| AMOADD | Atomic addition. |
| AMOAND | Atomic AND. |
| AMOOR | Atomic OR. |
| AMOXOR | Atomic XOR. |
| AMOMAX | Atomic signed maximum. |
| AMOMIN | Atomic signed minimum. |
| AMOMAXU | Atomic unsigned maximum. |
| AMOMINU | Atomic unsigned minimum. |

When a flush request is pending while memory control is idle, the LOAD, STORE, and AMO indications are masked so that a new operation cannot begin.

### 6.2 Address Calculation

The memory address is calculated through the shared adder.

- For an ordinary load or store, operand 1 is `i_rs1` and operand 2 is `i_imm`.
- For an AMO or an exclusive access, operand 2 is zero, so the address is `i_rs1`.
- During the second request of an AMO, the same base-address calculation is repeated so that the write targets the address read by the first request.

The low `E203_ADDR_SIZE` bits of the arithmetic result form `agu_icb_cmd_addr`.

### 6.3 Alignment Detection

Alignment is checked from the access size and address:

- A byte access is always naturally aligned.
- A halfword access is misaligned when address bit 0 is one.
- A word access is misaligned when either address bit 1 or bit 0 is one.

The current implementation does not perform a hardware split-and-merge sequence for an unaligned ordinary load/store. An unaligned load or store is completed through the commit path as a misalignment exception, with `cmt_o_misalgn` asserted and the calculated address supplied through `cmt_o_badaddr`.

An unaligned AMO is also rejected as a misalignment exception. No memory command is issued for that operation.

### 6.4 Ordinary Aligned Load/Store Handshake

An aligned ordinary load/store is presented to the LSU command interface and to the commit path together.

- `agu_icb_cmd_valid` is asserted when the instruction is valid and the commit path is ready.
- The execution result is valid when the instruction is valid and the LSU command interface is ready.
- The instruction input is ready when both the LSU command interface and the execution output are ready.

This coupling guarantees that the memory command is accepted in the same transaction in which the instruction is accepted for commit. It prevents one side from consuming the instruction while the other side stalls.

Aligned ordinary load/store operations assert `i_longpipe`. They do not write their eventual load data through `wbck_o_wdat` in this system. Their LSU responses are handled by the processor's long-pipeline completion path.

### 6.5 Command Read/Write Selection

For an aligned ordinary load:

- `agu_icb_cmd_read` is high.
- `agu_icb_cmd_back2agu` is low.
- The response is not consumed as a result by this system.

For an aligned ordinary store:

- `agu_icb_cmd_read` is low.
- `agu_icb_cmd_back2agu` is low.
- Store data and byte masks are generated as described below.

### 6.6 Store Data Alignment

The LSU command data channel is naturally aligned. For a store, `agu_icb_cmd_wdata` is formed from the applicable byte, halfword, or word portion of `i_rs2`, and `agu_icb_cmd_wmask` selects the addressed byte lanes according to the access size and low address bits. A word store enables all four byte lanes.

### 6.7 Command Attributes

`agu_icb_cmd_size` carries the decoded access size. `agu_icb_cmd_usign` carries the unsigned-load indication. `agu_icb_cmd_itag` carries `i_itag`.

For ordinary accesses, `agu_icb_cmd_lock` and `agu_icb_cmd_back2agu` are low. When atomic support is configured, `agu_icb_cmd_excl` follows the decoded exclusive indication.

### 6.8 Response Readiness and Error Scope

`agu_icb_rsp_ready` is continuously asserted. Responses directed back to this system are therefore accepted whenever `agu_icb_rsp_valid` is asserted.

Ordinary aligned load/store commands set `agu_icb_cmd_back2agu` low, so their response and any associated response error are not committed by this system. The data-side bus-error merge described in this document applies to the two responses of an aligned AMO.

### 6.9 Memory Commit Attributes

- `cmt_o_ld` is asserted for an ordinary, non-exclusive load.
- `cmt_o_stamo` is asserted for a store, AMO, or exclusive access.
- `cmt_o_badaddr` receives the calculated command address.
- A data-side misalignment or handled bus error suppresses normal register write-back.

## 7. Atomic Memory Operations

### 7.1 Overview

When `E203_SUPPORT_AMO` is configured, aligned atomic instructions execute as read-modify-write sequences:

1. Wait until no tracked long-pipeline instruction is outstanding.
2. Issue a locked read request.
3. Receive and retain the original memory value and first-response error.
4. Calculate the new value using the selected AMO operation.
5. Issue a write request to the same address.
6. Receive the write response and merge its error with the first response.
7. Return the original memory value for register write-back and commit the AMO.

The sequence is deliberately serialized. Performance is secondary to maintaining correct ordering and avoiding a deadlock with older long-pipeline operations.

### 7.2 Behavioral Phases

The AMO sequence uses the following descriptive phases. The names describe behavior and do not require a particular state encoding.

| Phase | Description |
| --- | --- |
| Idle | No atomic memory request is outstanding. |
| First-response wait | The atomic read request has been issued and its response is pending. |
| Atomic calculation | The read data is available for the selected arithmetic or logical operation. |
| Calculated-result hold | The new value has been captured for the write request. |
| Second-command wait | The system waits for the LSU to accept the atomic write command. |
| Second-response wait | The write request has been issued and its response is pending. |
| Final write-back | The original value and merged error are presented for commit/write-back. |

### 7.3 Starting an AMO

An aligned AMO can leave Idle only when:

- Its instruction is valid.
- `oitf_empty` is high.
- The first LSU command handshakes.
- `flush_pulse` is low.

Waiting for `oitf_empty` avoids a corner case in which an older long-pipeline error needs to flush the processor while an AMO has already started an uninterruptible memory update.

The first command is a read. `agu_icb_cmd_lock`, `agu_icb_cmd_back2agu`, and, when decoded, `agu_icb_cmd_excl` are asserted for the applicable request.

### 7.4 First Response

The first-response wait ends when either:

- The LSU response handshakes, in which case the returned memory value and `agu_icb_rsp_err` are retained.
- `flush_pulse` is asserted, in which case the operation returns to Idle.

On a normal response, the original memory value becomes operand 1 for the atomic calculation and `i_rs2` becomes operand 2.

### 7.5 Atomic Calculation

The selected operation computes the value that will be written back to memory:

| Operation | New memory value |
| --- | --- |
| AMOSWAP | `i_rs2` |
| AMOADD | `original + i_rs2` |
| AMOAND | `original & i_rs2` |
| AMOOR | `original \| i_rs2` |
| AMOXOR | `original ^ i_rs2` |
| AMOMAX | Signed maximum of `original` and `i_rs2` |
| AMOMIN | Signed minimum of `original` and `i_rs2` |
| AMOMAXU | Unsigned maximum of `original` and `i_rs2` |
| AMOMINU | Unsigned minimum of `original` and `i_rs2` |

The calculation phase advances unconditionally in one cycle unless a flush returns control to Idle. The following hold phase captures the calculated result and then advances to the second-command wait.

### 7.6 Second Command

The second request is a write to the same calculated address.

- `agu_icb_cmd_read` is low.
- `agu_icb_cmd_wdata` is the calculated atomic result.
- The write mask is all ones for the 32-bit AMO.
- If the first read response reported an error, the write mask is zero so that the second request cannot modify memory.
- `agu_icb_cmd_back2agu` remains high so that the write response returns here.

The second-command wait advances when `agu_icb_cmd_ready` is high, or returns to Idle on `flush_pulse`. During this phase the command-valid condition is implied by the active aligned AMO sequence.

### 7.7 Second Response and Error Merge

The second-response wait ends on a response handshake or a flush pulse.

The retained error is calculated as:

`merged_error = first_response_error | second_response_error`

The original memory data remains unchanged while the second response is captured. This original value, rather than the newly calculated store value, is the architectural AMO result.

### 7.8 Final Write-Back

During the final phase:

- The execution result is valid.
- Register write-back data is the original memory value.
- `cmt_o_buserr` is the merged response error.
- `cmt_o_stamo` is asserted.
- `cmt_o_badaddr` is the AMO address.

The operation returns to Idle when the common output is ready, or immediately on a flush pulse.

### 7.9 AMO Wait and Flush

`amo_wait` is high in every non-idle AMO phase. Once an AMO has progressed to a point where memory may have been modified, the processor must allow the sequence to reach a consistent final state before treating it as fully complete.

`flush_req` blocks a new operation only while the sequence is idle. `flush_pulse` is included in each phase's exit condition and redirects the control sequence to Idle.

### 7.10 Misaligned AMO

A misaligned AMO does not enter the multi-phase sequence and does not issue a memory command. It proceeds directly to commit with:

- `cmt_o_misalgn` asserted.
- `cmt_o_stamo` asserted.
- The calculated address in `cmt_o_badaddr`.
- Register write-back suppressed by the error condition.

## 8. Multiplication and Division

### 8.1 Availability and Supported Instructions

The iterative multiplication/division behavior is available when `E203_SUPPORT_MULDIV` is defined and is connected to this system's shared datapath when `E203_SUPPORT_SHARE_MULDIV` is defined.

Supported operations are:

| Instruction | Behavior |
| --- | --- |
| MUL | Low XLEN bits of signed-by-signed multiplication. |
| MULH | High XLEN bits of signed-by-signed multiplication. |
| MULHSU | High XLEN bits of signed-by-unsigned multiplication. |
| MULHU | High XLEN bits of unsigned-by-unsigned multiplication. |
| DIV | Signed quotient. |
| DIVU | Unsigned quotient. |
| REM | Signed remainder. |
| REMU | Unsigned remainder. |

### 8.2 Handshake

The input handshake completes when the instruction is valid and the iterative operation can present or immediately produce a result accepted by the common output path.

The result-valid indication is asserted:

- Immediately for a recognized back-to-back reuse case.
- Immediately for division by zero or signed-division overflow.
- On the last multiplication execution cycle.
- After the division remainder check when no correction is required.
- During the final remainder-correction phase when correction is required.

The result remains subject to common output readiness. Multiplication and division do not generate an execution exception, so their write-back error is always zero.

### 8.3 Iterative Phases

The behavior uses five phases:

| Phase | Description |
| --- | --- |
| Initial | Decode operands, determine signedness, detect special or reusable results, and perform the first iterative calculation. |
| Execute | Perform the remaining Booth multiplication or non-restoring division iterations. |
| Remainder check | Determine whether the division quotient and remainder need correction. |
| Quotient correction | Adjust the quotient by one when required. |
| Remainder correction | Add or subtract the divisor to produce the final remainder. |

The initial phase enters Execute for a valid non-special instruction that is not using a back-to-back result and is not flushed.

For multiplication, Execute returns to Initial only after the last execution cycle and successful result handshake. For division, Execute advances to Remainder check after the last division iteration.

Remainder check returns to Initial after a successful result handshake if no correction is needed. Otherwise it advances to Quotient correction, then unconditionally to Remainder correction. Remainder correction returns to Initial after the result handshakes.

`flush_pulse` returns any active phase to Initial.

### 8.4 Cycle Count

Multiplication is a 17-cycle operation consisting of the initial cycle and 16 Execute cycles. Division is a 33-cycle iterative operation consisting of the initial cycle and 32 Execute cycles, followed by a remainder-check cycle and, when necessary, correction cycles.

The execution counter is set to one when Execute is entered because the Initial phase has already performed cycle zero. Multiplication completes when the counter reaches 16; division completes its iterative portion when the counter reaches 32.

### 8.5 Multiplication Operand Signedness

The multiplicand and multiplier are extended according to the instruction:

- MUL and MULH treat both operands as signed.
- MULHSU treats `i_rs1` as signed and `i_rs2` as unsigned.
- MULHU treats both operands as unsigned.

The low result returned by MUL is the same for all signedness combinations. The high-half instructions select the result produced by their specified signedness.

### 8.6 Booth-4 Encoding

Multiplication uses Booth-4 encoding. Groups of three multiplier bits select each partial-product operation:

| Booth code | Partial product |
| --- | --- |
| `000` | 0 |
| `001` | +1 × multiplicand |
| `010` | +1 × multiplicand |
| `011` | +2 × multiplicand |
| `100` | -2 × multiplicand |
| `101` | -1 × multiplicand |
| `110` | -1 × multiplicand |
| `111` | 0 |

The selected partial product is added to or subtracted from the high partial-product value through the shared 35-bit adder. The high and low partial-product values are shifted and retained for the next iteration.

The final MUL result is taken from the low product. MULH, MULHSU, and MULHU return the appropriate high half.

### 8.7 Non-Restoring Division

Division uses a non-restoring signed algorithm. Signedness is selected as follows:

- DIV and REM sign-extend both dividend and divisor.
- DIVU and REMU zero-extend both operands.

Each iteration uses the previous quotient decision to add or subtract the divisor from the partial remainder. The sign relationship between the arithmetic result and the divisor determines the next quotient bit. Partial quotient and remainder values are retained between cycles.

### 8.8 Division Correction

After the final division iteration, the remainder is checked. Correction is required when the partial remainder:

- Has a sign inconsistent with the dividend and is not zero.
- Is the negation of the divisor.
- Is equal to the divisor.

When correction is required, the quotient is incremented or decremented according to the remainder/divisor sign relationship. The remainder is then corrected by adding or subtracting the divisor.

DIV and DIVU return the quotient. REM and REMU return the remainder.

### 8.9 Division by Zero

Division by zero is detected when every divisor bit is zero. It produces an immediate predefined result:

| Instruction | Result |
| --- | --- |
| DIV or DIVU | All ones |
| REM or REMU | Original dividend |

### 8.10 Signed Division Overflow

Signed overflow occurs when the dividend is the most-negative XLEN value and the divisor is -1.

| Instruction | Result |
| --- | --- |
| DIV | Most-negative XLEN value |
| REM | Zero |

The unsigned operations do not use this signed-overflow case.

### 8.11 Back-to-Back Result Reuse

The decode information may identify these sequences:

- A high-half multiplication followed by MUL using the same source operands.
- DIV or DIVU followed by REM or REMU using the same source operands.

When the back-to-back indication is present, the prior operation was not flushed, and `mdv_nob2b` is low, the retained partial-result storage can directly provide the companion result without repeating the full iteration.

A flush sets a retained “flushed” condition so that a later decode indication cannot incorrectly reuse stale data. The condition is cleared after a subsequent result handshake.

### 8.12 Long-Pipeline and Error Behavior

Although multiplication and division are multi-cycle, this shared implementation reports `i_longpipe` as zero. The instruction remains on the normal execution path until its result becomes valid.

There are no multiplication/division exception cases in this system. Division by zero and signed overflow return architecturally defined data rather than reporting write-back errors.

## 9. NICE Custom Instructions

### 9.1 Availability

This behavior is present when `E203_HAS_NICE` is defined. It forwards a decoded custom instruction and its source operands to an external accelerator while coordinating commit and multi-cycle completion tags.

### 9.2 Instruction Forwarding

When NICE is enabled:

- `nice_req_instr` receives `i_instr`.
- `nice_req_rs1` receives `i_rs1`.
- `nice_req_rs2` receives `i_rs2`.
- `nice_req_valid` is asserted when the NICE instruction is valid and the commit interface is ready.

The input instruction is ready only when the accelerator request side and the commit side are both ready. The NICE commit result is valid when the input instruction is valid and the request side is ready. These conditions ensure that the accelerator accepts the request in the same transaction in which the instruction is accepted for commit.

### 9.3 Disabled Behavior

When `nice_xs_off` is high:

- `nice_req_valid` is forced low so that no request reaches the disabled accelerator.
- Accelerator request readiness is treated as high internally.
- The instruction can still proceed to commit when the commit interface is ready.
- `i_nice_cmt_off_ilgl` supplies the illegal-instruction result for commit.
- `i_longpipe` is not asserted for the disabled operation.

### 9.4 Long-Pipeline Classification

When NICE is enabled, the instruction is marked as a long-pipeline operation. Its ordinary register write-back is therefore suppressed from the common write-back interface. Completion is instead associated with an instruction tag delivered through the NICE long-pipeline write-back interface.

### 9.5 Multi-Cycle Tag Queue

A four-entry FIFO preserves the issue order of multi-cycle NICE instruction tags.

- A tag is pushed when an enabled NICE request handshakes with the accelerator.
- The tag at the head is paired with the next asserted `nice_rsp_multicyc_valid`.
- `nice_longp_wbck_valid` is asserted when both the queue head is valid and a multi-cycle response is valid.
- `nice_rsp_multicyc_ready` is asserted when the long-pipeline write-back side is ready and the queue contains a valid head.
- A tag is popped when the response-valid and response-ready conditions handshake.

`nice_o_itag` is driven directly from the queue head rather than being masked by its valid signal. This keeps the data path independent of the control path and avoids a timing loop. Consumers must sample it only when `nice_longp_wbck_valid` is high.

### 9.6 Queue Capacity

The queue depth is four. Its ready-cut configuration does not impose an every-other-cycle acceptance restriction because that behavior applies only to a single-entry queue.

The current forwarding behavior does not use the queue's full indication to backpressure new NICE requests. The surrounding system must therefore ensure that no more than four multi-cycle NICE operations are awaiting completion. If a fifth tag is presented while the queue is full, that tag is not recorded and later completion-to-instruction association is no longer reliable.

### 9.7 NICE Corner Cases

- A disabled accelerator receives no request even when the instruction commits as illegal.
- A completion response cannot pop a tag when the queue is empty.
- Long-pipeline write-back backpressure also backpressures consumption of the accelerator completion.
- Request, commit, tag push, response, and tag pop are all governed by their respective ready/valid handshakes.

## 10. Reset, State Retention, and Shared Resources

### 10.1 Clocked and Combinational Behavior

Regular integer operations, branch/jump resolution, and CSR control are combinational and do not retain instruction state. AMO sequencing, multiplication/division sequencing, flush tracking, response-error retention, and NICE tag ordering require clocked state.

### 10.2 Active-Low Reset

When `rst_n` is low:

- AMO control returns to Idle.
- Multiplication/division control returns to Initial.
- Iteration counters and control flags that use reset are cleared.
- Retained AMO response-error state is cleared.
- The NICE tag queue becomes empty.

### 10.3 Non-Reset Working Data

The two shared 33-bit working values use load-enable storage without reset. Reset does not initialize their data bits.

This is safe only because reset clears every control state that could interpret those values as valid. Before consuming a shared value, the active AMO or multiplication/division sequence must have loaded it during the current operation.

### 10.4 Resource Sharing

The arithmetic resources may be shared among:

- Regular addition, subtraction, comparison, and logical operations.
- Branch and jump link calculation and comparisons.
- Load/store address generation.
- AMO arithmetic, logical, swap, maximum, and minimum operations.
- Multiplication and division intermediate addition/subtraction.

The instruction grouping and single active execution path ensure that unrelated request classes do not simultaneously select conflicting operands or operations.

### 10.5 Flush Effects

A flush pulse resets iterative control phases and prevents stale iterative results from being accepted as new results. It also invalidates eligibility for multiplication/division back-to-back reuse until a new valid result establishes fresh retained data.

The working data itself need not be cleared, because its validity is derived from the reset or flush-controlled operation state.

## 11. Commit, Exceptions, Constraints, and System Coordination

### 11.1 Write-Back Data Selection

The common write-back data is selected from the current instruction behavior:

- Regular arithmetic or logical result.
- JAL/JALR link address.
- Old CSR value.
- Original memory value for an aligned AMO.
- Multiplication, division, or remainder result.
- Zero for an incoming instruction-fetch exception.

NICE long-pipeline completion does not return ordinary write-back data through this selection.

### 11.2 Write-Back Suppression

Ordinary register write-back is suppressed when:

- `i_rdwen` is low.
- `i_longpipe` is high.
- The selected operation reports an error.

Reported errors include ECALL, EBREAK, WFI, illegal CSR access, incoming instruction-fetch exceptions, data-address misalignment, and handled AMO bus errors.

### 11.3 Commit Signals

The commit interface reports the selected instruction's architectural classification and exception information:

- Branch/jump prediction and resolution are valid only for the selected branch/jump instruction.
- MRET, DRET, FENCE.I, ECALL, EBREAK, and WFI are reported by their dedicated outputs.
- Data-side load/store/AMO attributes are valid only for the selected memory instruction.
- Incoming instruction-fetch exception signals are carried directly to their commit outputs.
- Illegal CSR access is combined with the incoming illegal-instruction indication.

### 11.4 Backpressure

The system must tolerate independent backpressure from:

- The commit interface.
- The ordinary register write-back interface.
- The LSU command interface.
- The NICE accelerator request interface.
- NICE long-pipeline write-back.

Valid data must remain stable until its corresponding ready/valid handshake completes. When a transaction requires simultaneous acceptance by two destinations, neither destination may observe a one-sided completion.

### 11.5 Memory Ordering

- An aligned ordinary load/store command is coordinated with commit in the same transaction.
- An AMO does not start until `oitf_empty` is high.
- Only one serialized AMO sequence is active through the phases described above.
- `amo_wait` remains asserted throughout that active sequence.
- The second AMO command uses the same address as the first and cannot write data when the first response reported an error.

### 11.6 Misalignment

The current implementation supports naturally aligned byte, halfword, and word accesses. It detects but does not execute unaligned halfword or word load/store operations.

An implementation conforming to this specification must not silently split an unaligned access into multiple commands. It must report the misalignment through commit and suppress normal write-back.

### 11.7 Bus Errors

The AMO path merges errors from its read and write responses. If either response reports an error, `cmt_o_buserr` is asserted and ordinary write-back is suppressed.

The response error for an ordinary aligned load/store is handled by the long-pipeline LSU response path and is not converted into `cmt_o_buserr` by this system.

### 11.8 Multiplication/Division Special Cases

Division by zero and signed division overflow are data-result cases, not execution exceptions. They must return the values specified in Sections 8.9 and 8.10 with write-back error low.

Back-to-back result reuse is an optimization and must not change architectural results. It is disabled by `mdv_nob2b` and after a flush.

### 11.9 NICE Ordering

Multi-cycle NICE completions are associated with instructions in FIFO order. The environment must not allow more than four outstanding multi-cycle NICE requests. A response must not be consumed without a queued tag and downstream tag-write-back readiness.

### 11.10 Signal Integrity

Inputs associated with a valid instruction must remain stable until the instruction handshakes. Outputs associated with a stalled valid transaction must remain stable until ready is asserted.

Unselected instruction groups must not affect the selected result, commit attributes, memory command, CSR operation, or write-back error.

### 11.11 Architecture Inference Requirements

This specification intentionally describes cohesive behaviors rather than assigning them to predefined internal modules. A valid implementation decomposition must nevertheless preserve the natural coordination boundaries implied by the requirements:

- Combinational integer, branch, and CSR behavior must integrate with a common instruction/result handshake.
- Memory command generation must coordinate alignment, commit, and multi-phase AMO state.
- Iterative multiplication/division must retain intermediate arithmetic data and survive downstream backpressure.
- NICE request forwarding must coordinate commit with an ordered multi-cycle tag queue.
- Shared arithmetic and working storage must be arbitrated so that only the selected instruction behavior controls them.
- Common commit and write-back selection must combine all instruction classes without leaking unselected status.

The internal hierarchy, state encoding, signal naming, and exact allocation of these responsibilities are implementation choices, not requirements of this specification.
