# Quickstart: 单机部署实施后的验收

日期：2026-10-16。本文所述seed/发布/门禁命令已实现；目标服务器尚未完成root安装与正式域名验收。按实际证据逐项执行，命令存在不等于已部署。只读检查与mock测试不能代替线上验收。

契约：[发布接口](contracts/deployment.md)、[运行接口](contracts/runtime.md)。上传范围见[deployment-inventory.md](deployment-inventory.md)。

## 1. 前置条件与角色

- 构建机：现有四例经审查的历史Store及全部引用文件、四例规格、必要RealBench材料；Web构建环境和已测试Agent环境。缺历史证据如实保留，不补造失败波形。
- 服务器：SSH dev可用，主机密钥已按现有记录验证；root维护者可按具体预览安装依赖及修改design路由。dev不能免密sudo，不能由dev伪装完成root步骤。
- root先将候选封存到dev不可写目录并审查固定脚本，再运行bootstrap，为`/opt/rtl-agent/toolchain/`安装受信固定版本uv/CPython 3.13.11及基础构建工具；不覆盖系统Python、Caddy或CAD解释器。bootstrap接口见发布契约。
- 模型沿用当前获授权端点/provider/model；服务器自己的私有环境/配置、Codex认证/profile和KG凭据就绪，不在聊天、命令行或日志填写实际密钥。服务所需环境由systemd提供，不依赖SSH中export。
- 已记录主站/www页面、Caddy有效配置、CAD服务及端口、资源基线；维护者安排服务/主机重启和回退窗口。首次上线前无须另一台计算机地址。

## 2. 构建和包检查（构建机）

以下命令以仓库根目录执行；build配置使用新提供的脱敏package模板填写本机路径，并保存在被排除的私有目录。build只读取已完成的dist，不替用户省略前端构建。

```bash
.venv-web/bin/python -m pytest tests/rtl_web
npm --prefix web/rtl-demo ci
npm --prefix web/rtl-demo run build
.venv-web/bin/python scripts/rtl_demo/deployment.py build --config .rtl-demo/deploy-package.yaml --release-id demo-20261016-r3 --out /tmp/rtl-demo-release
.venv-web/bin/python scripts/rtl_demo/deployment.py check --release /tmp/rtl-demo-release/demo-20261016-r3
```

预期：五层包完整、四例ID/规格/证据齐全、依赖锁和文件hash存在；不含开发文档、Git/venv、聊天/实时私有记录、整个历史工作区或实际秘密。不可只检查包大小；清单列明每项来源和用途。

执行一次干净目录演练：将release作为唯一项目输入，在无本机repo/RealBench/Conda映射的目标兼容环境重建依赖，导入seed；检查四例可读及三类入口依赖。若测试进程仍能通过原PYTHONPATH访问开发仓库，则该演练无效。

## 3. 上传、服务器准备与私有seed

只通过SSH/SFTP上传五层release到`/home/dev/deepvalleychip-site/releases/demo-20261016-r3/`，不使用仓库根rsync。私有层限制目录权限。root用受信系统工具将其复制封存至`/opt/rtl-agent/candidates/demo-20261016-r3/`，确认无链接/特殊文件且dev不可写，重算hash、审核脚本，然后从封存副本执行bootstrap。已有独立Python时直接重新check；摘要不一致停止。准备服务器自己的`/etc/rtl-demo/config.yaml`与秘密文件。

在服务器由root执行已审阅的脚本及固定解释器：

```bash
/opt/rtl-agent/toolchain/bin/python3.13 /opt/rtl-agent/candidates/demo-20261016-r3/ops/scripts/rtl_demo/deployment.py prepare --release /opt/rtl-agent/candidates/demo-20261016-r3 --config /etc/rtl-demo/config.yaml --dry-run
```

审查实际文件/账户/工具/服务和job容量变更，确认不含main/www/CAD目录操作，再执行同一prepare去掉`--dry-run`。任何root执行前均审核具体候选及预览；本指南不要求传输或公开root密码。

预期：两个生产环境在最终版本路径建立；oracle只读；parser目标构建/缓存可用；私有配置无开发路径；KG新生产数据由当前任务重建；未切换正式静态/路由。已有生产时只进行候选隔离检查，不能启动第二worker或覆盖旧状态。

seed独立演练命令（目标私有测试配置指向全新临时data_root，不能指向生产）：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli import-seed --config /path/to/isolated-config.yaml --source /path/to/release/seed --dry-run
.venv-web/bin/python -m zerorepo.rtl_web.cli import-seed --config /path/to/isolated-config.yaml --source /path/to/release/seed
```

预期：dry-run无Store/secret副作用；首次生成自己的DB/key，仅历史记录；二次导入幂等。篡改一文件/同ID不同内容应失败且无部分有效记录；不得导入本地会话和实时run。四例模块、报告、波形/分片均可读，契约缺失状态正确。

## 4. 运行环境与正式切换

先检查prepare给出的候选离线报告：必须绑定候选release及临时Store，不要求正式worker，不借用旧release缓存。正式生产seed与worker只在activate期间安装/启动，不能把下面的完整预检提前作为prepare前提。

root通过发布协调器activate的dry-run审查完整恢复集合，再正式执行。发布前备份、一致性处理Store/WAL、检查schema前后兼容；仅合并design站点。启动候选后执行完整就绪门禁，失败则恢复；仅通过后切换正式静态和入口，状态为active_unverified，而非accepted。

```bash
/opt/rtl-agent/toolchain/bin/python3.13 /path/to/reviewed/ops/scripts/rtl_demo/deployment.py activate --release-id demo-20261016-r3 --dry-run
```

准备阶段保存工具的实际固定路径，正式执行同一审核工具去掉dry-run。Caddy validate不通过不得替换有效配置；静态更新不需reload，入口/环境变更按实际systemd/Caddy配置执行。确认API/worker/KG系统服务账户正确、API仅loopback、28989保持原服务。

activate启动后的完整检查（协调器执行，维护者也可复核）：在实际服务账户和systemd同等环境分别检查四例。`--fail-if-unready`在缺依赖时非0退出：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli preflight --config /etc/rtl-demo/config.yaml --case e203 --json --fail-if-unready
.venv-web/bin/python -m zerorepo.rtl_web.cli preflight --config /etc/rtl-demo/config.yaml --case aes_cipher_system_hard --json --fail-if-unready
.venv-web/bin/python -m zerorepo.rtl_web.cli preflight --config /etc/rtl-demo/config.yaml --case aes_inv_cipher_top_system --json --fail-if-unready
.venv-web/bin/python -m zerorepo.rtl_web.cli preflight --config /etc/rtl-demo/config.yaml --case sdc_controller_system --json --fail-if-unready
```

上述命令从已激活release目录执行，且API/worker实际release_id均须一致。预检验证profile实际解析、KG解析/查询、sandbox启动、工具/材料/预算及worker，不默认付费调用。历史AES缺契约属于特定来源限制，不伪造契约来通过预检。实际问答、生成和修复另在下一节验收。

## 5. 正式域名验收矩阵

基础连通检查：认证使用交互密码，不把明文密码写入命令；gateway key由Caddy注入，浏览器不提供。

```bash
curl -I https://deepvalleychip.cn
curl -I https://www.deepvalleychip.cn
curl -I https://design.deepvalleychip.cn
curl --user demo https://design.deepvalleychip.cn/api/health
```

预期：主站/www基线一致；未认证design为401；认证health是JSON并显示实际release/能力。HTTP200或health ready仍不足以标记accepted。

| 验收 | 操作与预期 | 标准 |
| --- | --- | --- |
| 四例展示 | 浏览四例架构/代码/报告/真实波形，历史与实时区分；输入框持续可输入 | SC-001 |
| 真实问答 | 正式域名10轮自由提问/追问，打开有效证据；切标签、刷新保留；接收≤3秒，回答或失败≤120秒 | SC-002 |
| 真实执行 | 对四例各实际复验；E203通过且DUT/Reference、报告、RTL与输入清单绑定；从预置规格生成一次，对真实失败版本修复一次 | SC-003/012 |
| 技术结果 | 生成/修复如实记录结果；设计未收敛可失败，缺依赖/启动失败不能算能力已验收；AES加密无历史契约不强行修复 | SC-003 |
| 访问边界 | 未授权、直连后台、跨会话、跨案例、任意路径/命令均拒绝，无调用/任务副作用 | SC-004 |
| 原业务与并发 | 一次RTL任务期间3轮问答；主站/www各30次、CAD现有健康检查10次均符合基线；浏览p95≤5秒；记录资源峰值 | SC-005 |
| 幂等与恢复 | 同请求重复点击/刷新/断线只一个执行；全局第二任务409，问答超额429；结果≤5秒可见 | SC-006 |
| 持续运行 | 关闭开发机后台、退出SSH30分钟仍可交互；服务重启≤60秒、主机依赖就绪后≤120秒恢复；旧未完成任务不重跑 | SC-007 |
| 回退 | root按recovery_set预演并实际回退≤5分钟，旧入口/代码有效，新会话与证据仍在 | SC-008 |
| 秘密/材料 | 检查公开包、下载和普通日志无秘密/参考源码泄露；执行前后原spec/TB/参考hash不变 | SC-009 |
| 状态准确 | 维护者≤2分钟区分暂存、后台启动、部分能力和完整验收，能定位真实阻塞 | SC-010 |
| 干净准备/升级 | 只用声明材料可冷启动；无开发私有状态迁入；已有生产会话、结果、签名key升级后全部保留 | SC-011/012 |

隔离另做负向实测：任务尝试读取其他run/DB/key/CAD路径及写入spec/TB/参考均失败；Codex/native shell拿不到KG密码/参考源码，无法经桥接查询其他图分区；命名空间/资源限制实测生效。注入超时、OOM/磁盘不足与上游故障，只有当前任务中断，诊断安全、证据保留，原业务保持可用。

## 6. 收尾与失败处理

为SC-001～012逐项保存release/host/origin、实际operation/validation IDs、RTL/报告/波形摘要、耗时、资源和原业务对照。敏感诊断保存在受限运维目录，不复制到静态站点。

仅全部通过才将发布记为accepted。任何能力不齐或资源不足均保留实际状态和未完成项；需要扩容时给出同机资源建议，不改用假响应、不移除required KG或悄悄换后端。回退切旧代码/入口，不覆盖生产数据库；回退失败输出具体恢复位置和人工步骤。

## 7. 管理员登记验收

索引格式和root封存权限见 [RUNBOOK](../../deploy/rtl_demo/RUNBOOK.md)。索引及各证据绑定release/正式host/origin、prepare记录的host_id及SC编号，每个引用核对size/hash；当前机器及代码版本也须匹配。

```bash
/opt/rtl-agent/toolchain/bin/python3.13 SEALED/ops/scripts/rtl_demo/deployment.py accept --release-id ID --evidence-index INDEX --dry-run
/opt/rtl-agent/toolchain/bin/python3.13 SEALED/ops/scripts/rtl_demo/deployment.py accept --release-id ID --evidence-index INDEX
```

所有SC通过且重新核对生产就绪后才写accepted；缺证据或身份不匹配返回4。status只读，不自动调用付费模型或创建Store。


普通 SSH 账户当前可运行的预览入口、环境与真实验收限制，见 [ssh-preview.md](ssh-preview.md)。该预览不替代本文件的完整部署门禁。
