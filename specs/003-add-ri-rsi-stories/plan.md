# Implementation Plan：优化待接入与经验闭环展示

**Branch**: `main`（逻辑特性 `003-add-ri-rsi-stories`） | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: `specs/003-add-ri-rsi-stories/spec.md`，含用户补充“PPA 数据后面才会上线，目前还没有”与“不一定要保持单页，可以按照你觉得好的规划拓展”。

## Summary

将现有站点组织为“设计工作台 / 持续优化 / 经验闭环”三个独立入口，共享站点外壳、案例选择和常驻对话。工作台保留架构、代码、验证和波形；优化与经验各有完整内容空间。**本次优化页只显示 PPA 待接入，不做测量、候选搜索或收益曲线。** 经验页复用现有证据展示来源、实际使用、后续验证与修订，证据不足时明确所处阶段。

技术上沿用 TS 原生页面与 FastAPI，新增一个不可变故事读模型和只读 API；补上当前 Codex 路径的经验快照、三个记忆工具和可信使用记录。材料经维护者审核后进入版本化 seed，沿用现有部署五层。无 PPA 数据不阻塞本次页面交付，经验 UI 通过也不替代真实闭环验收。

## Technical Context

**Language/Version**: Python 3.13.11（现有部署基线）；TypeScript 5.9；Node/npm 沿用现有前端锁文件及构建环境。

**Primary Dependencies**: 现有 FastAPI/Uvicorn/Pydantic/PyYAML、SQLite；Vite 7.1、Vitest、Playwright；Agent 沿用现有 Codex MCP、RTLMemorySelector、distiller。保持 Web/Agent requirements 分离，本特性不升级依赖、不新增图表库。

**Storage**: 现有 SQLite WAL `records` 增加 `story` kind，无表结构迁移；可信文件账本追加 memory revisions/use events，保留旧 Markdown 兼容视图；RTL/报告/VCD 仍走原 artifact。

**Testing**: Python pytest、前端 Vitest/TypeScript 构建、Playwright；另外单列真实 Codex 跨运行复用及修订证据验收。测试 fixture 不作为公共故事。

**Target Platform**: Linux 后端，桌面浏览器，1366×768 基准；当前公网约 2 CPU / 2GB。入口 `agent.deepvalleychip.cn`；`design.deepvalleychip.cn` 原站保持独立。

**Project Type**: 现有 Web 工作台增量扩展及 Agent 工具适配，不新建应用或执行平台。

**Performance Goals**: 已加载案例的站内页面/工作台标签切换 95% ≤1 秒；无页面级横向溢出；本次 90 秒完成“PPA 待接入 → 经验链 → 对应验证 → 问答”。打开/刷新/导航不触发模型或重型任务。

**Constraints**: 不编造 PPA、复用或收益；不跨会话共享私有经验；所有公开引用校验哈希及归属；恢复固定经验快照；不放宽现有执行门禁；不修改其他域名职责。

**Scale/Scope**: 三个页面、工作台内部三个内容标签、四案例、E203 优先一条真实经验链；其他案例显示各自空状态。无 PPA 工具部署、实验调度、网页经验编辑器、自动公共发布或模型训练。

## 页面组织与导航决策

| 主导航 | 内容与职责 | 入口 |
| --- | --- | --- |
| 设计工作台 | 规格/架构、RTL、执行过程、验证报告及 DUT/参考波形；保留原三个内部标签 | `#/workspace` |
| 持续优化 | RI 流程、PPA 待接入说明；后续接真实实验和趋势 | `#/optimization` |
| 经验闭环 | 来源 → 固定经验版本 → 后续采用 → 验证 → 修订；证据状态与局限 | `#/experience` |

顶部固定品牌、案例、三个导航入口和连接状态，右侧对话共享一个实例。各页面保留清晰案例标识；运行/版本摘要只在确有关联时显示。工作台的阶段条和执行动作留在工作台，其他页面提供“查看对应代码/验证”跳转，不重复执行区。

采用轻量 hash 路由和共享 shell，而不是三个独立重载的 HTML：用户可以进入独立页面、复制公开证据链接、前进/后退，导航中保留对话与草稿；沿用原 Vite/静态部署，无需 Caddy 新路由或新前端依赖。旧 `?case=e203` 无 hash 时进入工作台。路由与证据参数恢复、校验顺序详见 `contracts/stories.md`。

此组织让“设计如何完成”“设计如何优化”“经验如何改进后续任务”各自清晰；当前不再增加总览、任务管理、设置等入口。未来新增页面按实际内容决定。

## Constitution Check

`.specify/memory/constitution.md` 仍是未填写模板，没有已批准的项目原则；不能把示例文字当成额外审批或 TDD 要求。本轮依据用户明确要求与已确定的仓库约束检查。

| Gate | 研究前 | Phase 1 后 | 依据 |
| --- | --- | --- | --- |
| 保持结构清晰、演示简洁 | PASS | PASS | 按用户授权拆成三个页面，共享对话与证据视图 |
| 当前无 PPA 也可交付 | PASS | PASS | 优化空状态；生产/曲线/工具链全部延后 |
| 事实与演示分开 | PASS | PASS | UI、经验链与未来 RI 分别验收；无样本不算收益 |
| 兼容与隔离 | PASS | PASS | v1 seed 保留、严格公共投影、会话与运行归属检查 |
| 执行与部署边界 | PASS | PASS | 无新重型网页操作；保留资源门禁和域名职责 |

无须豁免的冲突。技术不确定项已在 [research.md](research.md) 收敛；真实材料尚未准备不等于已经通过验收。

## Project Structure

### Documentation

```text
specs/003-add-ri-rsi-stories/
├── spec.md                         # 含本次范围补充
├── analysis.md                     # 原分析；PPA 建议标记为后续
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md                        # 后续 speckit-tasks 生成的执行清单
├── contracts/
│   ├── stories.md                  # 页面、GET、选择、对话
│   ├── memory-runtime.md           # 经验快照、工具与可信事件
│   └── evidence-package.md         # 导入、seed、公开与部署边界
└── checklists/requirements.md
```

`tasks.md` 已由后续 `$speckit-tasks` 生成，见 [任务清单](tasks.md)；清单生成不表示代码、真实材料或部署已经完成。

### Source Code（以下是拟修改/新增路径，不代表已经实现）

```text
web/rtl-demo/src/
├── shell.ts / router.ts            # 新增：共享导航/对话外壳、hash 路由
├── workspace.ts                    # 提取原工作台，保留原三个内部标签
├── optimization.ts                # 新增：PPA 待接入与流程短说明
├── experience.ts                  # 新增：一张经验卡、链路与修订
├── stories.ts                     # 新增：公共类型与证据状态
└── main.ts / state.ts / api.ts / chat.ts / styles.css
zerorepo/rtl_web/
├── story_schemas.py / stories.py   # 新增：读模型、审核输入及公共投影
└── schemas.py / api.py / chat.py / chat_runtime.py / import_case.py
    cli.py / seed.py / deployment_models.py / jobs.py / runtime.py
    settings.py / sandbox.py
zerorepo/rtl_impl/rtl_memory/
├── ledger.py / adapter.py          # 新增：不可变记录、只读快照与事件
└── schemas.py / store.py / distiller.py / selector.py
zerorepo/rtl_impl/codex_debug/
└── schemas.py / runner.py / session.py / mcp_server.py / history.py
zerorepo/rtl_impl/debug_agent/debug_runner.py / system_debug_runner.py
zerorepo/rtl_web/tool_bridge.py
scripts/rtl_demo/deployment.py      # v2 seed / 发布闭包支持
tests/rtl_web/test_story_*.py        # 新增：证据与公开访问
tests/test_rtl_memory_ledger.py     # 新增：版本、使用、恢复
web/rtl-demo/src/stories.test.ts    # 新增：状态与上下文
web/rtl-demo/src/router.test.ts     # 新增：路由、旧链接与恢复优先级
web/rtl-demo/tests/e2e/stories.spec.ts
```

**Structure Decision**：继续使用原目录，从 main 提取共享 shell 和工作台，通过轻量路由切换内容；公共读模型与私有运行账本分开，兼容原 Store、artifact、执行工具桥和构建发布流程。无需新数据库服务、前端框架或图表引擎。

## Phase 0：已完成的研究决策

详见 [research.md](research.md)：PPA 延后；Codex 记忆缺口；可信记账；单故事记录；额外历史运行解析；v2 seed 兼容；真实材料验收；小服务器的展示职责。研究仅只读核查，没有实际实验、模型调用或服务器修改。

## Phase 1：设计与实施顺序

1. **先建立数据契约和兼容路径**：StoryBundle、公共 DTO、revision/use 模型、v1/v2 seed；优化部分明确 `awaiting_data`，不接收未经支持的未来测量格式。
2. **补经验运行闭环**：冻结授权经验快照、传递外部/内部 run 绑定、接通三个工具、将声明与实际 diff/验证绑定。新增 revision 只形成草稿，维护者审核后发布；失败/回滚也记账。旧 ReAct 逻辑保持可用。
3. **接只读 API、导入和证据解析**：审核材料进不可变故事；统一解析额外历史 run/version/validation/artifact；静态与 API 同版本；无材料明确返回空状态。
4. **接前端和对话**：先提取共享 shell/工作台并保持原功能，再接三页路由、优化待接入、经验卡/链路/修订和原证据跳转；统一 URL、会话选择、刷新与前进/后退恢复，修复历史标识推断。对话、草稿和订阅不因路由重建，浏览不发模型请求。
5. **准备与分别验收**：先用 fixture 验证接口/UI，再在合适环境采集真实来源 A、实际使用 B、最终复验及有据修订。证据不足就保留阶段状态，不能用 mock 或仅打开卡片充数。PPA 记录为延后，收益对照为可选。
6. **后续实施发布**：以新 release 打包当前有效源文件与审核 seed，经本地验收及服务器预检后更新 Agent 站；保留回滚。此计划阶段不执行部署。

各阶段依赖前序契约；页面空状态可以先完成，真实链路验收必须等运行适配和真实材料到位。

## 需求与验收对应

| 范围 | 本次工作与验收 |
| --- | --- |
| FR-001～003、010、020 | 三个页面、共享对话、PPA 明确空状态、历史标记、无自动任务 |
| FR-004～009；SC-002/003 | 延后 PPA 接入，保留数据要求，不进入本次工具/图形任务 |
| FR-011～014、017/018 | 经验修订和实际使用账本；两真实运行及有据修订单独验收 |
| FR-015/016；SC-005 | 无对照显示收益待验证；本次不要求产生收益实验 |
| FR-019、021/022 | 选中对象问答、可访问引用、会话隔离、版本/波形闭包 |
| FR-023/024 | 经验真实材料与 UI 分开记录；RI 三版本证据延后 |
| SC-001/006～008 | 按规格范围补充后的演示路径、两问答、性能及四案例回归 |

## 验证策略

- Python：revision 不可变、重复导入幂等、快照恢复、真实采用门槛、accepted+FAIL、回滚、篡改、跨会话/案例/运行拒绝；v1/v2 seed 和公共导出闭包。
- 前端：无 PPA 不出现数值或曲线；案例切换不串选择；额外历史 run 不被标实时；直接链接、刷新、前进/后退恢复经验；跨页跳转对应版本，对话实例不重建。
- 端到端：1366×768、三页主导航和工作台三个标签、跨页对话/草稿保留、四案例/原波形、静态浏览、旧链接；监听确认浏览无模型/执行 POST及重复订阅；验证两独立会话隔离。
- 真实验收：Codex 实际读取特定 revision、声明与修改关联、后续验证及新证据修订；至少两轮真实问答验证引用与缺失说明。运行资源不足时保留未验收，不修改准入判断。

可执行场景、命令与未来命令的区别见 [quickstart.md](quickstart.md)。本轮只检查文档一致性，不宣称应用测试或真实闭环已通过。

## 部署适配与回滚

- 不新增端口、PPA 后台或常驻模型进程；API/网关继续回环监听，由现有 Caddy 服务 Agent 入口。
- 继续 design/runtime/seed/verifier/ops 五层。上传构建结果、必要运行代码及审核材料；不传 specs/tests/.git/node_modules、完整 rtl_outputs、原始全局记忆库、会话数据库、模型配置或密钥。
- 私有审计材料仅进私有 seed 存储，公开只导出白名单 DTO 与允许公开 artifact；参考设计私有源码不随经验正文透出。
- v2 seed 随兼容后端发布；旧版回退使用对应旧 seed 和 active 指针，不覆盖会话数据库，也不把 v2 输入交给 v1-only 后端。
- 当前服务有历史增量修复，不能盲用旧 sealed package；实施时重新生成完整 release manifest，保留 VCD 导入信号处理修复及 `design` 原站配置。
- 不修改 `design.deepvalleychip.cn`、主站、www 或其他服务。具体发布由实施阶段执行，本轮不连接服务器。

## Complexity Tracking

无 Constitution 违例，无新增基础服务。复杂度集中在必要的证据真实性和旧路径兼容；PPA 生产、曲线、实验平台及收益对照调度均已移出本次范围。
