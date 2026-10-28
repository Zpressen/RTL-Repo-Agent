# Implementation validation — 2026-10-19

最新状态：自进化概念新版已在 Agent 站上线，见文末公网发布记录；前文保留代码阶段的验收快照。

本记录区分代码、真实材料和部署。用户最新要求是“只完成代码，真实修复验收暂缓”。收到该要求后未执行真实 A/B 修复、真实问答或服务器写入；没有将 fixture 激活到本地正式故事库或公网。

| 范围 | 结果 |
| --- | --- |
| 三页 UI、共享对话及导航 | 代码与本地 UI 回归通过 |
| 原四案例、RTL、报告及 DUT/参考波形 | 历史浏览回归通过；没有新执行验证 |
| 经验账本、冻结快照、Codex 三工具、客观使用记账 | 协议与受控 reviewer 测试通过 |
| 审核 CLI、故事 API、静态导出、v1/v2 seed | 代码及边界测试通过 |
| 本地五层候选 | staged，独立目录导入和浏览通过 |
| 两真实运行、实际复用及有据修订 | 用户要求暂缓，未验收 |
| 真实问答及 90 秒完整实证演示 | 未验收 |
| 公网发布及验收 | 未执行；不能称新功能已经上线 |
| PPA 测量、曲线、收益对照 | PPA 按用户要求延后；记忆收益未验证 |

## 实现边界

三页分别为 `#/workspace`、`#/optimization`、`#/experience`。工作台保留原架构、代码、验证与真实波形；优化页只显示待接入与文字流程；经验页按已有审核材料显示阶段，没有材料时为空。经验来源打开固定 source_version；失效引用不借默认 PASS。显式 URL 优先，刷新/后退恢复选择；晚到响应不能覆盖较新的页面。草稿与进行中回复保留，对话订阅保持单实例，发送时上下文固定；纯经验选择不会携带无关波形窗口。

经验运行路径增加审核库选择、只读快照、摘要绑定与恢复检查；模型只能通过 query/read/declaration 三个受限工具访问当前快照。可信候选评估记录实际 diff，accepted+FAIL 保持 FAIL；回滚和最终复验分别记录，读取不算采用。Codex distiller 只产生任务私有草稿，维护者离线审核后才能供其他任务使用。旧 Markdown 保留兼容投影并另存内容历史，不伪造旧记录。

公共故事为内容寻址且不可变，typed refs 校验案例/归属/树/报告/VCD，查询时重新核验；实际使用需要可信事件文件，不能只写阶段标签。审核导入先预检、事务提交，dry-run 不改变 active 根。v1 摘要兼容；有审核故事才导出 v2。静态只输出 display 材料，服务端/静态比对 story_id/fingerprint。对话证据限制最多 5 个使用摘要、每个 20 个事件、10 个正文产物、正文合计 64000 字符。

没有新增图表库、PPA 工具、网页经验编辑接口、全局经验挂载或执行门禁绕过；没有改写 merged/oracle、现有模型配置或其他域名职责。保留用户既有未提交修改，未创建提交。

## 实际测试

环境：Web 使用 `.venv-web/bin/python`，Agent 使用 `/home/mokita/miniconda3/bin/python`，Python 3.13.11；Node 24.14.0、TypeScript 5.9、已锁定 Vite 7.3.7/Vitest 3.2.7。没有升级锁或系统包。需要回环 socket 的测试使用允许本地网络的执行环境，未放宽产品权限。

| 命令/范围 | 实际结果 |
| --- | --- |
| `.venv-web/bin/python -m pytest -q tests/rtl_web` | 最终 132 passed，40.29s；一个既有 Starlette/httpx 弃用提示 |
| Agent pytest：test_rtl_memory_ledger、test_codex_memory_adapter、test_codex_debug_resume、test_codex_debug_mcp、test_debug_memory_snapshot | 55 passed；后续新增 legacy 投影测试所在 ledger 文件 3 passed |
| `python -m pytest -q tests/test_repo_react_trace_gate.py -k memory` | 11 passed，86 deselected |
| `npm --prefix web/rtl-demo test` | 最终 14 passed，6 files |
| `npm --prefix web/rtl-demo run build` | TypeScript 和 Vite 构建通过；无额外图表依赖 |
| 全部 Playwright（新增最后一条竞态测试前） | 16 passed，37.6s；含四案例、前后波形、游标/缩放、对话、历史回放 |
| 最后导航修复后：stories/chat/optimization/composer | 10 passed；固定来源 RTL、失效 URL、草稿、回复跨页等 |
| 增加竞态与单订阅检查后：stories/composer | 5 passed；晚到响应被丢弃，跨页只有一个 EventSource |
| 最终发行包自己的源码/API | 四案例最终历史 PASS 和非空波形均可读取；经验为空，无模型调用 |
| 最终发行包静态浏览 | 三页直接打开、1366×768 无横向溢出，0 个模型/执行 POST |

SC-007：本地 Chromium，已加载案例交替切换优化/经验页面 20 次，最后一次 P95 为 54.86 ms（上一轮 74.78 ms），满足本地 ≤1s。不是公网延迟或真实模型耗时。完整历史回放另一场景为 19.695s。测试容器缺 CJK 字体，截图用于布局/行为核查，不能代替终端浏览器的中文字体验收。

浏览器使用 `/tmp/rtl-demo-playwright` 和现有私有 browser-deps；没有安装系统依赖。所有 provider/reviewer 替身都只在测试中，不打入公开站。

## 候选包与恢复

最终候选：`/tmp/rtl-demo-ri-memory-release/ri-memory-20261019-r4`。私有索引：`.rtl-demo/deployment/ri-memory-release/local-candidate.json`；本地验收原始记录在同目录。包为 `design/runtime/seed/verifier/ops` 五层，共 685 个清单文件。构建器要求输出在仓库外，因此这里只在 `.rtl-demo` 保存索引。临时目录会被系统清理，需要时按 quickstart 重建。

以包内标准库脚本 `python -B -S .../deployment.py check --release ...` 检查通过；在 `/tmp/rtl-demo-ri-memory-acceptance/` 使用候选 runtime 的 PYTHONPATH、全新 state-r4 导入 seed，通过路径断言确认没有从开发仓库导入 Web 源码。导入 97 个记录、99 个文件。测试用 `-B`/`PYTHONDONTWRITEBYTECODE=1` 防止在受清单约束的候选目录产生缓存。

当前 seed 是原审核历史 `rtl-demo-seed-v1`，ID 为 `seed-375af1ec9c5fa206b171f42518ae11b18dbef62bc74200ea0f19bab018d6494c`。因为没有真实审核故事，不生成假 v2。v2 的额外历史/静态/回退逻辑由明确的隔离协议 fixture 验证，不能称 E203 真实闭环。

manifest 目标为 `https://agent.deepvalleychip.cn`。构建/检查和验收身份按目标与 release 绑定；恢复仅切回对应 story 根，保留新会话与签名 key。旧 design activate 对 Agent 包明确拒绝，不能用于现有 `rtl-demo-public.service` 的自动升级。实际现有服务更新与公网验收仍为 T050/T051，本轮没有执行，未改 Caddy。旧已知 release/入口事实保存在私有索引，并未重查或承诺服务器仍处于同一状态。

## 真实材料及未完成项

`.rtl-demo/stories/e203/source-audit.json` 审计了现有五条 legacy 经验。头部声称 lint/module_sim/trace 不足以证明原始层级，所引用 trace 文件缺失；没有据此批准 v1、伪造采用或编写成功故事。

此前真实 A/B 修复请求被自动审批拒绝：当时授权未覆盖向外部模型端点发送修复规格、RTL 和诊断。随后用户明确选择只完成代码，因此没有重试，也没有改用其他端点。T034～T037、T044、T050～T051 继续未勾选。真实经验链、修订依据、两轮问答、线上升级及公网验收均未完成；收益保持未验证。

任务清单共 45/52 已完成。检查过 `.specify/extensions.yml`，文件不存在，无 before/after implement hook。requirements checklist 保持只读，16/16 已勾选，无改动。


## 后续展示调整：自进化机制叙事

按用户最新要求，经验页改为“自进化 · RSI”：以观测、评估、记忆、改进、再验证的可交互反馈循环讲述演进方向；展示设计经验/失败边界/任务策略，以及 RI 与 RSI 的双层故事。示例明确标为场景推演，未填收益或执行成绩。真实工程记录保留在折叠区；上文真实材料与公网的未验收状态不变。

本次改动直接进入本地 Vite 页面；先前 r4 候选包不包含这一后续展示调整，不可据旧包声称该叙事已部署。

本次展示调整验证：前端 14 项单测与 TypeScript/Vite 构建通过；stories/optimization/composer 的 11 项浏览器检查通过，覆盖五个环节点击、说明性标记、无执行请求、记录折叠、原证据跳转、草稿与单订阅。story_chat 的 3 项证据测试通过。没有调用真实模型或更新公网。


## 最新公网发布：evolution-20261019-r1

用户随后明确要求将新版本上线到 `https://agent.deepvalleychip.cn/`，据此执行现有 Agent 服务的独立发行目录更新。不是旧 r4 的发布，也没有使用旧 design 安装器。

- 发行目录：`/home/dev/rtl-agent-demo/releases/evolution-20261019-r1`；private launch/config 指向此代码与 release_id。
- 更新包：145 个白名单文件，约 1 MB gzip；包含构建静态文件与配套 Web/记忆/Codex 代码，无凭据、会话数据库、开发文档或完整仓库上传。其余运行资源从当前服务器发行版保留，现有虚拟环境使用明确目录链接复用，没有搬移、重装或升级依赖。
- 发布前比较现有 Web 源码，原资源门禁、网关、worker、会话 Store 与沙箱等有效修复一致并保留。四案例 bundle_id/source_fingerprint 与静态版本一致，无 seed/会话迁移。
- 候选使用独立 SQLite 副本及只读历史文件验证四例最终报告、非空真实波形、故事接口和 `view=experience` Selection；四案例问答依赖预检通过，无模型调用。
- 切换前在服务器私有目录备份 config、launch、运行预检缓存和 SQLite；只重启现有 Agent gateway 与 worker。保留数据库和签名 key，42 个已有会话均保留。
- 公网 Chromium 实际 HTTPS 浏览通过：三页直达/刷新、五步概念交互、机制标签、跨页草稿、四案例波形、无网页密码、独立访客访问返回 401、secure/httpOnly 会话 cookie；0 个 RTL operation、0 个模型请求、无页面错误。
- 系统 TLS 客户端确认四域名 HTTPS 200；Agent 首页哈希变化，design/main/www 响应哈希与切换前一致。Caddy、原静态站页面、模型凭据、认证设置和 session.key 的摘要均保持一致，后端仍监听原回环端口 18080。
- 实际问答验收被自动审批拒绝，原因是本次页面上下文/可能 RTL 资料外发缺少明确授权；请求未执行。已完成全部不依赖该授权的发布和 UI 验收，等待用户答复；不把健康状态当作真实问答通过。T051 保持部分完成，T034～T037/T044 的真实闭环与修复仍未执行。

私有证据目录 `.rtl-demo/deployment/evolution-public-20261019/` 包含 manifest、activation、candidate-check、origins.after、public-ui-acceptance 和 deploy-result。服务器 `/home/dev/rtl-agent-demo/updates/evolution-20261019-r1/` 保留实际恢复材料，绝不回灌旧会话 DB。服务器系统 Python 缺 YAML，实际部署与候选检查使用既有 `.venv-web/bin/python`；没有为此安装新包。
