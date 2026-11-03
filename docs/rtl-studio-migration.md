# RTL Studio 迁移

2026-11-03，网页前端、Python API/worker、网页专用测试、模板、配置、部署脚本、设计规格和本地运行数据已迁移至 `/home/mokita/RTL-Studio`。

```bash
cd /home/mokita/RTL-Studio
./start.sh
```

浏览器入口：http://127.0.0.1:5173/#/tasks/new 。

本仓库保留 Agent 核心、CLI、数据集、原始 RTL 输出和 `.zerorepo` 环境。Studio 通过 editable `zerorepo-agent` 包使用这里的源码；通用事件协议和 RTL 指纹在 `zerorepo/rtl_impl/`。仅网页任务需要的适配由 Studio 的 `zerorepo.runtime` 包入口提供，普通 Agent CLI 不要求安装网页依赖。

Studio 的 `repo_root` 指向 Studio，`agent_root` 指向本仓库。已有任务输入和报告保留原字节，旧操作路径在读取时重定位；不建立回指旧网页目录的软链接。已有未提交网页内容保存在新目录，迁移前源码备份位于新目录 `.migration-backup/original-web-source.tar.gz`。

迁移清单、验证记录和启动说明分别位于新目录的 `migration-manifest.json`、`migration-validation.json`、`README.md`。本次迁移不提交 Git、不更新公网服务、不发起模型生成。
