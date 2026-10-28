# 本地 Langfuse demo

通过 [Langfuse 官方 Docker Compose 部署方式](https://langfuse.com/self-hosting/deployment/docker-compose)
在 WSL 中运行 Langfuse v4.58.0，Python SDK 4.17.0 及依赖版本锁定在 `requirements.txt`。
服务包含 Web、Worker、PostgreSQL、ClickHouse、Redis 和 MinIO。
Web 只监听 `127.0.0.1:3000`，MinIO 只监听 `127.0.0.1:9090`，数据库不暴露宿主端口。
独立 Compose 项目名为 `langfuse-local`。

## 查看结果

在 Windows 浏览器打开 <http://localhost:3000>。
账号为 `demo@localhost.test`，随机密码见本目录的 `artifacts/login.txt`。
账号、组织和项目通过[官方自动初始化配置](https://langfuse.com/self-hosting/administration/headless-initialization)创建。

进入项目 **Local tracing demo** 的 **Tracing** 页面（Observations 列表），查看三种场景：

| 场景 | 调用结构 | 预期评分 |
|---|---|---|
| `demo-rag-success` | 主流程 → 检索、模拟模型回答、关键词评估 | 1 |
| `demo-rag-slow-generation` | 同上，模型步骤约 800 ms | 1 |
| `demo-rag-retrieval-error` | 主流程 → 检索；均标为 ERROR | 0 |

成功场景包含 4 个 observation，失败场景包含 2 个。
所有数据来自本地模拟，token 用量为演示值：输入 32，输出 28。
没有调用外部模型，也没有生成真实模型费用。

`artifacts/latest-run.json` 保存最新运行的链接、服务端读回的 observations 和 scores。
`artifacts/observations.png`、`artifacts/trace-success.png` 等为浏览器实际截图。

## 重跑 demo

```bash
cd /home/mokita/RPG-ZeroRepo/langfuse_local
.venv/bin/python demo.py
```

每次创建新的 session 和三条 trace，自动等待异步入库，再核对调用层级、输出、
token 用量、错误状态和评分。可用 `.venv/bin/python demo.py --verify-only` 验证已有运行。
验证使用当前 v4 的 observations API v2 和 scores API v3。

## 管理服务

```bash
docker compose ps
docker compose logs --tail=50 langfuse-web langfuse-worker
docker compose down
docker compose up -d
```

`down` 后数据仍保存在 Docker volumes 中。`.env` 中包含本地随机凭据，
权限设为 600，并已在 `.gitignore` 中排除。

若需要重建 Python 环境：

```bash
uv venv --python /usr/bin/python3 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

浏览器截图验证脚本是 `inspect_ui.py`，需要额外安装 Playwright 和 Chromium。
本次验证使用的浏览器、共享库和中文字体位于 `/tmp/langfuse-*` 下；
这些临时依赖不影响 Langfuse 服务或 `demo.py` 的正常运行。
具体运行时设置如下：

```bash
LD_LIBRARY_PATH=/tmp/langfuse-browser-deps/extracted/usr/lib/x86_64-linux-gnu \
PLAYWRIGHT_BROWSERS_PATH=/tmp/langfuse-browsers \
FONTCONFIG_FILE=/tmp/langfuse-browser-fonts/fonts.conf \
.venv/bin/python inspect_ui.py
```
