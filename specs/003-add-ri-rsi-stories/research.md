# Phase 0 Research：RI / 经验展示的仓库适配

日期：2026-10-19。依据本地代码只读核查及三个研究分支的汇总；未安装工具、执行模型、生成测量数据或访问服务器。用户最新确认的“PPA 数据后续上线”已同步至 `spec.md`，以下决策以该范围为准。

## 1. 三个展示页面共享外壳，PPA 生产与曲线延后

**Decision**：用户解除必须单页的约束后，采用设计工作台、持续优化、经验闭环三个页面，工作台保留原三个标签。通过共享 shell 与轻量 hash 路由保留案例、对话实例、草稿和兼容选择。优化页本次只有“PPA 数据待接入”、简短 RI 流程和数据缺口，无数值卡、假曲线或启动优化按钮。接口提供独立准备状态；后续有数据再实现趋势渲染与测量导入。

**Rationale**：三个入口让功能完成、持续优化、经验复用的叙事分开，又能随时跨页追证。现有 main 将启动、工作台和聊天装配在一起，先提取 shell/workspace 可复用旧代码。hash 路由适合已有静态入口，深链接刷新无需服务器 rewrite。仓库没有可比 PPA 序列，用户也不要求现在提供；Verilator PASS 和 mismatch 下降不能当作 PPA。

**Alternatives considered**：五个同层标签不再作为硬约束；暂不增加内容重复的总览页。独立 HTML 整页跳转会增加会话/草稿恢复负担，History API 路由需要额外静态 fallback 配置，当前选择 hash。不引入新路由/图表库、实验管理页或 PPA 执行服务，不使用示例数值假曲线。

**后续边界**：图形可以参考 [autoresearch](https://github.com/karpathy/autoresearch) 的候选点与历史最佳线。届时必须有同条件基线及两个真实候选、功能 PASS 和约束校验。记录测量范围、工具/库/约束指纹、单位、估计或物理阶段；功耗缺失保持空值。此处只保留接入要求，不选择本轮必须安装的 EDA 工具。

## 2. 当前 Codex 路径需要真正接入经验

**Decision**：复用已有 `RTLMemorySelector` 和 distiller，增加小型可信经验 adapter、不可变 revision、使用事件；向当前 Codex MCP 增加查询、读取和采用声明三个固定工具。浏览网页不调用这些工具。

**Rationale / 代码证据**：

- `zerorepo/rtl_impl/rtl_memory/store.py` 当前同 ID upsert 覆盖 Markdown，不能恢复旧经验内容。
- `repo_react/tools.py` 的补丁记录会调用 distiller，`repo_react/context.py` 会选取经验；当前 `codex_debug/{runner,session,mcp_server}.py` 没有对应工具和使用日志。不能将 ReAct 存档当作 Codex 已复用的证据。
- distiller 中 `verified_by` 有规则赋值；已有 E203 语法失败卡也带验证标签。导入必须查看客观原始结果，不能凭 header 判断已验证。
- `CodexDebugSession._accept_candidate` 的条件包括仿真完成，而不必是 PASS。提交、采用和验证成功必须分开。
- `SystemDebugRunner._run_codex_debug` 有内部运行 ID，网页还有外部运行 ID；需明确映射。

**Alternatives considered**：仅展示五条旧记忆不能证明闭环；不改写整个 ReAct、KG 或 Codex 执行架构；不将聊天历史改名为长期工程经验。

## 3. 运行时冻结经验，结果由可信路径记账

**Decision**：任务准备阶段只选审核公共库及本会话授权经验，形成只读快照并写入 job manifest。外部 run、内部 debug run、attempt、candidate 和 `memory_snapshot_sha256` 贯通 descriptor、工具桥、评估和恢复校验。采用声明与实际目标 diff 绑定后才显示采用；PASS/FAIL 来自实际验证。

**Rationale**：提供经验不代表执行者采纳，候选采纳也不代表通过，更不证明收益因果。旧运行恢复时如果读取最新经验，会破坏证据链。

**Alternatives considered**：不把全局记忆目录挂进每个沙箱；不接受模型传文件路径、其他 run ID、验证结果或公共发布指令；不通过放宽现有内存/存储/cgroup 门禁获得演示成功。

## 4. 一个故事读模型，复用现有证据

**Decision**：现有 SQLite `records` 只新增 `story` kind，一个不可变 `StoryBundle` 内嵌经验 revision、使用链和可选对照摘要；引用既有 run/version/validation/artifact。私有运行账本仍在可信经验 adapter 中，公共故事是审核后的投影。无新数据库、队列或管理 CRUD。

**Rationale**：现有 `Bundle` 不可变且 `extra=forbid`，不应原地添加故事；每个案例独立故事根便于空状态、稳定恢复和增量发布。

**Alternatives considered**：不用七张新表或通用实验平台；不用松散 JSON 拼接、不复制一套 RTL/波形模型。

## 5. 必须补齐历史证据解析和选择恢复

**Decision**：统一解析原 Bundle 与故事引用的额外归档运行；历史/实时取 `Run.origin`。Selection/Context 增加故事、经验 revision 和 use ID，预留 trial 引用；服务端、前端显式序列化、刷新恢复和聊天均校验归属。

**Rationale**：当前 `state.selectValidation()` 用主历史 run 是否相等来推断模式，会把其他归档运行误标实时；`main.ts` 仅在有 version ID 时恢复选择，无法恢复单独经验卡；代码、验证和静态导出目前主要覆盖原 Bundle 和单个 liveRun。

**Alternatives considered**：不把新增历史记录塞进 liveRun；不让经验自动借用屏幕上无关的 PASS 或波形。

## 6. seed 显式升级，部署仍用原五层

**Decision**：增加 `rtl-demo-seed-v2`，支持可选 `stories: {case_id: story_id}` 根和 `story` kind；保留严格 v1 reader 及其原摘要。仍只允许 `seed.json + files/`，从案例和故事根计算证据闭包；一次预检后事务导入。静态导出使用显式公共 DTO。

**Rationale**：现有 seed 验证器只认五种 record 和原案例根；直接塞文件会失败。现有通用 `public()` 删除路径键的方式不够审查新增经验正文，需要逐字段白名单与内容检查。

**Alternatives considered**：不偷偷扩展 v1、不依赖服务器原始工作区、不新增第六个部署包。runtime/design/seed/verifier/ops 五层保持，故事属于 seed；前端仅带公开投影。

## 7. 界面与真实闭环分开验收

**Decision**：本次分三项记录：UI 可用；经验链证据完整性；PPA 待接入。经验闭环准备至少两个独立真实运行、一次实际使用及有新证据支撑的 revision/retirement。无同条件启用/禁用对照时统一显示“收益待验证”。

**Rationale**：已有五条 E203 卡片未证明跨 run 复用，也未证明效率收益。单测 fixture 可以验证显示与约束，不能冒充真实演示素材。

**Alternatives considered**：不为本次强制安排收益对照实验，不展示成功率、学习速度或记忆数量增长曲线，不预设后续任务必定出现正收益或错误。

## 8. 服务器只承担增量展示与问答

**Decision**：沿用现有 TS/Vite、FastAPI、SQLite、独立 Web/Agent 环境和已批准的模型配置，无新 Web 依赖和公网端口。真实记忆链可在资源足够的受控环境准备，审核后上传。原生执行继续按现有准入判断。

**Rationale**：约 2GB 公网服务器已经有浏览和问答职责，拆分展示页面不需要新后台或常驻测量进程；安装 PPA 工具并不能解除完整生成/修复的资源限制。

**Alternatives considered**：不迁移整个仓库、不公开执行端口、不将记忆库或私有运行日志整体放入静态站。

## 研究结论

本次技术路线已明确；没有待用户决定的技术分歧。未来数据、真实复用样本和执行资源是实施与验收条件，不是假定已具备的结果。PPA 工具链、测量生产、候选优化和趋势图明确排除本次任务生成。
