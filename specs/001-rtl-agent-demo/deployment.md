# Deployment: Deep Valley Chip

生产部署已由 [002 单机方案](../002-secure-agent-deploy/plan.md)接续；执行步骤见 [002 quickstart](../002-secure-agent-deploy/quickstart.md)及随包 [RUNBOOK](../../deploy/rtl_demo/RUNBOOK.md)。默认在39.107.243.176同机安装API、worker、KG和验证工具，Caddy代理127.0.0.1:8000；不再要求额外大内存机器的私网地址。

001历史事实保留：2026-10-16本机两轮真实问答、刷新恢复与E203独立复验通过；101文件静态包曾上传dev准备目录 interactive-20261016-r2/design，逐文件hash通过。该次没有修改 /srv、Caddy或安装计算服务；生成/修复profile与正式域名验收未完成。这些事实不等同002上线或全能力验收。

目标服务器为2核、1870MiB，dev不能免密sudo；28989属于已有 /home/dev/cad-response-api，不能复用或替换。2GB容量是否足够由实际资源门禁决定；仅同步index.html无法部署交互后台。

只上传五层白名单候选；design进入 /srv/deepvalleychip/design，其余保留在私有部署路径。root先封存审查，再用bootstrap/prepare/activate操作，生产密码在服务器独立受限文件中配置。主站/www及CAD服务保持原样，不上传整个仓库、环境、私有会话和历史工作区。

正式域名需要全站演示认证、同源API和真实报告/波形。发布成功先记 active_unverified；SC-001～012的问答、三类执行、原业务、隔离、重启、升级/回退等全部留证据后才能accepted。实际进度见 [002 validation](../002-secure-agent-deploy/validation.md)，不沿用001勾选。
