# Data Model: RTL Studio 展示与证据导出

日期：2026-10-20。继承 `zerorepo/rtl_web/schemas.py`、`web/rtl-demo/src/state.ts` 的既有实体；新增展示投影和导出清单，不引入数据库表迁移。

## 1. Case / Bundle（复用、不可变）

现有字段：case_id、bundle_id、source_run_id、origin、title、summary、spec_artifact_id、planner_artifact_id、source_fingerprint、modules、versions、validations、events、comparison_pair。

- case_id 仍限定四个注册任务。
- Bundle.modules 为规划模块；Version.modules 为快照文件到 artifact 的映射，两者含义不同。
- 原 bundle、版本与验证记录不得为布局修改而覆盖；展示派生信息只在内存或静态导出副本存在。
- 在线额外 run 通过现有接口核对 case/origin；不因移除 story 页面而跳过版本权限检查。

## 2. StepDefinition（新增、固定八项）

| step_id | 名称 | panel |
| --- | --- | --- |
| spec | 规格解析 | spec |
| architecture | 架构规划 | architecture |
| rtl | RTL 生成 | code |
| syntax | 语法检查 | code |
| verify | 仿真验证 | verify |
| diagnose | 差异定位 | repair |
| repair | 自动修复 | repair |
| complete | 最终复验 | verify |

这是 UI 展示顺序，不改变 runtime 原有 stage，也不代表八项都有独立执行记录。

## 3. TimelineStep / TraceItem（新增投影）

TimelineStep：step_id、panel、record_state、result、selected、replay_reached、event_sequences[]、attempts[]、evidence_refs[]、summary、source_kind、missing[]。

- record_state：not_recorded / partial / recorded；表示材料充分度。
- result：unknown / running / pass / fail / mixed；表示已知检查结果。与 selected 和 replay_reached 分离。
- source_kind：original_event / report_summary / current_snapshot / unrecorded。
- attempts：trial_no、source_sequence、summary、validation_id?、version_id?；仅现有 ID 可打开，只有摘要不制造详情对象。
- observed_at 可空；replay_delay_ms 只决定播放节奏。投影不创建新的历史时间戳。

TraceItem：id、origin、source_kind、event_type、step_id?、observed_at?、text、evidence_refs[]。历史 id 使用 bundle_id+sequence；实时使用持久 event id；去重后最多显示最近 100 条，可折叠，不当作完整私有审计记录。

映射规则：spec/architecture/rtl/complete 直接按事件分组；有明确语法结果的记录可列 syntax；带 simulation_completed 的 validation 列 verify；失败报告的位置整理为 diagnose 并标 report_summary；旧 repair 事件保留其原文与轮次，不能推出独立补丁或根因已记录。无依据时不自动完成前序步骤。

## 4. StudioSelection / ReplayCursor（新增 UI 状态）

StudioSelection：case_id、panel、step_id?、run_id?、version_id?、validation_id?、module_id?、comparison?。comparison 为 before_validation_id 与 after_validation_id，不进入现有操作 Context，服务端下载单独校验。

ReplayCursor：bundle_id、event_index、playing、reached_sequences[]。UI 手动选步骤停定时器；继续从当前事件继续；从头清空播放位置；完成停在最后已有事件。步骤没有事件时可浏览空状态但不产生可播放事件。

选择规则：

1. case→run→version→validation 必须一致；发现显式不一致应报错，不回退最终 PASS。
2. 波形属于 validation，源 VCD hash 与公开波形 artifact hash 分别验证，不互相替代。
3. 选择版本时清除不属于该版本的 module；当前文件路径通过 file_manifest 与已有文件 artifact 映射取得。
4. 比较前后先按规范信号名取交集，并根据 timescale 换算到共同物理时间；视口取有效交集、cursor clamp，无法精确换算或无重叠时提示而不是伪对齐。
5. 验证选择与回放游标独立，顶部明确“所选历史记录”与“播放位置”。

## 5. Panel / Context / Selection（兼容扩展）

Panel：spec / architecture / code / verify / repair。URL、前端 state 与后端使用同一枚举；verification 仅作为旧恢复值归一为 verify。

Context：保留现有 case/view/run/version/validation/module/signal/time_range 字段，新增可选 workspace_panel（上述五枚举）。新消息 view=workspace；旧 view 和 story/memory 字段保持服务端读兼容，不重写历史消息。

Selection：继续继承 Context，browsing_mode 保持 historical/live；workspace_panel 默认 architecture 以兼容旧客户端，新工作台无显式选择时自行选择 verify 后保存。

JSON payload 不需要表迁移。新增字段不可反向写入旧消息 context_ref，问答证据以发送时上下文为准。

## 6. SpecPresentation / VersionFile（新增投影）

SpecPresentation：summary、summary_label、source_artifact_id、constraints[]、missing[]。Constraint：label、value?、source_artifact_id、source_locator?、state（recorded/needs_confirmation/not_recorded）。只摘取公开规格或已有规划明确字段；没有结构化提取记录时叫“规格摘要整理”，不宣称当时完成了约束提取。

VersionFile：path、sha256、size_bytes?、artifact_id、module_id?、role（design/definition/other_rtl）。列表必须完整覆盖 file_manifest，e203_defines.v 可查看；架构仍只画 9 个规划模块。展示缺失映射要报错，不能悄悄漏文件。

RepairPresentation：before/after validation refs、failed_signals[]、first_failure_ticks?、changed_files[]、attempt_summaries[]、root_cause?、root_cause_state、missing[]。缺少根因时显示未记录；对比摘录与完整代码区分，不能从“最终通过”推断每轮修改的因果解释。

## 7. ChatSnapshot / Capability（复用并规范）

发送快照：case_id、session_id、context_ref、client_message_id、text；幂等重试不改变快照。浏览器草稿按 case 独立存 sessionStorage，消息归服务端会话。

能力：transport_connected、session_ready、chat_available、verify_available、generate_and_verify_available、fix_available。输入始终可编辑；三种显式操作句按其能力发送，普通问题需要 chat_available。未知能力不当作就绪；后端再次校验。

证据按钮携带消息 context_ref 和 artifact_id；操作按钮携带所属 operation。事件抵达或回复过晚不修改其他案例当前 state；单页签切换不重建 chat。

## 8. EvidencePackageSelection / Manifest（新增、派生）

Selection：case_id、validation_id（单次或 after）、before_validation_id?。最多两条验证，必须同案例且属于公开历史 bundle，可读私有 owner 不代表可公开导出。

Manifest（rtl-demo-evidence-v1）：case_id、bundle_id、source_fingerprint、selection、validations[]、versions[]、files[]、missing[]、exclusions[]。详细字段见下载契约。只列正向选择的公开信息，不复制整个实体 JSON。

File entry：archive_path、role、validation_ids[]、version_id?、artifact_id?、source_artifact_sha256?、source_sha256?、archive_sha256、size_bytes。静态派生 wave index 重写相对路径后，archive_sha256 计算实际 ZIP 条目字节；源 hash 仍保留。

必需关系不一致或 RTL/report 损坏则终止导出；可选波形不存在则列 missing，存在但 hash/绑定异常则终止，不把损坏解释为缺失。

## 9. EvidencePackageIndex（新增静态派生）

仅在 export_static 输出的 manifest 增加可选 evidence_packages：schema_version=rtl-demo-evidence-index-v1，single 为 validation_id→PackageDescriptor，comparisons 为 PackageDescriptor 列表。

PackageDescriptor：kind、validation_id、before_validation_id?、url、sha256、size_bytes。URL 位于 cases/<case_id>/evidence，文件名为内容 hash。索引本身不成为历史验证证据，不改变 source_fingerprint。

静态索引必须与相同 bundle_id/source_fingerprint 配套；没有匹配包且后台不可达，明确不能下载，不降级到另一版本。
