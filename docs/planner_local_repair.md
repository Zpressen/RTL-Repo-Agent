# Stage3–Stage5 局部修复与恢复

Stage3、Stage4 模块计划和 Stage5 子任务生成共用有次数上限的修复循环。首次生成后，程序保留候选和完整诊断，要求模型只返回明确目标的补丁。每次合并后重新校验完整产物；请求失败由 LLM 请求层处理，不作为文档错误重新生成。

## 修复范围

| 阶段 | 修复目标 | 保留内容 |
| --- | --- | --- |
| Stage3 | 章节正文；身份明确时可修复单个 Behavioral Overlay 条目 | 其他正文、标题及 RTL 围栏内容 |
| Stage4 模块计划 | 子任务的 description、constraints 等字段；身份冲突时修复无法可靠关联的子任务集合 | 唯一身份明确的其他子任务 |
| Stage5 | 当前子任务的 code、完整 contract 或 contract 的明确字段 | 其他子任务；仅修复契约字段时保留 code 和其他字段 |

Stage4 规格分块仍执行确定性处理。Stage4 的 id、target、spec_refs 和 Stage5 的任务身份字段由程序按权威输入组装。语义缺失不通过填入 `unspecified`、空列表或推测内容消除。缺失字段和显式 `[]` 分别处理。

模型修复响应采用：

```json
{
  "patches": [
    {
      "target": "subtasks/B2_update/description",
      "replacement": "根据当前规格生成该块负责的状态更新。"
    }
  ]
}
```

只接受请求中列出的目标，且每个目标恰好出现一次。Markdown 章节补丁只包含正文；章节标题由程序保留。旧格式的完整响应只有在未指定内容保持一致时才可接受。结构无法可靠定位的输出在当前生成单元内重新构建，不接受被自动补闭合的截断 JSON。

Stage5 契约字段使用 `contract.writes`、`contract.reads`、`contract.clocking`、
`contract.reset_behavior`、`contract.hold_behavior`、`contract.latency`、`contract.assumptions`。
列表的 replacement 是完整列表，不是追加项；writes 必须覆盖代码中能可靠识别的内部及输出赋值目标。
诊断的 expected 给出全部已识别目标，actual 给出当前列表，消息单独指出漏项。
契约缺失或不是对象时才修复完整 contract；代码修改必须同时提供完整 contract，并重新校验。
未知、重复和父子重叠补丁目标均拒绝，Stage4 的补丁命名保持兼容。

Stage5 旧完整响应仅补回缺失的任务身份字段，不接受显式错误身份或其他未授权变化。
兼容处理记录在日志中。被拒绝补丁的 allowed_targets、received_targets、response_kind、reason
保存为失败草稿的 patch_diagnostics，并提供给下一次修复请求。

## 诊断与检查点

- `<planner outputs>/.repair_drafts/<stage>/<prompt hash>/attempt_N.json`：失败原文、候选、全部问题、格式整理记录及补丁拒绝原因，不作为成功产物。
- `<planner outputs>/.repair_cache/block_spec/<module>.json`：与规格和骨架指纹绑定的 Stage4 检索结果，可跨失败重试复用。
- `<workspace>/fragments/<module>_checkpoint.json`：已验证子任务及其输入和内容指纹。片段和契约写入后，最后原子替换检查点作为提交标记。
- 检查点中的 `pending_subtasks` 是需要按当前输入重新核验的历史候选，不属于已完成子任务。

Stage5 恢复时重新核验当前计划、规格、骨架、宏上下文和已验证前置片段，复用有效前缀。一个子任务失效后，后续子任务重新生成，因为当前提示会包含全部前置片段。恢复过程只把已核验前缀传给模型。

只有完整通过检查的模块才能进入 Stage6。失败及依赖阻塞会保存在 manifest 的 status/error 中；独立模块可继续生成。存在失败模块时跳过系统调试，主入口报告失败并保留恢复数据。Stage6 合并缓存通过输入和内容指纹失效，不能仅凭文件存在或语法通过复用。

Stage6 对 failed/blocked 记录报告状态和原因，仅对 completed 记录检查路径和产物存在性。
这些改进不提高全局修复策略版本，也不改变已有检查点指纹；已保存子任务仍需在恢复时通过原有核验。

新修复策略版本参与 Stage3 及后续阶段的指纹，不改变 Stage1、Stage2 的缓存策略。旧的片段标记本身不再是完成凭据。

## 校验范围

格式、结构和能确定性核对的接口约束分别报告。Stage3 能在其他章节损坏时继续核对已经解析出的 Module Frame。Stage5 要求显式契约，并检查明显赋值目标与契约的一致性。

正则提取的读写信息只作为诊断线索，不自动改写契约。自然语言描述的时序、复位、共享对象所有权和边界覆盖不能由这些检查证明；质量报告标记为 unverified，继续由下游硬件行为验证检查。

## 原始故障的离线验证

对 `sdc_serial_engine` 的三次失败输出重新解析：

| 输出 | 一次报告的问题数 | 修复目标 |
| --- | --- | --- |
| initial | 12 | Behavioral Overlay、Decision Ledger |
| retry_after_doc_parse_failure_1 | 4 | Behavioral Overlay 的 B1 条目、Decision Ledger |
| retry_after_doc_parse_failure_2 | 3 | Decision Ledger |

最后一次同时报告 `topic`、`decision`、`reason` 缺失。三个普通风险/延期列表可无损整理为 items 列表，无需重新生成其他章节。该验证仅解析本地日志，没有重放 API 请求。

运行方式保持不变；`scripts/run_main.sh` 已设置 `RESUME=true`：

```bash
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/sdc_controller_hard/sdc_controller_system.md
```

## 规格检索、请求预算与实时草稿

模块规格检索使用 `module_spec_selection_v2`：模型只选择来源块，并给出简短理由、置信度和待确认问题。
程序校验候选标识，按来源顺序去重，恢复原文及文件路径，并组装连续 Sxxx 编号。
下游仍读取 `module_spec_context_retrieval_v1`；新产物额外保留 `source_ranges`，包含原文字符范围及父标题。
旧完整响应只有在正文与其引用来源一致时才接受，截断 JSON 不自动补闭合。

默认每块不超过 6,000 字符，扫描一至六级标题并识别围栏；候选最多 24 块、48,000 字符，
事实上下文最多 8,000 字符，完整检索提示最多 64,000 字符。顶层端口章节及其续块由程序强制纳入；
超出提示预算的强制章节在本地补入，不裁掉正文。

检索成功或降级后，立即原子保存 `.repair_cache/module_spec/<module>.json`，不等待骨架生成完成。
指纹绑定实际来源内容、模块职责、相关事实、候选集、检索版本和模型配置，并校验结果摘要与来源。
已有未完成模块的无指纹旧文件不作为可信新缓存；已完成模块沿用原检查点校验。
`resume=false` 或 `force_rebuild=true` 绕过检索缓存。

检索失败默认 **降级并继续**，使用确定性候选集及强制端口章节，保留原文及低置信度声明。
降级原因记录在检索结果、日志及 Stage3 的 open_issues/质量警告中。
生成调用失败则直接报请求错误并保留检查点，不进入文档格式修复循环。

默认请求策略可在 `rtl_module_planner.request_policy` 配置：

| 调用 | 总预算 | 首段正文/正文停滞上限 | 输出上限 |
| --- | --- | --- | --- |
| Stage3、Stage4 检索 | 180 秒 | 各 120 秒 | 4,096 tokens |
| Stage3、Stage4 生成及局部修复 | 600 秒 | 各 120 秒 | 沿用模型配置 |
| Stage5 生成及局部修复 | 600 秒 | 首段 240 秒、停滞 120 秒 | 沿用模型配置 |

Stage5 生成及局部修复现单独使用 240 秒首段有效正文等待、120 秒正文停滞上限，
总预算仍为 600 秒。可通过 `request_policy.stages.stage5_codegen` 覆盖。
前导空白和后续纯空白块原样存入草稿，但不能开始或延长有效正文计时。
日志保留 `content_chars`，新增 `effective_content_chars` 与本次调用的实际等待限制。

Stage5 在未收到有效正文时发生首段超时，可以在总预算内重新请求一次；
它与网络/API 重试共享至多一次的重试额度，不占用文档局部修复次数。
正文已经开始后的停滞、总预算耗尽、认证失败和截断不使用此重试分支。
连接在重试前取消并关闭，不同尝试的正文不拼接。退避也计入原总预算。
读取层为每次 SDK 请求覆盖读取时限，避免客户端默认 120 秒提前终止 240 秒的首段等待。
草稿目录另存 `attempt_N.status.json`，用于保留各次请求的超时及服务端诊断。

每次调用独立传递 `LLMRequestOptions`，不修改共享模型配置。总预算覆盖连接、读取、至多一次传输重试及退避。
默认 OpenAI 兼容后端使用可取消的异步读取，保持 Planner 同步入口；等待响应头或下一块数据时也能取消。
总时限和正文停滞超限不自动重试。自定义后端未声明 `request_options` 参数时保持原调用接口；
网络预算需要由该后端接入或自行实现。

普通 APIError 的结构化 type/code 为 upstream_error 时，允许在同一预算内重试一次。
认证错误、未知 APIError、正文停滞、总时限超限和截断保持原失败行为。流内错误后的重试从头请求，
不同尝试的正文不拼接，各次草稿保留。异常未提供 HTTP 状态或请求标识时，保留已收到的响应头信息；
HTTP 200 只表示流连接成功，仍可能同时记录 server_error_type/server_error_code。

每 30 秒输出阶段、模块、尝试次数、正文进度、最近速度和剩余预算；最近 120 秒低于每秒 2 字符时告警。
请求错误记录 HTTP 状态、错误类型/代码、服务端请求标识和等待阶段，忽略认证信息及任意错误正文。

接收中的正文定期保存到 `.llm_drafts/<stage>/<module>/<request_id>/attempt_N.partial.txt`，
`status.json` 记录 running、retrying、completed、failed 或 interrupted。
attempt 表示传输尝试次数，repair_attempt 表示生成/文档修复调用次数。
中断或失败后保留草稿；这些文件不是正式骨架或成功检查点。

本次 SDC 规格的离线预算验证：`sdc_system_control` 检索提示从 154,751 字符降至约 62,994 字符，
候选正文约 46,002 字符，事实上下文约 7,979 字符；模型输出改为选择信息，正文由本地恢复。

2026-10-10 使用当前接口验证：16-token 短请求约 10 秒完成；随后运行上述原命令，
前两个模块从检查点复用。第三个模块 `sdc_system_control` 的检索在 88.6 秒完成，
模型输出 3,382 字符的选择信息，本地恢复 12 个规格块，未使用降级。
骨架初次生成约 216 秒，一次 Structural Skeleton 章节局部修复约 138 秒；
文档和 JSON 已保存并通过一致性检查，Stage3 检查点推进到 3/5，前两个模块文件摘要保持一致。
验收在第三个模块提交后主动中断，因此该次日志末尾的 interrupted/执行失败来自停止验收；
继续原命令可恢复剩余模块。Stage4–Stage5 和知识图谱通过离线回归，尚未进行本次完整在线运行。

2026-10-11 对 Stage5 实际失败草稿进行离线回放：`sdc_stream_buffers` 和
`sdc_transfer_engine` 第二次响应中的 `contract.writes` 补丁均可直接合并并通过现有片段/契约检查，
代码及其他契约字段保持一致；第三次漏掉六个输出的 writes 列表仍失败。
现有四个模块检查点中的 10 个子任务通过当前片段检查、契约检查及内容摘要核验，
检查点文件保持不变。本次未重放外部请求，也未将失败草稿提交为正式产物。

## 稳定来源、完整产物保护与 debug 接续

Stage5 条目使用 `fingerprint_version=stage5_source_v2`，保存 `source_snapshot` 和
`source_fingerprint`。来源包括模块职责、任务、规格、完整骨架摘要、接口、宏、前置片段及
实际子模块端口；不包含本模块的 materialized/planned 状态、actual_path 或生成代码接口。
子模块端口按名称排序，依据完整接口而非截断提示计算摘要。来源改变时日志报告具体组件。
全局 `local_repair_v1` 保持不变。

旧条目只有旧输入摘要可重算、契约和片段核验通过时才迁移；完整骨架和截断子接口需要
历史 Stage6 来源绑定及完整代码树补充证明，不能直接把当前摘要填给旧代码。
缺少证据时保留历史，重新生成。父模块 Stage6 的依赖实现变化只有在历史绑定可核验、
完整子接口相同且现有 RTL 摘要/语法有效时才迁移绑定；其他来源或接口变化仍失效。

存储位置：

- `workspace/.stage5_generations/<module>/<digest>/fragments/`：不可变片段、契约和检查点包。
- `workspace/.stage5_candidates/<module>/<source-key>/checkpoint.json`：可恢复的候选提交标记。
- `workspace/.stage5_history/<module>/`：保留的旧检查点，引用完整包。
- `workspace/fragments/`：兼容入口；完整活动标记仅在包写完后切换。
- `workspace/.stage5_publish/`：兼容文件发布过程的中断标记，恢复时从此前活动包还原。

新候选逐任务保存。新生成失败不会降级或覆盖旧 completed 包；旧来源真的过期时，旧包仅为历史，
不能进入当前 Stage6。兼容文件被手工改动仍会触发核验失败，不因文件存在而接受。

系统 debug 使用独立 run_record/run_result 绑定规格、契约、验证器与全部 RTL。
来源、已接受基线、持久状态及 Codex 会话记录一致时，继承 run_id、会话和累计验证次数；
输入改变或无法核验时将旧 codex_task/codex_private 移到 `debug_system/<top>/history/`，保留原因。
未提交的 native 修改在接续前回滚。episode 编号递增，日志追加，累计验证次数不重置。
按 2026-10-13 的用户选择，每次重新启动流水线新增 `max_trials` 次验证额度（默认 30）；
一次启动内部的多个 Codex episode 共享同一额度，不会各自再获得 30 次。
例如累计 30 次时再次启动，offset 为 30、累计上限为 60；本次允许再验证 30 次。
`debug_status.budgets` 同时记录累计次数、本次已用次数及剩余次数，`launches/` 保存每次额度记录。
Stage6 的 `debug_trials` 表示本次启动的验证次数，私有 run_result 与会话状态保留累计次数。
新线程标识在收到 thread.started 时立即保存，支持父进程中断后的跨运行恢复。

私有 CODEX_HOME 保留会话数据库；选定 profile 合并为私有默认配置，使不带 --profile 的
exec resume 使用同一个 provider。认证或 provider 配置缺失明确失败，不切换默认服务。
接续前校验所选 profile、模型及 provider 配置摘要；变更时保留已存配置和会话并明确失败。
旧会话没有配置绑定标记时，需要与已有私有默认配置一致才能迁移；摘要中不保存认证内容。
中断父进程会终止其拥有的 Codex 子进程，防止后台继续修改候选。

`system_debug_latest.json` 和 Stage6 的 `latest_system_debug` 保留最近实际调试结果；
`system_debug` 表示本轮结果，skipped 不会清除历史。

2026-10-12 已离线恢复 SDC 串行模块 8/8，并核验五个模块的 34 个子任务与五份现有合并 RTL。
合并文件内容保持不变。旧运行归档在短验收时被遗漏的工作目录初始化清理删除；
初始化现已修正并增加回归测试。从先前工具记录恢复了 15 次验证的原因、预期效果、
语法/功能结果、mismatch 数及 5 次回滚摘要。完整原始 journal、native trace 与候选文件
用户确认没有同一次运行的备份，完整原始文件无法还原；摘要不等同于原始日志。
当前缓冲 RTL 与旧会话基线不同，因此本次使用新 debug 会话。

使用原 bash 命令的短验收中，五个模块的 Stage5/Stage6 全部复用，未重新生成代码，
约 174 秒完成缓存、语法检查和新系统 debug 会话建立。
新会话验证计数为 0，建立后主动停止。第二次执行原命令约 171 秒，五个模块再次全部复用，
保留同一 run_id 与 Codex session_id，episode 从 1 增到 2。已修正的初始化路径保留了新会话和
恢复的旧摘要，全部合并 RTL 内容仍与实施前一致；第二次同样主动停止，没有继续功能修复。
该次日志的 interrupted 来自停止验收，不表示缓存恢复失败，也不表示 RTL 功能验证通过。
恢复审计保存在 `module_planner/outputs/resume_recovery_report.json`；继续原命令可接续新会话。

扩大回归范围得到 515 passed、3 skipped、1 deselected；另有 9 个无关失败：一个已有的
多行 if/else 赋值追踪问题，八个依赖缺失 `rtl_outputs/rtl_spec_/.zerorepo/repo_data.json` 的测试。
全目录收集还受四个旧测试文件的缺失模块/依赖阻碍（asserter、repo_encoder、libcst）。
原先已确认的多分支追踪用例继续排除；本次来源、完整包保护、缓存迁移与 debug 接续测试通过。
补充 profile/provider 变更保护后，57 个 Codex 与系统 debug 测试通过。

2026-10-12 对 E203 的重复生成超时增加上述 Stage5 首段等待及受限重试策略。
KG 提示使用 `stage5_planning_context_v2`，保留规格引用标识，删除与规格块重复的引用元数据和
选择理由；子模块端口紧凑表示为 `[name, direction, width]`，从完整来源契约恢复，避免旧预算
优先删掉端口。完整规格、宏、前置代码及来源指纹不变，自定义 KG 格式继续兼容。
本地 B6 预览的用户提示从 69,554 降到 66,664 字符，子端口从旧提示的 54 个恢复到全部 201 个。
此前 71,754 是包含 System Role 和重复 Stage Context 的日志块大小，并非单独用户提示的长度。
本次预览验证八个已完成子模块和顶层 B1–B5，未发送请求且检查点未改动。
在线验收曾被自动审批拒绝，等待明确允许将此次 E203 上下文发送到配置的模型服务；
离线测试不等同于已经确认上游请求恢复。
本次最终相关回归为 374 passed、1 skipped；编译与 diff 检查通过。
恢复与请求策略审计写入 `module_planner/outputs/stage5_request_recovery_report.json`。

2026-10-13 修正 debug 后重启重新合并的问题：在系统 debug 前保存不可变生成来源和原 RTL 树，
接受 debug 修改后提交独立绑定，并同步 Stage6 输入/输出摘要。重启先核验整个接受树与完整来源，
Stage5 使用经核验的原生成依赖契约，避免 debug 合法修改子端口后触发父模块重生成。
来源、契约、校验器或文件损坏时拒绝复用；未知手工修改不会被当作已接受产物。
本模块运行状态和 debug 的累计计数不会改变来源绑定。

旧 E203 会话利用完整 launcher_baseline、原 Stage6 输入/输出摘要及 38 个 Stage5 片段的硬性校验
离线迁移。9 个模块缓存均可复用，当前所有合并 RTL、原 30 次验证记录和 Codex 会话保持不变。
下次启动可从这个接受基线新增 30 次验证；本次没有调用模型或继续功能修复。
审计保存在 `module_planner/outputs/debug_resume_binding_report.json`。

合并规格检索和子模块上下文缓存分别记录来源/结果内容摘要，不再用文件修改时间判断过期。
没有可信来源摘要的旧检索缓存需要重新检索一次；已接受 debug 树复用时不进入该检索分支。
