# Phase 1 Data Model

本模型用于本次无 PPA 数据版本。字段为拟定契约；未表示代码已经实现。所有公开对象都属于一个案例并具有明确证据状态。

## 1. 存储分工

| 层 | 保存内容 | 写入者 |
| --- | --- | --- |
| 现有 SQLite records | 一个新增 story kind，引用原 run/version/validation/artifact | 维护者导入命令 |
| 私有经验账本 | revision、生命周期事件、运行使用事件、冻结快照 | 可信 adapter/维护者审核 |
| 原 artifact 存储 | RTL 快照、验证报告、波形和审计材料 | 原验证及导入路径 |
| 静态站 | 审核后的故事 DTO 与 exposure=display 的证据 | 现有静态导出器 |

公共 StoryBundle 是不可变读模型，不是执行器直接写入的全局经验库。网页访问和问答不写经验，也不改变公共故事。

## 2. StoryBundle

| 字段 | 规则 |
| --- | --- |
| schema_version | rtl-demo-story-v1 |
| story_id | 规范化内容摘要派生；自身 ID 不参与摘要 |
| case_id | 原四案例之一 |
| origin | 本次审核故事固定 historical |
| source_fingerprint | 绑定原始输入和审核 manifest；不包含私有路径 |
| review | 审核标识、时间、审核内容摘要；导入只接收 approved |
| optimization | 本次仅 state=awaiting_data、说明、缺少证据类别；无实测数字 |
| memories | 审核可公开的 MemoryRevision 数组 |
| uses | MemoryUse 摘要及其可追溯事件 |
| lifecycle_events | 有依据的审核、修订、淘汰事件 |
| comparisons | 可空的收益对照记录；本次不要求生产对照 |
| evidence_refs | 明确类型的 run/version/validation/artifact 引用闭包 |
| experience_readiness | 从记录校验结果推导，不能由模型指定完成 |

ID 相同内容不同拒绝；相同内容重复导入幂等。公开 DTO 与私有审核对象分别摘要，公共接口不得直接序列化私有对象。

**经验准备状态**：

- empty：无审核可展示条目。
- archived_only：有来源条目，无完整后续实际使用。
- partial：有部分链路，或缺少有据修订/淘汰。
- complete：至少两个独立真实运行、一条实际采用及后续客观验证、一条有据修订或淘汰，引用闭包一致。验证 FAIL 允许如实记录；complete 不意味着收益或全部 PASS。
- incomplete_evidence：原应存在的材料缺失、哈希或版本冲突；相关成功结论必须撤下。

材料缺口独立列出，不能因为优化待接入而隐藏已有经验，也不能因经验完整而把 RI 标就绪。

## 3. MemoryRevision

| 字段组 | 内容 |
| --- | --- |
| 身份 | memory_id、revision_id、content_sha256、parent_revision_id |
| 隔离 | scope=private_session/project/public_reviewed、case、owner/project；公共 DTO 不带 owner 标识 |
| 内容 | title、lesson、问题类型、适用条件、禁用条件、正向做法/失败方向、局限 |
| 来源 | 外部 run、内部 debug run、attempt/candidate、backend/producer |
| 输入绑定 | spec/verifier/full RTL tree 摘要、原始证据 refs |
| 验证 | 实际 level 与结果；未核实 legacy header 只标 reported/unverified |
| 修订依据 | 新证据 refs、变更原因、与 parent 的实质差异、创建时间 |

revision_id 绑定规范化内容和 scope；相同内容不增加独立经验数量。历史内容不覆盖。只有标题或排版变化不能算经验改进。verified_by 旧标签和规则 confidence 均不推导成功率。

生命周期用追加事件表达：draft → approved_active → superseded / retired。新 revision 的审核与旧 revision 的 supersede 在一次可信提交中关联；旧运行仍指向原 revision。退役或未审核条目不进入新任务选择，但历史可读。新版本未被使用时显示待验证。

兼容旧 Markdown：保留当前文件作为最新可用投影，历史 JSON 放专用 revisions 目录；不让旧扫描器把历史修订当成多条记忆。旧文件首次迁入只能证明当时可读内容，不能补造此前覆盖掉的历史。

## 4. MemorySnapshot 与运行绑定

snapshot_sha256 绑定排序后的固定 revision 内容、允许证据、scope 和选择配置。job manifest 保存 snapshot 摘要、所选 revision、选择器版本/配置摘要，以及外部 run/case。

任务仅能读取审核公共库与本会话授权范围，复制至只读 job_inputs/memory/。descriptor 另保存外部 run、内部 debug run、attempt 映射；resume 必须匹配原输入、profile 和 snapshot，不能切换到“最新经验”。无经验时也记录明确空快照，保持原执行可用。

执行模型看不到 owner、任意磁盘路径、其他任务或整个全局库；经验快照不含参考设计私有源码或秘密。

## 5. MemoryUseEvent 与 MemoryUse

每个事件包含 event_id/idempotency_key、外部/内部 run、attempt、revision、snapshot 摘要、可信调用标识、时间与依据。事件不可覆盖；恢复不得重复计数。

| 事件 | 可信来源 | 不表示什么 |
| --- | --- | --- |
| retrieved | 冻结快照内查询确实命中 | 不表示已交给执行者 |
| provided | 工具确实返回内容及响应摘要 | 不表示理解、采用或成功 |
| application_declared | 执行者声明 apply/reject/not_applicable 及目标 | 不足以证明实际修改 |
| applied | 可信评估绑定已提供 revision、具体 candidate 和真实目标 diff | 不表示验证 PASS 或收益因果 |
| validation_observed | 可信评估/最终复验的原始结果及版本 | 不表示普遍收益 |

MemoryUse 聚合一个后续运行中某 revision 的上述事实；各阶段可独立缺失，不按顺序自动补齐。应用到候选后回滚也保留，不能把被拒候选的 PASS 当成最终系统结果。

applied 必须同时满足：revision 在本任务快照且曾提供；apply 声明属于当前 candidate；目标在允许文件集；有实际相关 diff；manifest/hash 可恢复。无修改、过期候选、仅打开卡片均不满足。该规则支持工程采用证据，不声称证明模型内部因果。

后续验证绑定 candidate/version/tree、verifier、report 和可选 waveform；必须显示具体验证层级。accepted、simulation_completed 均不等于 PASS。最终系统 PASS 仅来自对应最终版本的真实系统复验。

## 6. BenefitComparison（可空）

记录启用/不启用经验的两个真实运行、冻结起点、spec/model/profile/tool/verifier/资源/预算摘要、经验差别、其他条件差异、样本与执行顺序。结果仅包含已记录的 verdict、尝试数、耗时与可选 token/费用。

条件不一致则 not_attributable；无对照则 unverified。一个样本只展示一次观察，不能当作统计显著或普遍提升。失败、超时也保留；缺成本不补零。该实体仅允许导入有据材料，本次不构建对照调度器。

## 7. 现有实体与选择扩展

run/version/validation/artifact 的原 ID、权限和哈希规则继续使用，不改旧 Bundle。新增故事可以引用额外 historical run；统一 resolver 校验 run.case、version.run、validation.version 及 waveform 摘要，所有历史标识取 Run.origin。

Context/Selection 本次新增可空 story_id、memory_revision_id、memory_use_id；memory ID 可由 revision 推导。Context 增加 view=workspace/optimization/experience（默认 workspace），Selection 另存 workspace_panel=architecture/code/verify（默认 architecture）。页面和标签不参与运行证据判定。原请求省略新字段时行为保持，Selection PATCH 需显式保存新增字段。

- revision 必须属于 story/case，use 必须指向该 revision。
- 选择经验不自动借用当前无关版本；只有明确选中来源或使用事件后，才同步相应 run/version/validation。
- 切案例或选择不相容普通验证时，清除故事子选择；跨页面/标签不清同案例会话、草稿或既有兼容选择。聊天保留当前 view 与可见选择摘要，消息冻结发送时上下文。
- 旧 story ID 仍能恢复其固定历史内容；active 指针变化不改写旧会话上下文。

### 导航恢复状态

路由状态为 view、case、可选公开证据意图及 workspace_panel；会话状态仍保存私有上下文与消息，不能整体写 URL。显式 URL 的页面/公开证据优先于同案例已保存选择，全部证据须校验后恢复；失败链接显示缺口而非借默认成功记录补齐。无 hash 的旧入口默认工作台。

跨页引用保留固定 story/revision/use，打开对应验证后可通过后退恢复；页面导航不新建会话或修改运行 origin。快速导航的异步响应按案例/导航版本匹配，旧响应不得覆盖新选择。具体入口及浏览器历史行为见 `contracts/stories.md`。

## 8. 后续 PPA 数据边界（本次不实现）

未来另版本扩展 OptimizationCampaign/Trial/Measurement：案例与命名范围、主要目标/方向/单位、约束、预定改善阈值、基线、条件指纹、完整 RTL 树及测量 scope 摘要、功能验证、实际报告、候选处置。候选 RTL 摘要与可比条件指纹分开；不同条件不混线。

基线未验证、单位不明、缺测、违反约束或功能失败时不能进入最佳线；零基线不计算改善百分比。面积代理/估计/物理结果分开，功耗缺失为未测量。三条真实可比测量到位后才验收 RI 图；本次 schema 不接受假 campaign 或填零占位，优化状态固定待接入。
