# RTL 项目级 SPEC 示例：`axi_uart_periph`（SRS）

## 0. Meta 信息（版本/工具链/风格）

**解释（为什么要写）**  
本节用于冻结工程环境、语言子集、编码风格与验收工具链。对于项目级 RTL 生成任务，环境约束与实现风格属于第一层硬约束。若该部分缺失，agent 容易生成与工具链不兼容的代码，或在复位语义、时序风格、命名规则上出现全局不一致。

**示例内容**

- Project: `axi_uart_periph`
- Spec-Version: `0.2`
- RTL: `SystemVerilog (IEEE 1800-2017 synthesizable subset)`
- Toolchain:
  - Lint: `verilator --lint-only -Wall`
  - Sim: `iverilog -g2012`
  - Optional waveform: `vvp + dump.vcd`
- Reset policy:
  - `rst_n`：**active-low，同步释放**
- Clocking:
  - 单时钟域：`clk`
- Naming:
  - ports/signals：`snake_case`
  - parameters：`UPPER_SNAKE_CASE`
- Repo root: `axi_uart_periph/`
- RTL style rules:
  - 时序逻辑使用 `always_ff @(posedge clk)`
  - 组合逻辑使用 `always_comb`
  - 时序寄存器更新使用非阻塞赋值 `<=`
  - 组合逻辑中必须对所有输出/next-state 给出默认赋值
  - 不允许推断 latch
  - 不允许多驱动

**Implementation Hint**
- 该节应视为全文的“硬前提”，下游章节不得与本节冲突。
- 若仓库代码中存在多个风格来源，应以本节声明为统一约束进行归并。
- 若 agent 从现有仓库反推 spec，应优先从顶层模块、构建脚本与 lint 配置中抽取本节内容。

------

## 1. Abstract 

**解释**  
本节提供系统的目标能力、对外接口类别与交付形态，是整个规格文档的全局语义锚点。摘要不要求覆盖所有细节，但必须足以界定系统范围，并与后续模块划分、寄存器设计、验证计划保持一致。

**示例内容**  
`axi_uart_periph` 是一个基于 **AXI4-Lite** 可配置的 UART 外设，提供 **发送、接收、可编程波特率、TX/RX FIFO、状态寄存器与中断**，面向 SoC 低速串口通信与调试场景。项目交付物包括可综合 RTL、可执行 testbench、构建脚本与寄存器说明。

**Code Example**
```systemverilog
// Top-level capability summary (illustrative only)
assign irq = (ctrl_rx_irq_en && !rx_empty)
          || (ctrl_tx_irq_en && tx_empty)
          || (ctrl_err_irq_en && (framing_err || rx_overrun));
```

**Implementation Hint**
- 摘要中的能力项必须能在后续章节中找到对应落点：接口、REQ、CSR、TEST。
- 若仓库实现中存在“未在摘要中声明的重要功能”，应在 spec 整理阶段回填至摘要与 Goals。

------

## 2. Goals / Non-goals（范围边界）

**解释**  
本节定义系统范围的正反边界。Goals 表明必须实现的能力；Non-goals 用于排除容易被自动生成系统误扩展的方向。该节应直接服务于需求条目（REQ-*）的收敛，并为后续验收标准提供范围依据。

**示例内容**

### 2.1 Goals（必须实现）

- G1：实现 8N1 UART（8 data bits, no parity, 1 stop bit），支持可选奇偶校验（可配置开关）。
- G2：提供 AXI-Lite CSR（寄存器读写、状态查询、清中断）。
- G3：支持可编程波特率（分频器），支持运行时改波特率。
- G4：提供 TX/RX FIFO（深度参数化），并产生相应状态/中断。
- G5：提供一个最小可用 testbench，覆盖基本收发、寄存器访问、中断与边界场景。

**Code Example**
```systemverilog
// Goal-aligned parameter and feature switches
localparam int DATA_BITS = 8;
logic parity_en;
logic parity_odd;
```

**Implementation Hint**
- Goals 应尽量映射到可验证的对象：端口、寄存器、状态机、测试。
- 若 agent 需要从仓库生成 spec，可将“可配置项 + 已实现功能路径”优先映射到 Goals。

### 2.2 Non-goals（明确不做）

- NG1：不实现 AXI full、burst、out-of-order。
- NG2：不实现 DMA、不实现多串口通道。
- NG3：不要求严格兼容 16550 寄存器布局（但允许参考其语义）。
- NG4：不处理多时钟域 CDC；所有逻辑均处于 `clk` 域。
- NG5：不提供 UVM 环境；仅要求最小可运行 testbench。

**Code Example**
```systemverilog
// Explicitly excluded: no burst transfer support
// Only single beat AXI4-Lite accesses are supported.
```

**Implementation Hint**
- Non-goals 应优先用于约束 agent，防止其引入未要求的复杂机制。
- 若仓库中有“未被使用的预留代码”，不应自动提升为 Goal，除非存在明确调用路径或测试覆盖。

------

## 3. Glossary（术语表）

**解释**  
术语表用于消除歧义，特别是状态类、错误类和时序类术语。对于 agent 而言，术语表是把自然语言叙述映射到一致命名体系的重要桥梁。

**示例内容**

| Term         | Meaning                        |
| ------------ | ------------------------------ |
| `baud_tick`  | 波特率发送/采样使用的周期脉冲  |
| `tx_fifo`    | 待发送字节队列                 |
| `rx_fifo`    | 已接收字节队列                 |
| `rx_overrun` | RX FIFO 满仍继续接收导致丢字节 |
| `irq`        | 中断输出（电平触发）           |
| `framing_err`| stop bit 非法                  |

**Code Example**
```systemverilog
typedef enum logic [2:0] {
    TX_IDLE,
    TX_START,
    TX_DATA,
    TX_PARITY,
    TX_STOP
} tx_state_e;
```

**Implementation Hint**
- 术语表中的关键名词应尽量与代码中的信号名、状态名、寄存器字段名保持一致。
- 若存在代码命名与 spec 术语不一致，应在 spec 中显式列出映射关系。

------

## 4. System Context（系统上下文）

**解释**  
本节给出系统在更大系统中的位置、对外依赖与内部模块分层。对于项目级 RTL repo，该节应描述 top 模块、外部总线/引脚、内部子模块职责与典型数据流向。

**示例内容**

- Top module：`axi_uart_top`
- External connections：
  - AXI-Lite slave（控制/状态寄存器）
  - UART pins：`uart_tx`, `uart_rx`
  - Interrupt：`irq`
- Internal blocks：
  - `axi_lite_regs`：AXI-Lite → CSR
  - `baud_gen`：生成 `baud_tick`
  - `uart_tx`：发送器（含 shift/FSM）
  - `uart_rx`：接收器（含 oversample/FSM）
  - `fifo_sync`：同步 FIFO（TX/RX 各一个）

**Code Example**
```systemverilog
axi_lite_regs u_regs (
    .clk      (clk),
    .rst_n    (rst_n),
    .wr_en    (wr_en),
    .rd_en    (rd_en),
    .addr     (csr_addr),
    .wdata    (csr_wdata),
    .rdata    (csr_rdata)
);

uart_tx u_tx (
    .clk      (clk),
    .rst_n    (rst_n),
    .baud_tick(baud_tick),
    .fifo_pop (tx_fifo_pop),
    .fifo_rdata(tx_fifo_rdata),
    .uart_tx  (uart_tx)
);
```

**Implementation Hint**
- 本节建议优先由顶层实例化关系、文件名、包依赖关系自动抽取。
- 若仓库中模块职责不清晰，应在 spec 归整时按“对外接口 + 内部状态归属”重新分层描述。

------

## 5. Interfaces & Contracts（最关键：接口契约）

> 本章用于冻结外部接口的结构与行为，是从代码反推详细 spec 时最重要的部分之一。  
> 对于 RTL spec2repo，接口契约不仅包括端口表，还包括握手规则、回压策略、错误码与时序约束。

### 5.1 Clock & Reset

**解释**  
必须明确时钟域、复位极性、复位释放语义与复位期间的可见行为。对于仓库级生成任务，复位契约是最基础的一致性来源，影响寄存器初始化、状态机起始态、波形检查与断言书写。

**示例内容**

- `clk`：主时钟，上升沿触发所有时序逻辑
- `rst_n`：active-low，**同步释放**
- 复位期间要求：
  - 所有输出端口（除 AXI ready/resp 等可固定值信号）应为已定义值，不得 X/Z
  - `uart_tx` 在 reset 期间与 idle 状态均为 `1`
  - CSR 复位值见 Regmap

**Code Example**
```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        tx_state <= TX_IDLE;
        uart_tx  <= 1'b1;
        irq      <= 1'b0;
    end else begin
        tx_state <= tx_state_n;
        uart_tx  <= uart_tx_n;
        irq      <= irq_n;
    end
end
```

**Implementation Hint**
- 当从仓库代码提炼 spec 时，应优先搜索 reset 分支中的赋值，提取复位值与初始态。
- 若存在异步复位写法但脚本/注释宣称同步释放，应在 spec 中保留真实行为并记录差异。

------

### 5.2 Top-level Port List（端口表）

**解释**  
端口表是接口契约的结构化载体。应给出方向、位宽、时钟域与语义说明，并避免使用省略形式。对于自动生成详细 spec 的任务，端口表应可直接从顶层 module header 与连接关系中抽取。

**示例内容**

| Port            | Dir  | Width | Domain | Description               |
| --------------- | ---- | ----- | ------ | ------------------------- |
| `clk`           | in   | 1     | clk    | system clock              |
| `rst_n`         | in   | 1     | clk    | active-low reset          |
| `s_axi_awvalid` | in   | 1     | clk    | AXI-Lite write addr valid |
| `s_axi_awready` | out  | 1     | clk    | AXI-Lite write addr ready |
| `s_axi_awaddr`  | in   | 16    | clk    | AXI-Lite write address    |
| `s_axi_wvalid`  | in   | 1     | clk    | AXI-Lite write data valid |
| `s_axi_wready`  | out  | 1     | clk    | AXI-Lite write data ready |
| `s_axi_wdata`   | in   | 32    | clk    | AXI-Lite write data       |
| `s_axi_wstrb`   | in   | 4     | clk    | AXI-Lite byte enables     |
| `s_axi_bvalid`  | out  | 1     | clk    | AXI-Lite write response valid |
| `s_axi_bready`  | in   | 1     | clk    | AXI-Lite write response ready |
| `s_axi_bresp`   | out  | 2     | clk    | write response code       |
| `s_axi_arvalid` | in   | 1     | clk    | AXI-Lite read addr valid  |
| `s_axi_arready` | out  | 1     | clk    | AXI-Lite read addr ready  |
| `s_axi_araddr`  | in   | 16    | clk    | AXI-Lite read address     |
| `s_axi_rvalid`  | out  | 1     | clk    | AXI-Lite read data valid  |
| `s_axi_rready`  | in   | 1     | clk    | AXI-Lite read data ready  |
| `s_axi_rdata`   | out  | 32    | clk    | AXI-Lite read data        |
| `s_axi_rresp`   | out  | 2     | clk    | read response code        |
| `uart_tx`       | out  | 1     | clk    | UART TX line (idle=1)     |
| `uart_rx`       | in   | 1     | clk    | UART RX line              |
| `irq`           | out  | 1     | clk    | interrupt level           |

**Code Example**
```systemverilog
module axi_uart_top #(
    parameter int ADDR_W      = 16,
    parameter int DATA_W      = 32,
    parameter int FIFO_DEPTH  = 16,
    parameter int OVERSAMPLE  = 16
) (
    input  logic                 clk,
    input  logic                 rst_n,
    // AXI4-Lite slave
    input  logic [ADDR_W-1:0]    s_axi_awaddr,
    input  logic                 s_axi_awvalid,
    output logic                 s_axi_awready,
    input  logic [DATA_W-1:0]    s_axi_wdata,
    input  logic [DATA_W/8-1:0]  s_axi_wstrb,
    input  logic                 s_axi_wvalid,
    output logic                 s_axi_wready,
    output logic [1:0]           s_axi_bresp,
    output logic                 s_axi_bvalid,
    input  logic                 s_axi_bready,
    input  logic [ADDR_W-1:0]    s_axi_araddr,
    input  logic                 s_axi_arvalid,
    output logic                 s_axi_arready,
    output logic [DATA_W-1:0]    s_axi_rdata,
    output logic [1:0]           s_axi_rresp,
    output logic                 s_axi_rvalid,
    input  logic                 s_axi_rready,
    // UART
    output logic                 uart_tx,
    input  logic                 uart_rx,
    output logic                 irq
);
```

**Implementation Hint**
- 端口表不应保留 `...` 作为最终 spec 内容；在模板示例中可以保留，但增强版 v2 作为 agent 参考时应尽量列全。
- 从仓库自动生成 spec 时，应补充 port width 的参数化来源（如 `ADDR_W`, `DATA_W`）。

------

### 5.3 Protocol Contract：AXI4-Lite Slave（事务规则）

**解释**  
该部分定义总线事务语义，包括支持范围、回压策略、响应时序、地址约束与错误处理。它决定 testbench 的 driver 行为，也决定 CSR side effect 的验收方法。

**示例内容（最低约束版，强烈推荐）**

- Supported: 32-bit data, 16-bit address（可参数化）
- Outstanding:
  - 仅支持 **single outstanding** 读/写事务
- Ready/backpressure:
  - `awready/wready/arready` 允许在内部忙时拉低
  - 不允许协议死锁
- Write semantics:
  - AW 与 W 都完成握手后，在 1~N cycles 内给出 `bvalid`
  - 对齐要求：仅支持 word-aligned address
  - 非法地址返回 `SLVERR`
  - `WSTRB` 按字节使能生效
- Read semantics:
  - AR 完成握手后，在 1~N cycles 内给出 `rvalid`
  - 非法地址返回 `SLVERR`
- TXDATA write side effect:
  - `wdata[7:0]` 作为写入字节
  - 若 TX FIFO 满，则不入队并返回 `SLVERR`

**Code Example**
```systemverilog
always_comb begin
    bresp_n = 2'b00; // OKAY
    tx_fifo_push = 1'b0;

    if (wr_fire) begin
        unique case (wr_addr)
            TXDATA_ADDR: begin
                if (!tx_full) begin
                    tx_fifo_push  = 1'b1;
                    tx_fifo_wdata = wdata[7:0];
                end else begin
                    bresp_n = 2'b10; // SLVERR
                end
            end
            default: begin
                bresp_n = 2'b10; // SLVERR
            end
        endcase
    end
end
```

**TB Example**
```systemverilog
task automatic axi_write32(
    input  logic [15:0] addr,
    input  logic [31:0] data,
    input  logic [3:0]  wstrb,
    output logic [1:0]  bresp
);
    @(posedge clk);
    s_axi_awaddr  <= addr;
    s_axi_awvalid <= 1'b1;
    s_axi_wdata   <= data;
    s_axi_wstrb   <= wstrb;
    s_axi_wvalid  <= 1'b1;
    wait (s_axi_awready && s_axi_wready);
    @(posedge clk);
    s_axi_awvalid <= 1'b0;
    s_axi_wvalid  <= 1'b0;
    wait (s_axi_bvalid);
    bresp = s_axi_bresp;
    s_axi_bready <= 1'b1;
    @(posedge clk);
    s_axi_bready <= 1'b0;
endtask
```

**Implementation Hint**
- 若仓库实现中 AXI-Lite 行为分散在多个 always block，应在 spec 中统一抽象为“读路径”“写路径”“响应路径”三个契约对象。
- 建议将 `wr_fire` / `rd_fire` 等内部握手抽象为 spec 中的中间事件描述，以增强可读性。

------

### 5.4 Protocol Contract：UART（电气/时序语义）

**解释**  
该部分定义 UART 线级语义与位级行为，包括 idle 电平、帧格式、采样策略、波特率 tick 与错误定义。对 agent 而言，这类内容最好辅以小段代码锚点，而不是仅靠文字叙述。

**示例内容**

- Line idle level:
  - TX idle = `1`
- Frame format (default):
  - start bit: `0`
  - data bits: 8 (LSB first)
  - parity: disabled by default（可配置 odd/even）
  - stop bits: 1
- Sampling:
  - RX 使用 `OVERSAMPLE=16`（默认）在起始位中点对齐
  - `baud_tick`：每 bit time 的边界 tick
- Error definition:
  - stop bit != 1 → `FRAMING_ERR=1`
  - RX FIFO 满仍收到新字节 → `RX_OVERRUN=1`

**Code Example**
```systemverilog
typedef enum logic [2:0] {
    RX_IDLE,
    RX_START,
    RX_DATA,
    RX_PARITY,
    RX_STOP
} rx_state_e;

always_ff @(posedge clk) begin
    if (!rst_n) begin
        rx_state <= RX_IDLE;
    end else if (os_tick) begin
        rx_state <= rx_state_n;
    end
end
```

**TB Example**
```systemverilog
task automatic uart_drive_rx_byte(
    input byte data,
    input int  baud_div
);
    int i;
    uart_rx <= 1'b1;
    repeat (baud_div) @(posedge clk);
    uart_rx <= 1'b0; // start bit
    repeat (baud_div) @(posedge clk);
    for (i = 0; i < 8; i++) begin
        uart_rx <= data[i];
        repeat (baud_div) @(posedge clk);
    end
    uart_rx <= 1'b1; // stop bit
    repeat (baud_div) @(posedge clk);
endtask
```

**Implementation Hint**
- 若仓库中已经存在 UART model 或 monitor，应在 spec 中优先吸收其帧格式与采样假设。
- 对于 framing error / parity error / overrun，应同时在本节和测试节给出一致表述。

------

## 6. Parameters & Configuration（参数化/配置）

**解释**  
参数与配置项会影响端口宽度、时序、FIFO 容量和验证策略。项目级代码生成的一个常见失败模式是参数定义与使用分散，导致文档与实现不一致。

**示例内容**

- `DATA_W`：固定 32（本项目不参数化）
- `ADDR_W`：默认 16
- `FIFO_DEPTH`：默认 16，范围 [1, 1024]
- `OVERSAMPLE`：默认 16，范围 [8, 32]
- `CLK_FREQ_HZ`：默认 50_000_000
- `BAUD_DEFAULT`：默认 115200

**Code Example**
```systemverilog
localparam int unsigned FIFO_DEPTH = 16;
logic [$clog2(FIFO_DEPTH+1)-1:0] tx_count, rx_count;
```

**Implementation Hint**
- 参数定义建议由 package 或顶层参数唯一承载，不应在多个模块中重复硬编码。
- 若 agent 反推 spec，应同时列出“定义点”和“使用点”，以发现潜在不一致。

------

## 7. Functional Requirements（需求清单，带可验证 ID）

**解释**  
本节将系统能力形式化为可验证需求。每条需求应包含优先级、行为陈述、边界条件与验证映射。对于 spec2repo 场景，REQ 是连接实现、测试与文档的核心追踪主键。

### REQ-001：复位行为

- Priority: MUST
- Statement:
  - When `rst_n==0`, the design shall reset all CSRs to their reset values and drive `uart_tx=1`, `irq=0`.
- Corner Cases:
  - Reset release is synchronous.
- Verify:
  - SIM(TEST-001), FORMAL(PROP-001)

**Code Example**
```systemverilog
if (!rst_n) begin
    ctrl_reg   <= '0;
    irq_status <= '0;
    uart_tx    <= 1'b1;
end
```

### REQ-002：TXDATA 写入与发送

- Priority: MUST
- Statement:
  - When SW writes `TXDATA` and TX FIFO is not full, the byte shall be enqueued and eventually transmitted on `uart_tx`.
- Corner:
  - TX FIFO full 时返回 `SLVERR`
- Verify:
  - SIM(TEST-010), SIM(TEST-011)

**Code Example**
```systemverilog
if (wr_fire && wr_addr == TXDATA_ADDR && !tx_full) begin
    tx_fifo_push  <= 1'b1;
    tx_fifo_wdata <= wdata[7:0];
end
```

### REQ-003：RX 接收与入队

- Priority: MUST
- Statement:
  - When a valid UART frame is received, the byte shall be pushed into RX FIFO.
  - If RX FIFO is full, set `RX_OVERRUN` and drop the incoming byte.
- Verify:
  - SIM(TEST-020), SIM(TEST-022)

**Code Example**
```systemverilog
if (rx_frame_done) begin
    if (!rx_full) begin
        rx_fifo_push  <= 1'b1;
        rx_fifo_wdata <= rx_shift_reg;
    end else begin
        rx_overrun <= 1'b1;
    end
end
```

### REQ-004：中断（电平触发）

- Priority: SHOULD
- Statement:
  - `irq` shall assert whenever an enabled interrupt condition is true and remain asserted until the condition is cleared.
- Verify:
  - SIM(TEST-030), FORMAL(PROP-010)

**Code Example**
```systemverilog
assign irq = (ctrl_rx_irq_en && !rx_empty)
          || (ctrl_tx_irq_en && tx_empty)
          || (ctrl_err_irq_en && (framing_err || rx_overrun));
```

### REQ-005：波特率更新

- Priority: MUST
- Statement:
  - When SW updates `BAUD` divider, the new baud rate shall take effect for subsequent frames.
- Verify:
  - SIM(TEST-040)

**Code Example**
```systemverilog
if (wr_fire && wr_addr == BAUD_ADDR) begin
    baud_div <= wdata[15:0];
end
```

**Implementation Hint**
- 建议每条 REQ 都映射到至少一个测试编号；如条件适合，再映射到一个自然语言 property。
- 若从仓库自动生成 spec，应优先由测试命名、错误码路径、寄存器 side effect 来恢复 REQ 粒度。

------

## 8. Register Map / CSR（寄存器表）

**解释**  
寄存器表是最容易结构化抽取、最适合自动评分的内容之一。应同时提供地址布局、访问属性、复位值、字段定义与 side effect。

### 8.1 Address Map（32-bit, word-aligned）

| Reg        | Addr | Access | Reset       | Description |
| ---------- | ---- | ------ | ----------- | ----------- |
| `CTRL`     | 0x00 | RW     | 0x0000_0000 | enable, irq enables, parity config |
| `BAUD`     | 0x04 | RW     | `BAUD_DEFAULT` | baud divider |
| `STAT`     | 0x08 | RO     | 0x0000_0000 | fifo status, busy flags, error flags |
| `TXDATA`   | 0x0C | WO     | -           | write byte to TX FIFO |
| `RXDATA`   | 0x10 | RO     | -           | read byte from RX FIFO |
| `IRQ_STAT` | 0x14 | RW1C   | 0x0         | irq status (write-1-clear) |

**Code Example**
```systemverilog
localparam logic [15:0] CTRL_ADDR     = 16'h0000;
localparam logic [15:0] BAUD_ADDR     = 16'h0004;
localparam logic [15:0] STAT_ADDR     = 16'h0008;
localparam logic [15:0] TXDATA_ADDR   = 16'h000C;
localparam logic [15:0] RXDATA_ADDR   = 16'h0010;
localparam logic [15:0] IRQ_STAT_ADDR = 16'h0014;
```

### 8.2 Field Definitions（示例）

- `CTRL.EN` (bit0): RW, reset=0
  - effect: 1=enable UART; 0=TX idle, RX disabled
- `CTRL.TX_IRQ_EN` (bit1): RW, reset=0
- `CTRL.RX_IRQ_EN` (bit2): RW, reset=0
- `CTRL.ERR_IRQ_EN` (bit3): RW, reset=0
- `CTRL.PARITY_EN` (bit4): RW, reset=0
- `CTRL.PARITY_ODD` (bit5): RW, reset=0
- `STAT.TX_FULL` (bit0): RO
- `STAT.TX_EMPTY` (bit1): RO
- `STAT.RX_FULL` (bit2): RO
- `STAT.RX_EMPTY` (bit3): RO
- `STAT.TX_BUSY` (bit4): RO
- `STAT.FRAMING_ERR` (bit8): RO
- `STAT.RX_OVERRUN` (bit9): RO
- `IRQ_STAT.FRAMING_ERR` (bit0): RW1C
- `IRQ_STAT.RX_OVERRUN` (bit1): RW1C

**Code Example**
```systemverilog
if (wr_fire && wr_addr == IRQ_STAT_ADDR) begin
    if (wdata[0]) framing_err <= 1'b0;
    if (wdata[1]) rx_overrun  <= 1'b0;
end
```

**Implementation Hint**
- 建议在 spec 中同时写出“读写语义”与“副作用语义”，例如 RXDATA 读取是否 pop、IRQ_STAT 是否 RW1C。
- 若仓库中 side effect 分散在多个模块，应在 spec 中统一归入对应寄存器项。

------

## 9. Timing & Microarchitecture（时序与微架构约束）

**解释**  
本节用于约束实现空间，确保不同实现仍在相同微架构意图下可比较、可验证。项目级 RTL spec 不需要给出完整实现，但应给出模块职责、关键状态机与边界行为。

### 9.1 Module Decomposition（文件级职责）

| Module          | Responsibility |
| --------------- | -------------- |
| `axi_uart_top`  | top integration, port wiring |
| `axi_lite_regs` | AXI-Lite slave + CSR + reg side effects |
| `baud_gen`      | divider -> `baud_tick` and optional oversample tick |
| `uart_tx`       | serialize bytes: idle/start/data/parity/stop FSM |
| `uart_rx`       | detect start, sample bits at midpoints, assemble byte |
| `fifo_sync`     | parameterized sync FIFO for TX/RX |

**Code Example**
```systemverilog
fifo_sync #(
    .DEPTH(FIFO_DEPTH),
    .WIDTH(8)
) u_tx_fifo (
    .clk   (clk),
    .rst_n (rst_n),
    .push  (tx_fifo_push),
    .pop   (tx_fifo_pop),
    .wdata (tx_fifo_wdata),
    .rdata (tx_fifo_rdata),
    .full  (tx_full),
    .empty (tx_empty)
);
```

### 9.2 TX FSM（必须写状态/转移条件）

- States: `IDLE`, `START`, `DATA[0..7]`, `PARITY`, `STOP`
- Transition driver: `baud_tick`
- Data source: TX FIFO pop when entering `START`
- Idle behavior: `uart_tx=1`

**Code Example**
```systemverilog
always_comb begin
    tx_state_n = tx_state;
    uart_tx_n  = 1'b1;
    tx_fifo_pop = 1'b0;

    unique case (tx_state)
        TX_IDLE: begin
            uart_tx_n = 1'b1;
            if (ctrl_en && !tx_empty && baud_tick) begin
                tx_fifo_pop = 1'b1;
                tx_state_n  = TX_START;
            end
        end
        TX_START: begin
            uart_tx_n = 1'b0;
            if (baud_tick) tx_state_n = TX_DATA;
        end
        default: ;
    endcase
end
```

### 9.3 RX Sampling（关键 corner）

- Start bit detect: line goes low, wait half-bit to confirm
- Sample points: every 1 bit time at mid-bit
- On framing error (stop bit !=1): set error flag and drop byte

**Code Example**
```systemverilog
if (rx_state == RX_START && os_tick) begin
    if (sample_cnt == OVERSAMPLE/2) begin
        if (uart_rx == 1'b0) begin
            rx_state_n = RX_DATA;
            bit_idx_n  = '0;
        end else begin
            rx_state_n = RX_IDLE;
        end
    end
end
```

**Implementation Hint**
- 若仓库实现中 TX/RX 被写成一个合并模块，spec 仍建议拆分为“发送路径 / 接收路径”两个逻辑职责。
- 对边界行为（例如 framing error 丢弃/保留字节）必须在本节与测试节保持一致。

------

## 10. Repository Blueprint（仓库蓝图：多文件契约）

**解释**  
仓库蓝图描述最终交付物的组织形式。对于 spec2repo，这一节不仅是目录树说明，也是一种“文件责任契约”。

**示例内容**

```text
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
      uart_pkg.sv
  tb/
    axi_uart_tb.sv
    models/
      uart_ref.py
  scripts/
    run_sim.sh
    lint.sh
  Makefile
  README.md
```

**Code Example**
```makefile
sim:
\tbash scripts/run_sim.sh

lint:
\tbash scripts/lint.sh
```

**Implementation Hint**
- 从仓库自动提炼 spec 时，本节可由文件树、构建脚本、test 入口与顶层文件推断。
- 若仓库中存在冗余/废弃文件，可仅将参与构建与验证的文件纳入 blueprint。

------

## 11. Verification Plan（验收证据：tests / assertions / coverage）

**解释**  
该节定义系统的可执行验收证据，是将抽象需求转化为自动判定的关键。对于 agent 而言，Tests 应尽量给出调用接口、刺激、期望结果与通过条件。

### 11.1 Tests（Directed + 边界）

**解释**  
每个测试至少应包含：目标、前置配置、刺激序列、检查点与通过条件。推荐同时给出 TB task 接口示例，作为 agent 编写 testbench 的脚手架。

**示例内容**

#### TEST-001 Reset defaults
- Purpose：验证复位值与复位输出不为 X
- Steps：
  1. `rst_n=0` 保持 10 cycles
  2. `rst_n=1` 释放
  3. 读取 `CTRL/STAT/IRQ_STAT`
- Checks：
  - `uart_tx==1`
  - `irq==0`
  - CSR 为 reset 值

#### TEST-010 TX single byte
- Purpose：验证 `TXDATA` 写入后 TX 帧正确（8N1）
- Steps：
  1. 写 `CTRL.EN=1`
  2. 写 `BAUD`
  3. 写 `TXDATA=8'h55`
  4. 采样 `uart_tx`
- Checks：
  - 帧为 start + 8 data + stop
  - 数据值正确

#### TEST-011 TX FIFO full behavior
- Purpose：验证 FIFO 满时返回 `SLVERR`
- Steps：
  1. 写满 FIFO
  2. 继续写 1 次 `TXDATA`
- Checks：
  - `BRESP=SLVERR`

#### TEST-020 RX receive + read RXDATA
- Purpose：验证 RX 收帧与读寄存器
- Steps：
  1. 通过 `uart_drive_rx_byte` 注入字节
  2. 读 `RXDATA`
- Checks：
  - 读回字节一致

#### TEST-022 RX overrun
- Purpose：验证 RX FIFO 满再来数据时的 overrun 行为
- Checks：
  - `RX_OVERRUN` 置位
  - 溢出的最后字节被丢弃

#### TEST-030 IRQ behaviors
- Purpose：验证 irq 条件与清除
- Checks：
  - 条件满足时 irq 为 1
  - 条件清除后 irq 为 0

#### TEST-040 BAUD update semantics
- Purpose：验证波特率更新对下一帧生效
- Checks：
  - 两帧 bit 间隔不同，第二帧按新 divider 工作

**TB Example**
```systemverilog
task automatic axi_read32(
    input  logic [15:0] addr,
    output logic [31:0] data,
    output logic [1:0]  rresp
);
    @(posedge clk);
    s_axi_araddr  <= addr;
    s_axi_arvalid <= 1'b1;
    wait (s_axi_arready);
    @(posedge clk);
    s_axi_arvalid <= 1'b0;
    wait (s_axi_rvalid);
    data  = s_axi_rdata;
    rresp = s_axi_rresp;
    s_axi_rready <= 1'b1;
    @(posedge clk);
    s_axi_rready <= 1'b0;
endtask
```

**Implementation Hint**
- 建议测试条目与 REQ 编号做显式映射。
- 若仓库中已有 testbench，可优先抽取 driver task、monitor、scoreboard 的接口签名与核心检查逻辑。

### 11.2 Assertions / SVA（可选但强力）

**解释**  
断言用于补充仿真测试难以覆盖的安全性/活性约束。即使暂不提供完整 SVA，也应给出足够明确的自然语言 property。

**示例内容**

- PROP-001：复位期间 `uart_tx==1 && irq==0`
- PROP-010：当 `RX_IRQ_EN && !RX_EMPTY` 时，`irq` 必须拉高
- PROP-020：FIFO count 不得越界

**Code Example**
```systemverilog
assert property (@(posedge clk) disable iff (!rst_n)
    (ctrl_rx_irq_en && !rx_empty) |-> irq
);
```

**Implementation Hint**
- 若仓库代码中已存在 `assert` / `cover` / checker module，应直接映射为 Assertions 小节内容。
- 对 RW1C、握手活性、FIFO 安全性等推荐优先编写 property。

### 11.3 Coverage（建议模板保留）

**解释**  
覆盖项用于说明测试应命中的关键边界行为。它不一定需要精确到功能覆盖组语法，但应说明最小覆盖意图。

**示例内容**

- COV-001：TX FIFO full → 返回 SLVERR
- COV-002：RX overrun 触发并被清除
- COV-003：BAUD 更新在发送中途发生
- COV-004：irq 因 RX not empty 触发并在 pop 后释放

**Code Example**
```systemverilog
// Example coverage intent (informal)
cover property (@(posedge clk) disable iff (!rst_n)
    tx_full ##1 wr_fire && wr_addr == TXDATA_ADDR
);
```

**Implementation Hint**
- 若仓库无显式 coverage，可从测试矩阵与 corner case 推导覆盖项。
- 覆盖项应优先服务于验收完整性，而非追求工具特定写法。

------

## 12. Build & Run（可复制命令）

**解释**  
本节定义统一构建入口与执行方式，是自动评测与 CI 的前提。对于 spec2repo，推荐明确写出脚本职责与退出码语义。

**示例内容**

- `make sim`：编译 RTL 与 TB，运行仿真并给出 PASS/FAIL 退出码
- `make lint`：执行 lint
- `make wave`：可选，生成波形文件

**Code Example**
```bash
#!/usr/bin/env bash
set -e
iverilog -g2012 -o sim.out \
  rtl/pkg/uart_pkg.sv \
  rtl/modules/fifo_sync.sv \
  rtl/modules/baud_gen.sv \
  rtl/modules/uart_tx.sv \
  rtl/modules/uart_rx.sv \
  rtl/modules/axi_lite_regs.sv \
  rtl/axi_uart_top.sv \
  tb/axi_uart_tb.sv
vvp sim.out
```

**Implementation Hint**
- 若仓库已有脚本，本节应尽量直接引用真实命令而不是重新发明命令行。
- 对于多工具链项目，可注明“参考工具链”与“可选工具链”。

------

## 13. Acceptance Criteria（最终验收门槛）

**解释**  
该节定义判定项目是否完成的门槛。对于 agent 任务，验收门槛应尽可能基于自动化结果，而不是人工主观判断。

**示例内容**

- AC1：`make sim` exit code == 0
- AC2：TEST-001/010/011/020/022/030/040 全部通过
- AC3：无 X/Z 输出（TB 启用 X-check）
- AC4：CSR 行为与第 8 章一致
- AC5：AXI 非对齐访问返回 `SLVERR`

**Code Example**
```systemverilog
if (test_fail_count == 0) begin
    $display("ALL_TESTS_PASS");
    $finish;
end else begin
    $fatal(1, "TESTS_FAILED: %0d", test_fail_count);
end
```

**Implementation Hint**
- 验收标准建议分为“骨架可编译”与“功能通过”两层；若保持原标题不变，可在此节内部写出层次。
- 若从仓库反推 spec，应优先以 CI/脚本/现有测试的真实门槛为准。

------

## 14. Implementation Nodes（可选但强力：防长程漂移）

**解释**  
该部分为 agent 提供分阶段交付与门禁条件。Node 应描述阶段目标、受影响文件、预期产物与 gate。对于从仓库代码反向生成 spec 的任务，Nodes 也可作为“代码组织的施工意图”进行恢复。

**示例内容**

### Node-00：Repo skeleton + build plumbing
- Goal：创建目录树、Makefile、脚本、空壳模块
- Deliverables：
  - `Makefile`
  - `scripts/run_sim.sh`
  - `scripts/lint.sh`
  - 各 RTL/TB 文件占位
- Gate：
  - `make sim` 至少完成编译入口验证

### Node-01：Top integration + package
- Goal：实现 `axi_uart_top` 与 `uart_pkg`
- Deliverables：
  - 完整端口列表
  - CSR 地址常量与公共 typedef
- Gate：
  - 编译通过

### Node-02：AXI-Lite register file
- Goal：实现 `axi_lite_regs`
- Deliverables：
  - CSR decode
  - 读写响应
  - `WSTRB` 支持
- Gate：
  - 基本寄存器读写通过

### Node-03：FIFO
- Goal：实现 `fifo_sync`
- Deliverables：
  - `push/pop/full/empty/count`
- Gate：
  - FIFO 单元行为通过

### Node-04：baud_gen
- Goal：实现 divider → tick
- Gate：
  - tick 周期与 divider 一致

### Node-05：uart_tx
- Goal：实现 TX FSM + FIFO pop + frame output
- Gate：
  - TEST-010/011 通过

### Node-06：uart_rx
- Goal：实现 RX FSM + sampling + overrun/error
- Gate：
  - TEST-020/022 通过

### Node-07：irq + RW1C closure
- Goal：实现 irq 逻辑与错误清除
- Gate：
  - TEST-030 通过

### Node-08：BAUD update semantics
- Goal：实现 BAUD 更新边界行为
- Gate：
  - TEST-040 通过

**Code Example**
```systemverilog
// Node-oriented skeleton example: CSR decode shell
always_comb begin
    ctrl_reg_n   = ctrl_reg;
    baud_div_n   = baud_div;
    bresp_n      = 2'b00;
    if (wr_fire) begin
        unique case (wr_addr)
            CTRL_ADDR: ctrl_reg_n = wdata;
            BAUD_ADDR: baud_div_n = wdata[15:0];
            default:   bresp_n    = 2'b10;
        endcase
    end
end
```

**Implementation Hint**
- 节点设计的目标是“先保证骨架可编译，再逐步闭合行为”；不要在 Node-00/01 过早实现所有功能。
- 若从现有仓库抽取 Nodes，可按文件依赖图、模块实例化顺序和测试解锁顺序进行恢复。

# 你拿这份当模板时，最重要的“写到什么程度才算合格”标准

- 接口契约必须精确到足以支撑 testbench driver 与 checker 编写。
- 寄存器表必须包含地址、字段、访问属性、reset 与 side effect。
- 每条 REQ 应至少映射一个 TEST；重要安全性约束建议再映射一个 PROP。
- Tests 节应给出足够的任务接口与刺激示例，避免仅有抽象文字。
- Implementation Nodes 应体现“骨架 → 子模块 → 闭环测试”的推进路径。
