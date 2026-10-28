# Research: 仓库适配与服务器部署

日期：2026-10-15。使用当前代码、真实 E203 产物和官方文档进行只读研究。没有执行模型调用、仿真或远程部署。用户已确认后台运行于现有大内存服务器，私网信息稍后补充。

## 1. 简洁页面与前端技术

**Decision**: Vite + TypeScript + 原生 DOM/CSS，三个标签和一个固定对话区；模块层次用简单树，固定信号波形用 SVG。代码只读并以文本展示，第一版不引入编辑器、通用图谱组件、前端路由或 SSR。

**Rationale**: 仅一个案例，布局和状态规模有限；静态构建可直接接入已有 Caddy 服务目录，服务器不需要 Node 常驻。Vite 的 `dist` 是完整发布单元，不能只发布 index.html。[Vite 静态部署说明](https://vite.dev/guide/static-deploy.html)

**Alternatives considered**: React/Vue 可用于后续复杂界面；当前原生组件已够用。全静态假对话无法满足实时操作；直接做完整 IDE 增加产品范围。

## 2. 三类操作需要不同适配入口

**Decision**: 新建 `zerorepo/rtl_web/runtime.py`，用同一配置构造逻辑分别调用生成、verify-only 和 fix，不通过已有 CLI 猜参数。

**Rationale**: `main.py:291-430` 的 rtl_planner 调用 `PlannerRunner.run(..., end_stage="stage6")`，生成后自动进入系统 Debug。`SystemSimReviewer.review` 可独立复验；`SystemDebugRunner.run_system` 能处理失败并修复，修改应只发生在副本中。`PlannerRunner` 最后可能在 Debug 异常后仍完成 merge，且能读取旧 latest；merge 完成或进程正常退出不能代替系统 PASS。

**Alternatives considered**: 扩充 CLI 两个 mode 需要改主入口且仍要做状态适配；每次都启动完整 CLI 会让“重新验证”意外触发生成或修复。

具体复用点：

- `zerorepo/rtl_impl/module_planner/interfaces.py:PlanningArtifactSink.record_stage_output`：阶段产物通知。
- `zerorepo/rtl_impl/debug_agent/system_debug_runner.py:SystemSimReviewer`：新的 verify output_dir。
- 同文件 `SystemDebugRunner`：复制后的 workspace 及正确 task、contract、merge records。
- `zerorepo/rpg_gen/base/llm_client`：问答使用 LLMConfig、LLMClient、Memory；普通问答与自动修复状态分离。
- `codex_debug/history.py`：保留现有规格/验证器/accepted manifest 的绑定与恢复规则。

## 3. 进程与状态

**Decision**: 一个轻量 API 服务、一个 SQLite 单任务 worker 服务、独立 runtime 子进程；问答使用单独的短期子进程，不与 RTL 工作抢同一运行槽。API/worker 共享同机本地 SQLite。

**Rationale**: 模型和编译耗时长，不能占用请求或依赖 API 内存保住任务。FastAPI 官方区分短后台工作与重计算；本项目规模用单 worker 足够，不需要分布式队列。[FastAPI 后台任务说明](https://fastapi.tiangolo.com/tutorial/background-tasks/)

SQLite WAL 的读写并发适合小规模会话和事件，但要求相关进程在同一主机，不能把 DB 放公网机或网络共享盘。[SQLite WAL 约束](https://www.sqlite.org/wal.html)

**Alternatives considered**: 纯内存丢失刷新/重启状态；直接把重任务放 API BackgroundTasks 无独立运行恢复；Redis/Celery 超出单案例所需。

**Process rules**: 事务落实幂等和运行槽；worker 持有文件锁。argv 数组启动进程，不拼接用户 shell。超时终止进程组，systemd 服务停止时清理整个 cgroup；worker 重启将未确认的运行标 interrupted，不自动重放。现有 `run_bash_command` 有 shell 子进程边界，需要外层进程组保护，不将其当整体取消控制。

## 4. 对话与实时更新

**Decision**: 普通问答完整返回一条答案；操作发起为固定结构化意图，API 校验后登记。统一 SSE 推送已持久化消息、阶段、操作和产物事件，GET 快照用于恢复。

**Rationale**: 客户端命令通过 POST，服务端进度单向推送即可；原生 EventSource 支持事件 ID 和重连。[MDN SSE 说明](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)

**Alternatives considered**: WebSocket 双向协议无首版必要；逐 token 流引入额外状态，不能提高结果可信度；关键词固定回复不能覆盖自由问答。

回答只引用服务端登记的证据 ID，不接受模型返回任意路径/脚本。首版保留已有模型配置与 Debug backend；目前配置为 Codex backend，required KG 开启，不因为 handoff 提到“未来 Claude”而改变后端。

## 5. E203 可复用的可信证据

**Decision**: 以同次候选验证中的 RTL + report + VCD 三件套导入，trial 5 为修复前，trial 9 为修复后；最终通过同时连接独立 final_verify 的结果和匹配 RTL 清单。

**Rationale**: 工作根目录 wave.vcd 与最终成功波形同 hash，已覆盖初始失败。根 initial report 的 2/222@1315 无法再直接配该波形。某些 trace_report 已过期，lint_failed 候选也可能持有克隆波形；必须先检查 journal 的 sim_completed。

候选共同前缀：
`rtl_outputs/e203_exu_alu_system/.zerorepo/workspace/debug_system/e203_exu_alu_system/codex_private/candidates/`

| 内容 | 修复前 | 修复后 |
| --- | --- | --- |
| 候选 | candidate_ea234d9c8dd7/revision_001 | candidate_e0e2441d4dfd/revision_001 |
| Trial / accepted baseline | 5 / 3 | 9 / 4 |
| 真实总行统计 | 1/222，不匹配 @1125ps | 0/222，PASS |
| wave.vcd SHA256 | 7b1f0334e90e737a7d007a3fa7fc1ecbc5fa5200276d4c473654e9d1d8050389 | 798397b37c1c87dc1b5aa2d8d9797fbccc8e7f3e31089da21635cbf96e1a6a8a |
| debug_sim_output.json SHA256 | 9558d273a5898cbfa0bc902f549fd356d71faade74d688197e59ac7161b21fd6 | 3f47a7e3b26f073c16dc5f99a230dd5262b0c3091cef321ef59911f24bb06ba9 |
| e203_exu_muldiv.v SHA256 | 09b3b34d19388d699f41ed1c6b86d86f9f4262a30806a9b8fa427e270ba67556 | 1f9f0fad3cf27a727813060fbdd0be7799d2b93bfc99bb9b2440c548a5ca480e |

report 和 VCD 位于候选下 `artifacts/`，RTL 在 `merged/`。必须为完整 RTL 文件清单计算哈希，而不只对乘除法文件计算。

**Alternatives considered**: 直接发布整个输出目录会混用 stale latest 和 private 数据；仅给波形截图无法交互或追溯；手写假波形不满足真实性要求。

## 6. 采样判定与原始波形

**Decision**: 原始信号照实绘制；权威采样 marker 从该次 VCD 的 `tb.stats1` 计数器变化提取并与 report 交叉校验。无法匹配布局时保留报告结论，但不提供权威采样 marker。

**Rationale**: 当前 testbench `always @(posedge clk)` 内比较，VCD 同 tick 的稳定值可能包含比较之后的更新。最终 PASS 在1125ps附近仍有原始 DUT/REF 不同或 tb_match=0。testbench 没有 reset/valid/ready 屏蔽，不能为了图上更好看新增这些屏蔽。

`stats` 为109个32bit int的 packed struct，`stats1` 宽3488bit。clocks 增长标记采样，errors/逐信号错误counter增长标记失败。现有 trial 5 解码222次采样、1125ps一处失败；trial9解码222次采样、零失败。`sampled_value_available=false`，因为计数器没有存当时比较的完整数据值。

实际受信环境与仓库同名 verifier 文件不同，不能只凭文件名识别：

- 当前外部 verifier/testbench 与 latest binding 一致，testbench SHA256 `9b0ed0a069b71bdfc4b1a3132b355b36a8bd87210ac969e1b4b327e0a9f25a2e`。
- verifier SHA256 `fe54eb389cd4fc839d3aef8cd2d87fd58882505c26318cf07c88c7e0732ef23a`。
- packed 字段名顺序以换行连接的布局摘要：`7e5618937902926343edd8bcda8e2d6a13c6c6b0c1f50da5fa165612bb923f41`。
- 仓库 `rtl_dataset/e203_exu_alu_hard/verify_test/` 同名文件可用于查找结构，不可冒充本次受测环境的字节指纹。

已有 `trace_report.resolve_vcd_signal` 可用于信号映射；`sample_vcd_signals` 有截断/采样行为，不直接用于完整 transition 视图。`sim_review_mismatch_cnt` 累加重复失败提示会把1个失败采样计为2；只解析唯一总行统计。

**Alternatives considered**: 用 tb_match 组合线或原始值相等重算判定会与现有评分冲突；重写 golden 或 comparator 改变验收语义；新 sidecar 采样器没有首版必要。

## 7. 外部运行依赖的迁移

**Decision**: 明确 registry 和健康检查，复制完整受信验证环境到计算机，环境路径可配置；Web 与 Agent 运行环境分离，runtime 解释器沿用已验证配置。

**Rationale**: `oracle_root` 默认本机路径，E203 project_hint 与 top_module 不同；verifier 的 SYSTEM_TEST_DIR 还依赖 `e203_hbirdv2/e203_exu_alu/verification` 中 golden、stimulus、canonical headers。只复制 verify_test 或 rtl_outputs 不能运行现场复验。当前 requirements 还包含 torch/transformers/llama-index 等，不能把完整依赖当轻量 API 安装包。

**Alternatives considered**: 公网机直接安装所有依赖会引入未知资源压力；浏览器直接请求模型泄露凭据；静默关闭 required KG 改变实际能力。

## 8. 服务器路由与访问范围

**Decision**: 采用用户已确认的两机分工：公网 Caddy 静态前端 + 私网大内存后台。设计域名增加共享演示访问保护，无注册页面；后台仅允许网关访问并验证网关凭据，模型端口不公开。

**Rationale**: handoff 已有静态服务路径与未来私网反代约定。Caddy `handle` 保留 `/api` 前缀；`handle_path` 会剥离前缀，故本计划不用它。代理与静态处理互斥，避免 API 失败返回 index.html。[Caddy 反向代理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)、[handle_path 路径语义](https://caddyserver.com/docs/caddyfile/directives/handle_path)

SSE 返回 text/event-stream 并保持 heartbeat；Caddy 已对该类型按流转发，可显式配置 flush_interval -1。共享演示访问用 Caddy basic_auth 的密码哈希，不在前端存模型或网关密钥。[Caddy basic_auth](https://caddyserver.com/docs/caddyfile/directives/basic_auth)

**Alternatives considered**: 新公网后端域名与开放模型端口不符合 handoff；增加应用账号中心超出要求；只有纯静态发布不能支持真实操作。

## 9. 研究结论及事实边界

所有影响设计的选择已解决。部署时仍需填写计算机私网地址、服务用户、解释器与验证资源路径，并做实际连通性、工具链和磁盘预检；这些是部署参数，不需要假装已获知。

没有 SSH 登录，也未验证公网机资源和 Caddy 现行内容。尝试从浏览工具读取三个域名均未取得页面内容，不能据此推断站点离线；本计划中的站点配置事实来自用户 handoff。上线前先读取备份现行配置并核对差异。
