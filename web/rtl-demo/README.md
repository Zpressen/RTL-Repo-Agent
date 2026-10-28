# RTL Studio

四个预置案例、三个页面的 RTL Agent 演示前端。顶部下拉框切换 E203、AES 加密、AES 解密、SDC 控制器，保留各自的对话。源码采用原生 TypeScript 和 CSS，无 UI 框架。

从仓库根按 [本地指南](../../specs/001-rtl-agent-demo/quickstart.md) 创建 Web 环境，运行 `python -m zerorepo.rtl_web.cli prepare-cases --config configs/rtl_demo.local.yaml --out web/rtl-demo/public/cases` 导出真实历史包，再运行 `npm --prefix web/rtl-demo run dev`。`/api` 开发代理默认访问本机 8000。构建用 `npm --prefix web/rtl-demo run build`，部署完整 dist。

后端未连接时读取 `/cases/index.json` 和 `/cases/<case_id>/manifest.json`，保留真实历史代码、报告和波形；对话/执行没有离线替身。SDC 波形按真实时间窗口加载，避免截断长波形。测试中的模型替身不导出到产品。

部署与当前验收状态见 [部署方案](../../specs/001-rtl-agent-demo/deployment.md) 和 [实施记录](../../specs/001-rtl-agent-demo/validation.md)。

当前页面入口：`#/workspace`（架构/代码/验证和波形）、`#/optimization`（PPA 数据待接入）、`#/experience`（自进化机制构想及折叠的工程记录）。页面间共享对话和草稿，历史公开链接可刷新恢复。PPA 尚无实测数据，经验没有材料时保持待准备；代码测试 fixture 不作为公开材料。

经验审核、导入和发布包命令见 [本次指南](../../specs/003-add-ri-rsi-stories/quickstart.md)，实际验证和暂缓事项见 [本次实施记录](../../specs/003-add-ri-rsi-stories/validation.md)。本轮按用户要求只完成代码，不执行真实 A/B 修复或更新公网。

用户最新展示口径：自进化页面先讲观测、评估、记忆、改进、再验证的机制故事，以场景推演解释方向；具体工程依据移至折叠区，不要求先完成真实闭环才能浏览概念说明。页面标注机制构想，未编造落地成果或提升数据。

当前公网自进化概念版：`https://agent.deepvalleychip.cn/?case=e203#/experience`，发行版 `evolution-20261019-r1`。三页、波形与访客隔离已在公网验证，真实问答验收仍待本次外发授权；未运行生成/修复。
