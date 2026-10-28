# 单机部署实现与验收记录

2026-10-16。ready表示依赖就绪，与真实验收通过分别记录。私有原始证据留在`.rtl-demo/deployment/`，不随seed迁移。

现有事实：001已有四例历史展示，本机两轮真实问答和E203复验通过；静态101文件曾暂存dev目录。它们不是本特性的正式域名交付证据。本轮不继承其验收勾选。

| 标准 | 状态 | 验收环境 | 证据 |
| --- | --- | --- | --- |
| SC-001 | 未执行 | 正式域名 | — |
| SC-002 | 未执行 | 正式域名 | — |
| SC-003 | 未执行 | 正式域名 | — |
| SC-004 | 未执行 | 正式域名 | — |
| SC-005 | 未执行 | 正式域名 | — |
| SC-006 | 未执行 | 正式域名 | — |
| SC-007 | 未执行 | 正式域名 | — |
| SC-008 | 未执行 | 正式域名 | — |
| SC-009 | 未执行 | 正式域名 | — |
| SC-010 | 未执行 | 正式域名 | — |
| SC-011 | 未执行 | 正式域名 | — |
| SC-012 | 未执行 | 正式域名 | — |

## 实现检查

- 规格质量门禁16/16通过，checklists保持只读。
- 启用前/后扩展hooks文件不存在。
- 安装与模型调用、真实仿真、发布和重启结果分别登记；未执行不得标通过。

- T004～T012：13项seed/包安全测试通过；真实四例seed已导出97条历史记录/99文件（含原始审计附件），43,953,513字节，无本地会话/操作。正式域名SC仍未执行。
- T013/T014：新建两个CPython 3.13.11隔离环境，按哈希锁安装，Web API/Store/波形及Agent Planner/Reviewer/KG/LLMClient真实导入通过。修复干净环境发现的MCP传输符号和SQLAlchemy asyncio缺失依赖，不改变已有环境。
- T015：官方固定发布包已下载并计算真实hash，OS包版本来自目标缓存。目标工具尚未安装，native构建与实际能力另行验收。

- T016/T017：664文件分层候选构建成功；job当前输入物化、摘要校验与私有契约解析已接入。seed导入新Store后再导出保持同一97记录/99文件内容标识。
- T018～T027：runtime生产入口改为job，不读共享Store；worker重新校验ID/输入/报告。验证器部署适配记录原件hash和有效flags；目标parser源码重建和AST通过；统一profile实际读取、KG独立分区、候选/生产preflight与实际release核对，前端构建通过。
- Web回归56项通过（worker重构前完整检查）；worker/job最新针对性8项通过。真实部署场景浏览器测试仍在修正环境后执行，正式域名未验收。

- T028：新增四例浏览/对话框可编辑及刷新草稿浏览器场景通过；构建通过。浏览器所需现有库目录为browser-deps/extracted，不是开发工具默认路径。
- T029～T037：全局问答事务准入、幂等优先/429、执行预算、系统服务资源模板、KG私网配置及有界job卷准备脚本已实现；4项准入/预算测试及16项对话/目录回归通过。硬cgroup/卷/namespace尚需真实环境验证，不勾选T038。

- T039/T042/T047：分块/缺Content-Length请求上限已实测，从422修正为413且不创建会话；认证/同源/Caddy数值上限统一20,000字节。
- T040～T048：5项真实namespace/本机桥接负向测试通过，证明其他Store/key/run不可读、规格不可写、未知工具/任意KG查询/错误token拒绝；namespace原生探针通过。Codex及真实KG分区综合测试仍为T049未执行，不将这些测试替代它。

- 真实隔离仿真（本机，不是正式域名）：E203 PASS 25.771s、AES加密 PASS 29.163s、AES解密 PASS 32.253s、SDC PASS 25.019s。每次执行均经原生namespace与当前job入口，产物由worker归档，operation/run IDs和耗时保存在私有 local-four-verifications.json。未将这些结果勾为T069。
- T051～T058：发布协调器实现prepare/activate/status/rollback/accept；SQLite backup API抓取WAL一致快照，回退保留新消息/key/hash资源，完整Caddy仅替换design块。17项发布/worker/预算针对性测试通过。真实root安装、主机恢复窗口与服务器升级演练仍未执行。
- 扩展发布包负向测试发现并修复规格缺件、seed案例错配和缺依赖锁仍放行问题；11项包测试通过，包括python -S无Git/无第三方依赖运行check。
- 兼容回归：Web测试76项通过（新增包测试和缓存签名变更前），既有LLM流式/Codex resume/MCP/SystemDebugRunner回归77项通过；前端4项测试和TypeScript/Vite构建通过。最终变更后相关测试另核。

- 最新Web回归89项通过，前端完整浏览器9项通过（四例、10轮替身对话、离线输入/重连、刷新与真实历史波形等）。这是自动化界面验证，不是正式域名真实问答。
- T049实际演练：两个唯一KG分区真实构图/查询互不覆盖，模型侧namespace拒绝读取私有descriptor、Agent配置、参考验证器和另一run，规格只读；测试分区已按精确ID清理。真实Codex使用当前合法profile；原根地址及对齐已授权/v1的服务专用副本均在模型/MCP调用前返回上游403，不能算嵌套链路完整通过，T049保持未完成。未更换模型/端点域名、未改个人配置、未使用mock补通过。
- 安全补强：选定native Codex二进制单独挂载，不挂个人HOME；job绑定配置/profile/CLI摘要；模型侧仅提供所选provider变量；生成RTL含已知私有值时拒绝公开归档，报告先脱敏，保留原始私有材料。
- 目标只读复查：2核，MemTotal=1,961,869,312字节、MemAvailable=1,383,297,024，磁盘空闲34,340,229,120字节；Caddy、主站/www、CAD28989/health均正常，实际native namespace启动通过。CAD进程现属原SSH session scope，不能假设其具备主机重启自启。dev无root权限；候选1792MiB预算加现有占用超过物理内存，切换前容量门禁会阻止发布。正式root安装/域名验收仍未执行。

## 本轮收尾（2026-10-16）

- 最终Web回归：`timeout 180 .venv-web/bin/python -m pytest tests/rtl_web -q`，93 passed（29.68s）；Agent兼容回归：现有Agent解释器执行test_llm_streaming、test_codex_debug_resume、test_codex_debug_mcp、test_system_debug_runner，77 passed。前端vitest4 passed、TypeScript/Vite构建通过、完整Playwright9 passed。依赖版本和弃用提示未当作功能失败。
- 发布候选demo-20261016-secure4：672个清单文件，runtime382/seed100/verifier61/ops27/design102，未包含实际provider/gateway值、本地私有会话、开发文档或虚拟环境；实际上传后全部size/hash核对通过。deployment.json SHA256=d62969b63412374914d2c4856be85610d4a3f869607852e65231a33cb1f50365。
- 暂存目录：`/home/dev/deepvalleychip-site/releases/demo-20261016-secure4`，仅dev私有目录，未修改/srv、/etc/Caddy或系统服务。只读标准库check通过，包内源码与本机最终实现一致。
- 60/73任务完成。剩余T038/T049/T059、T063～T066、T068～T073分别是硬资源/实际Codex/目标生命周期及正式上线验收，保持未完成。SC-001～012均未在正式域名执行；发布状态仅staged，不是prepared/active/accepted。
- 实际阻塞：dev无可用免密提权；同机物理容量低于候选预算+现有业务；本机真实Codex Responses上游403。维护者交接包含具体封存摘要、独立环境/秘密/权限配置、容量建议、固定系统服务、Caddy design合并和恢复步骤；私有证据不随包公开。
- 上传后复查：Caddyfile、主站index和design index的摘要均与上传前一致；主站/www/design及CAD28989/health仍返回200。原业务未被候选暂存操作替换。原先挂起的本轮测试进程已结束，未遗留本轮验收任务。


## 普通 SSH 账户预览增量（2026-10-16）

- T074～T077：新增全站认证的回环 gateway、SSH 专用 Origin/Cookie、问答硬地址空间限制及用户 supervisor。完整 Web 回归 96 项通过；最后增加上游 403 提示后相关 11 项通过。公开部署原门禁保留。
- 目标独立 Python/uv 和两个依赖环境已安装。包源连接缓慢改用匹配 glibc/Python 的官方 wheels，目标仍按原哈希锁验证。四例 preflight 的 replay/chat 依赖就绪；verify/generate/fix 明确不就绪。
- 真实服务器浏览器检查四例可输入、草稿刷新保留、真实 DUT/参考波形；E203 修复前定位 1125 ps、修复后 0/222，无 API 替身、无页面异常。证据 `server-browser-check.json` 与截图保存在本机私有部署目录。
- 用户明确授权后，经 SSH 单独提供选定模型密钥至 dev 私有 0600 配置。没有传 SSH 私钥、其他服务凭据或原始完整配置。此前自动审批拒绝的动作在明确授权后重新审批通过。
- T078 尚未通过：首轮真实 E203 问答失败，最小诊断请求确认当前端点 Cloudflare HTTP 403 / HTML，不是模型回答；未继续用替身完成第二轮。私有证据 `server-real-chat.json`。
- 问答期间采样进程树峰值 142,942,208 字节，宿主最低可用内存 1,240,621,056 字节；不能外推为完整 RTL 执行峰值。三个原域名与 CAD HTTP 检查正常。证据 `server-rootless/resource-real-chat-check.json`。
- T079：原 crontab 保留并备份，追加仅管理 Demo 的用户级恢复段。SSH 启动会话断开后仍运行；受控停止 supervisor 后 34.01 秒恢复。未重启主机、不勾选正式部署的重启门禁。证据 `server-rootless/recovery-check.json`。
- 当前后台仅 `127.0.0.1:18080`，通过本机 SSH 隧道 18173 访问；正式 Caddy 路由、完整 RTL 工具链/资源边界和目标现场仿真尚未完成。参见 [普通账户查看与限制](ssh-preview.md)。


## 用户指定切换 DeepSeek 后的复验（2026-10-16）

- 原 inroi 403 仍是原端点的真实失败证据；用户随后明确指定 DeepSeek 官方端点与新模型凭据，没有绕过原服务访问规则。
- 部署 `deepseek-v4-pro` / `provider=openai` / `https://api.deepseek.com`，max_tokens=65536、temperature=0.6、reasoning_effort=high。实际密钥单独替换 dev 的 0600 环境文件，未写入代码、文档或版本摘要，也未修改本机原始模型配置。
- 修复配置存在却未传入 reasoning_effort 的问题；对话运行预算支持服务器明确配置的 65536，不再强制截为 2000。参数契约/原 LLM 流式回归 21 项通过，完整 Web 回归 97 项通过。
- T078/T081 通过：真实服务器、真实页面、无 API 拦截/替身，两轮分别 15.578s / 19.063s，均 answered，各有一个有效证据引用。回答正确标明历史回放及 0/222 的证明范围，绑定同一 E203 run/version/validation。私有证据 `server-real-chat-deepseek.json` 与对应截图；旧失败存为 `server-real-chat-inroi-failed.json`。
- 此结果解决私有预览问答阻塞，不能勾选正式域名两轮验收、现场 RTL 复验或完整生成/修复等原有未完成任务。Caddy 路由与完整执行环境限制仍有效。

- DeepSeek 问答时采样峰值 143,736,832 字节（约 137 MiB），宿主最低可用 1,241,546,752 字节；三个原域名及 CAD /health 均 HTTP 200。证据 `server-rootless/resource-deepseek-chat-check.json`。


- 用户要求取消网站密码：新增显式 SSH 预览免密码设置，页面/API 无凭据均 HTTP 200，chat 就绪；9 项认证/来源边界回归通过。未修改模型密钥、后台监听地址或 Caddy。浏览器独立无凭据验收见私有 `passwordless-browser-check.json`。

## 服务器执行依赖补齐（2026-10-19）

- T083/T084：锁定官方 Verilator 5.044、Codex 0.154.0、Neo4j 5.26.32、JRE 21.0.12.1+1 的档案校验通过；g++ 10.2.1、cpp、C++ 开发头文件、flex/bison/zlib/git 使用目标机信任的精确版本签名 RPM，仅提取至用户工具目录，无系统安装脚本或 root 修改。Verilator 使用单线程普通二进制构建，跳过开发 debug binary 和生成手册；构建参数及 hash 保存在 `server-runtime-20261019/native-tools-install.json`。
- 在服务器本机编译 Verilog grammar 并实际 AST 解析通过。四例原验证器/参考设计接入实际私有运行配置，仅适配路径/工具/编译并发 1；原 TB、刺激和比较语义不改。
- T085：独立 required KG 实际认证查询通过，Bolt 只监听 `127.0.0.1:17687`，HTTP/HTTPS 关闭，独立随机凭据保存在 0600 私有配置。采用 heap 128m/pagecache 32m 与 JVM 限制、进程树 448 MiB 监测和宿主 256 MiB 余量；演练采样峰值 423,198,720 字节。用户 cron 保留原条目并追加 KG 恢复段；未重启主机，不将该监测称为 cgroup。
- T086：真实目标服务器四例 private operator native rehearsal 全部 PASS：E203 33.730s（0/222），AES cipher 36.773s，AES inverse 42.256s，SDC 29.203s。每例均有真实 report/VCD、输入清单及 RTL/hash 绑定；最大执行树采样峰值 532,205,568 字节。结果为 `server-runtime-20261019/server-four-verifications.json`。四次经实际 namespace 和固定 job/runtime 入口执行，使用独立演练 Store；未勾选正式域名 T069。
- T049/T087：服务器使用用户指定的 `deepseek-demo` profile、真实 DeepSeek V4 Pro 和 Codex read-only CLI，27.079s 完成。三个实际 MCP 工具 `get_debug_status` / `query_rtl_kg` / `run_check` 均有 completed 事件且 error=null；两个真实 KG 分区不相互覆盖，模型无法读取私有 descriptor/Agent 配置/oracle/另一 run，spec 只读。结果为 `server-runtime-20261019/server-codex-mcp.json`；采样峰值 501,780,480 字节、宿主最低可用 559,407,104 字节，无预算终止。原 inroi 403 是历史失败，当前 DeepSeek 完整集成通过；此次未修改 RTL，不能作为自动修复收敛或 T070 证明。
- T088：启动独立真实 worker supervisor 并安装 dev cron 恢复段；受控终止本次 worker 后 3.502s 恢复，gateway PID 保持不变，证据 `server-runtime-20261019/worker-recovery-check.json`。worker 在准备/执行每个生产任务前再次核验能力，避免队列任务绕过已缺失资源边界。
- T089：四例最新实际 preflight 的 verifier/reference/Verilator/compiler/parser/backend/auth/CLI/profile/KG/query/worker/API-release/worker-release 全为 true；verify/generate/fix 仅剩 `memory_budget`、`job_volume`、`cgroup_memory`、`cgroup_cpu`、`cgroup_tasks` 阻塞。历史和真实问答就绪；详细检查为 `server-runtime-20261019/four-case-preflight.json`。公开网站仍是原 Caddy 静态入口，未替换正式域名部署状态。
- 最后使用系统 curl 检查主站/www/design 均 HTTP 200，CAD 28989/health 与回环 gateway /api/health 均 200。独立 Python 最初的公共 HTTPS 探针因 CA 路径错误失败，未当作业务中断；系统 curl 正常。新增服务没有公网监听，原业务未被替换。
- 原 T038/T059、T063～T066、T068～T073 和正式域名 SC 仍未完成；本轮解决的是实际依赖与服务器链路，不以 YAML 放行、移除 KG 或测试替身补齐剩余门禁。维护事项与当前准确状态见 [执行环境记录](runtime-environment.md)。
- 最终 Web 回归：`timeout 180 .venv-web/bin/python -m pytest tests/rtl_web -q`，100 passed（36.39s），含新增 SSH 问答增量内存准入和生产 worker 执行前复核测试。受限工具沙箱内的 Starlette/AnyIO TestClient 线程桥接挂起，诊断后中断；相同测试在允许本机事件循环/回环通信的执行环境完整通过，没有据此跳过功能测试。

## 公网域名实际接入（2026-10-19）

- 用户明确授权 sudo 与公网接入后，实测 `sudo -n` 已可用；没有将聊天中的 sudo 密码写入脚本、环境、命令参数或部署文档。
- T090～T093：Caddy 仅替换 design 块，将 `https://design.deepvalleychip.cn` 代理到 `127.0.0.1:18080`；原主站/www 配置和 `/srv` 两份页面摘要不变。后台 public 模式限定正式 HTTPS Origin、Secure/HttpOnly 会话，按用户要求免网站密码。模型/KG/后台端口没有公网暴露。
- 安装 root 所有的 `rtl-demo-public.service`，实际运行身份 dev，已 enable，替换旧 gateway cron 段；KG/worker 恢复段保留。API 的 cgroup v1 内核 `memory.limit_in_bytes=268435456`、CPUQuota=100%、TasksMax=128；256 MiB 是 API 服务边界，不是 native worker 的资源门禁。早期仅 MemoryMax 的配置在目标 v1 上为 infinity，修正为兼容 MemoryLimit 后核验生效。
- Caddy 2.6.4 最初将请求体超限错误包装为 502；对明确的内部超限原因增加 413 映射，最终真实 Content-Length 和 chunked 超长请求均 413。跨来源 POST 为 403，未创建模型调用。参考 [Caddy 错误路由](https://caddyserver.com/docs/caddyfile/directives/handle_errors) 与 [systemd 资源控制](https://www.freedesktop.org/software/systemd/man/devel/systemd.resource-control.html)，最终以目标实际探针为准。
- Web 回归 103 passed（37.87s），新增正式域名 gateway/Cookie/Origin 和 public 受限问答测试；没有放开 native worker 门禁。
- 无凭据、TLS 校验开启的真实公网浏览器验证四案例输入/刷新草稿、DUT 与参考波形、E203 修复前 1125 ps 定位及修复后 0/222，页面错误为 0。私有证据 `public-ingress-browser.json/.png`。
- 首次真实对话提交曾返回 502，没有作为完成证据；启用故障栈/退出码诊断并重启后，最小场景两轮真实问答为 11.830s/10.729s，完整四例浏览后再问答为 10.145s/21.845s，均 answered、各有一条有效证据引用。前者为 `public-chat-only.json/.png`，后者为 `public-ingress-browser.json/.png`，均无 API 拦截或替身。
- 受控终止本次 gateway 子进程，supervisor 11.508s 内启动替代进程；恢复窗口出现一次临时页面失败并单独保留，最终主站/www/design/API/CAD 均 HTTP 200。API cgroup 累计峰值 115,273,728 字节、memory.failcnt=0、oom_kill=0，未外推为完整 Agent 容量。原始系统检查为 `public-ingress-system-check.json`。
- 原始 Caddyfile 备份 `/var/lib/rtl-demo-ingress/Caddyfile.before-1792395561`；root 所有脚本提供 design 接入前配置回退，未实际执行回退或重启整台主机。入口与命令详见 [公网接入记录](public-ingress.md)。正式公网路由已接通，但完整 worker 内存/卷/cgroup、生成修复、升级/重启和全部 SC 尚未通过，不登记为完整 accepted。

## 切换 agent 子域名与断管退出修复（2026-10-19）

- 用户指定 `agent.deepvalleychip.cn`。目标 DNS 已解析到 39.107.243.176；备份 Caddy 和私有配置后，仅新增 agent 代理站点并把 design 改为保留 URI 的 301 重定向。后台 Origin 仅允许 `https://agent.deepvalleychip.cn`，维持免网站密码、Secure Cookie、受限问答及完整 worker 门禁。Caddy validate 与热加载通过，未改主站/www。
- 新域名第一次模型提交重现 502。实际退出记录为 returncode=-13，内存 failcnt/OOM 均为 0；逐个导入确认 API 导入使 SIGPIPE 从 ignored 改为 default，源于 `vcdvcd` 的顶层 signal.signal 调用。未将这次失败记为成功，也没有通过增大内存或关闭资源限制掩盖。
- `waveform.py` 导入依赖前后保存/恢复应用的信号处理。新增真实子进程测试在修复前因 SIGPIPE 以 -13 失败，修复后通过；目标进程核对 SigIgn 后实际发送 SIGPIPE，进程继续运行，health=200。私有服务器证据为 `agent-domain-sigpipe-check.json`。符合 [Python 对断管信号的处理说明](https://docs.python.org/3/library/signal.html)。
- 最终 Web 回归 105 passed（40.35s）。实际无凭据浏览器、TLS 校验开启：四案例输入/刷新草稿、真实 DUT/参考波形、E203 修复前后定位通过，Secure Cookie、旧 Origin 403、异常 Origin 403、超长请求 413，页面错误为 0。一次真实 E203 问答 answered，13.302s、一条有效证据引用；证据 `agent-domain-browser.json/.png`，无 API 替身。
- 运行发布和历史数据保持原标识，未把重定向当成会话跨域迁移或完整部署验收。完整 worker 资源及生成修复门禁仍保留，当前入口与运维说明见 `public-ingress.md`。

## design 恢复独立静态站（2026-10-19）

- 用户随后明确要求 design 恢复原页面、不跳转。只将 design 块改回原 `/srv/deepvalleychip/design` 的 root/file_server/encode；agent 块与主站配置逐字节保持不变，未重启 Agent。
- Caddy 校验和热加载通过。实际 design HTTPS GET 为 200，无 Location，解压后的响应 SHA256 与原 index.html 完全相同：`62338d5073b517c428aa288849c1108729ef859b1c73ed29fc6148f06ae01eca`。agent 页面/API、主站/www 和 CAD 均 200。
- 接入脚本的 agent 模式同步保留 design 静态站，防止下次 activate 恢复跳转；站点合并与重复应用检查通过。历史 301 记录保留，当前路由以本节为准；浏览器可能需要清除旧的永久跳转缓存。私有证据 `design-static-restored.json`。
