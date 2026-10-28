# Implementation Plan: RTL Studio 参考页面改版

**Branch**: `main`（实际 Git 分支；Spec Kit 逻辑功能标识 `004-redesign-rtl-studio`） | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: `specs/004-redesign-rtl-studio/spec.md`。最新约束：移除 RI / RSI 入口，尽量遵循 `web/RTL Studio 演示-html/Demo.dc.html` 的排版，保留可持续交互的对话和真实工程证据。

## Summary

在现有 TypeScript/Vite 工作台与 Python/FastAPI bridge 上改版，不重写 RTL Agent。把白底工作台改为参考稿的深色三栏：顶部任务栏与细进度条；左侧八步；中间五页签；右侧指标、动态和固定输入区。现有四案例继续使用，各阶段状态从真实事件与证据投影，缺失项明确说明。

主要新增：八步数据适配、独立规格/修复视图、五页签与旧链接兼容、可公开证据 ZIP 及静态下载。复用波形、版本绑定、会话隔离、问答和三种执行操作。RI/RSI 从页面导航与渲染链移除，旧地址进入工作台，后台记忆功能不删除。

## Technical Context

**Language/Version**: TypeScript 5.9.3，Node.js 24.14.0；当前本地 web Python 3.13.11。沿用现有锁文件及生产 Python 版本要求，不在此次升级运行时。

**Primary Dependencies**: Vite 7.3.7、原生 DOM/SVG；现有 FastAPI/Uvicorn/Pydantic/PyYAML/vcdvcd。ZIP 使用 Python 标准库 zipfile，不增加 UI 库、浏览器 ZIP 库或 Agent 依赖。

**Storage**: 现有 SQLite JSON records、sessions/messages/operations/events；不可变快照与 artifact 文件；静态 public/cases。仅添加可选选择字段和派生下载索引，无数据库表迁移、无历史 bundle 原地重写。

**Testing**: Vitest 3.2.7、Playwright 1.64.1（当前锁定版本）、pytest/httpx TestClient；归档数据与便携 fixture，模型和执行结果可控替身。

**Target Platform**: 现有 Linux/Caddy/FastAPI 部署及桌面浏览器；1440×900、1280×800 为主要展示尺寸，390×844 验证窄屏可操作。未来发布域名仍为 agent.deepvalleychip.cn。

**Project Type**: 已有 web 应用改版，含受控公开下载接口和静态降级。

**Performance Goals**: E203 90 秒演示路径；回放按现有 delay 压缩；沿用波形每窗口最多 20,000 transitions，SDC 分片按需加载；不在前端下载全部原始 VCD。三栏中输入区持续可见。

**Constraints**: 无模型调用、无真实修复验收、无部署动作；不公开原始私有 VCD/seed/config；不修改参考设计或真实 RTL；下载默认输入上限 64MiB、条目上限 128、在线生成并发 1；不新增登录流程。

**Scale/Scope**: 4 案例、8 主步骤、5 页签、1 持续对话区；E203 9 规划模块/10 文件/9 候选，3 条详细验证；AES/SDC 各 1 条最终记录。PPA、RSI、任意规格上传、在线编辑、人工审批接管不在本次范围。

## Constitution Check

*GATE: Phase 0 前核对，Phase 1 后复核。*

constitution.md 当前是未填充模板，不把示例中的测试审批等当作已生效规则。以下为从用户和规格继承的项目检查项：

| 检查项 | Phase 0 前 | Phase 1 后 | 依据 |
| --- | --- | --- | --- |
| 参考稿优先、移除 RI/RSI、控制范围 | PASS | PASS | 三栏八步五页签；只增加必要对话和下载 |
| 结论、版本、报告、波形绑定 | PASS | PASS | 共享 selection/验证器与 ZIP 清单逐层校验 |
| 历史回放不冒充实时执行 | PASS | PASS | 播放位置与执行状态分开建模 |
| 会话隔离与材料公开界限 | PASS | PASS | 沿用 cookie/owner；下载限定公开历史闭包 |
| 沿用既有后端和部署 | PASS | PASS | 无框架替换、表迁移、域名或 Caddy 变更 |
| 暂缓真实模型/修复 | PASS | PASS | fixture 验收，不运行付费调用或真实修复 |

无未解释冲突，无阻塞项。尚未实现，不将设计检查通过写成业务验收通过。

## Project Structure

### Documentation (this feature)

```text
specs/004-redesign-rtl-studio/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── workspace.md
│   └── evidence-package.md
└── checklists/requirements.md
```

`tasks.md` 由后续 speckit-tasks 生成，本轮不创建。

### Source Code (repository root)

```text
web/RTL Studio 演示-html/         # 只读视觉参考，不进入正式应用运行时
web/rtl-demo/
├── src/
│   ├── workspace.ts             # 改为三栏装配；去除主导航/故事视图
│   ├── styles.css               # 深色 tokens、三栏与局部滚动
│   ├── studio-model.ts          # 新：八步/指标/来源适配
│   ├── timeline.ts              # 新：八步、候选记录及回放控制
│   ├── spec.ts                  # 新：原文、摘要、来源约束
│   ├── repair.ts                # 新：失败/变更文件/候选与最终复验
│   ├── evidence-selection.ts    # 新：共享版本/报告/比较选择校验
│   ├── evidence-download.ts     # 新：静态优先、API 下载与错误反馈
│   ├── architecture.ts          # 重排真实架构与职责
│   ├── code.ts                  # 全量文件列表、版本与对比片段
│   ├── verification.ts          # 复用报告与波形，抽取共享选择
│   ├── waveform.ts              # 保留 SVG/BigInt 与比较规则
│   ├── chat.ts                  # 单实例、固定 composer、引用上下文
│   ├── router.ts / state.ts     # 五页签、旧路由兼容、独立 UI 状态
│   ├── api.ts                   # panel 上下文、受控 SSE、下载索引
│   └── *.test.ts
├── tests/e2e/                   # 新布局、兼容、下载及交互回归
└── public/cases/                # 原公开材料 + 派生 evidence ZIP/索引
zerorepo/rtl_web/
├── schemas.py                  # Context/Selection 可选 panel 与五枚举
├── api.py                      # 公开证据下载 GET；其余接口复用
├── chat.py / chat_runtime.py    # workspace 证据不依赖故事；提示按五页签聚焦
├── evidence.py                 # 新：闭包/校验/清单/有界 ZIP
├── import_case.py              # export_static 增加预生成 ZIP/索引
└── artifacts.py / store.py     # 复用 hash/path/owner；不放宽权限
scripts/rtl_demo/
├── release.py                  # 窄范围 ZIP 白名单与内部检查
└── deployment.py               # 同步 design 包检查
tests/rtl_web/                 # selection/下载/静态/部署回归
```

**Structure Decision**: 在现有前后端中增加小型展示适配及证据导出模块；参考稿的 vendor 和 support.js 不复制进生产包。前端不再导入 shell/optimization/experience 渲染及自动故事加载；未使用旧页面文件和测试按实际引用清理，后端记忆模块与旧消息保持兼容。

## Phase 0 — Research Completed

见 [research.md](research.md) R1–R9。已确认：后端 workspace_panel 需扩展；SSE 目前丢弃正文；E203 定义文件已在公开 artifact 内；原始 VCD 私有；静态部署拒绝 ZIP；全部问题均已有明确决策。无需新增外部服务或询问服务器凭据。

## Phase 1 — Design

### 页面布局与交互

设计 tokens 取自参考：底色 #0B1014、卡片 #10181D、边框 #22313A、正文 #E8EEF1、次级 #9DAEB6、主强调 #4FD1A5；成功/失败/等待沿用绿/红/黄语义。顶部允许换行容纳案例选择，不出现旧 hero、主导航或 RI/RSI 区域。字体使用系统中文回退与等宽回退，避免新增字体外网依赖。

桌面主体占剩余视口高度，左右栏与中心局部滚动；中心 min-width:0。右栏保留参考三张小指标卡，动态默认只露最近少量事件，可展开；消息占剩余空间，输入区不收缩。窄屏折叠时间线并提供对话打开/收起控制，保持草稿与节点实例，不遮住核心操作。

新默认打开 E203 历史最终验证，视图为 verify；不是自动播放。点击任一步骤停回放并切页签；原事件 sequence 驱动回放，八步是分组而非凭空追加的事件。完整规则见 [workspace contract](contracts/workspace.md)。

### 数据与选择

`studio-model.ts` 投影当前 bundle/run，不改源材料。缺失语法或定位事件时提供依据报告整理/未单独记录说明；从报告派生的卡片带 source ref。统计仅依据当前数据。共享选择逻辑校验 case→run→version→validation→waveform；修复与仿真视图共享它。

五 panel 名统一，Context.workspace_panel 可选，Selection 默认保留 architecture 以兼容旧客户端，新 UI 显式传 verify 默认。旧存储值和 legacy hash 在单处归一，URL 与 Selection 不再各自映射 verification。新消息带 view=workspace，旧消息不改写。当前 story/memory 参数不再影响工作台加载；公开有效证据仍核对归属。

后端 chat.py 在 workspace 请求中只组织工程证据，不再无条件加载 story_view；显式旧经验上下文单独保持兼容。chat_runtime.py 的提示按 workspace_panel 聚焦五页签，去除当前页面为 RSI 的硬编码，保留证据不足、历史/实时、采样规则与执行意图边界。该项只以受控 provider 验证资料和上下文，不发真实模型请求。

案例切换保持整页导航，复用每案例 cookie/localStorage/sessionStorage。波形比较按实际 timescale 换算和取交集；选中验证变化清除不属于目标的模块/信号。完整模型见 [data-model.md](data-model.md)。

### 证据 ZIP

新增受控 GET 导出与静态预生成，统一后端 builder。只从公开历史 bundle 的受控闭包选择最多两条详细验证；不从任意路径或私有 owner 记录生成公开包。原始私有 VCD 不导出，关键 waveform JSON 和全部 tiles 标为派生波形，清单注明范围与 raw_vcd_not_public。在线用临时文件与分块发送，静态用内容寻址 URL。完整接口、hash 和错误见 [evidence-package contract](contracts/evidence-package.md)。

静态 manifest 仅增加 evidence_packages 派生索引，source_fingerprint 与不可变记录不变。api.ts 合并索引前核对 bundle_id/source_fingerprint；单次与对比必须精确匹配 ID，不能退回其他包。发布检查仅允许指定 cases 路径的经校验 ZIP，不泛开二进制后缀。

## Implementation Sequence (供后续任务拆分)

1. **建立适配和兼容层**：八步模型、共享证据选择、Panel/Context/Selection、旧路由归一；用四案例基线验证，不改变页面数据结论。
2. **搭建参考稿外壳**：深色 tokens、顶部、进度条、左时间线、中心五页签、右侧固定输入；移除 RI/RSI 渲染与主导航，保持单一 chat 实例。
3. **接入五页签证据**：规格与来源、架构职责、全量文件、验证波形及修复页；复用报告/窗口读取，列明缺失证据。
4. **完成交互联动**：回放暂停/继续/重头、选择恢复、受控 SSE 动态、引用发送时上下文、单独 capability 与离线草稿；同步后端工程证据选择与五页签提示，移除 workspace 对故事数据的依赖。
5. **完成下载闭环**：ZIP builder/GET/静态预生成/索引/窄白名单，覆盖 defines、SDC tiles、绑定和脱敏，前端下载精确选择。
6. **验收与后续发布准备**：更新旧 UI 测试、三尺寸截图、四案例及离线/访客隔离；构建与打包校验通过后形成新 release。实际上线由后续明确部署任务执行。

步骤 1 是布局和证据联动前置；下载 builder 可在选择契约稳定后与页面工作独立推进；所有验收以完整 spec 为准，不以外壳完成代替下载/隔离完成。

## Validation Strategy

- 单元：事件映射不补造状态、panel/旧地址归一、选择绑定、timescale/缺失信号、case-scoped 草稿/引用；不为简单样式写镜像测试。
- 后端：五枚举选择兼容、公开 ZIP 闭包/hash、完整 RTL/defines、SDC 全部 tiles、私有原始 VCD/seed 不导出、跨案例/访客拒绝、预算与清理、静态与 API 语义一致、ZIP 发布白名单。
- 浏览器：1440×900、1280×800、390×844；五种内容状态对照参考，八步操作、回放不执行、trial5→final、四案例、草稿/IME/三轮回复、断线/延迟、旧链接/前后退、静态/API 下载和两访客隔离。
- 外部模型/真实修复不运行。所有 UI 操作请求由测试拦截或禁止；保留现有波形与访问边界测试。具体命令见 [quickstart.md](quickstart.md)。

## Deployment Adaptation (后续发布)

交付分为 dist（含四案例公开材料和受限 ZIP）、runtime 中新增/更新的 rtl_web 代码，以及 release/deployment 检查脚本。沿用既有依赖锁文件、私有配置、运行数据和 Caddy 同源反向代理，不新增公网模型端口。无新增第三方包时复用现有虚拟环境。

不上传设计参考目录及 vendor、specs、tests、.agents、.specify、node_modules、.git、实际环境文件、SSH 文件、codex_private、数据库或原始私有 VCD。Agent 原有 prompt/grammar 等运行资产按现有包清单保留，不因“少传文档”删除必需资产。

这次针对已运行服务采用代码/静态材料的增量候选，不重走全量安装或重新传输 private seed；已有私有 seed、运行输入和 data 目录留在服务器原位。全量部署打包器用于检查 design 白名单的改动，不意味着此次要重新发送其所有私有层。

前后端与静态材料同 release 预检；验收仅浏览/fixture，不发送真实模型请求。切换代码入口前备份当前 release 指向，data_root/session.key/数据库和私有 environment 不覆盖；回滚时恢复旧入口，新增可选 JSON 字段可被旧客户端忽略。外部域名仍为 agent，主站/www/design 保持原状。

## Complexity Tracking

无 Constitution Check 违规，无新增框架、数据库、模型服务、任务队列或数据库迁移。唯一新增外部接口是公开证据 GET，必要的配套为静态 ZIP、索引及发布校验；其余为现有能力重排。

## Phase 1 Completion

已生成 research、data-model、两份 contracts 和 quickstart；设计后检查全部 PASS。前置/后置扩展文件均不存在，按技能规则跳过钩子。未创建 tasks.md，未实现、部署或调用模型。

## Agent Trace 补充适配（2026-10-20）

以 `agent_trace.py` 在静态导出阶段从原始 debug journal 提取正向字段；保留不可变归档与证据 ZIP 的原绑定。公开补充包含 journal SHA-256 和案例/归档/run/来源指纹，前端同源匹配后使用。右栏采用独立可滚动八步卡片及嵌套候选记录，持续保留输入区；实时 SSE 事件仅按当前 run_id 投影，不借用历史 journal。新增代码随本地 r4-trace 增量候选交付，不隐含公网部署。

## 当前阶段 Trace 修正（2026-10-21）

保留完整 traceModel 作为内部来源模型；通过 selectedTrace 仅投影所选阶段为右栏单个内容卡片，不再渲染所有阶段列表。stepForPanel 对齐中央页签与左侧选择；语法/RTL、定位/修复和仿真/复验按明确步骤区分。仅显示本阶段实时事件；左侧报告推导阶段同步对应候选回放位置，避免已选复验显示尚未到达。

## 可点击卡片与统一对话窗口（2026-10-21）

右侧仅渲染当前阶段的摘要按钮与候选摘要按钮，详情按需创建原生modal dialog，内容使用一层滚动；旁栏只保留自身滚动，不再让trace列表、内嵌工具日志等分别滚动。全局深色细滚动条适配系统主题。统一非模态chat dialog持有原有唯一chat实例，默认隐藏、顶部按钮打开、支持关闭与Escape；reveal确保重新打开后可见最新历史。既有后端和权限不变。

## 完整历史修复过程适配（2026-10-21）

以configs/rtl_demo_e203.history.json审核来源快照、journal、报告和VCD的SHA-256；recorded_history.py导入不可变版本/验证并生成chronology-v2补充归档，原始bundle保持不变。每次候选绑定真实基线、版本、验证、决策和波形，并校验原始报告与VCD采样计数。语法失败不发布继承波形；公开数据仅投影允许字段和脱敏日志。

前端historyJourney纯展示层串联39次候选及连续事件，不改run/version/validation来源身份；阶段与右侧卡片联动，history-repair在中央展示真实基线Diff和相应前后波形。仿真默认原始initial_system，最终复验选择最终final_system。API新会话使用同一初始记录；静态/在线合并同时核对归档指纹与历史投影指纹。

证据ZIP按所选验证及实际基线生成；私有seed闭包包含新增归档和必要VCD，排除模型配置、访客会话和状态库。增量候选要求服务器现有审查基础runtime，先dry-run再合并种子；前后端同批切换，保留既有数据库、会话密钥与模型配置。此轮仅本地准备，不执行上线、模型问答或新仿真。

## AES ReAct 历史接入（2026-10-21）

新增recorded_react_history.py，按configs/rtl_demo_aes_cipher.history.json固定journal、工具轨迹、部分RTL快照、初始报告、最终RTL/报告/VCD的SHA-256。从最终完整树逆序撤销已保留修改，再按日志顺序重放；逐字节核对每个before/after，未改动S-box与原始生成草稿一致，避免用部分目录冒充完整受测版本。不启动Agent或仿真器。

复用chronology补充归档、historyJourney与候选卡片协议，保持原目录/原bundle不可变。报告没有总采样数时保留null，新增signal_mismatches、probe_samples、探针来源指纹和缺失说明；公开的工具摘要仅选取允许字段并脱敏。探针绑定最近产生VCD的候选，回退代码不意味着回退VCD；后续top_sim run_check后才切回实际基线。最后一次通过结果复用同一保存报告/VCD，注明没有另一独立复验。

中央verification支持各输出差异与分页离散探针，不做波形插值；history-repair展示真实基线Diff及修改前后各自证据。证据ZIP清单保留离散探针和缺失信息，私有seed包含新的记录闭包。新增运行时文件和审核清单随r8增量候选准备；没有额外依赖或凭据变更，未执行公网部署。

## AES 解密接入与未验证修改（2026-10-21）

recorded_react_history.py按case_id选择AES加密/解密审核清单；新增rtl_demo_aes_inverse.history.json固定4次前后快照、journal、trace、报告、VCD和4个未改动模块来源。完整树重建保持原来的逐字节检查；初始统计与首条patch的before_metrics核对，不以首条修改后的结果代替初始。

新增edit_only验证种类与lint_pass=null，保留代码但不添加假仿真结论、失败时刻、计数或探针；对应事件属于repair，非syntax。前端将计数标题改为代码修改，区分未独立检查、语法失败和完成仿真，中央保留真实修改前基线与当前候选独立状态。离散探针默认优先展示已有记录的失败输出，绝不插值。复用现有ZIP与seed闭包，前后端及新增私有记录随r9本地候选准备，无新依赖、模型调用或公网发布。

## SDC Codex 历史适配（2026-10-22）

复用recorded_history.py导入17次系统级候选；configs/rtl_demo_sdc.history.json固定来源run_record、绑定、journal、初始/候选/最终RTL与报告、候选/最终VCD的SHA-256。核对规格、测试平台、最终树与原案例归档，原bundle保持不变。回退后基线只由真实accept更新。

publish_validation增加仅供已审核历史使用的recorded_signal_report入口：固定系统FAIL摘要及输出差异提示可确认仿真已完成，普通parse_report仍保守。verify_signal_counters把VCD每个非零输出末计数与报告逐项比较，并核对errortime；通过记录要求错误计数清零。原报告总采样统计仍保留null。SDC专用信号列表由审核配置选择，原案例定义与旧归档不改写；窗口、分片和采样标记继续使用真实VCD。ZIP清单保留计数核对状态。

完整私有历史种子实际705,850,107字节，超过原512MiB预算。仅将管理员导入的私有seed总上限调整为1GiB，并在写出及读入早期拒绝超额；公开ZIP64MiB和单个VCD256MiB限制保持。相关防超额测试通过。前后端、审核配置与种子随r10本地增量候选准备，不上传私有VCD到静态目录，不更改凭据、Caddy或公网。

## 公网部署执行（2026-10-22）

审核现有evolution-20261019-r1 runtime：本地所有既有Web文件差异均已包含于增量。SSH沿用已验证主机指纹；58,906,393字节压缩包固定SHA-256传入dev私有更新目录。复用旧环境与完整Agent基础代码，叠加r10 Web适配与全量design，保留旧哈希JS/CSS供已有浏览器使用。625条种子记录与服务器97条同ID记录无冲突，新增528条；先在私有SQLite副本导入并校验4案例，再在维护窗口合并生产数据，不替换数据库或session.key。

原子切换private/config.yaml的repo_root/release_id及launch指向，重启仅Agent网关/worker。自动恢复期间旧worker曾抢先持锁，已再次重启到新发布并确认worker_release=true；刷新新版本离线预检缓存后四案例chat.available=true，无真实模型请求。保留独立prepared/activation/post-activation记录及旧release/配置回滚文件。TLS校验开启的真实浏览器直接访问公网域名验收，通过四案例、版本绑定、波形、下载、私有文件边界及访客隔离。

## 根因定位数据与视图修正（2026-10-22）

新增prepare_root_causes.py从固定SHA的Codex公开agent_message、journal reason及ReAct patch hypothesis构建白名单注释；不发布reasoning条目、原始轨迹、任意工具字典或私有路径。中文摘要与来源、源行号分别保留。新root_causes.py以case/source/history指纹、run/candidate/revision、验证ID、修改前RTL树哈希校验注释，任一绑定失配时不附加；按只读投影合并到expanded_bundle和静态manifest，不重写不可变run、validation或RTL，不做数据库迁移。

前端history-diagnosis.ts独立于history-repair.ts，右侧在定位阶段展示判断而不是候选验证结果；包括最终通过候选与未单独验证的AES修改，未记录项明确说明。代码仅加载基线版本，并区分原始定位范围/候选变更关联。原始来源、修改前验证按需展开；切到自动修复才显示Diff和前后波形。下载、顶部状态及选择说明指向定位关联的修改前验证。

部署r11时复用旧依赖，以硬链接准备独立release、用原子替换叠加22个审核文件，保留旧release。只有已整理注释、Web bridge和前端增量上传，不重传seed或原始调试记录；在状态库副本核对四案例静态/API指纹后切换网关与worker。保护Caddy、其他站点、密钥及会话，保留指针和配置回退材料。

## 对话分析恢复（2026-10-26）

chat_analysis.py提供确切快捷问题的只读证据解读：使用expanded_bundle、发送时validation/RTL、真实报告计数及绑定的根因/修复记录，不触发模型或执行。Message增加可选answer_source/finished_at；新旧记录兼容。自由问题继续走模型，默认chat_execution_enabled=false时服务端拦截执行决策。prepare_chat_job只传递chat_max_tokens/chat_thinking/chat_execution_enabled白名单，对话专用参数不改变原Agent配置；OpenAI兼容客户端仅转发显式extra_body。

前端分析按钮可直接提交；执行按钮保留并立即说明限制，不依赖执行预检或创建消息。回应只依赖chat能力，三个快捷入口在模型不可用时也可读档。等待时每2秒刷新当前会话，并可手动刷新；SSE并发更新合并后补一次刷新，避免message.updated在已有刷新未结束时丢失。根因页发送问题时绑定修改前验证和RTL，不将本次候选当作旧代码分析。

r12以10文件增量继承r11，隔离状态副本加不可变artifact硬链接验收后切换；生产runtime仅修改聊天专用配置，模型密钥/Agent配置、访客会话和归档不变。普通问答一次真实验收限于已有DeepSeek端点与当前E203公开证据；不启动生成、修复或新仿真。

## 纠正快捷摘要方案：统一真实模型对话（2026-10-26）

删除chat_analysis中的固定分析生成器，只保留两项不支持请求的提示。respond将其余所有问题统一交给model_decision；旧“分析并修复”文本只改写为只读分析问题，仍调用模型。evidence提供当前规格/规划/所选RTL/验证，以及严格绑定的候选基线、诊断和最终归档上下文；live运行不借用历史架构/根因。原有问答超时、事件刷新补偿和执行拦截保持。

chat_runtime在LLMClient.generate完成后从SDK last_usage记录模型、Token数与耗时，经独立受控输出字段返回API；模型JSON先按ChatDecision校验，不能声明内部回执。API私有属性传递回执并保存到消息，前端标注模型名；旧recorded_evidence只标为历史归档摘要。三个分析按钮也受chat就绪状态约束，模型故障明确报错而不伪造成功。

r13作为8文件增量继承r12，保留原模型配置和短回答预算。服务器隔离副本使用provider替身验证四案例全部分析路径后切换；真实公网用七次模型请求验证E203三个按钮及连续追问，其他三案例各一次验证解释，逐条检查非零SDK输入/输出Token及模型来源。
