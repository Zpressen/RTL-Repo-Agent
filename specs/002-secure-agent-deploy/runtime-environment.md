# 目标服务器执行环境

2026-10-19，`dev@39.107.243.176`，当前运行发布 `ssh-demo-20261016-r1`。

同日后续已完成 [公网域名接入](public-ingress.md)：现在直接访问 <https://agent.deepvalleychip.cn> 可浏览和真实问答，无需 SSH 隧道。下文的 worker 完整资源检查仍保留。

此前只完成 Web/Agent 的 Python 环境、历史案例和真实问答，未安装或接入 native 仿真工具、KG 和 Codex。这些是运行依赖，不能由静态页面部署自动补齐。本轮已在服务器实际安装、配置并验证。

## 已运行的依赖

| 依赖 | 实际版本或配置 | 验证 |
| --- | --- | --- |
| Verilator | 5.044，目标机源码构建，普通运行二进制 | 四例真实仿真 PASS |
| g++ | GCC 10.2.1，目标发行版签名 RPM 的私有安装 | 四例实际编译 |
| Codex | 0.154.0，锁定原生 musl 二进制 | 真实 DeepSeek Responses 与三类 MCP 调用完成 |
| Neo4j / Java | Neo4j 5.26.32 / JRE 21.0.12.1+1 | required KG 查询、两个 run 分区隔离通过 |
| Verilog parser | grammar C 源码在服务器重建 | 真实 AST 解析通过 |
| 验证器与参考设计 | 原审核候选的 61 个 verifier 文件 | 四例路径、工具、单编译进程接入 |
| Worker | 独立普通用户 supervisor | heartbeat/release 检查通过，3.502 秒恢复 |

工具目录为 `/home/dev/rtl-agent-demo/toolchain/`；源码及两个虚拟环境位于 `/home/dev/rtl-agent-demo/releases/ssh-demo-20261016-r1/`。运行配置为 `/home/dev/rtl-agent-demo/private/config.yaml`，Agent 配置和服务专用 Codex profile 在同一私有目录内。原始完整开发配置和 SSH 私钥没有上传。

KG 仅监听 `127.0.0.1:17687`，关闭 HTTP/HTTPS；Web gateway 仅监听 `127.0.0.1:18080`。用户要求的网站免密码设置保留。未修改 Caddy、主站、www 或 CAD 28989。

## 真实服务器演练

| 案例 | 结果 | 耗时 | 执行进程树采样峰值 |
| --- | --- | --- | --- |
| E203 | PASS，0/222 不匹配 | 33.730 秒 | 346.6 MiB |
| AES cipher | PASS | 36.773 秒 | 438.0 MiB |
| AES inverse cipher | PASS | 42.256 秒 | 507.6 MiB |
| SDC controller | PASS | 29.203 秒 | 352.3 MiB |

以上通过固定 job 入口和实际 namespace 执行，保留原始报告、VCD、RTL 与输入摘要，没有更改验证规则。它们属于私有运维演练，结果位于独立演练 Store，不是网页新提交的实时 operation。

真实 Codex/MCP 演练耗时 27.079 秒，`get_debug_status`、`query_rtl_kg`、`run_check` 均有实际完成事件且无工具错误；两个 KG 分区和模型侧文件隔离检查通过。该演练使用历史失败 E203 检查工具链，没有修改 RTL，不能作为自动修复收敛证明。Codex 对自定义模型的元数据回退提示仍存在，不影响这次实际工具调用。

原始摘要保存在本机私有 `.rtl-demo/deployment/server-runtime-20261019/`，服务器原始报告及波形在 `control/native-rehearsal/state/jobs/`，MCP 原始事件在 `control/mcp-rehearsal/`。这些资料不随静态页面公开。

## 网页执行尚未放开的原因

四例最新 preflight 均确认 verifier/reference、Verilator/compiler、parser、KG、Codex 认证/profile/CLI、worker 和 API/worker release 已就绪。剩余阻塞为：

- `memory_budget`：这台机器实际约 1871 MiB，现有完整服务预算和原业务占用未通过总量检查。
- `job_volume`：尚无供执行使用的限容量挂载卷。
- `cgroup_memory` / `cgroup_cpu` / `cgroup_tasks`：普通用户设置未形成有效的内核限制。

2GB 已证明可以运行这次串行运维仿真；它还没有证明能在现有业务、KG、实时问答和生成/修复并行时满足完整预算。KG 演练采样峰值约 403.6 MiB，Codex/MCP 执行树约 478.5 MiB；采样结果不能替代内核硬边界或最坏负载容量验收。

正式执行边界由维护者安装受审阅的 worker slice/service 和固定容量 job 卷，核对实际 cgroup 文件、worker 所属 slice 与资源描述符，再复测预算。现有模板位于 `deploy/rtl_demo/rtl-demo-worker.slice`、`rtl-demo-worker.service`，存储准备脚本为 `scripts/rtl_demo/prepare-job-storage.sh`。当前运行目录在用户 HOME；正式系统账户迁移需同步路径与配置，不能直接启动旧 `/opt` 模板覆盖当前进程。

首次依赖安装时 dev 没有可用的 sudo。后续用户开通 sudo，已用于公网接入及 API systemd 服务；worker 的完整资源部署仍未完成。不能用 YAML 的 ready=true、禁用 required KG、development 放行或用户监测代替它们。worker 已增加执行前复核，即使遗留队列任务也会在缺失边界时明确失败。

正式域名已通过 Caddy 代理至回环服务，详见 [公网接入记录](public-ingress.md)。已有旧候选 `demo-20261016-secure4` 是历史封存材料，不包含本轮所有源码增量，完整正式发布前须重新生成并封存带完整清单的新候选，不能篡改其既有 manifest 或直接复用旧模型配置。完整生成/修复、全部正式部署 SC 及系统重启验收仍保留未完成。
