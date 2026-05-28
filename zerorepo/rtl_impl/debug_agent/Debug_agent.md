
一、构建 Trace Report
入口在 rtl_editor.py:540-548，进入调试循环时调用 build_trace_report()，实现在 trace_report.py。

1.1 从仿真日志提取失败信号和时间
_extract_fail_signals_and_time() (trace_report.py:27-54)：

用两个正则从 stdout 中提取：


Hint: Output 'sig_name' has 5 mismatches. First mismatch occurred at time 12345.
SIMULATION FAILED - 3 MISMATCHES DETECTED...FIRST AT TIME 67890
返回 (earliest_fail_time, [{sig, mismatches, time}, ...])。

1.2 解析 RTL 为 Block 列表
parse_rtl_blocks(rtl_text) (trace_report.py:258)，实现在 trace_slicer.py：

优先用 tree-sitter-verilog AST 解析（trace_slicer.py:394-471），找不到则 fallback 到正则：

在 AST 中找到 module_declaration 节点
遍历其子节点，找到所有 always_construct 和 continuous_assign
对每个 block 提取：
类型：always / assign
时钟方式：seq（有 posedge/negedge）/ comb（always_comb 或 @(*)）/ latch（always_latch）/ unknown
写信号集：非阻塞赋值 <= 和阻塞赋值 = 的 LHS 信号
读信号集：所有标识符减去写信号
如果 parser 完全失败，会做一个 fallback：把整个 module body 包装成一个 RtlBlock(id="A1")（trace_slicer.py:474-521），确保 debugger 至少有一个 block_id 可用。

1.3 构建 Driver Graph + 动态后向切片

# trace_report.py:279-293
drivers = build_driver_map(blocks)      # signal_name → [RtlBlock, ...]

fail_signal_names = [fo["sig"] for fo in fail_outputs if fo.get("sig")]
if not fail_signal_names:
    fail_signal_names = ports["outputs"]  # fallback: 所有输出

suspect_blocks = dynamic_slice(
    fail_signals=fail_signal_names,
    drivers=drivers,
    max_depth=3,          # 反向追踪最多 3 层
)
dynamic_slice() 在 trace_slicer.py:568-592：


第 0 轮: frontier = {失败的输出信号}
  → 找到驱动这些信号的 block，收集它们的 reads
  
第 1 轮: frontier = {第0轮收集到的 reads}
  → 找到驱动这些 reads 的 block，收集它们的 reads
  
第 2 轮: frontier = {...}
  → 同上

最多 max_depth=3 轮
本质就是：从出错输出反向追踪，经过 3 层组合/时序逻辑，找出所有可能相关的 always/assign 块。

1.4 读取 VCD 波形，构建输入窗口
如果 wave.vcd 存在（trace_report.py:295-311）：

找 clk 信号 → 提取所有时钟边沿时刻
选 fail_time 前最近的 10 个边沿 作为输入窗口（_build_window_times()，trace_report.py:209-235）
对窗口内每个时间点采样：
所有 primary inputs
每个失败信号的 _ref（期望值）和 _dut（实际值）
suspect block 的内部读写信号（最多 20 个）
采样逻辑（trace_report.py:357-368）：

非 clk 信号：取时间 t 之前的最后一个值（模拟 always@(posedge) 中看到的 NBA 前值）
clk 信号：取时间 t 的即时值
1.5 对齐诊断 (Alignment Diagnosis)
alignment_diagnosis 是 trace report 中最有价值的部分（trace_report.py:419-476）：

对每个失败输出信号，在 fail_time 之前的 200 个时钟边沿上采样 _ref 和 _dut，计算四种对齐方式的匹配率：

对齐方式	含义
match_rate_current	DUT 和 Ref 在相同时刻的值匹配率
match_rate_dut_lag1	DUT 延迟 1 拍（DUT[t] vs Ref[t-1]）匹配率
match_rate_dut_lead1	DUT 提前 1 拍（DUT[t-1] vs Ref[t]）匹配率
match_rate_posedge	仅在 posedge 采样点的匹配率
match_rate_negedge	仅在 negedge 采样点的匹配率
选出 best_alignment：匹配率最高的对齐方式。如果 dut_lag1 匹配率最高，说明 DUT 比预期晚了一拍——这是一个明确的诊断信号。

1.6 Timing Hints
timing_hints（trace_report.py:393-416）：

在 fail_time 和前一拍之间做跨周期比对：

actual_matches_prev_expected：当前 DUT 输出 == 前一拍 Ref 期望值 → 1-cycle delay
prev_actual_matches_current_expected：前一拍 DUT 输出 == 当前 Ref 期望值 → 1-cycle lead
1.7 最终 Report 结构
返回的 report dict（trace_report.py:478-511）包含：


{
    "fail_time": 12345,                    # earliest mismatch time
    "total_mismatches": 5,                 # 总 mismatch 数
    "fail_outputs": [                      # 每个失败输出的 期望值/实际值
        {"sig": "data_out", "expected": "ff", "actual": "00"},
    ],
    "input_window": [                      # fail_time 前 10 个边沿的信号快照
        {"t": 12300, "edge": "posedge", "clk": "1", "rst": "0", "data_in": "ab", ...},
    ],
    "alignment_diagnosis": {               # 每个失败输出的对齐分析
        "data_out": {
            "match_rate_current": 0.12,
            "match_rate_dut_lag1": 0.94,   # ← 强烈暗示 DUT 晚了一拍
            "best_alignment": "dut_lag1",
        }
    },
    "suspect_blocks": [                    # 动态切片结果
        {
            "id": "A3",
            "kind": "always",
            "clocking": "seq",
            "writes": ["data_out"],
            "reads": ["data_in", "state"],
            "start_line": 45,
            "end_line": 62,
            "code_snippet": "always @(posedge clk) begin\n  ..."  # 前 1200 字符
        },
    ],
    "notes": {
        "vcd_available": True,
        "timing_hints": {"data_out": {"actual_matches_prev_expected": True}},
    }
}
二、拿到可疑代码块列表
在 RTLEditor 中通过 _EditSession.list_suspect_blocks() 暴露给 Agent（rtl_editor.py:226-229）：


def list_suspect_blocks(self) -> list[dict[str, Any]]:
    if not self.trace_report:
        return []
    return list(self.trace_report.get("suspect_blocks") or [])
Agent 调用 list_suspect_blocks 工具时，实际执行的是 _tool_list_suspect_blocks()（rtl_editor.py:450-455），返回 JSON 格式的 suspect block 摘要列表。

每个 suspect block 摘要（来自 trace_summary，rtl_editor.py:287-298）包含：


{
    "id": "A3",
    "clocking": "seq",
    "start_line": 45,
    "end_line": 62,
    "writes": ["data_out", "state_next"],
    "reads": ["data_in", "state"]
}
同时 trace_summary() 还会返回（rtl_editor.py:256-302）：


{
    "trace_report_path": "...",
    "fail_time": 12345,
    "total_mismatches": 5,
    "fail_outputs": [{"sig": "data_out", "expected": "ff", "actual": "00"}],
    "suspect_blocks": [...],         # 最多 8 个
    "alignment_diagnosis": {...},    # 压缩版（每个信号只保留关键指标）
    "timing_hints": {...},
}
Agent 的系统提示明确告诉它先看 alignment_diagnosis（rtl_editor.py:155-158）：

Check trace_summary.alignment_diagnosis first:
If it suggests a 1-cycle shift or wrong sampling edge, fix timing/reset/edge issues before changing core logic.
Otherwise focus on combinational correctness in the suspect block(s).
三、读取具体代码
Agent 调用 read_block(block_id) 时执行 _tool_read_block()（rtl_editor.py:457-461），底层实现是 _EditSession.read_block()（rtl_editor.py:231-236）：


def read_block(self, block_id: str) -> str:
    if not self.blocks_by_id or block_id not in self.blocks_by_id:
        return f"ERROR: Unknown block_id '{block_id}'."
    block = self.blocks_by_id[block_id]
    lines = block.code.splitlines()
    return "\n".join(
        f"{block.start_line + i}: {line}"
        for i, line in enumerate(lines)
    ) + "\n"
blocks_by_id 是在 _refresh_trace() 中构建的（rtl_editor.py:238-251），它是 {block.id: RtlBlock} 的映射，RtlBlock 来自 trace_slicer 解析的结果。

返回格式是带原始行号的代码，例如：


45: always @(posedge clk or negedge rst_n) begin
46:     if (!rst_n) begin
47:         data_out <= 8'h00;
48:         state <= IDLE;
49:     end else begin
50:         data_out <= next_data;
51:         state <= next_state;
52:     end
53: end
行号对应的是当前 rtl.sv 文件中的真实行号，这是 replace_block 能够精确定位替换的前提。

四、编辑 → 仿真 → 判断 的闭环
当 Agent 调用 replace_block(block_id, new_code) 时（rtl_editor.py:381-410）：

用 block.start_line - 1 到 block.end_line - 1 定位原代码在文件中的位置
用新代码替换对应行
调用 _judge_replace_action_execution()（rtl_editor.py:315-379）：
语法检查：check_syntax(rtl_path) — Verilator lint-only
仿真：sim_reviewer.review()
回滚判断：
mismatch 减少 → 接受
mismatch 增加 + fail_time 后移 → 接受（允许小幅增加 ≤10% 或 ≤5 个）
mismatch 增加 + fail_time 没后移 → 回滚，写入原文件
语法错误 → 回滚
接受后：调用 _refresh_trace() 用新的 sim log 重新构建 trace report，更新 suspect_blocks 和 alignment_diagnosis
这样就形成了一个完整的感知→定位→编辑→验证→再感知的闭环。