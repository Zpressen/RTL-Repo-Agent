# Implementation Plan: RTL Agent 投资人演示工作台

**Branch**: `001-rtl-agent-demo`（Spec Kit 功能标识；实际 Git 分支仍为 `main`） | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: `specs/001-rtl-agent-demo/spec.md`，以及用户提供的 Deep Valley Chip 服务器 handoff。

## Summary

2026-10-16 用户扩展已适配：四个预置案例共用单页和三标签，增加顶部任务选择器。`cases.py` 固定注册规格、top、RealBench 验证器、参考目录和信号组；`import_catalog.py` 校验三例归档 SHA256。会话、对话、操作、RTL/报告/波形均按案例绑定；仍共用一个全局执行槽。通过 `prepare-cases` 一次导出四例静态包，部署完整 dist。SDC 使用精确时间分片，无波形降采样；报告明确 PASS 与可选采样统计分别解析。原始 E203 单案例计划保留为基线，范围变更以此补充和更新后的规格为准。真实三例复验与自动化记录见 validation.md。

交付一个 E203 单案例演示页：左侧持续对话，右侧“架构 / 代码 / 验证”三个标签；验证页内放真实波形、修复前后切换和测试采样标记。现有 RTL Agent 保持主流程，通过薄适配层接入生成、单独验证和修复。第一版不增加项目管理、账号注册、在线编辑器或通用 EDA 工具界面。

公网 `39.107.243.176` 上的 Caddy 继续服务主站和 www；仅调整 `design.deepvalleychip.cn` 站点。前端编译产物及经过筛选的历史演示包部署在原 design 静态目录。`/api/*` 保留完整路径代理到大内存计算机的私网后台；计算后台部署 API、单一执行 worker、现有 Agent 和完整外部验证依赖。用户已确认使用现有大内存服务器，私网地址稍后提供，由部署配置注入，不猜测或硬编码。

本地实现已完成主要代码与自动化验收；真实两轮模型问答、刷新恢复和从对话发起的独立 verify 已通过。生成/修复仍待指定后端profile与完整现场验收。已SSH核对公网Caddy并把完整静态包暂存到dev准备目录，未切换线上配置或部署计算机服务；大内存计算机的实际地址仍待补充。详见 [validation.md](validation.md)。

## Technical Context

**Language/Version**: 后端沿用已确认的 Python 3.13.11 环境；前端 TypeScript + HTML/CSS，构建机使用已确认的 Node.js 24.14.0。目标服务器复刻经过验证的运行环境，不能仅凭 Python 版本认定兼容。

**Primary Dependencies**: 新增 FastAPI、Uvicorn、Pydantic 2、vcdvcd；前端 Vite + TypeScript，无 UI 框架、在线编辑器或图布局服务。已锁定 FastAPI 0.143.2、Uvicorn 0.54.0、Pydantic 2.14.1、vcdvcd 2.6.0；前端实际版本见 package-lock.json。复用现有 LLMClient/Memory、PlannerRunner、SystemSimReviewer、SystemDebugRunner；不替换当前 Codex Debug backend 或 required KG 配置。

**Storage**: 计算机本地磁盘 SQLite，保存会话、消息、运行、操作、版本、验证、事件；API 与 worker 同机，WAL/短事务。原始产物、不可变 RTL 快照和 VCD 存文件系统。公共静态目录只放经过筛选的历史展示包；数据库、密钥、模型配置、golden 和 Codex 私有会话不进入静态目录。

**Testing**: pytest 覆盖导入溯源、统计口径、采样标记、操作去重及接口；前端使用 Vitest 检查状态和波形窗口边界，Playwright 覆盖三标签、对话、两次点击定位差异与刷新恢复。真实 E203 复验作为有依赖的集成验收，不在普通测试中自动调用收费模型。

**Target Platform**: Linux/systemd；已有 Caddy 作为公网入口。计算 API 默认私网端口 8000；28989 仅视为 handoff 中已有检查项，不假定端口空闲或其服务类型。

**Project Type**: 在现有 Python 仓库中增加一个静态前端和薄 Web 适配层；首版单机计算后台，API 与执行 worker 两个服务，不引入 Redis、Celery、容器编排或额外数据库服务。

**Performance Goals**: 首屏已有案例 ≤5 秒；执行请求接收或拒绝 ≤3 秒；真实阶段/终态产生后 ≤5 秒可见；历史回放 ≤3 分钟；完整生成和修复遵循原运行预算，不承诺短时完成。

**Constraints**: 单个活动 RTL 操作为全局上限，比规格的单会话限制更严格；问答保持可用。每个实时运行独立输出及临时目录；历史只读。所有 PASS 必须匹配 RTL 与独立系统验证；原始波形与测试采样判定分别展示。

**Scale/Scope**: 一个 E203 案例、一名演示者、一个页面、三个内容标签、固定关键波形组；聊天可问答并触发三类受控操作。域名通过 HTTPS 提供受访问保护的演示，不开放匿名任务执行。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

当前 `.specify/memory/constitution.md` 仍为未填写模板，没有已批准的项目原则；不能把示例注释当作强制规范，也不在本任务中修改 constitution。以用户明确要求和功能规格为本次检查依据。

| Gate | Phase 0 前 | Phase 1 后 |
| --- | --- | --- |
| 简单页面：一个案例、持续对话、三个内容标签 | PASS：范围明确 | PASS：不增加产品页面或配置中心 |
| 复用既有 Agent 与独立 verifier | PASS：入口存在 | PASS：三种操作分别接已有同步入口 |
| 真实证据及版本绑定 | PASS：发现历史证据陷阱并列为研究项 | PASS：固定候选快照、哈希、报告及采样计数交叉校验 |
| 服务器适配 | PASS：沿用用户 handoff | PASS：仅 design 的静态资源及代理变更；私网后台，无公网模型端口 |
| 实施边界 | PASS：仅计划 | PASS：未生成业务实现、未运行部署、未自动生成 tasks.md |

未发现需要例外批准的违反项。服务器 CPU/内存、实际私网路由、Caddy 版本和 root 执行条件是部署预检输入；设计不依赖未经验证的具体数值，预检未通过则只启用可用能力，不能冒充完整演示已上线。

## Project Structure

### Documentation (this feature)

```text
specs/001-rtl-agent-demo/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── deployment.md
├── quickstart.md
├── contracts/
│   ├── web-api.md
│   └── evidence.md
└── checklists/requirements.md
```

实施进度见 `tasks.md`，实测结果见 `validation.md`。

### Source Code (repository root)

以下目录已新增；原有 main.py 和 RTL Agent 算法未修改：

```text
web/rtl-demo/
├── package.json / package-lock.json
├── index.html / vite.config.ts
└── src/
    ├── main.ts / state.ts / api.ts / styles.css
    ├── chat.ts / architecture.ts / code.ts
    └── verification.ts / waveform.ts
zerorepo/rtl_web/
├── api.py / schemas.py / store.py / settings.py
├── chat.py / chat_runtime.py
├── worker.py / runtime.py
├── artifacts.py / import_case.py / waveform.py / cli.py
└── __init__.py
configs/rtl_demo.example.yaml
requirements-web.in / requirements-web.txt
scripts/rtl_demo/
├── preflight.sh
├── stage-release.sh
└── install-as-root.sh
deploy/rtl_demo/
├── Caddyfile.design.example
├── rtl-demo-api.service
├── rtl-demo-worker.service
└── environment.example
tests/rtl_web/
```

**Structure Decision**: 前端与现有 Python 核心分目录；Web 模块只负责证据、对话、调度和接口。原有 `main.py` CLI 和 `zerorepo/rtl_impl` 保持兼容。若需要解析 verifier 位置的配置注入或子模块进度钩子，只做向后兼容的可选参数/通知，不复制整个规划流程。Web API 不通过导入 `main.py` 启动 RTL，也不把 RepoReAct 的自动修复循环当用户聊天。

## Repository Adaptation

| 能力 | 已有代码或产物 | 适配措施 |
| --- | --- | --- |
| 六阶段生成与系统 Debug | `main.py` 的 rtl_planner、`module_planner/planner_runner.py:PlannerRunner.run` | 在独立运行子进程构造相同配置与 task；以 run_id 隔离 output/checkpoint/workspace |
| 只重新验证 | `debug_agent/system_debug_runner.py:SystemSimReviewer.review` | 对所选快照的副本调用；新的 output_dir，禁止意外进入自动修复 |
| 修复失败版本 | `SystemDebugRunner.run_system` | 从所选快照创建实时运行副本，提供真实规格、契约、merge records 和 KG；保留修改前快照 |
| 阶段与模块进度 | `PlanningArtifactSink.record_stage_output`、模块产物与 validation journal | 实现输出通知，增量观察实际文件/journal；只发布确有证据的阶段事件 |
| 多轮对话 | `zerorepo/rpg_gen/base/llm_client` 的 LLMClient/Memory | 每次模型调用在 runtime 解释器的受限子进程中执行；普通问答返回整条回答，首版不做 token 流 |
| 波形 | VCD + `debug_agent/trace_report.py` 信号解析 | 新增完整 transition 窗口与 packed stats 解码；不直接使用会下采样的 probe 返回值画完整波形 |
| 受信验证环境 | 外部 RealBench verifier 与配套 SYSTEM_TEST_DIR | 配置 root 与固定 registry；不依赖本机 `/home/mokita` 绝对路径，不向浏览器公开 golden |

固定案例注册项必须区分：`case_id=e203`、规格/验证目录名 `e203_exu_alu_hard`、planner/runtime top `e203_exu_alu_system`、testbench DUT module `e203_exu_alu`。使用现有仅 staging 的模块别名兼容，不修改原始规格、测试规则或 golden。

`stage6.status=completed`、CLI 退出码 0、旧 `system_debug_latest.json` 均不能直接产生本次 PASS。适配层必须核验本次运行的最终系统报告和输入/输出快照。首次接入使用当前 `rtl_debug.backend=codex` 和 required KG；hand-off 中“未来接 Claude”不构成已有 Claude 后端证据。

## Runtime and Conversation Design

- API 单 Uvicorn 进程，仅做短请求、数据库登记和 SSE；独立单 worker 领取已接受的 RTL 操作，再以 argv 数组启动 runtime 子进程，HTTP 请求不等待编译和模型循环。
- 接收操作在同一事务内落实幂等键、目标快照和全局运行槽。相同键返回同一操作；另一个操作返回 busy；不增加排队界面。
- 生成在新运行目录；verify 对选中快照的工作副本执行；fix 从失败版本派生新运行，候选按现有 accept/rollback 规则保存。所有模式默认不重用原始演示工作目录。
- worker 锁与数据库同时控制唯一执行者。API 重启不杀 worker；worker/systemd 重启清理整组运行子进程并标 interrupted，不自动重新执行。已经登记但尚未开始的 accepted 操作允许 worker 首次领取。
- 问答不占用 RTL 运行槽。每会话同一时间一个模型回答，收到后先持久化消息和 replying 状态，再在独立、限时的 runtime 子进程调用既有 LLMClient。API 重启时未完成回答标 interrupted，用户可重试；不能自动产生写入操作。
- 对话动作只允许 `generate_and_verify | verify | fix | open_artifact | clarify | answer`。模型返回结构化意图与证据 ID，服务端重新验证目标、状态与范围；不接受模型或浏览器提供的 shell 命令、路径和运行配置。
- 每条消息固定当时的案例/运行/版本上下文。SSE 发布持久事件 ID，重连补发；前端另以 GET 获取快照作校准。切换历史仅改变浏览选择，正在执行的目标保持不变。
- 历史回放的模型问答仍是实时回答，但引用来源标为历史；页面操作卡与证据必须标明各自来源，不把问答时间误当历史执行时间。

## Evidence and Waveform Design

首个导入包选择 trial 5 与 trial 9 的候选快照，而非根工作目录。每组同时导入该候选的 `merged/`、`artifacts/debug_sim_output.json`、`artifacts/wave.vcd`，检查 journal 的 `sim_completed=true`。成功候选还关联最终独立复验及其 RTL 清单。

差异计数以唯一 `Total mismatched samples is X out of Y samples` 总行为采样统计，内部 mismatch_count 单独保留。trial 5 为 1/222，trial 9 为 0/222；不能把内部重复累加的 2 当作 2 个失败采样。

重要实际行为：成功 VCD 在 1125ps 附近仍可显示瞬态 DUT/Reference 不同，原始组合 `tb_match` 不是最终采样 verdict。首版保持原始波形，额外从匹配 testbench 的 `tb.stats1` packed counters 解码采样 marker，再与同次报告核对。失败组出现 1125ps 的 1 个失败采样，成功组 222 个采样均通过。游标值标为波形显示值，不伪造 active 区采样数据。界面仅保留短说明“结果按测试平台采样判定”，实现细节留在报告中。

只提供固定关键组和线性模块层次图；不用通用信号搜索、完整因果图或复杂时间轴。波形窗口返回起点值及所有变化，保留 x/z、位宽和时间单位；超过上限显式分段，不能静默下采样漏掉差异。

## Delivery Sequence

1. **证据与适配地基**：固定 E203 registry，导入可信 before/after 证据，完成哈希、采样统计和波形测试。
2. **简单展示页**：一个页面与三个标签，接静态历史包、回放、代码和波形比较。
3. **对话及实时执行**：接持久会话、SSE、三类操作、现有模型与 Debug；演示环境做真实复验。
4. **服务器发布验收**：准备完整前端静态目录和后端服务，验证 Caddy 路由、访问保护、私网连通及回滚；上线后复核主站和 www。

各阶段均属于首版交付，阶段 2 可先评审页面效果，不代表省略后续实时能力。

## Validation Strategy

FR-001～004/020 用页面与历史回放验收；FR-005～009 用持续对话、结构化动作、幂等及忙状态测试；FR-010～014/019 用隔离运行、独立验证与快照绑定测试；FR-015～017 用真实候选 VCD 和 stats1 解码测试；FR-018 用刷新、断连、模型不可用与超时场景验收；FR-021/SC-009 对应部署入口、私网后台与原站点保留验收。具体操作见 [quickstart.md](quickstart.md)。

上线门槛包括：真实 verify 成功、至少一次可审查的修复验证过程、三类操作确实调用既有流程、历史与实时不串数据、错误包导入被拒绝、只有私网地址监听后台、未认证请求无法执行任务。无需为纯排版编写镜像式单元测试。

## Complexity Tracking

无 constitution 例外。新增 SQLite 和单 worker 用于运行恢复及隔离长任务；不增加分布式队列。受保护的域名访问由 Caddy 完成，不新增账号产品流程。
