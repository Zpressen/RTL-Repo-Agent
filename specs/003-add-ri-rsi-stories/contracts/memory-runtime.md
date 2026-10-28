# Contract：当前 Codex 执行路径的经验接入

状态：待实现；沿用当前执行架构与准入。此契约不增加网页操作类型，不要求公网小服务器承担新的重型实验。

## 1. 输入和隔离

可信任务准备从“审核公共经验 + 当前会话授权经验”选出固定 revision，写只读 `job_inputs/memory/` 和 manifest；限制数量和正文长度，不挂载全局经验根。复用已有选择器，选择成本不因网页浏览产生。

沿 `jobs.prepare_job → runtime.configure_agent → SystemDebugRunner → CodexDebugRunDescriptor → MCP Session` 传递：case、外部 run、内部 debug run、attempt、memory snapshot 摘要和授权 revision。私有路径只由可信配置传递，不接受模型提交。

descriptor 和 `debug_binding` 同时绑定 snapshot、原输入及 profile。resume 读取原快照；不一致拒绝恢复，不能悄悄换新版。无可用经验用空快照，原行为不受阻。

## 2. 新增固定工具

| 工具 | 参数 | 返回及事件 |
| --- | --- | --- |
| `query_rtl_memories` | 可选 module_name、signals、failure_type；limit ≤5 | 仅当前快照命中的 revision/摘要/适用范围；记录 retrieved；若已返回完整内容须同时记录 provided |
| `read_rtl_memory` | revision_id；max_chars ≤8000 | 已授权清洗内容、适用/禁用条件、可访问依据；记录 provided 和响应摘要 |
| `record_memory_application` | revision_id、decision=apply/reject/not_applicable、reason、target_files、target_signals | 仅当前任务声明，记录 application_declared，不直接记 applied 或 PASS |

工具不接受路径、scope、owner、run ID、candidate ID、verdict 或发布参数。当前任务身份由可信 Session 取得。target_files 仅允许本任务可写的规范化相对文件；revision 不在快照、路径穿越、跨 run、超长输入均拒绝。

工具定义、runner TOOL_NAMES、MCP schema/dispatch、Session 和 tool_bridge FIELDS/验证必须同步更新，不能只改提示词。日志不记录秘密或整套私有提示。

## 3. 执行提示与采用门槛

提示要求检查相关经验、对照当前规格后说明采用/拒绝原因；不强迫每任务采用。经验是参考材料，不能覆盖规格、oracle、参考设计、约束或验证规则。

可信 `_evaluate_changes` 对一次 apply 声明检查：已提供的固定 revision、当前 attempt、允许目标、实际 candidate diff/manifest。满足才产生 applied，绑定精确候选；多个候选不得沿用过期采用声明。仅查询、读卡或无实际修改都不能成为采用。

这种关联是可审计的执行者声明和工程修改证据，不保证模型内部推理因果。失败/回滚保留，最终选中版本另有客观验证。

## 4. 验证与提炼

客观 lint、局部仿真和最终系统复验分别产生 validation_observed，保存输入树/候选/验证器/报告/波形绑定。accepted 和 simulation_completed 不升级 PASS；采用后的结果可以为 FAIL 或 unverified。

Codex adapter 将实际结果交给 distiller，输出当前任务私有草稿；修正旧 header 不能代表缺失的原始验证。只对确有证据的层级赋值，未证实字段保留未验证。不得伪造 ReAct patch entry 让旧 distiller 看起来已经闭环。

草稿审核、修订或淘汰通过维护者离线命令完成；修改内容必须产生新 revision 和有依据的生命周期事件。任何模型草稿都不自动变成公共经验或其他会话可用材料。

## 5. 幂等、失败与可信记账

- revision 使用内容寻址、原子提交；同 ID 异内容失败，不覆盖历史。
- 使用事件由可信 adapter 追加，幂等键包含任务/attempt/工具调用或验证标识；恢复不重复计数。
- 需要客观证据的阶段如果记账失败，不能输出成功复用结论；原执行错误可按现有机制报告，已产出的 RTL 不因展示需求被改写。
- 原始事件私有保存，公开故事另经清洗审核；历史中 source run 与 use run 必须区分，并记录实际 producer/backend。

## 6. 真实闭环验收

准备来源运行 A 的真实问题与验证，提炼并审核 revision v1；独立运行 B 的冻结快照包含 v1，Codex 实际读取、声明、修改，并完成对应验证；B 的新证据支撑 v1→v2 或 retirement。A/B 不可用同 run 的两轮聊天代替。

若没有修订依据，不能预编剧情或只改措辞充数；继续采集真实边界材料或标部分完成。补充被实际验证的适用范围可称证据范围修订，不能称旧经验已被反例推翻。v2 未再使用继续待验证。

无同条件有/无经验对照时收益待验证。mock reviewer 仅用于逻辑测试，不能替代实际 Codex 工具交付、真实运行与真实报告。执行资源不足时使用足够资源的授权环境准备材料，不降低当前准入门槛。
