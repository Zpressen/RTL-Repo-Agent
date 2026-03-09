# RTL 项目级 SPEC 示例：`axi_uart_periph`（SRS）

> Project intent：一个可综合的 AXI4-Lite 从设备 + UART 外设（含 CSR、TX/RX FIFO、可选中断），提供可一键仿真的 testbench。
> Repo size target：≤ 50 files（本示例 ~ 10–15 个文件以内）。

---

## 0. Meta 信息（版本/工具链/风格）

**解释**  
Meta 信息用于“锁死工程语义”：工具版本、SystemVerilog 子集、风格规范、默认参数等。它直接决定 agent 生成代码是否可编译、是否可被既有脚本跑通。

**示例内容**

- Language / dialect：
  - SystemVerilog-2017（只用 synthesizable 子集）
  - 禁止：dynamic array、class、mailbox（仅 TB 可用）
- Toolchain（验收以这些为准）：
  - 编译/仿真：`iverilog (SystemVerilog)` 或 `verilator` 二选一（本例以 iverilog 为主）
  - Lint（可选）：`verilator --lint-only` 或 `svlint`
- Coding style（硬约束）：
  - 时序逻辑：`always_ff @(posedge clk)`；组合逻辑：`always_comb`
  - 复位：`rst_n` 为 active-low，**同步释放**
  - 非阻塞赋值：时序逻辑用 `<=`；组合逻辑用 `=`
  - 所有输出在任何时刻不得为 X/Z（TB 可加 X-check）
- Default parameters（在无说明时采用）：
  - `ADDR_W=16, DATA_W=32, FIFO_DEPTH=16, OVERSAMPLE=16, CLK_FREQ_HZ=50_000_000, BAUD_DEFAULT=115200`

---

## 1. Abstract / One-liner（电梯陈述）


`axi_uart_periph` implements an AXI4-Lite slave UART peripheral with TX/RX FIFOs, CSR regmap, optional parity and interrupt, delivered with a runnable SV testbench and one-command simulation.

---

## 2. Goals / Non-goals（范围边界）

### 2.1 Goals（必须实现）



- G1：实现 AXI4-Lite Slave（32-bit，word-aligned），可访问 CSR 与数据寄存器
- G2：实现 UART TX（8N1 默认，可配置 parity），支持可编程波特率


### 2.2 Non-goals（明确不做）



- NG1：不支持 AXI full（只支持 AXI4-Lite）
- NG2：不支持 multi-clock / CDC（所有逻辑单时钟域 `clk`）


---

## 3. Glossary（术语表）



- `baud_tick`：UART “每 1 bit time” 的边界 tick（驱动 TX shift / RX bit 采样推进）
- `os_tick`：oversample tick（默认 16x；用于 RX 起始位对齐与中点采样）
- `frame`：UART 帧（start + data + optional parity + stop）


---

## 4. System Context（系统上下文）



- SoC/MCU 通过 AXI4-Lite 访问 `axi_uart_periph`：
  - 写 `TXDATA` 触发发送
  - 读 `RXDATA` 获取接收字节
  - 通过 `CTRL/BAUD/STAT/IRQ_STAT` 配置与查询状态

---

## 5. Interfaces & Contracts

### 5.1 Clock & Reset


- `clk`：主时钟，上升沿触发所有时序逻辑
- `rst_n`：active-low，**同步释放**
- 复位期间要求：
  - 所有输出端口应为已定义值（不得 X/Z）
  - `uart_tx` 在复位期间与复位后空闲态均为 `1`
  - CSR 复位值见 Regmap（第 8 章）

### 5.2 Top-level Port List（端口表）


| Port            |  Dir |      Width | Domain | Description                                   |
| --------------- | ---: | ---------: | ------ | --------------------------------------------- |
| `clk`           |   in |          1 | clk    | system clock                                  |
| `rst_n`         |   in |          1 | clk    | active-low reset (sync deassert)              |
| `s_axi_awaddr`  |   in |   `ADDR_W` | clk    | write address (byte address)                  |
| `s_axi_awprot`  |   in |          3 | clk    | protection type (ignored, must be accepted)   |
| `s_axi_awvalid` |   in |          1 | clk    | write address valid                           |
| `s_axi_awready` |  out |          1 | clk    | write address ready                           |
| `s_axi_wdata`   |   in |   `DATA_W` | clk    | write data                                    |
| `s_axi_wstrb`   |   in | `DATA_W/8` | clk    | byte enables                                  |
| `s_axi_wvalid`  |   in |          1 | clk    | write data valid                              |
| `s_axi_wready`  |  out |          1 | clk    | write data ready                              |
| `s_axi_bresp`   |  out |          2 | clk    | write response (`OKAY=2'b00`, `SLVERR=2'b10`) |
| `s_axi_bvalid`  |  out |          1 | clk    | write response valid                          |
| `s_axi_bready`  |   in |          1 | clk    | write response ready                          |
| `s_axi_araddr`  |   in |   `ADDR_W` | clk    | read address                                  |
| `s_axi_arprot`  |   in |          3 | clk    | protection type (ignored, must be accepted)   |
| `s_axi_arvalid` |   in |          1 | clk    | read address valid                            |
| `s_axi_arready` |  out |          1 | clk    | read address ready                            |
| `s_axi_rdata`   |  out |   `DATA_W` | clk    | read data                                     |
| `s_axi_rresp`   |  out |          2 | clk    | read response (`OKAY/SLVERR`)                 |
| `s_axi_rvalid`  |  out |          1 | clk    | read data valid                               |
| `s_axi_rready`  |   in |          1 | clk    | read data ready                               |
| `uart_tx`       |  out |          1 | clk    | UART TX line (idle=1)                         |
| `uart_rx`       |   in |          1 | clk    | UART RX line                                  |
| `irq`           |  out |          1 | clk    | interrupt level                               |

### 5.3 Protocol Contract：AXI4-Lite Slave（事务规则）


- Outstanding model：
  - **Single outstanding**：同一时间最多处理 1 个写事务（AW+W→B）与 1 个读事务（AR→R）
- Ready/backpressure：
  - `*_ready` 可回压（允许拉低），但不得造成死锁
  - 默认策略：当内部 CSR/数据通路可接受时拉高 ready
- Write semantics（简化且可测）：
  - 写事务在同时完成 `AW` 与 `W` 握手后进入执行阶段
  - 对 CSR 写：支持 `WSTRB` 字节掩码（仅对被 strobe 的 byte 生效）
  - 对 `TXDATA` 写：仅使用 `WDATA[7:0]`
    - 若 TX FIFO 未满：入队并 `BRESP=OKAY`
    - 若 TX FIFO 满：不入队并 `BRESP=SLVERR`（避免软件无限等待）
- Read semantics：
  - 读事务在 `AR` 握手后返回 `RDATA`
  - 对 `RXDATA` 读：若 RX FIFO 非空则返回 `RDATA[7:0]=byte` 并 **pop**；若为空则返回 `0` 且 `RRESP=OKAY`（是否置 `RX_UNDERFLOW` 由第 8/7 章定义）
- Addressing：
  - 仅支持 **word-aligned (addr[1:0]==0)**；非对齐访问返回 `SLVERR`
  - 地址为 byte address；内部以 `addr[? : 2]` 选择寄存器

### 5.4 Protocol Contract：UART（电气/时序语义）


- Line idle level：
  - TX idle = `1`
- Frame format (default)：
  - start bit: `0`
  - data bits: 8 (LSB first)
  - parity: disabled by default（`CTRL.PARITY_EN` 可开；odd/even 由 `CTRL.PARITY_ODD`）
  - stop bits: 1

---

## 6. Parameters & Configuration（参数化/配置）


- `DATA_W`：固定 32（本项目不做参数化更稳）
- `ADDR_W`：默认 16（覆盖 64KB 地址空间即可）
- `FIFO_DEPTH`：默认 16，范围 [1, 1024]
  - 行为影响：`STAT.TX_FULL/TX_EMPTY`、`STAT.RX_FULL/RX_EMPTY`、overrun 条件
- `OVERSAMPLE`：默认 16，范围 [8, 32]
  - 行为影响：RX 对齐与采样 tick 间隔
- `CLK_FREQ_HZ`：默认 50_000_000（用于 BAUD_DIV 计算/解释）
- `BAUD_DEFAULT`：默认 115200（复位后有效）

---

## 7. Functional Requirements（需求清单，带可验证 ID）


### REQ-001：复位行为

- Priority: MUST
- Statement:
  - When `rst_n==0`, the design shall reset all CSRs to their reset values.
  - `uart_tx` shall be driven to `1` during reset and after reset when idle.
  - `irq` shall be `0` during reset.
- Verify: SIM(TEST-001), FORMAL(PROP-001)

## 8. Register Map / CSR（寄存器表）


### 8.1 Address Map（32-bit, word-aligned）

| Reg        | Addr | Access | Reset                  | Description                                          |
| ---------- | ---- | ------ | ---------------------- | ---------------------------------------------------- |
| `CTRL`     | 0x00 | RW     | 0x0000_0000            | enable, irq enables, parity config                   |
| `BAUD`     | 0x04 | RW     | `BAUD_DEFAULT` encoded | baud divider (implementation-defined encoding below) |
| `STAT`     | 0x08 | RO     | 0x0000_0000            | fifo status, busy flags, error flags                 |
| `TXDATA`   | 0x0C | WO     | -                      | write byte to TX FIFO                                |
| `RXDATA`   | 0x10 | RO     | -                      | read byte from RX FIFO (read pops)                   |
| `IRQ_STAT` | 0x14 | RW1C   | 0x0                    | irq status (write-1-clear for latched errors)        |

> BAUD encoding（写清，避免 agent 自作主张）：  
> - `BAUD.DIV` (bits[15:0])：`baud_div` = cycles per bit time tick  
> - `baud_tick` asserted every `baud_div` cycles  
> - SW 可直接写入预计算的 divider（TB 也用该规则预计算）

### 8.2 Field Definitions（示例）

- `CTRL.EN` (bit0): RW, reset=0
  - effect: 1=enable UART; 0=TX idle, RX disabled（RX 不采样）
- `CTRL.TX_IRQ_EN` (bit1): RW, reset=0
- `CTRL.PARITY_ODD` (bit5): RW, reset=0 (0 even, 1 odd)
- `STAT.TX_FULL` (bit0): RO
- `STAT.TX_EMPTY` (bit1): RO
- `STAT.RX_FULL` (bit2): RO


**Side effects（必须写清）**
- Read `RXDATA`：
  - if RX FIFO non-empty：`RDATA[7:0]=byte` and pop 1 entry
  - else：`RDATA=0`（不置错误；若要 underflow，必须在此处显式定义）
- Write `TXDATA`：
  - if TX FIFO non-full：push `WDATA[7:0]`
  - if full：no push，AXI write response `SLVERR`

---

## 9. Timing & Microarchitecture（时序与微架构约束）


### 9.1 Module Decomposition（文件级职责）

| Module          | Responsibility                                        |
| --------------- | ----------------------------------------------------- |
| `axi_uart_top`  | top integration, port wiring                          |
| `axi_lite_regs` | AXI-Lite slave + CSR + reg side effects               |
| `baud_gen`      | divider -> `baud_tick` and optional oversample tick   |
| `uart_tx`       | serialize bytes: idle/start/data/parity/stop FSM      |
| `uart_rx`       | detect start, sample bits at midpoints, assemble byte |
| `fifo_sync`     | parameterized sync FIFO for TX/RX                     |

### 9.2 TX FSM（必须写状态/转移条件）

- States: `IDLE`, `START`, `DATA[0..7]`, `PARITY`, `STOP`
- Transition driver: `baud_tick`
- Data source:
  - On entering `START` from `IDLE`：
    - if `CTRL.EN==1` AND TX FIFO not empty：pop 1 byte into shift register
- Output behavior:
  - `IDLE`: `uart_tx=1`
  - `START`: `uart_tx=0`
  - `DATA[i]`: `uart_tx = data[i]` (LSB first)
  - `PARITY`: `uart_tx = parity_bit` when enabled
  - `STOP`: `uart_tx=1`
- Busy definition:
  - `STAT.TX_BUSY=1` when FSM not in `IDLE` OR TX FIFO not empty (implementation choose one; **本例选择：FSM not IDLE**)

### 9.3 RX Sampling（关键 corner）

- Start detect:
  - detect `uart_rx` falling edge while enabled
  - wait `OVERSAMPLE/2` oversample ticks to confirm mid-start still low
- Sampling:
  - sample 8 data bits at each bit’s midpoint
  - optional parity sample when enabled
  - sample stop bit:
    - if stop bit != 1 → set `FRAMING_ERR` and drop the byte（或保留 byte，二选一必须写清；本例：drop）
- FIFO push / overrun:
  - if RX FIFO full when a complete valid frame arrives → set `RX_OVERRUN` and drop

---

## 10. Repository Blueprint（仓库蓝图：多文件契约）


```
axi_uart_periph/
  rtl/
    axi_uart_top.sv
    modules/
      axi_lite_regs.sv
      baud_gen.sv
      uart_tx.sv
      uart_rx.sv
      fifo_sync.sv
    pkg/
      uart_pkg.sv           # typedef/params/helpers
  tb/
    axi_uart_tb.sv          # 纯 SV TB（或 cocotb/）
    models/
      uart_ref.py           # 可选：golden model
  scripts/
    run_sim.sh
    lint.sh
  Makefile
  README.md
```

- **文件职责约束（必须写一句话）**
  - `rtl/axi_uart_top.sv`：只做集成，不承载复杂逻辑
  - `rtl/modules/axi_lite_regs.sv`：CSR 与 side effects 的唯一来源（避免分散在多个模块）
  - `tb/axi_uart_tb.sv`：覆盖 TEST-001/010/011/020/030/040（见第 11 章）
  - `scripts/run_sim.sh`：一条命令跑完编译+仿真并给出 PASS/FAIL 退出码

  ---

  ## 11. Verification Plan（验收证据：tests / assertions / coverage）


  ### 11.1 Tests（Directed + 边界）


  > TB 基础结构（agent 指导）  
  > - 提供 AXI-Lite driver tasks：
  >   - `task axi_write32(input [ADDR_W-1:0] addr, input [31:0] data, input [3:0] wstrb, output [1:0] bresp);`
  >   - `task axi_read32 (input [ADDR_W-1:0] addr, output [31:0] data, output [1:0] rresp);`
  > - 提供 UART line helper tasks（纯 TB）：
  >   - `task uart_drive_rx_byte(input byte b, input int baud_div, input bit parity_en, input bit parity_odd);`
  >   - `task uart_capture_tx_byte(output byte b, input int baud_div, input bit parity_en, input bit parity_odd);`
  > - 提供通用检查宏：
  >   - `ASSERT_EQ(name, got, exp)`
  >   - `ASSERT_TRUE(name, cond)`

  #### TEST-001：复位一致性

  - Purpose：验证 reset 后 CSR/输出符合 REQ-001
  - Steps：
    1. `rst_n=0` 持续 N 个 clk
    2. 释放 `rst_n=1`（同步释放）
    3. 读 `CTRL/STAT/IRQ_STAT`
  - Checks：
    - `uart_tx==1`
    - `irq==0`
    - CSR 为 reset 值
  - Pass：全部满足

  ### 11.2 Assertions / SVA（可选但强力）


  - PROP-001 Reset outputs defined：
    - 当 `rst_n==0` 时，`uart_tx` 必为 1，`irq` 必为 0
 

  ### 11.3 Coverage（建议模板保留）


  - COV-001：TX FIFO full → 溢出写触发 SLVERR
  - COV-002：RX overrun 触发并被 RW1C 清除
  - COV-003：BAUD 更新在“发送中途”发生
  - COV-004：irq 因 RX 非空触发并在 pop 后释放

  ---

  ## 12. Build & Run（可复制命令）


  - `make sim`：编译 + 运行 TB（返回码反映 PASS/FAIL）
  - `make lint`：可选 lint
  - `scripts/run_sim.sh` 示例行为：
    - 编译：`iverilog -g2012 -o sim.out <rtl files> <tb files>`
    - 运行：`vvp sim.out`
    - 若 TB 打印 `ALL_TESTS_PASS` 则 exit 0，否则 exit 1

  ---

  ## 13. Acceptance Criteria（最终验收门槛）


  - AC-001：`make sim` exit code == 0
  - AC-002：TEST-001/010/011/020/022/030/040 全部 PASS
  - AC-003：无 X/Z 输出（TB 启用 X-check）

  ---

  ## 14. Implementation Nodes（可选但强力：防长程漂移）


  ### Node-00：Repo skeleton + build plumbing

  - Goal：生成目录树、Makefile、脚本、空壳模块（可编译）
  - Deliverables：
    - 目录结构与文件占位（第 10 章一致）
    - `make sim` 能跑通（即便测试暂时只做 smoke）
  - Gate：
    - 编译通过（无语法错误）
    - TB 启动并能结束（不死循环）

  ### Node-01：Top integration + package

  - Goal：实现 `axi_uart_top` 与 `uart_pkg`
  - Deliverables：
    - 完整端口列表匹配第 5.2 章
    - 包含统一参数/typedef（例如 CSR addr 常量、bit 定义）
  - Gate：
    - lint/编译通过
    - 端口未使用警告可接受但不得 X 驱动


  