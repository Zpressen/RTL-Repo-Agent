# Evidence and Waveform Contract v1

## 导入包

每包包含 manifest、可展示的规划摘要、选中RTL快照、脱敏报告、固定信号的波形变化及回放事件；原始VCD、未脱敏日志及私有验证依赖保存在计算后台。静态包波形从同一真实VCD预计算，带源hash，不能使用手绘或随机数据。

```json
{
  "schema_version":"rtl-demo-bundle-v1",
  "bundle_id":"e203-demo-v1",
  "case_id":"e203",
  "source_run_id":"recorded-e203-run",
  "origin":"historical",
  "spec_artifact_id":"spec",
  "planner_artifact_id":"repo-plan",
  "verifier_fingerprint":"sha256-of-test-input-manifest",
  "versions":[],
  "validations":[],
  "artifacts":[],
  "events":[],
  "comparison_pair":{"before_validation_id":"trial5","after_validation_id":"final-system"}
}
```

示例ID仅说明结构，实施时由导入器登记真实映射；修复后默认展示独立final-system结果，trial9 candidate验证仍保留。manifest_sha256由不包含该字段本身的规范化manifest计算。

### Validation binding

每个验证必须登记：validation_id、version_id、完整RTL文件清单摘要、verifier_fingerprint、report_source_sha256、report_display_sha256、waveform_sha256、source_candidate/revision/trial、simulation_completed、kind、verdict、total_samples、mismatched_samples、internal_mismatch_count、first_failure_ticks、timescale、comparison_policy、marker_status。

binding_level区分历史recorded_candidate与实时full_input_manifest；历史未保存的golden/stimulus完整指纹明确列为限制，不以当前文件摘要冒充。RTL、同次报告/VCD及testbench核心关联仍是历史可信对比的必要条件。

- candidate trial必须有对应journal的evaluate以及simulation_completed，字段名兼容现有sim_completed；lint失败携带的继承wave不当作本次wave。
- 当前工作目录的latest报告只作为发现线索，不作为归属证明。final-system必须绑定独立final_verify输出与accepted RTL树，不能将候选PASS改名为最终复验。
- 相同RTL的候选和最终复验是两个validation；两次VCD hash相同也不合并记录身份。
- 采样统计来自唯一总行；存在冲突总行或report/counter冲突则导入失败。内部差异计数保留原字段和名称，不覆盖采样统计。
- 导入按白名单复制，拒绝目录穿越和symlink逃逸。排除codex_home、provider配置、认证、原始消息会话和任意服务器路径；前端日志仅用脱敏副本。
- 代码、报告和对话正文按文本渲染，不能将产物或模型输出作为可执行HTML；证据跳转只使用已验证的实体ID。
- 历史首次导入验证文件关联和现有绑定，不能宣称hash本身证明所有硬件输入都正确。

## 固定信号与波形窗口

第一版信号组为实际存在的clk/rst_n、i_valid/i_ready、cmt_o_ready、wbck_o_ready、DUT/Reference wbck_o_valid及wbck_o_wdat；映射到完整VCD信号名，最多16条。信号不存在明确标出，不用近似名称静默替代。

```json
{
  "validation_id":"trial5",
  "version_id":"baseline3",
  "waveform_sha256":"7b1f0334e90e737a7d007a3fa7fc1ecbc5fa5200276d4c473654e9d1d8050389",
  "timescale":{"value":1,"unit":"ps"},
  "start_ticks":"1100",
  "end_ticks":"1160",
  "signals":[
    {"id":"clk","full_path":"tb.clk","width":1,"initial_value":"0","changes":[["1105","1"],["1110","0"]]}
  ],
  "sample_markers":[
    {"time_ticks":"1125","sample_index":113,"verdict":"fail","failed_signals":["wbck_o_wdat"],"source":"testbench_counter_delta","sampled_value_available":false}
  ],
  "marker_status":"verified",
  "comparison_policy_id":"e203-posedge-stats-v1",
  "truncated":false
}
```

波形变化与sample_index为结构示例，实际采样序号与变化必须从VCD导出，不使用示例值。当前E203失败时间1125ps与原始统计是已核对事实。

- 起点initial_value是该信号在start_ticks处的已知VCD值；changes覆盖 `start_ticks < t < end_ticks` 的全部可用变化，按顺序返回。起点之前无值时标unknown，不补0。
- 值为按位二进制字符串，包含原始x/z；数字显示可以转十六进制但保留位宽与未知位。
- tick使用十进制字符串；浏览器用BigInt或受检安全转换进行时间运算。实际当前数据约2220ps，但契约不依赖小数值。
- 单次最多16条信号、20000次变化。超过上限返回413 window_too_large与建议缩小的范围，不返回不完整数据冒充完整波形；成功时truncated始终false。静态导出包必须遵循同一限制并可拆分连续窗口。
- 原始VCD可能不记录delta-cycle中间状态；游标显示值仅对应所存VCD。不得据此伪造active区采样值，也不宣称逐时刻波形完全重合。

## Comparison policy

2026-10-16 扩展：AES 两例的 stats1 为 7×32bit，SDC 为 39×32bit；白名单布局与实际 testbench SHA256 固定在 `configs/rtl_demo_cases.evidence.json`。新增验证的 policy ID 使用 `<case_id>-stats-v1`，旧 E203 包保留原 ID。受信系统验证器的明确 `system_verify: PASS` 或案例命名结论不依赖可选 Hint 统计行；统计未记录则保持 null。已有计数或错误信息与 PASS 冲突时不得判为通过。SDC 全波形超过每窗口变化上限，静态索引包含精确时间分片，保留每个变化与采样标记；浏览器只合并所请求窗口，不降低采样精度。新增三例缺少修复前波形和完整候选次数，比较前项与次数均为 null。

当前已核对testbench在posedge clk时递增clocks并进行比较；没有按reset、valid或ready屏蔽。参考输出中的未知位依照原testbench的比较表达式解释，UI不另行定义通过规则。

`e203-posedge-stats-v1` 保存实际testbench/hash、packed字段序列和宽度。`tb.stats1`为3488bit：109个32bit int，按声明顺序从高位解码；只使用布局匹配的字段。对每个变化比较clocks/errors及逐信号counter增量，并用最后计数校验报告的total_samples和mismatched_samples。

- clocks增长表示新增采样；errors增长表示失败采样；逐信号counter增长提供failed_signals。
- 一个tick如果跨过多个样本而无法逐个定位，标记位置精度不足，不人为展开成相同tick的伪样本。
- counter回退、无法解释的跳变、字段宽度变化或与报告矛盾，marker_status=inconsistent，不输出verified marker；支持的布局缺失则unsupported，可仅展示报告与原始波形。
- `tb_match`/`tb_mismatch`只是原始组合信号，不产生权威失败marker。最终通过来自该版本独立报告，并与counter一致性校验。
- `sampled_value_available=false`明确表示没有真实比较瞬间的操作数快照。界面不能把游标值标作测试平台当时采样的值。

首个bundle必须包含trial5的1/222失败与trial9/final-system的0/222通过，并验证其采样marker。不得为了绿色波形调整刺激、比较规则、屏蔽条件或原始值。

## 回放事件

历史事件含sequence、source_ref、stage、module_id或validation_id、origin=historical及可空observed_at。只对确有记录的事实生成事件；原始时间未知保持null。replay_delay_ms是演示节奏，不能显示为真实处理耗时。最终结果仅到对应事件后揭示；无内容阶段显示未记录。
