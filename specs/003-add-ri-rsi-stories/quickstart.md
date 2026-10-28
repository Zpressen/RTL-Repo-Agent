# Quickstart：本次范围的验证指南

本文件对应已实现的三页界面、经验账本和导入命令。本轮按用户最新要求只完成代码、测试与本地候选封装，真实 A/B 修复和公网更新暂缓。PPA 数据未提供，本次不安装 PPA 工具、不生成候选、不测量、不验收收益曲线。

> 最新展示调整：经验入口现为“自进化 · RSI”，主体是可点击的五步机制构想，工程经验记录在折叠区。下文关于真实闭环的步骤仍是后续实证指南，不作为浏览该概念页的前置。当前已发布到 https://agent.deepvalleychip.cn/（evolution-20261019-r1）；旧 r4 候选包不包含本次后续调整。

## 1. 前提与环境

- 在仓库根执行命令；使用现有 Web/Agent 独立环境与锁文件，不全量升级依赖。
- 已有本地配置 `configs/rtl_demo.local.yaml` 及私有模型环境文件；保持秘密在现有私有文件内，命令和文档不填真实密钥。
- 本地历史案例与原验证资源按既有配置准备；经验材料先在资源足够且执行准入就绪的受控环境采集，不因演示关闭门禁。
- 下文 `$STORY_WEB_CONFIG`、`$STORY_REVIEW_INPUT` 等均是维护者设置的文件路径变量，不是现有秘密或仓库自带真实样本。

已有启动器（现在已存在）：

```bash
bash scripts/rtl_demo/run-local.sh \
  --config configs/rtl_demo.local.yaml \
  --env-file .rtl-demo/runtime.env
```

本地浏览 `http://127.0.0.1:5173`。启动器会导入历史案例并启动 API/worker/Vite；它不自动生成新 PPA 或经验链。要强制确认问答依赖，在上述命令增加 `--require-chat`。若本机使用其他私有环境文件，以实际路径替换，不把内容写进公开配置。

## 2. 代码验证

Web 与 Agent 分别使用各自环境。测试不得默认使用真实模型或启动真实修复。

```bash
.venv-web/bin/python -m pytest tests/rtl_web -q
npm --prefix web/rtl-demo test
npm --prefix web/rtl-demo run build
npm --prefix web/rtl-demo run test:e2e -- tests/e2e/stories.spec.ts
```

私有 ledger/adapter 测试使用实际 Agent 测试环境解释器运行，例如：

```bash
"$STORY_AGENT_PYTHON" -m pytest tests/test_rtl_memory_ledger.py -q
```

验证重点：旧 v1 seed、v2 roundtrip、额外历史运行解析、经验不变性、accepted+FAIL、使用声明无 diff、回滚、跨会话拒绝、resume 快照变化拒绝。Playwright fixture 只证明显示和边界，不作为投资人材料。

## 3. 无 PPA / 无经验材料也能浏览

使用原四案例数据启动后：

1. 检查“设计工作台 / 持续优化 / 经验闭环”三个主导航和跨页对话；工作台保留架构/代码/验证三个内部标签。优化页显示“PPA 数据待接入”，没有数字、曲线、改善率或执行按钮。
2. 未导入故事的案例显示经验空状态，不能复制 E203 内容。切换案例、刷新、切回验证，原报告和 DUT/参考波形可打开。
3. 监听网络请求：打开、刷新、跨页或切内部标签均不触发问答 POST 或 operation POST；访客主动发送提问时才调用模型，导航不重复创建会话或消息订阅。
4. 在 1366×768 检查页面无横向溢出，对话仍可输入；已加载页面/标签切换 95% 在 1 秒内完成。
5. 分别直接打开 `http://127.0.0.1:5173/?case=e203#/workspace`、`#/optimization` 和 `#/experience`，刷新保持页面。旧 `?case=e203` 仍进入工作台；使用前进/后退恢复页面与有效选择，不需要新增 Caddy 配置。

预期：UI 可以验收；PPA 标延后，经验真实闭环仍未验收。

## 4. 准备真实经验闭环材料

此步骤会使用真实 Agent 和仿真资源，必须显式人工发起并记录成本；不由打开页面触发。沿用现有受控修复运行入口，工具与输入约束见 `contracts/memory-runtime.md`。

1. 核查 E203 旧卡片及原始日志：无法证明的验证标签降为未核实。选择有真实来源的 A，或在合适环境执行实际来源运行，保存完整输入/版本/报告/波形。
2. 从客观结果形成 v1 草稿，经维护者审核。CLI 已实现，但本轮不采集真实材料：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli review-memory \
  --config "$STORY_WEB_CONFIG" --case e203 \
  --source "$STORY_MEMORY_REVIEW" --dry-run
```

校验通过后去掉 `--dry-run`，追加审核版本及生命周期。review manifest 的来源、清洗与权限要求见 `contracts/evidence-package.md`；不得从网页公共输入接收这些路径。

3. 发起独立运行 B，确认 descriptor/job manifest 固定 v1 快照；实际调用记忆 query/read，声明采用、产生真实相关 diff、执行验证。外部/内部 run ID 映射和 candidate 绑定可检查。
4. 检查最终版本和复验，而非只看 accepted。失败或回滚也照实归档。
5. 根据 B 或后续真实边界证据产生 v2/retirement，再审核。无修订依据不编造情节，保留 partial；v2 未再使用显示待验证。

通过条件：至少两个独立真实运行、一条实际使用后验证链、一次有据修订/淘汰，均可恢复固定 revision 和证据。没有同条件对照时收益仍待验证。

## 5. 审核导入与历史发布

先组装经维护者审核的 story manifest，引用上述真实材料。按 [evidence-package.md](contracts/evidence-package.md) 执行：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli validate-stories \
  --config "$STORY_WEB_CONFIG" --case e203 \
  --source "$STORY_REVIEW_INPUT"
.venv-web/bin/python -m zerorepo.rtl_web.cli import-stories \
  --config "$STORY_WEB_CONFIG" --case e203 \
  --source "$STORY_REVIEW_INPUT" --dry-run
```

预检通过后显式导入并激活本案例公共根：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli import-stories \
  --config "$STORY_WEB_CONFIG" --case e203 \
  --source "$STORY_REVIEW_INPUT" --activate
```

相同 ID/内容重复导入应幂等；修改内容保留旧 ID、缺引用、伪造 owner/运行、路径穿越应整体失败且 active 根不变。已审核材料只证明审核范围，不能用布尔 approved 替代人工审查。

既有导出命令已支持故事闭包，输出目录应尚不存在：

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli export-seed \
  --config "$STORY_WEB_CONFIG" --out "$STORY_SEED_OUT"
.venv-web/bin/python -m zerorepo.rtl_web.cli export-static \
  --config "$STORY_WEB_CONFIG" --case e203 --out "$STORY_STATIC_OUT"
```

有 active story 时 seed 为 v2，原四案例和新故事的额外历史代码/验证/波形闭包都在；静态只有 display 内容，无私有日志、参考私有源码或内部路径。API 与静态 story ID/fingerprint 一致。

## 6. 页面与真实问答验收

选中经验，追溯来源 A → 固定 v1 → 实际使用 B → 后续验证 → v2/淘汰依据；逐个打开正确版本代码、报告和真实波形。有材料未公开时明确说明，不把私有 URL 暴露给浏览器。

主动发送至少两轮真实问题，例如“这条经验实际用到哪里，有什么依据？”及“目前有 PPA 改善数据吗？”。第一问引用当前可访问材料并保留验证层级；第二问明确 PPA 待接入，不生成面积、时序或功耗成绩。真实问答沿用已有授权模型配置，本指南不默认执行。

在经验页输入未发送草稿，进入优化页再返回，草稿、消息和当前会话保留；问答进行中导航不取消或重复发送。在经验页点击证据进入工作台准确验证/版本，后退返回原经验选择，刷新也能恢复。公开链接的 URL 只含公开证据 ID，不带私有会话信息；显式失效链接显示缺口，不替换成最近 PASS。

换独立浏览器会话不能读到前者私有对话/任务。把第二个归档 run 打开到验证页仍标历史；快速跨页/切案例时不被旧请求覆盖。断开 API 后公共历史可看，聊天不返回假成功。

## 7. 验收记录与后续服务器发布

分别记录 UI、经验链、真实问答、四案例回归及隐私检查；PPA 项记录“按用户要求延后”，不能勾成已完成。收益对照未做则记录未验证，不计算学习加速。

实施发布仍走现有 release/seed/静态流程与服务器预检，仅更新 Agent 站，不新开端口、不改 design 原站。不整体复制仓库或旧封存包覆盖当前有效修复。发布前保留旧 release/seed，先校验新清单，再切换并检查四案例、波形及对话；失败回退对应发行版及根，不覆盖会话数据库。

未来接入 PPA 时再扩展 schema、导入器和图形，并落实 FR-004～009、SC-002/003；本指南不安排 EDA 安装或测量命令。


## 8. 本轮候选包（仅本地）

`deploy/rtl_demo/package.example.yaml` 的目标已绑定 `https://agent.deepvalleychip.cn`。复制到私有目录，设置实际 runtime_config、dist、oracle_root 的绝对路径后执行：

```bash
.venv-web/bin/python scripts/rtl_demo/deployment.py build \
  --config .rtl-demo/deployment/ri-memory-package.yaml \
  --release-id ri-memory-20261019-r1 --out /tmp/rtl-demo-ri-memory-release
python -S scripts/rtl_demo/deployment.py check \
  --release /tmp/rtl-demo-ri-memory-release/ri-memory-20261019-r1
```

构建器要求输出在仓库外；私有索引放在 `.rtl-demo/deployment/ri-memory-release/`。五层为 design（静态产物的层名称，不代表发布到 design 域名）、runtime、seed、verifier、ops。没有审核故事时输出原 v1 seed 和经验空状态，不伪造 v2/闭环。

当前旧安装器针对 design 的 activate 已拒绝 Agent 目标，避免覆盖独立旧站。此包不自动更新现有 `rtl-demo-public.service`；未来线上更新须保留现有私有配置、会话库与 Caddy 路由，按 RUNBOOK 的 Agent 更新边界执行。当前没有上传、切换或新增端口。
