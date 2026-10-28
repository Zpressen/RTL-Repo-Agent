# RTL Agent 同机部署

## 当前 Agent 站与 003 候选包

当前演示入口为 `https://agent.deepvalleychip.cn`，既有服务为 `rtl-demo-public.service`。用户随后明确授权上线，新版 `evolution-20261019-r1` 已发布并完成公网 UI、四案例波形和会话隔离检查；真实问答验收等待本次外发授权，真实 A/B 修复未执行。design、主站和 www 保持原职责。

新 package manifest 通过 `target_origin` 绑定 Agent 域名，check 核对故事 seed 与静态 story_id/fingerprint。有故事导出 v2 seed；无审核故事保持 v1 和空状态。运行 build/check 不需要模型或修改生产服务，具体命令见 specs/003-add-ri-rsi-stories/quickstart.md（开发仓库文档，不上传）。

**以下 /opt 与 design 激活流程是旧 002 安装器，不能用于当前 Agent 站更新。** 对 Agent 目标执行旧 activate 会在任何主机修改前明确拒绝，不能以旧 design 包覆盖线上有效修复。未来更新现有 Agent 服务时，先保留实际 WorkingDirectory、release、私有配置、同版 seed 和公共根；候选须在独立目录重建环境、导入 seed 并验证静态/接口绑定后，才可在授权发布窗口切换现有服务。保留会话 DB 与签名 key，不回灌旧数据库，不开启后端公网端口，不改 design 的 Caddy 块。自动 Agent 激活适配与公网验收尚未完成，不运行下面的旧激活命令代替。

## 已发布 Agent 站的实际布局与恢复

2026-10-19 发布目录为 `/home/dev/rtl-agent-demo/releases/evolution-20261019-r1`。私有 `launch.json` 与 Web config 的 repo_root/release_id 指向新版；data_root、agent.yaml、environment.json、auth.json、验证资源及 parser 保持原路径。新目录的 `.venv-web` / `.venv-agent` 明确链接原环境，没有移动或复制虚拟环境，旧发行版因环境与 systemd 启动器依赖继续保留。

systemd 网关仍由原服务启动器读 private launch；worker 继续原独立 supervisor，二者在切换中重启。当前网关只监听 `127.0.0.1:18080`，没有调整 Caddy 或添加公网端口。原站 TLS/页面摘要均保持一致。

本次服务器私有恢复材料位于 `/home/dev/rtl-agent-demo/updates/evolution-20261019-r1/`。定制更新器位于 `/home/dev/rtl-agent-demo/staging/evolution-20261019-r1/update.py`，以 dev 和原 Web 解释器运行，只有固定 systemctl 服务操作通过已有 sudo 授权；没有以 root 执行 dev 可写 Python 代码。

如该发行版需要恢复，核对服务器留存脚本及 backup 后使用其 `rollback` 动作（本轮未在公网额外演练回退）：

```bash
/home/dev/rtl-agent-demo/releases/ssh-demo-20261016-r1/.venv-web/bin/python -B \
  /home/dev/rtl-agent-demo/staging/evolution-20261019-r1/update.py rollback
```

恢复只还原 config/launch/预检缓存并重启对应 Agent 组件，保留当前会话 DB 与 session.key。不要用旧 SQLite 备份覆盖访客新对话。发布记录及私有脚本本地索引在 `.rtl-demo/deployment/evolution-public-20261019/`。旧五层构建器的 activate 仍只适用于下面旧布局，不能拿来替代此实际 Agent 更新流程。

## 旧 002 同机安装流程（仅供对应部署维护）

仅 design.deepvalleychip.cn 接入新后台；主站、www 和现有 CAD :28989 保持原服务。后台监听 127.0.0.1:8000，Neo4j 监听 127.0.0.1:7687。生产服务由 systemd 管理，开发电脑不提供运行能力。

## 上传内容

候选必须包含 deployment.json 和 design/runtime/seed/verifier/ops 五层。只将 design 安装到 /srv/deepvalleychip/design。runtime 是运行源码、四例规格、grammar/提示词及许可；seed 只有经审查的历史闭包；verifier 只有四例验证资源原件；ops 包含锁、脚本、模板与本说明。

不要上传整个仓库、.git、specs、.agents、tests、开发文档、venv、node_modules、rtl_outputs、整个 RealBench、本地 .rtl-demo、会话数据库或实际配置。发布包不携带任何实际模型/网关/KG凭据。四例规格 Markdown 属于运行输入，保留。

## root 维护者操作

1. 记录本次候选 deployment.json 的独立 SHA256。用受信系统工具复制 dev 暂存候选到 /opt/rtl-agent/candidates/ID；固定目录及祖先由 root 持有且不可被 dev/服务账户写入。拒绝链接、特殊文件及硬链接；重新比对该独立摘要和每个文件摘要，再审查封存脚本。后续只从封存副本执行，不能 sudo 运行 dev 可写脚本。
2. 审查 bootstrap-as-root.sh --release SEALED --dry-run，再执行正式命令。它只在 /opt/rtl-agent/toolchain 安装锁定工具；使用签名、精确版本 RPM 和官方 hash 核验的档案，不改变系统 Python/Caddy/CAD。
3. 创建服务账户 rtl-demo 与 rtl-demo-kg 后，准备 /etc/rtl-demo/config.yaml、agent.yaml、environment，以及 /etc/caddy/rtl-demo.env。config/agent 使用 root:rtl-demo 0640，environment 与 Caddy env 使用 root:root 0600，父目录禁止普通用户写入。所有模板占位符须由维护者在私有文件内填写；不要将秘密粘贴到聊天或命令参数。
4. Web config 从 configs/rtl_demo.production.example.yaml 起步（候选 ops 含 production config 模板）。Agent config 使用 agent.example.yaml，保留当前选定模型、Codex backend/profile 和 required KG。模型 key 只通过 environment 注入 ZEROREPO_API_KEY。KG 使用新生成的独立长密码，存于私有 agent.yaml；首次启动通过 loopback Bolt 参数修改 Neo4j 初始密码，不将密码放入 argv。
5. 将本服务实际选定的 Codex 配置层放入 /var/lib/rtl-demo/.codex/config.toml 和 proxy-a.config.toml（如选定 profile 另名，以该名为准），所有者 rtl-demo，目录0700/文件0600。可参照 codex-profile.example.toml（保存为上述两个实际层文件），沿用已授权/v1端点和当前provider/model，环境变量经environment注入CODEX_PROXY_A_API_KEY。不要复制个人整个 ~/.codex、其他 MCP、会话或 auth。预检按这些实际文件和env_key检查；没有配置不能用其他全局登录冒充。当前本机真实Responses验收曾返回上游403，需在目标机核对授权/网络并完成真实MCP验收，不能用preflight ready代替。
6. 用独立解释器执行封存 ops/scripts/rtl_demo/deployment.py prepare --release SEALED --config /etc/rtl-demo/config.yaml --dry-run，审查后去掉 dry-run。两个环境在 /opt/rtl-agent/releases/ID 的最终路径建立；锁含全部传递依赖/hash，禁止移动现成 venv。parser 在目标重建。候选用临时 Store 验证，不碰生产 DB/key、不启动第二 worker、不切入口。
7. 确认资源门禁：候选 API256MiB + worker768MiB + KG512MiB + 至少256MiB余量 + 原业务基线 <= 物理内存。约2GB机器未经实测不能承诺承载。job 使用 root 所有的 /var/lib/rtl-demo-jobs.ext4 固定8GiB卷，宿主另留至少5GiB；首次配置不重分区，不覆盖已有卷。
8. 审查 activate --release-id ID --dry-run，再正式执行。协调器记录恢复集合，暂停准入、做SQLite一致性备份、停API/worker、导入历史、切只读版本、安装并启动受限系统units、核对四例完整就绪，最后发布design并合并完整Caddy配置。Caddy validate/reload读同一环境，验证不通过不得替换有效入口。成功状态仅 active_unverified。

prepare/activate 缺 root 返回5；环境未就绪返回4；失败已恢复返回6；恢复不完整返回7。check/status 仅标准库，无模型调用、无数据库创建。生产服务不允许以 development 环境变量绕过限制。

## 状态与验收

```
/opt/rtl-agent/toolchain/bin/python3.13 SEALED/ops/scripts/rtl_demo/deployment.py status --release-id ID
```

状态区分 staged（仅包）、prepared（准备完成）、active_unverified（入口切换）、accepted（SC全部验收）。四例依次从正式网页复验、10轮真实对话、一次生成/真实失败版本修复、执行并行问答及原业务检查、身份/隔离/预算拒绝、SSH退出30分钟、服务/主机重启、升级与5分钟回退必须分别留真实证据。测试替身、HTTP200和preflight ready不能替代这些证据。

验收索引由 root 封存到 /opt/rtl-agent/deployment/evidence/ID/；其JSON包含 release_id、host=39.107.243.176、origin=https://design.deepvalleychip.cn、prepare记录中的host_id，以及12条 criteria。每条 criterion=SC-001..SC-012、status=passed、evidence 为 path/size_bytes/sha256。每个证据JSON也绑定上述身份、criterion/status，并附实际操作ID、版本/验证/波形与测量。缺一项不能 accepted。

```
PYTHON SEALED/ops/scripts/rtl_demo/deployment.py accept --release-id ID --evidence-index INDEX --dry-run
PYTHON SEALED/ops/scripts/rtl_demo/deployment.py accept --release-id ID --evidence-index INDEX
```

## 排错与恢复

systemctl status rtl-demo-api rtl-demo-worker rtl-demo-kg；journalctl 按服务查看安全诊断。只在 loopback 检查8000/7687，28989继续归CAD。health返回真实JSON及release；401查演示认证与网关一致性，503查具体能力缺件、内存/cgroup/job卷、profile/KG和worker版本。不要禁用KG、换模型或回退裸运行来通过门禁。

```
PYTHON SEALED/ops/scripts/rtl_demo/deployment.py rollback --recovery-set RECOVERY_ID --dry-run
PYTHON SEALED/ops/scripts/rtl_demo/deployment.py rollback --recovery-set RECOVERY_ID
```

恢复集合位于 /opt/rtl-agent/deployment/recovery/；回退恢复旧代码/入口/units，保留已发布hash资源；绝不把旧DB或session.key覆盖回来。自动恢复失败返回7，维护者按recovery.json核对每个目标和摘要；保存失败版本/产物，不删除原VCD/归档腾空间。prepare失败保留部分环境供诊断，同ID不静默复用，需维护者确认清理失败目录后重试。

主机重启及回退验收由维护者安排窗口后执行，不能在已有业务上无预告演练。无需另一台机器的私网地址；若同机容量不足，先按实测数据扩容同一台服务器。
