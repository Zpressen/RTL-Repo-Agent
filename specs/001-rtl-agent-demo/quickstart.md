# 本地运行与验收

网页、API、worker 和发布脚本已实现；本机两轮真实模型问答、刷新恢复和对话发起的真实独立验证已通过。生成/修复仍待指定后端profile验收，服务器尚未发布。实际结果见 [validation.md](validation.md)。

## 两个 Python 环境

Web API 不安装完整 Agent 依赖，也不改根 requirements.txt。`runtime.python` 指向现有 Agent 解释器；它需要能从本仓库导入新增的 `zerorepo.rtl_web`，并具有现有 LLMClient、PlannerRunner、Debug 和 KG 依赖。

```bash
python -m venv .venv-web
.venv-web/bin/python -m pip install -r requirements-web.txt
cp configs/rtl_demo.example.yaml configs/rtl_demo.local.yaml
npm --prefix web/rtl-demo ci
```

编辑被 gitignore 排除的 `configs/rtl_demo.local.yaml`：

- 本地设 `development: true`，仅允许 loopback 监听及配置中的来源域名。
- `repo_root`、`data_root` 按配置文件位置/仓库解析；生产 data_root 使用同机持久盘。
- `runtime.python` 使用既有 Agent 环境的绝对解释器路径；`oracle_root` 指完整 RealBench 根目录；`toolchain_bin` 指 Verilator 所在目录。
- `runtime.agent_config` 使用现有受限配置。当前 Agent 配置通过 `${ZEROREPO_API_KEY}` 读取凭据；在运行 API/worker 的服务环境中注入，勿写到前端或提交文件中。
- 保留原有 Codex backend/profile 和 required KG；当前机器的指定 profile 检查未通过，需按既有配置准备，不能自动切换。预检不调用付费模型，也不会自动替换后端。

## 导入真实案例和构建

从仓库根目录执行。导入需要四个案例的原始输出；固定审查摘要位于 `configs/rtl_demo_e203.evidence.json` 和 `configs/rtl_demo_cases.evidence.json`。同一 bundle ID 不覆盖不同来源，源证据或归档被修改会拒绝复用。

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli prepare-cases --config configs/rtl_demo.local.yaml --out web/rtl-demo/public/cases
npm --prefix web/rtl-demo run build
```

只发布完整 `web/rtl-demo/dist/`；其中包括 assets 与历史包，不能只复制 index.html。已导出的静态文件不需要模型服务就能浏览真实代码、报告和波形。

推荐统一启动，避免只启动前端导致“后台未连接”。直接沿用 `runtime.agent_config` 指定的现有模型配置：

```bash
scripts/rtl_demo/run-local.sh --config configs/rtl_demo.local.yaml --require-chat
```

此命令使用同一环境依次预检、导出四例并启动真实API、单一worker和Vite；Ctrl+C停止本次启动的服务，日志位于data_root的api.log/worker.log/web.log。`--require-chat`在问答依赖缺失时直接报错；依赖就绪不等于模型调用已验收。已有Vite时加 `--no-web`，已有API/worker时先在其所属终端停止，避免重复服务。只需验证仿真且尚未配置模型时可省略 `--require-chat`，命令会明确显示问答未就绪。

如果现有配置使用 `api_key: ${ZEROREPO_API_KEY}`，这只是变量引用，需要在当前服务环境提供实际值；可在被忽略的 `.rtl-demo/runtime.env` 中填写 `ZEROREPO_API_KEY=<实际值>`，权限设600，启动命令加 `--env-file .rtl-demo/runtime.env`。已有有效模型配置无需另建环境文件。环境文件仅解析KEY=value，不执行shell脚本。服务器可用下文systemd的EnvironmentFile传入同一变量，不能依赖SSH交互终端中临时export的环境。实际凭据不进入静态包。

也可分别在三个终端手动启动（与上述统一启动二选一，API和worker须继承同一模型环境）：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli serve --config configs/rtl_demo.local.yaml --host 127.0.0.1 --port 8000
```

```bash
.venv-web/bin/python -m zerorepo.rtl_web.worker --config configs/rtl_demo.local.yaml
```

```bash
npm --prefix web/rtl-demo run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173/`。顶部下拉框可切换 E203、AES 加密、AES 解密、SDC 控制器；也可直接打开 `http://127.0.0.1:5173/?case=sdc_controller_system`。每个案例保留自己的对话和操作目标。更新代码后重启 API 和 worker，再刷新浏览器。

启动 worker 后重新运行预检，让 health 反映真实可用能力：

```bash
RTL_DEMO_CONFIG=configs/rtl_demo.local.yaml scripts/rtl_demo/preflight.sh
```

缺模型凭据时依然可通过“重新验证当前设计”执行真实 verify；普通问答、生成与修复会明确说明未就绪。注入凭据后须重启服务并重新预检；预检成功只说明依赖检查通过，真正模型调用仍可能返回服务错误。

对话框在后台离线时仍可输入；草稿按案例保存在当前浏览器标签页，刷新或切换任务后可恢复。启动 API 后点击输入框下方的“重新连接”，会恢复会话和发送能力，草稿不会自动发送。中文输入法确认候选词的回车不触发发送。

## 三分钟演示路径

1. 默认“架构”：展开规格摘要，点击乘除法模块查看只读 RTL，点击“查看修复差异”。
2. “验证”：查看最终独立复验 0/222，再选“修复前 · trial 5”，看到 1/222。
3. 点击“定位差异”到 1125 ps，查看 `wbck_o_wdat` 采样标记；切回最终复验，同一窗口保留。游标是原始 VCD 值，测试结论来自采样统计。
4. 使用“历史回放”，可暂停、继续；展示节奏约 21.3 秒，不代表真实生成耗时。未记录原始阶段时间如实说明。
5. 服务就绪后在常驻对话框提问，点击依据；输入“重新验证当前设计”“按预置规格生成并验证”或在失败版本输入“分析并修复失败版本”。当前状态/目标由消息记录固定，历史浏览不会被实时结果强制覆盖；点击操作卡查看实时过程/本次结果。
6. 顶部切换 AES 加密、AES 解密或 SDC，查看各自真实模块、RTL、PASS 报告和 DUT/Reference 波形。SDC 可在“时间刻度”输入 `70000` 并跳转。这些案例没有归档可比较的修复前波形，因此只显示最终验证。

E203 默认是最终 PASS（0/222）；“修复前 · trial 5”的 1/222 是另一个历史 RTL 版本。三个新增案例的报告有明确 `system_verify: PASS`，但未输出采样总数，因此显示“报告未记录采样统计”；不将缺失统计当作失败，也不填造数字。

首版为四个固定案例、三类操作、固定关键波形，不支持规格上传、任意 shell、在线编辑或新建项目。单案例 CLI 命令可用 `--case e203|aes_cipher_system_hard|aes_inv_cipher_top_system|sdc_controller_system`，实时依赖仍由现有环境提供。

## 自动化检查

```bash
.venv-web/bin/python -m pytest tests/rtl_web/ -q
npm --prefix web/rtl-demo test
npm --prefix web/rtl-demo exec -- playwright install chromium
npm --prefix web/rtl-demo run test:e2e
npm --prefix web/rtl-demo run build
```

Linux 浏览器需 Playwright 对应系统库与中文字体。本机浏览器缓存、解包依赖和截图仅用于本地验收，不作为部署配置。普通测试不调用收费模型、不 SSH、不写生产目录。API/浏览器测试需要本机 socket 权限。

验收包括：真实历史计数与来源、错误 hash/继承波形拒绝、carry-in/x/z/变化数上限、10轮替身对话与证据跳转、幂等冲突、跨会话隔离、超时子进程组回收、API 重启不重跑、design-only 发布/回滚。替身通过不能代替真实模型调用。

## 服务器部署

生产使用 [002 同机部署指南](../002-secure-agent-deploy/quickstart.md)及[运维说明](../../deploy/rtl_demo/RUNBOOK.md)，在39.107.243.176部署受限系统服务并由Caddy代理127.0.0.1:8000。无需另一台机器的私网地址。仅变更design，主站/www/CAD保持原服务；root权限、实际容量及全部正式域名验收未通过时，不认定上线完成。
