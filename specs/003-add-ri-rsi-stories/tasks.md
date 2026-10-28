---
description: "三页 RTL 演示、PPA 待接入与真实经验闭环的实施任务"
---

# Tasks：优化待接入与经验闭环展示

**Input**：`specs/003-add-ri-rsi-stories/` 下的 spec、plan、research、data-model、contracts 与 quickstart。

**Branch**：沿用 `main`；逻辑特性 `003-add-ri-rsi-stories`。日期：2026-10-19。

**Tests**：规格 FR-021/022/024 与 SC-004～008 要求证据、隔离及独立验收，以下安排对应边界测试和端到端验证；不增加无关测试或全项目 TDD 要求。代码测试使用明确的 fixture，不默认调用真实模型；真实运行与问答另有任务。

**Organization**：Phase 1/2 是共享前置；Phase 3～5 分别对应 US1/US2/US3，均为 P1；最后处理发布与跨故事验收。所有任务初始未执行，勾选必须有实际产物及验证依据。

## 本次范围与完成口径

- 三个页面：`#/workspace`、`#/optimization`、`#/experience`；共享案例、对话、草稿和兼容证据选择。工作台保留架构、代码、验证及真实波形。
- **PPA 当前无数据**：US1 本次只交付待接入页、缺口说明与只读数据边界；不实现测量、候选搜索、收益曲线、图表库或 EDA 安装。FR-004～009、SC-002/003 和 FR-023 的 RI 三版本实证延后，不列成本次待办。
- **经验不能只做卡片**：US2 包含当前 Codex 路径的真实读取、采用/验证记录与不可变修订；公开闭环须有两个独立真实运行和一次有据修订/淘汰。无证据就保留 partial，不勾真实材料任务。
- UI、经验实证、问答、部署分别验收；无同条件记忆对照则收益待验证。本次不调度收益对照，不宣称模型训练或已证明强意义 RSI。
- 沿用既有技术栈、Web/Agent 独立环境及五层发布。`.specify/memory/constitution.md` 是未填写模板，不从示例推导额外流程。

**2026-10-19 用户最新范围**：只完成代码，真实修复验收暂缓。本轮继续代码/UI/协议回归与本地候选封装；T034～T037、T044、T050～T051 保持未执行/未完成，不调用真实模型采集材料，不更新公网。

## Format 与路径

任务格式为 `- [ ] Tnnn [P?] [USn?] 说明及准确路径`。路径相对仓库根；新增路径均需实现时创建。`[P]` 仅表示达到本文列出的前置检查点后，可与不同文件任务并行；不允许同文件并发写入。依赖节给出可并行批次。

`.rtl-demo/` 是已忽略的私有产物目录，承载原始验收记录，不作为整树上传或公开目录。公开规格中的验证摘要不得包含凭据、会话标识、私有日志或参考设计私有源码。

## Phase 1：Setup — 核对现有基线

**Purpose**：使用原应用和运行环境，不初始化新项目或升级依赖。

- [X] T001 核对当前前端、Web/Agent 解释器、四案例、既有部署入口与工作区未提交变更，在 `specs/003-add-ri-rsi-stories/validation.md` 建立本特性验收记录，分别列出 UI、经验实证、问答、部署状态及 PPA 延后；仅记录配置路径/工具版本，不读取输出秘密或覆盖用户变更。
- [X] T002 [P] 在 `tests/rtl_web/story_fixtures.py` 与 `web/rtl-demo/tests/fixtures/stories.ts` 创建明确标为 synthetic 的最小故事 fixture：空状态、仅存档、实际采用后 PASS/FAIL、修订、缺引用与跨案例；引用真实格式的固定哈希但不伪装真实素材，供后续测试复用且禁止公共激活。

**Checkpoint**：已有技术栈和本次边界明确，测试素材与真实演示素材分开。

## Phase 2：Foundational — 共享契约、证据与页面外壳

**Purpose**：本阶段完成前不进入各用户故事；只建立共享能力，经验执行逻辑归 US2。

- [X] T003 [P] 在 `tests/rtl_web/test_story_contracts.py` 编写契约测试，覆盖旧 Context 兼容、未知字段、跨案例/会话引用拒绝、显式链接失效不借默认 PASS、StoryBundle 同 ID 异内容拒绝和公共 DTO 不含私有字段；以测试 fixture 验证边界，不调用模型。
- [X] T004 [P] 在 `web/rtl-demo/src/router.test.ts` 编写路由契约测试，覆盖三个 hash 入口、旧 `?case=e203`、未知路由、公开证据查询参数、URL/会话/默认值优先级，以及 URL 不序列化私有会话、聊天或草稿。
- [X] T005 在 `zerorepo/rtl_web/story_schemas.py` 定义严格 StoryBundle、公共 DTO、经验 revision/use/lifecycle/可选 comparison 读模型及审核输入模型；optimization 本次只允许 awaiting_data，准备状态与验证层级明确，原 Bundle 保持不可变；依据 `data-model.md` 限制字段和大小。
- [X] T006 在 `zerorepo/rtl_web/stories.py` 建立不可变 story 存取、显式公共投影、typed refs 遍历和原 Bundle/故事额外历史运行的统一证据解析；校验 case/run/version/validation/tree/report/VCD 关系及权限，引用冲突不得借另一版本补齐，不新增数据库表或通用管理 CRUD。
- [X] T007 在 `zerorepo/rtl_web/schemas.py`、`zerorepo/rtl_web/chat.py` 与 `zerorepo/rtl_web/api.py` 增加 story/revision/use、view 和 Selection.workspace_panel，补齐 validate_context、Selection PATCH 的显式取字段与存储；保留旧请求默认行为，校验归属，页面字段不能影响操作准入、权限或 verdict。
- [X] T008 在 `web/rtl-demo/src/stories.ts`、`web/rtl-demo/src/state.ts` 与 `web/rtl-demo/src/api.ts` 定义对应公共类型、当前 view/工作台 panel、故事读取与归档证据缓存接口，显式序列化新增上下文；version/validation 解析覆盖故事额外历史，历史模式依据 Run.origin，不把非主历史 run 塞进 liveRun。
- [X] T009 在 `web/rtl-demo/src/router.ts` 实现三个 hash 路由、旧链接解析、公共证据链接构建及历史通知接口；仅允许契约字段，不增加路由依赖或 Caddy rewrite，为后续异步校验恢复提供明确导航版本标识。
- [X] T010 在 `web/rtl-demo/src/shell.ts`、`web/rtl-demo/src/workspace.ts`、`web/rtl-demo/src/main.ts` 与 `web/rtl-demo/src/styles.css` 提取共享品牌/案例/导航/对话外壳与原工作台，保留原三标签、阶段条、操作、回放及波形；对话和消息订阅只初始化一次，尚未注册的故事页显示准备状态，不重建应用或自动运行任务。

**Checkpoint**：原工作台可用，三页外壳及共享契约就绪；尚未实现的内容不得显示成功数据。运行 T003/T004 的对应检查并记录实际结果。

## Phase 3：US1 — 持续优化入口与 PPA 待接入 (Priority: P1)

**Goal**：让演示者知道 RI 的目标与流程，同时准确说明当前尚无 PPA 数据。本次不实现规格中延后的有数据图形场景。

**Independent Test**：无任何 PPA/经验故事输入也可直接进入优化页；四案例各自显示 PPA 待接入，说明缺少什么；无数字收益、曲线、实验按钮、模型请求或执行 POST，原工作台仍可浏览。

### Tests

- [X] T011 [P] [US1] 在 `tests/rtl_web/test_story_read_api.py` 编写两个 GET 接口的契约测试，覆盖无故事 200 空状态、固定历史 story、未知/不可访问 ID 的统一错误和损坏引用不拼接；验证 optimization 始终 awaiting_data 且不接受未支持的实测 campaign。
- [X] T012 [P] [US1] 在 `web/rtl-demo/src/optimization.test.ts` 编写优化页测试，覆盖不同案例的缺口、历史/流程标识、无图表/改善率/默认零值/重型操作，以及单独加载时不依赖经验链。

### Implementation

- [X] T013 [US1] 在 `zerorepo/rtl_web/api.py` 与 `zerorepo/rtl_web/stories.py` 实现 `GET /api/cases/{case_id}/stories` 和 `GET /api/stories/{story_id}`，无 active story 返回契约空 DTO，已有审核 story 返回固定公共投影；仅提供只读查询，不新增实验或公开经验写接口。
- [X] T014 [US1] 在 `web/rtl-demo/src/optimization.ts` 实现“RI：在验证约束内改进设计”、PPA 待接入说明、缺口与文字流程，并在 `web/rtl-demo/src/main.ts` 注册优化路由；按案例读取真实准备状态，不画趋势、不计算改善、不新增执行按钮。
- [X] T015 [US1] 在 `web/rtl-demo/tests/e2e/optimization.spec.ts` 验证直接入口、四案例空状态、返回工作台与 1366×768 布局；监听确保只浏览不发 messages/operations POST、不安装资源，结果记录到 `specs/003-add-ri-rsi-stories/validation.md` 的 US1 本次范围项。

**Checkpoint**：US1 的本次待接入增量可独立演示。RI 实测故事和三版本验收仍标延后，不得因本阶段通过而勾成已完成。

## Phase 4：US2 — 经验来源、实际复用与有据修订 (Priority: P1)

**Goal**：将已有记忆机制接入当前 Codex 执行路径，展示固定版本的来源—采用—后续验证—修订；事实不足时保持已存档或部分完成。

**Independent Test**：不依赖 PPA 数据，导入一条审核经验即可浏览其真实阶段；完整闭环验收另外要求两个独立真实运行、一次实际采用与客观验证、一次有据修订/淘汰。旧 revision 可恢复，查询/打开卡片不算采用，accepted+FAIL 不显示成功收益。

### Tests

- [X] T016 [P] [US2] 在 `tests/test_rtl_memory_ledger.py` 编写不可变 revision、生命周期、重复导入、scope 隔离、旧 Markdown 投影、退役条目不进入新任务和事件幂等测试；不得补造旧文件被覆盖前的历史。
- [X] T017 [P] [US2] 在 `tests/test_codex_memory_adapter.py` 与 `tests/test_codex_debug_resume.py` 编写快照/工具/候选绑定测试，覆盖只读授权范围、外部/内部 run 映射、跨任务/路径/超长参数拒绝、无 diff 不算采用、accepted+FAIL/回滚和 resume 更换 snapshot 拒绝；用可控 reviewer 验证记账而非模拟真实闭环成功。
- [X] T018 [P] [US2] 在 `tests/rtl_web/test_story_evidence.py` 与 `tests/rtl_web/test_story_seed.py` 编写审核导入、版本/哈希/归属篡改、synthetic 禁止公共激活、同 ID 冲突/幂等/事务、v1 原摘要兼容、v2 闭包与公共导出测试；包含额外 historical run 的报告/waveform tile 引用，以及记忆对照条件不一致、单样本或缺成本不得升级收益的边界。
- [X] T019 [P] [US2] 在 `web/rtl-demo/src/stories.test.ts` 与 `web/rtl-demo/src/experience.test.ts` 编写各经验阶段独立显示、来源/采用者区分、修订未再用保持待验证、失败/淘汰/缺证据，以及无对照收益待验证的测试；不从条目数或规则 confidence 推导提升。

### Implementation：可信经验运行路径

- [X] T020 [US2] 在 `zerorepo/rtl_impl/rtl_memory/schemas.py` 与 `zerorepo/rtl_impl/rtl_memory/ledger.py` 实现 revision、生命周期、snapshot 和使用事件，按 scope/内容寻址并原子追加；在 `zerorepo/rtl_impl/rtl_memory/store.py` 保留最新 Markdown 兼容投影，历史 JSON 不进入旧扫描器的条目计数，旧记录不就地覆盖。
- [X] T021 [US2] 在 `zerorepo/rtl_impl/rtl_memory/adapter.py` 复用 `zerorepo/rtl_impl/rtl_memory/selector.py` 实现审核公共库和本会话授权库的相关经验选择、清洗、固定快照与有界查询/读取；保存选择配置摘要，无经验也有明确空快照，不授予模型全局目录读取权限。
- [X] T022 [US2] 在 `zerorepo/rtl_web/settings.py`、`zerorepo/rtl_web/jobs.py`、`zerorepo/rtl_web/deployment_models.py` 与 `zerorepo/rtl_web/sandbox.py` 接入可信经验库配置和冻结快照 job manifest/load 校验，复制到只读 job_inputs/memory；仅可信工具端可读，模型侧不挂载该私有目录；在 `configs/rtl_demo.example.yaml` 添加无秘密示例，未配置时保持原执行行为，不放宽现有门禁。
- [X] T023 [US2] 在 `zerorepo/rtl_web/runtime.py`、`zerorepo/rtl_impl/debug_agent/debug_runner.py` 与 `zerorepo/rtl_impl/debug_agent/system_debug_runner.py` 将外部 run/case、内部 debug run/attempt 和经验 snapshot 传到当前 Codex 路径，区分运行身份，直接原生运行也产生明确来源绑定，不把网页 run 和内部 UUID 混用。
- [X] T024 [US2] 在 `zerorepo/rtl_impl/codex_debug/schemas.py` 与 `zerorepo/rtl_impl/codex_debug/history.py` 扩展 descriptor/debug_binding 和恢复检查，冻结 revision/snapshot 与原输入/profile；旧无经验描述可按明确空快照兼容，不能为旧运行静默注入新经验或替换当前绑定。
- [X] T025 [US2] 在 `zerorepo/rtl_impl/codex_debug/runner.py`、`zerorepo/rtl_impl/codex_debug/mcp_server.py`、`zerorepo/rtl_impl/codex_debug/session.py` 与 `zerorepo/rtl_web/tool_bridge.py` 同步接通 query_rtl_memories、read_rtl_memory、record_memory_application 的 schema/白名单/分发/方法及提示词；身份由可信 Session 取得，限制 limit≤5/max_chars≤8000，不接收外来路径、run、scope 或 verdict，apply 声明不直接产生成功结论。
- [X] T026 [US2] 在 `zerorepo/rtl_impl/codex_debug/session.py`、`zerorepo/rtl_impl/rtl_memory/adapter.py` 与 `zerorepo/rtl_web/runtime.py` 将 retrieved/provided/声明/实际 diff/候选评估/accept或rollback/最终系统复验分别追加到使用账本；applied 只关联已提供 revision 和当前真实目标 diff，验证绑定固定 tree/verifier/report/VCD，失败、回滚和未验证均保留且恢复不重复计数。
- [X] T027 [US2] 在 `zerorepo/rtl_impl/rtl_memory/distiller.py` 与 `zerorepo/rtl_impl/rtl_memory/adapter.py` 从当前 Codex 的客观结果提炼任务私有经验草稿，验证层级按实际证据赋值，修正固定 verified_by 误导并保持 ReAct 兼容；不伪造旧 patch entry，不自动审核、发布或写其他会话经验库。
- [X] T028 [US2] 在 `zerorepo/rtl_web/cli.py` 与 `zerorepo/rtl_impl/rtl_memory/ledger.py` 实现 review-memory 的审核 manifest 校验、dry-run、追加批准/修订/淘汰和错误码；审核材料须绑定来源/新证据与授权范围，拒绝模型自称 approved 替代维护者审核，默认输出不含正文、凭据或私有路径。

### Implementation：审核故事与经验页面

- [X] T029 [US2] 在 `zerorepo/rtl_web/stories.py` 与 `zerorepo/rtl_web/cli.py` 实现 validate-stories/import-stories、dry-run 与显式 activate：审核输入、文件/typed refs 闭包、来源后端、实际阶段、修订依据、公共字段与缺口均校验；可选记忆对照匹配起点/spec/model/profile/verifier/资源/预算，不一致标不可归因，单样本注明范围、缺成本不补零；先预检所有冲突再原子导入，active 根不在失败或 dry-run 时变化，保留旧故事供历史选择恢复。
- [X] T030 [US2] 在 `zerorepo/rtl_web/deployment_models.py`、`zerorepo/rtl_web/seed.py` 与 `zerorepo/rtl_web/cli.py` 实现判别式 v1/v2 seed，v2 增加 story kind/故事根并遍历全部额外历史证据；保持 v1 原摘要，严格 seed.json+files、白名单和事务，排除会话/队列/私有 owner/不可达记录，有故事不静默导成丢失内容的 v1。
- [X] T031 [US2] 在 `zerorepo/rtl_web/import_case.py` 与 `zerorepo/rtl_web/stories.py` 扩展 export-static/prepare-cases，输出案例 stories manifest、显式公共 DTO 和额外历史 display 代码/报告/VCD索引/tiles；私有审计不导出，记录未公开材料缺口，并生成 API/静态身份比对所需 story_id+fingerprint。
- [X] T032 [P] [US2] 在 `web/rtl-demo/src/experience.ts` 与 `web/rtl-demo/src/styles.css` 实现经验列表/单卡、来源—使用—验证链和修订摘要，用事实阶段显示 PASS/FAIL/未记录、局部/系统层级、旧版与待验证新版、可选对照及局限；只显示有据数据，无 PPA 或其他案例材料也可独立渲染。
- [X] T033 [US2] 在 `web/rtl-demo/src/main.ts`、`web/rtl-demo/src/api.ts` 与 `web/rtl-demo/src/state.ts` 注册经验页面，接通审核故事加载、revision/use 选择和固定证据打开；无故事/损坏/未公开材料显示明确状态，静态回退检查 story_id+fingerprint，禁止拼接另一发行版或无关验证。

### 真实材料：单独验收，不可由 fixture 替代

- [ ] T034 [US2] 核查 `rtl_outputs/e203_exu_alu_system/.zerorepo/workspace/rtl_memory/` 现有五条经验与原日志，建立 `.rtl-demo/stories/e203/source-audit.json`；确定来源运行 A 并保存固定输入/RTL/验证证据，不足时在准入就绪环境通过现有受控修复路径补采真实 A，再形成 `.rtl-demo/stories/e203/reviewed-memory-v1.json` 并用 review-memory 审核 v1，不修改原 merged/oracle 来编故事。
- [ ] T035 [US2] 在资源与执行准入就绪的受控环境，经现有 `POST /api/sessions/{ident}/operations` 的 fix 或对应原生路径启动独立运行 B，冻结 v1；记录真实 Codex query/read、采用声明、目标 diff、候选及最终验证，形成 `.rtl-demo/stories/e203/reuse-acceptance.json`，保存外部/内部 run 和摘要；无实际采用不得勾选本任务，不用 mock、同 run 聊天或关闭门禁替代。
- [ ] T036 [US2] 根据 B 或新增真实边界证据形成 `.rtl-demo/stories/e203/reviewed-memory-v2.json` 的修订或淘汰，经 review-memory 追加并保留 v1；明确变更依据与未再使用状态，纯排版/虚构反例不算修订。缺少新证据时保持 partial、本任务未完成，按已有预算采集而不启动无限循环。
- [ ] T037 [US2] 在 `.rtl-demo/stories/e203/reviewed-story.json` 组装并人工审核公开经验闭环，保留原始/公开摘要和授权来源映射，通过 validate-stories、import-stories dry-run 后在本地显式激活；在 `specs/003-add-ri-rsi-stories/validation.md` 分别记录真实两运行、采用后验证及修订是否通过，无对照的收益继续未验证，不公开整套私有日志。

**Checkpoint**：经验页面可独立浏览；只有 T034～T037 的客观材料达到 FR-023 经验部分，才能称真实闭环完成。PPA 不参与本阶段验收，实际验证失败允许照实展示，链路完整不等于收益为正。

## Phase 5：US3 — 连贯导航、证据跳转与持续对话 (Priority: P1)

**Goal**：三个页面间可持续对话，选择、公开链接、刷新与浏览器历史保持一致；对选中经验给出有依据回答，对 PPA 缺失直说未接入。

**Independent Test**：可用一个已审核故事或明确标记的 UI fixture，验证“经验 → 对应工作台验证 → 后退 → 优化”的导航，草稿和消息保留；真实问答另外使用实际审核材料验收。失效引用不得借最近 PASS，额外历史 run 不误标实时。

### Tests

- [X] T038 [P] [US3] 扩展 `web/rtl-demo/src/router.test.ts` 与 `web/rtl-demo/src/state.test.ts`，覆盖无 version 的经验选择恢复、URL/会话优先级、view/panel 保存、深链接失效、额外历史 origin、快速导航旧响应丢弃、切案例隔离与私有 ID 不入公共 URL。
- [X] T039 [P] [US3] 在 `tests/rtl_web/test_story_chat.py` 编写选中 revision/use 的有限证据、当前 view、固定发送上下文、allowed refs 过滤、PPA 缺失和跨会话拒绝测试，确保浏览与恢复不创建问答或运行；使用测试 provider 验证协议，不冒充真实问答结果。

### Implementation

- [X] T040 [US3] 在 `web/rtl-demo/src/state.ts`、`web/rtl-demo/src/api.ts` 与 `web/rtl-demo/src/main.ts` 完成异步恢复和统一证据解析：显式公共 URL 意图优先，同案例已保存选择其次，普通入口才用默认历史；支持纯经验选择、旧故事、正确 run.origin，按案例/导航版本隔离过期响应，显式失败引用保留缺口。
- [X] T041 [US3] 在 `web/rtl-demo/src/router.ts`、`web/rtl-demo/src/shell.ts` 与 `web/rtl-demo/src/main.ts` 完成证据到工作台 panel 的跨页跳转、公开链接、前进/后退、刷新与案例切换；保留兼容选择和单个对话/SSE 实例，清除不兼容参数，运行中回复不因导航取消或重复提交，URL 不携带私有实体或聊天。
- [X] T042 [US3] 在 `zerorepo/rtl_web/chat.py`、`zerorepo/rtl_web/chat_runtime.py` 与 `web/rtl-demo/src/chat.ts` 接入当前 view、选中 revision/use、准备状态和有界公开证据摘要，继续使用原模型服务及合法 artifact 引用；明确历史/实际使用/验证/收益差别，PPA 无数据不生成成绩，发送后消息上下文固定，私有聊天不进入公共经验。
- [X] T043 [US3] 在 `web/rtl-demo/tests/e2e/stories.spec.ts` 覆盖三页直接打开、刷新/前进后退、草稿与进行中对话、证据跳转/失效、快速切案例、旧链接、断网静态回退、独立会话、1366×768 和浏览无模型/执行 POST；验证无重复订阅，fixture 仅用于 UI 验收。
- [ ] T044 [US3] 使用 T037 审核后的真实经验，在本地或候选运行环境主动完成至少两轮真实问答，覆盖“实际用到哪里/依据是什么”和“现在有 PPA 结果吗”，检查合法证据及局限；完成本次范围 90 秒跨页演示，原始记录保存 `.rtl-demo/stories/e203/chat-acceptance.json`，在 `specs/003-add-ri-rsi-stories/validation.md` 记录实际 host/release 与结果，不用测试 provider 补齐。

**Checkpoint**：三个页面可连贯演示，历史证据和实际问答各自有依据。若实证或问答条件未满足，界面可验收但相关任务和能力状态仍未完成。

## Phase 6：Polish — 回归、封装与公网验收

**Purpose**：只处理本特性必要的跨故事兼容和实际发布，不改变其他域名或解除执行门禁。

- [X] T045 [P] 在 `tests/rtl_web/test_story_deployment.py` 增加五层发布闭包、v1/v2 seed 兼容、公开/私有文件边界、旧故事恢复和回退输入测试；确认构建不需要开发仓库/全局 memory/本地 RealBench 隐式路径，不把 specs/tests/凭据或私有日志放到静态站。
- [X] T046 在 `scripts/rtl_demo/deployment.py`、`zerorepo/rtl_web/deployment_models.py` 与 `deploy/rtl_demo/package.example.yaml` 接通故事 seed 的构建/检查/恢复清单，保持五层白名单及必要运行资源；发布与验收目标绑定当前 Agent 站和实际 release，不能沿用旧 design 目标或旧封存包覆盖现有有效修复，不新增端口或密码。
- [X] T047 在 `specs/003-add-ri-rsi-stories/quickstart.md`、`web/rtl-demo/README.md` 与 `deploy/rtl_demo/RUNBOOK.md` 更新实际已实现命令、三页入口、审核/导入/seed 与回退步骤，明确材料状态和 PPA 延后；只写路径/无秘密示例，区分开发启动、候选演练和公网发布。
- [X] T048 按 `specs/003-add-ri-rsi-stories/quickstart.md` 在对应 Web/Agent 环境运行本特性及受影响的原有测试、前端 test/build 和相关 Playwright 场景，回归四案例、DUT/参考波形、会话隔离和旧记忆/ReAct/Codex 恢复；将命令、真实结果及 SC-007 切换性能写入 `specs/003-add-ri-rsi-stories/validation.md`，不为文档或占位界面宣称实证通过。
- [X] T049 用 `scripts/rtl_demo/deployment.py` 的 build/check 流程在仓库外 `/tmp/rtl-demo-ri-memory-release/` 准备新发行版和对应历史 seed，并将索引保存到 `.rtl-demo/deployment/ri-memory-release/`，执行隔离候选目录导入/静态浏览演练并校验哈希；保留原发行版/seed/active 根回退指向，只上传五层必要文件，不整体复制仓库或覆盖会话数据库。
- [X] T050 在既有授权 SSH 发布流程和预检满足后，用 `scripts/rtl_demo/deployment.py` 及 `deploy/rtl_demo/RUNBOOK.md` 更新 `agent.deepvalleychip.cn` 的对应发行版/seed/公共根，保持后端回环监听和原访问方式；不改 design 原站、主站/www 或其他端口，私有实施记录保存 `.rtl-demo/deployment/ri-memory-release/deploy-result.json`，条件不足则保留未执行而不假报上线。
- [ ] T051 在实际 Agent 公网入口验收三页直达/刷新、共享对话与合法引用、经验到真实代码/波形、两访客隔离和原四案例；至少一次主动真实问答确认部署链路，检查 design 原站及主站/www 保持原职责，将绑定实际 host/release 的证据存入 `.rtl-demo/deployment/ri-memory-release/public-acceptance.json`，失败按已保留的同版 seed/根回退。
- [X] T052 在 `specs/003-add-ri-rsi-stories/validation.md` 汇总逐项验收与真实证据索引，在 `specs/003-add-ri-rsi-stories/tasks.md` 仅勾选实际完成任务；区分代码/UI、两运行经验闭环、问答和公网状态，PPA 与未做的收益对照明确延后/未验证，不因剩余资源或预算不足把未完成能力标成成功。

**Checkpoint**：所有已勾选工作可复查，UI/经验/问答/公网分别有结果；本次未包含的 PPA 仍明确待接入。

## Dependencies & Execution Order

### Phase dependencies

```text
Phase 1：T001～T002
    ↓
Phase 2：T003～T010（所有故事的共享前置）
    ├── US1：T011～T015（无 PPA 数据即可完成）
    └── US2：T016～T037（运行闭环与页面可分线开发）
             ↓
US1 + US2 → US3：T038～T044（整合导航、选择与真实问答）
             ↓
Phase 6：T045～T052（兼容发布、公网与最终记录）
```

阶段按编号给出推荐单人实施顺序；三故事都是 P1，保留规格顺序。US2 经验域、渲染器和证据测试不依赖 US1 的 PPA 页面，达成共享前置即可开发；共同涉及 stories.py/api.py/main.ts 等文件的集成必须串行。US3 的完整演示依赖 US1/US2，路由/对话契约测试可以先行。

### 关键任务依赖

| 任务/批次 | 前置与说明 |
| --- | --- |
| T003、T004 | T001/T002；契约测试可并行编写，针对尚未实现能力的失败必须可解释 |
| T005 → T006 → T007/T008 | 固定读模型后再接公共解析及双端上下文；T007/T008 触及不同文件可分线但最终契约一致 |
| T009 → T010 | T004/T008；先解析路由，再提取共享外壳并回归原工作台 |
| T011/T012 → T013/T014 → T015 | Phase 2；后端读取与优化渲染测试无共享写文件，集成 main 由单一修改者完成 |
| T016/T017/T018/T019 | Phase 2；测试文件不同，可同批编写，不真实调用模型 |
| T020 → T021 → T022 → T023 → T024 → T025 → T026 → T027 | 经验模型、快照、传递、恢复、工具、客观事件、草稿顺序；共享文件顺序修改 |
| T028 → T029 → T030 → T031 | 可信审核先于公共导入，完整闭包先于 seed 和静态输出；CLI/模型文件不可并发写 |
| T032 | T005/T008/T019；可与 T020～T031 后端线并行，只改 experience.ts/styles.css |
| T033 | T013/T029/T031/T032；统一接入已批准数据及静态回退，不以空 fixture 宣称闭环 |
| T034 → T035 → T036 → T037 | T025～T031；按实际来源、审核、真实后续运行和新证据顺序收集；受真实资源/证据约束 |
| T038/T039 → T040 → T041 → T042 → T043 → T044 | T033；无材料时 T038/T039 可先写，真实问答需 T037，不能用 UI 测试抵扣 |
| T045/T046 → T048/T049 → T050 → T051 → T052 | 发布检查先于激活；T047 可在命令稳定后补齐；服务器验收不能由本地结果替代 |

T034～T037 条件不足时继续不依赖真实材料的 UI/测试/封装工作，相关实证任务保持未勾选并显示缺口。需要采集新真实材料时沿用现有授权模型与预算，不重置预算、不制造结果，也不因等待实证停止其他可完成工作。

## Parallel execution examples

### US1

Phase 2 完成后，同时编写 T011 的 GET/空状态测试与 T012 的优化渲染测试；各自测试契约稳定后，T013 后端 GET 和 T014 优化组件可分别开发，接入 main 的修改串行，最后 T015 验证完整页面。此并行不涉及 PPA 实验。

### US2

Phase 2 后 T016～T019 可并行。T005/T008/T019 具备后，T032 经验组件仅依赖公开读模型，可与 T020～T031 的账本、工具和导入后端线并行。真实采集 T034～T037 必须串行并固定输入，不能并行更换同一 revision 或候选。

### US3

T038 前端导航/恢复测试与 T039 后端问答证据测试可以并行。随后前端恢复 T040/T041 与后端 chat.py/chat_runtime.py 的证据组装可按接口分线；T042 中 chat.ts 的接入及 main/state 写入由各自单一修改者串行整合，再做 T043/T044。

`[P]` 是任务调度说明，不要求启动额外 Agent；本轮仅生成任务清单。

## Implementation strategy

### MVP first

1. Phase 1/2 + US1 形成**界面 MVP**：原设计工作台、三页共享外壳和真实 PPA 待接入说明；经验入口保持明确准备状态。此版本不能称完整 RI/RSI 演示。
2. 完成 US2 的审核存档页和真实使用适配，先验收归档能力，再补 T034～T037 的真实链；材料不足照实显示 partial。
3. US3 完成跨页证据与持续问答，达到可讲述的经验闭环演示；最后通过 Phase 6 发布验收。

### 增量交付与完成证据

每个故事按独立标准验证，不把阶段检查点当作中止未授权后续工作的理由。实施时持续完成本次已授权、无外部阻塞的全部任务；遇到资源或材料缺口保留未完成项和可见状态。代码测试通过、真实经验链成立、可量化收益成立、公网已上线是不同结论，分别记录。

| 规格范围 | 当前任务覆盖 |
| --- | --- |
| FR-001/002/003/010/020 | T007～T015、T032、T040～T043 |
| FR-004～009、SC-002/003、FR-023 RI 部分 | 用户要求延后，不生成本次测量/曲线任务 |
| FR-011～014/017/018、SC-004、FR-023 经验部分 | T016～T037 |
| FR-015/016、SC-005 | T005、T019、T029、T032：导入约束和无对照待验证；不强制新收益实验 |
| FR-019/021/022、SC-006 | T003、T006～T008、T017/018、T029～T031、T038～T044 |
| SC-001/007/008 | T015、T038～T044、T048、T051 |
| FR-024 | T001、T015、T037、T044、T048、T051/052 分项记录 |

## 任务计数与格式检查

共 52 项：Setup 2、Foundational 8、US1 5、US2 22、US3 7、Polish 8。每项都有连续 T001～T052、未勾选框和明确文件路径；仅用户故事阶段带对应 US 标签。标记 `[P]` 的任务需遵守依赖节，不代表可绕过前置或同文件并发修改。


## 2026-10-19 实施状态

已完成 45/52 项代码、协议/UI 回归与本地候选封装；未完成 7 项为 T034～T037、T044、T050～T051，按用户“只完成代码，真实修复验收暂缓”保留未勾选。

- T034 已审计五条 legacy 经验，结果见私有 source-audit.json；缺 trace 原始证据，未升级验证层级，未形成审核 v1。
- T046 完成五层 build/check、v1/v2 闭包、静态身份比对、目标域名及验收身份绑定、故事根恢复；Agent 目标明确拒绝旧 design activate。本轮未实现或执行现有公网服务的自动升级，实际服务更新仍属于 T050；不能把本地包称已发布。
- T049 仅本地 staged 候选及隔离导入/浏览。构建器要求包在仓库外；私有索引保留旧发行版事实与新包摘要，无上传、无生产 DB 或 active 根修改。
- UI、经验协议、真实两运行、真实问答和公网分别记录于 validation.md；不使用测试 fixture 抵扣真实任务。


## 后续公网发布（用户明确要求新版本上线）

T050 已完成：`evolution-20261019-r1` 发布到 `https://agent.deepvalleychip.cn`，对应物理目录 `/home/dev/rtl-agent-demo/releases/evolution-20261019-r1`。采用现有 Agent 服务的独立目录更新，没有使用旧 design activate。候选四案例/波形/新 Selection 接口检查通过；环境复用现有不可移动的解释器目录，保留旧 release，凭据不重新传输。

公网三页、五步机制交互、刷新/草稿、四案例真实波形与独立访客隔离通过。Caddy、design/main/www 响应保持原样；42 个已有会话保留。私有发布记录见 `.rtl-demo/deployment/evolution-public-20261019/`。

T051 仅 UI 与隔离部分通过：真实问答验收被自动审批拒绝后没有执行，等待用户对本次外发明确授权，故仍未勾选。真实 A/B 修复与原真实经验链继续未执行。当前总计 46/52 已完成；前文 45/52 是代码阶段记录。
