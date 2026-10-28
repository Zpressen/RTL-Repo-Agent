# 部署入口与 SSH 预览历史

更新于 2026-10-19，目标 `dev@39.107.243.176`，发布 `ssh-demo-20261016-r1`。本轮执行依赖与真实服务器复验见 [执行环境记录](runtime-environment.md)。

**当前入口已切换至 <https://agent.deepvalleychip.cn>，无需密码或 SSH 隧道。** HTTPS 公网来源、Secure Cookie 和 systemd 服务已配置，真实公网问答已通过；详见 [公网接入记录](public-ingress.md)。下文的 localhost 连接方式和“Caddy 尚未接入”描述属于此前预览阶段记录，不能作为当前状态。

网页、四例历史数据与真实波形已在服务器运行。用户随后指定切换为 DeepSeek 官方端点，服务器已完成两轮真实网页问答。此前 inroi 端点的 Cloudflare HTTP 403 失败记录保留，不作为当前 DeepSeek 的状态。

## 此前 SSH 预览方式（当前请使用上方公网地址）

建立仅回环监听的 SSH 隧道后，可打开 <http://127.0.0.1:18173>。隧道只在对应 SSH 会话存续时可用：

```bash
ssh -i /home/mokita/.ssh/id_ed25519 \
  -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -N -L 127.0.0.1:18173:127.0.0.1:18080 dev@39.107.243.176
```

按用户要求已取消网站登录密码，直接打开即可；原私有连接信息文件标记为 `password_required: false`，无需使用其中的旧登录凭据。若端口已被当前隧道占用，直接访问页面。此入口服务实际运行在服务器，浏览器没有连接开发机 Agent。

## 实际上传与环境

- 基础包沿用已审核的 `demo-20261016-secure4`，在用户目录建立独立发布；先追加六个明确列出的源码文件，摘要记录在私有 `ssh-preview-overlay.json`；模型切换另追加两个文件，记录在 `deepseek-overlay.json`。没有整体同步仓库、文档、原始配置、开发数据库或 SSH 私钥。
- `/home/dev/rtl-agent-demo/toolchain/`：独立 uv 0.10.8 和 CPython 3.13.11；Web/Agent 分别新建虚拟环境。Agent wheels 从官方 PyPI 下载，匹配目标 glibc/Python，并在目标机按原 requirements 哈希锁离线安装；没有复制本机 venv。
- `/home/dev/rtl-agent-demo/releases/ssh-demo-20261016-r1/`：运行源码和构建后的 `design/`。前端无需服务器安装 Node。
- `/home/dev/rtl-agent-demo/state/`：独立 Store、97 条导入记录、99 个历史证据文件，以及本次服务器会话。
- `/home/dev/rtl-agent-demo/private/`：重新生成的配置。用户明确授权后，仅传输了选定模型密钥，存于 `environment.json`，dev 所有、0600；没有传输其他服务或 SSH 凭据。同属 dev 的进程仍处于同一账户权限边界。

后台只监听 `127.0.0.1:18080`。用户明确要求取消网站密码后，当前 SSH 预览不再进行浏览器 Basic 登录；SSH 通道仍使用现有 SSH 认证。内部 gateway key 由服务器注入，Origin 限本机地址，公网默认模式的 Secure Cookie 不受影响。没有开放模型、KG 或执行服务的公网端口。

## 常驻与验证

`scripts/rtl_demo/user-supervisor.py` 只管理本次 Demo 进程。dev 的 crontab 增加有标记的开机/分钟恢复段，原条目保留，备份为服务器 `control/crontab.before-preview`。普通退出不会停止它；管理员可删除该标记段并终止 supervisor 后停用。PID 和日志在 `control/`，不能只凭陈旧 PID 杀进程，应核对进程所有者、命令与发布目录。

已验证 SSH 启动会话结束后仍可访问；受控停止 supervisor 后 34.01 秒自动恢复。未重启整台主机，也未将此演练标为正式部署的主机重启验收。

真实浏览器连接服务器，四例输入框可编辑、刷新草稿保留、DUT/参考波形可见；E203 修复前定位 1125 ps，修复后显示 0/222。没有拦截或伪造 API。

原端点第一轮真实问答失败，私有诊断确认 HTTP 403、`server=cloudflare`、HTML 响应。用户明确指定后，已换为 `provider: openai`、`model: deepseek-v4-pro`、`base_url: https://api.deepseek.com`，并配置 `max_tokens: 65536`、`temperature: 0.6`、`reasoning_effort: high`。新密钥仅替换服务器私有环境文件，未写入仓库源码或文档，未覆盖本机原始 `zerorepo_config.yaml`。

已补齐 reasoning_effort 参数透传，并让对话运行预算遵从 65536 上限；原默认 2000 的行为保留给未配置该预算的部署。120 秒超时与单问答准入保持生效。参数契约及原 LLM 流式回归 21 项通过，完整 Web 回归 97 项通过。

服务器实际浏览器两轮问答分别 15.578 秒、19.063 秒完成，均为 answered，各有一个有效证据引用。回答正确标明当前 E203 为历史回放，并解释 0/222 的覆盖范围；两轮上下文均绑定相同 run/version/validation。证据及截图位于本机私有 `server-real-chat-deepseek.json/.png`，原端点失败保留为 `server-real-chat-inroi-failed.json`。未用替身补齐验收。

## 2GB 与正式域名

这台机器可以承载已经运行的网页、历史波形和受限问答进程。真实问答期间进程树采样峰值 142,942,208 字节（约 136 MiB），宿主最低可用内存 1,240,621,056 字节。采样不是完整生成/仿真的容量证明。API 与单个 SDK 解释器各有 384 MiB 硬地址空间上限，且有全局问答准入与独立 namespace；这不是全部后代的 cgroup 总内存限制。

2026-10-19 已补齐 Verilator/g++、独立 required KG、Codex、目标 parser、四例验证器路径及真实 worker。四例在服务器受控串行仿真全部 PASS 并生成真实报告/VCD；实际 Codex/MCP、两个 KG 分区及文件隔离也通过。安装、路径和证据见 [执行环境记录](runtime-environment.md)。

网页上的完整 RTL 生成、现场复验与自动修复仍因总内存预算、有效执行 cgroup 和限容量 job 卷未通过而拒绝。用户 systemd 接受 MemoryMax 等配置，但内核限制没有生效；本轮没有将监测或运维演练冒充该硬边界。完整生成/修复端到端验收尚未执行。

`design.deepvalleychip.cn` 仍使用原 Caddy 静态站。dev 无权修改 `/etc/caddy/Caddyfile` 和实际 `/srv` 服务目录，不能把准备目录更新当作正式上线。正式域名需维护者按原交接进行 Caddy/HTTPS/认证和公开同源配置切换；不能把当前仅允许 localhost 的 SSH 配置原样代理后就宣称可用。另一台大内存服务器仍需实际私网地址，同机部署则使用回环地址。

本次未修改主站、www、CAD 28989 或 Caddy；实际 curl 核验三个域名均 HTTP 200，CAD `/health` 亦为 200。完整 002 的未完成门禁保留在 `tasks.md`。


2026-10-16 取消密码复验：私有 auth 配置明确设置 `password_required: false`，缺省行为仍保留原认证模式。无凭据的页面与 API 均 HTTP 200；测试继续验证会话 Cookie 和来源限制。修改仅针对当前回环预览，未开放新端口或改动 Caddy。
