# Phase 0 Research: RTL Studio 参考页面改版

日期：2026-10-20。只读核对当前代码、四案例包与参考稿；未调用模型、未运行生成/修复、未访问服务器。按 speckit-plan 分别开展前端布局/状态兼容与公开证据导出研究，并将结果合并如下。

## R1 — 沿用现有技术和目录

**Decision**：继续使用 `web/rtl-demo` 的原生 TypeScript DOM、Vite 和 `zerorepo/rtl_web` FastAPI。参考稿仅提供布局、样式和交互层级，不复制其 React/design-component 运行时。

**Rationale**：现有 architecture/code/verification/waveform/chat 已具备主要能力；参考目录 README 明确为设计参考稿。切框架并不能补充工程数据。

**Alternatives considered**：直接托管 Demo.dc.html 会留下示意波形、写死结论和无功能下载；引入 React 或新 UI 库会扩大改造范围。均不采用。

依据：`web/rtl-demo/package.json`、`src/workspace.ts`、`web/RTL Studio 演示-html/README.md`。

## R2 — 忠于三栏，移除 RI / RSI 导航

**Decision**：紧凑顶部栏和 3px 进度条下，采用左时间线、中证据、右指标/动态/对话。桌面列宽 `clamp(220px,18vw,250px) minmax(0,1fr) clamp(300px,24vw,340px)`；三栏间用边框分隔，中心内边距约 18–20px。1280 宽时中心仍约 670px，1440 时约 840px。低于 1100px 重排，窄屏折叠时间线、提供对话开关。

**Rationale**：与参考稿视觉一致，且可容纳五页签和输入区。右栏用受限高度布局，指标固定、动态可折叠、消息滚动、输入区不收缩。`chat()` 只创建一次。

**Alternatives considered**：保留旧站主导航和 hero 会偏离参考；直接堆叠全部执行动态会挤走输入区。均不采用。

依据：参考稿 header/main/aside、`styles.css`、`chat.ts`。字体优先系统中文字体和现有等宽字体，不新增 Google Fonts 网络依赖；品牌链接指向当前工作台，避免参考稿中不存在的 Main.dc.html。

## R3 — 八步是展示投影，不是新增执行流水线

**Decision**：新增纯数据适配层 `studio-model.ts`，从现有 Bundle/Run/Validation/事件构建八步。保留原事件 sequence、trial_no、source ref；语法和差异定位没有独立事件时明确区分“日志摘要”“报告整理”“未单独记录”。不为八步重写 worker，也不覆盖历史 bundle。

**Rationale**：E203 有 13 条回放事件、9 次候选检查，全部 observed_at 为 null。第 1/2 次为语法失败，后续为仿真差异/通过；详细 validation 仅导出 trial5、trial9、final。AES/SDC 主要是四条归档阶段事件，不能自动涂满八个完成状态。

**Alternatives considered**：按旧 stage 顺序将前序步骤全部设为完成会造假；重新导入并改写相同 bundle_id 会违反不可变归档约束。保留原 bundle，增加前端兼容投影。

依据：四案例 `public/cases/*/manifest.json`、`import_case.py`、`import_catalog.py`、`worker.py`。适配器可展示原事件明确写出的语法失败摘要，但不得靠模糊文本匹配生成“独立检查通过”。

## R4 — 统一五页签并兼容旧选择

**Decision**：统一 `Panel = spec | architecture | code | verify | repair`，旧内部 verification 归一 verify；后端扩展 Selection.workspace_panel，并在 Context 增加同名可选字段，让问题携带发送时页签。旧 Context.view 枚举保留读兼容，新请求固定 workspace。

**Rationale**：当前后端严格拒绝 spec/repair，前端单独改页签会导致保存失败；JSON payload 存储无需表结构迁移。现有路由还依赖 loadStories，应移除普通工作台对故事加载的依赖。

**Alternatives considered**：将 spec/repair 保存成旧 architecture/code 会丢失刷新位置；删除所有旧枚举会破坏已存消息。不采用。

旧 optimization/experience hash 用 replaceState 归一 workspace，保留经核对的 case/run/version/validation/module，移除 story/memory 选择，不加载故事内容。当前四案例静态故事索引 runs 都为空，现有随版有效工程证据全部位于案例包；额外服务端归档用现有 validation/run 接口加载，无静态材料时说明不可用，不静默退回最终 PASS。

## R5 — 复用波形与版本绑定，补证据展示缺口

**Decision**：复用 waveform.ts 的 SVG/BigInt/窗口读取和 api.ts 的 tile 合并/20,000 transitions 限制；补 spec.ts、repair.ts 和共享 evidence-selection.ts。RTL 文件树按 file_manifest 展示全量文件，规划模块计数只用 Bundle.modules。

**Rationale**：E203 规划 9 模块但快照有 10 文件，含 e203_defines.v。Version.modules 实际是文件到 artifact 的映射，也含定义文件，不能用于规划计数。当前历史差异只取首个变化文件，新修复页应列全量变更文件，保留 simpleDiff 的“对比片段”标注或使用已有服务端 unified diff。

**Alternatives considered**：手绘五格波形、只比较游标瞬时值或只显示一处补丁，不能代表现有测试平台结论。尤其最终波形在 1125ps 的组合瞬时值也可能不同，PASS 仍依报告与采样规则判断。

依据：`code.ts`、`verification.ts`、`waveform.ts`、`test_waveform_evidence.py`。前后 timescale 不同要换算到共同物理时间，不能复制原始 ticks。

## R6 — 对话生命周期与受控动态

**Decision**：保留每案例整页切换（location.assign）以复用现有 session/cookie 隔离；发送时捕获 case、session、context、幂等键。引用回调携带消息自己的 context_ref，而不是仅 artifact_id。订阅回调接收经允许的 SSE 正文，按 event id 去重，再刷新持久记录。

**Rationale**：当前 chat.ts 已支持 IME、防重复、pending 草稿和发送中新草稿；api.subscribe 目前丢弃事件正文，不能直接用于右侧动态。输入区不随页签重建，过晚返回不可覆盖当前会话。

**Alternatives considered**：新增浏览器全局共享会话或本轮改为 SPA 无刷新切案例会增大污染风险；将原始工具日志/思维过程直接输出也不符合公开边界。

问答模型不可用时，准确匹配现有三条显式操作句仍可根据对应 capability 发送；普通问题保留草稿并解释原因，后端仍为能力校验权威，不新增模糊执行判断。

还需同步解除后端故事依赖：当前 `chat.py:evidence()` 无条件调用 story_view，`chat_runtime.py:PROMPT` 将当前页面叙述为自进化概念页。新版 workspace 按 workspace_panel 组织规格/架构/RTL/验证/修复证据，不加载 story；仅旧的显式 story/经验上下文保留兼容分支。提示保留证据、采样、历史/实时及执行意图约束，移除当前页面为 RSI 的预设。使用可控 provider 检查 payload 和提示，不调用真实模型。

## R7 — 公开证据包与原始 VCD 边界

**Decision**：新增 evidence.py，使用标准库 zipfile，统一在线导出和 export_static 预生成。只接受同案例已公开历史验证及其公开材料，默认导出关键 waveform JSON 和全部 tiles；原始 VCD 不导出。RTL 按 file_manifest 全量验证并打包。正向字段清单见 contracts/evidence-package.md。

**Rationale**：原始 VCD 在 publish_validation 中归档为 private，seed 还含 contracts/audit 等私有内容。public() 仅移除部分字段，不能用作 ZIP 脱敏器。公开 ZIP 应复用已有 display 字节并校验来源，不导出整个 bundle/run 或 private seed。

**Alternatives considered**：浏览器聚合长波形会增加内存；直接下载 seed/整个目录扩大公开范围；新增原始 VCD 公布需要另行范围决定，均不采用。

当前 display artifact 总量约：E203 0.50MB、AES 加密 0.26MB、AES 解密 0.16MB、SDC 7.85MB。默认输入 64MiB、128 条目、在线生成并发 1、压缩等级 1 足够当前样例。使用私有临时文件和 FileResponse，清理覆盖成功、异常、断线和启动遗留，不用 BytesIO 汇聚全包。

## R8 — 静态降级和发布白名单一起适配

**Decision**：静态导出为每条公开详细验证和 E203 trial5→final 预生成 ZIP。只在导出的 manifest 增加 evidence_packages 索引，不修改不可变存储记录；包内 wave index 指向相对 tile 路径，重新计算导出字节 hash，同时保留源 artifact hash。

**Rationale**：后台不可达仍应浏览并下载历史材料。当前 release.py 与 deployment.py 均拒绝 .zip，必须同时增加限定 `cases/<known-case>/evidence/<safe-name>.zip` 的白名单及归档内清单、路径、hash、大小检查。

**Alternatives considered**：只补在线接口会在纯静态模式失效；泛开 .zip 后缀会绕过原部署检查。不采用。

本轮不执行部署。后续发布应同批更新前端、web 后端、静态证据索引/ZIP与发布检查脚本；沿用 agent 域名和现有 Caddy/私有配置，保留 data_root/session.key/state.sqlite3。

## R9 — 无模型验收

**Decision**：数据适配和 ZIP 使用本地归档或便携 fixture；对话与操作使用测试替身；浏览器拒绝所有未拦截的执行/问答写请求。更新旧 RI/RSI 导航测试为旧地址归一测试，保留后台记忆账本与证据隔离测试。

**Rationale**：用户已暂缓真实模型和修复验收；界面、绑定及下载测试不需要模型费用或真实仿真。

**Alternatives considered**：以线上真实问答、修复或 Verilator 重跑作为布局验收前置，既无必要也超出本轮授权。

所有研究问题已解决，无待澄清技术项。未发现需要新增数据库或前端框架的理由。
