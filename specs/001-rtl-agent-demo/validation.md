# 实施与验证记录

日期：2026-10-15。范围：本地实现和验收；未连接、修改或发布公网服务器。没有改动现有 RTL Agent 算法、原始 rtl_outputs、数据集或 RealBench 文件。检查清单 requirements.md 为原有 16/16，通过的是规格质量，不是实现完成证明。

## 已实现

- 原生 TypeScript / Vite 单页，左侧常驻对话，右侧架构、代码、验证三个标签；规格摘要、只读 RTL、历史播放/暂停/继续、修复差异、真实 SVG 波形。
- FastAPI 适配层、独立 SQLite WAL 账本、单执行 worker 和独立 Agent 子进程。问答沿用 LLMClient/Memory；verify / generate_and_verify / fix 分别调用 SystemSimReviewer / PlannerRunner / SystemDebugRunner。
- 幂等键、全局执行槽、会话隔离、SSE 补发、刷新恢复、进程组超时回收、不可变完整 RTL 快照及报告/VCD 绑定。API 重启不重新提交执行。
- 仅 design 静态发布脚本、完整文件清单、dry-run、备份和回滚；私网后端 systemd 与 Caddy 示例。脚本不改主站/www、原部署脚本或完整 Caddyfile。

## 环境与命令

本机 Python 3.13.11、Node 24.14.0、npm 11.9；轻量环境 `.venv-web` 与现有 Agent 解释器独立。实际依赖以 requirements-web.txt 与 package-lock.json 为准。没有升级根 requirements.txt。

```bash
.venv-web/bin/python -m zerorepo.rtl_web.cli import-case --config configs/rtl_demo.local.yaml
.venv-web/bin/python -m zerorepo.rtl_web.cli export-static --config configs/rtl_demo.local.yaml --out web/rtl-demo/public/cases/e203
.venv-web/bin/python -m pytest tests/rtl_web/ -q
npm --prefix web/rtl-demo test
npm --prefix web/rtl-demo run test:e2e
npm --prefix web/rtl-demo run build
```

API 与浏览器需要本机 socket/线程唤醒权限：沙箱中的 TestClient 卡在 anyio portal；同一测试在沙箱外正常完成。浏览器使用 Playwright Chromium，在 `/tmp` 解压 libnspr4/libnss3 与中文字体供本机验收，无系统安装修改。截图是界面检查，模型替身仅用于契约测试，不属于投资人演示证据。

## 真实历史证据

- bundle：`e203-demo-v1`，9 个规划模块、9 次候选验证（包含语法失败）、before/after 两份完整 RTL 树、候选验证两份及独立最终复验一份。
- before：trial 5，`candidate_ea234d9c8dd7/revision_001`，1/222，失败采样位于 1125 ps，信号 `wbck_o_wdat`。
- after 候选：trial 9，`candidate_e0e2441d4dfd/revision_001`，0/222。
- 最终系统复验：`codex_private/final_sim_output.json` 与 `codex_private/final_verify/wave.vcd`，0/222；核对 accepted_baseline 完整 RTL 树。
- before RTL 树：`8038533f629ab7132ee1acfb75836ccdfa0020ef04721e07b799810f4d2cbcb9`。
- after RTL 树：`c1b96536ca58900a26ec5d31d3ef9b494ba1cd8f78380a78fd2d348466f8812b`。
- before VCD：`7b1f0334e90e737a7d007a3fa7fc1ecbc5fa5200276d4c473654e9d1d8050389`。
- after/final VCD：`798397b37c1c87dc1b5aa2d8d9797fbccc8e7f3e31089da21635cbf96e1a6a8a`。

统计解析唯一总行，重复 Hint 不重复累计。基于 3488 bit stats1 中 clocks/errors/errors_<signal> 的增量还原 222 个采样，before 仅一次失败；不以原始 tb_match 或原始值是否相等生成失败。after 的 1125 ps 原始 DUT/REF 数据不同仍照实显示；`sampled_value_available=false`，游标不是活动区比较快照。错误布局、计数冲突、继承 VCD、哈希不符均有测试拒绝或限制。

历史绑定等级是 recorded_candidate；不宣称已还原当时全部外部依赖。原始私有会话、Codex 工作目录与原始 VCD 留在计算后端；静态包只发布白名单元数据、RTL、脱敏报告和真实固定信号数据。

## 本次真实执行

第一次独立 verify：

- operation：`op-f35e90ac3a2f4e2998c29c0b5deb3505`
- run：`run-4102c80e8e944cc282a7bccc0aa1bf63`
- validation：`run-4102c80e8e944cc282a7bccc0aa1bf63-final-check`
- 最终 PASS，0/222，产生真实 VCD，RTL 在独立工作区中运行。

第二次独立 verify（完整输入指纹归档）：

- operation：`op-b9c2c44246fe47febeb39540958a0d4a`
- run：`run-ece41de5db5c4bdab933c7f748e48458`
- validation：`run-ece41de5db5c4bdab933c7f748e48458-final-check`
- RTL 树与历史 after 相同；VCD SHA256 与历史 final 相同；最终 PASS，0/222，marker verified。
- input manifest / verifier fingerprint：`c49f4d430b05b73d4bd42af9ad44c52c51f24bf9b8f7873d74df41239d7fcd9c`。
- 指纹文件包含完整 RTL 文件清单、规格摘要、受信 verifier/TB/参考源码摘要、包装器/Reviewer 摘要、Python/Verilator/g++ 版本和超时配置；artifact 为私有，验证记录引用其 ID。
- API 接收请求实测 58ms；SSE 收到本会话事件。长仿真期间两次客户端轮询发生 10/15 秒超时，重连后可恢复并查到归档结果；尚不据此宣称 SC-004 全过程响应达标。
- 独立 HTTP 探测：health/case/session 请求 2–23ms；SSE 断开后重新查询会话三次均为 2–3ms。API 重启未使 worker 重跑或改变最终结论。

真实问答尝试未通过：现有私有配置使用 `${ZEROREPO_API_KEY}`，当前服务环境未注入该变量。没有借用其他进程的凭据、切换模型或用固定回复替代。已修正现有 LLMClient.generate 的 max_retries=0 导致不执行调用的问题，现在设为一次尝试；子进程有独立超时与脱敏诊断。

沙箱外无付费预检：replay=true、verify=true，KG 连通、Codex CLI 登录可用；chat/generate/fix 因 model_credentials 缺失而不可用。注入既有凭据后需要重新 preflight，再完成真实问答和生成/修复验收。

## 待完成的环境验收

- T025：10 轮接口/浏览器契约与真实 verify 已验证；真实模型问答尚未成功。
- T042：生成与修复适配层有替身调用边界测试，尚未执行有凭据的真实生成/修复；不能用历史修复或替身结果代替。
- T043/T044：尚缺大内存服务器私网地址、网关连通方式、服务用户/安装路径及 root 发布条件；尚未 SSH、部署或改 Caddy。
- 最终 SC-003/004/009 不能认定完整通过；最终全量交付 T048 保留未完成。

## 自动化验收结果

- `pytest tests/rtl_web/ -q`：30 通过。包含 10 轮带固定 context 的 API 问答替身、虚构证据 ID 过滤、跨会话 run 拒绝、全局执行槽、幂等冲突、事件游标补发、API 重启保留 worker 状态、worker 超时、独立 setsid 子进程回收、多 revision 候选与持久回滚、完整输入副本、五类结论边界、波形 x/z/缺信号/错误布局/范围限制、design-only 备份与回滚。
- `npm test`：Vitest 3 通过，覆盖 carry-in/x/z、巨大整数 tick 精度、缩放与范围不可比。
- `npm run test:e2e`：Playwright 4 通过（1366×768）。10 轮对话、依据跳转、刷新不重发、真实静态历史/报告、播放/暂停、全部回放、两次点击定位、修复前后窗口保持和游标。
- 实测首屏 302ms；首次到最终独立复验显示 20,600ms，回放全部定时计划为 21,300ms。计时是本地历史展示，不代表 Agent 生成耗时。
- 现有 Agent 回归：`python -m pytest tests/test_system_debug_runner.py -k 'uses_dataset_project_to_locate_verifier or accepts_system_suffixed_planner_top or preserves_wave_vcd_from_verifier_tempdir or missing_verifier_is_error' -q`：5 通过，9 未选中；没有调用模型。
- 前端 TypeScript 检查及 Vite build 通过；无 UI 框架、路由器、在线编辑器。生成 JS 约 27KB（gzip 约11KB）；历史证据另作为静态数据加载。
- FastAPI/Starlette 测试客户端给出 httpx 弃用提示；测试全部通过。未据此升级现有 Agent 环境。

最终预检进一步核对指定 Codex profile 后，backend 检查未通过；此前的 CLI 可执行/登录检查不足以证明 profile 可用。生成/修复必须准备现有配置指定的 profile，再重新预检，不能静默切换 profile。当前已核实 KG 可连接、verify 可执行；模型凭据仍缺失。

## 逐项需求登记

“部分”表示代码/替身边界已验证，但缺少对应真实执行或环境验收；不视为完整交付通过。

| 条目 | 状态 | 证据或限制 |
| --- | --- | --- |
| FR-001 | 通过 | 单页、常驻对话、三标签、摘要；1366×768浏览器验收 |
| FR-002 | 通过 | 真实9模块规划、模块职责、只读RTL；点击跳转验收 |
| FR-003 | 通过 | 真实13条历史事件、播放/暂停/继续、未记录原始时间说明 |
| FR-004 | 通过（本地） | 历史/实时标识、实际 verify 操作卡及独立 run |
| FR-005 | 部分 | 10轮上下文接口/浏览器通过；真实模型问答未通过 |
| FR-006 | 部分 | 有效证据引用白名单/跳转通过；真实模型回答质量待验收 |
| FR-007 | 部分 | 三入口适配/白名单/澄清边界通过，真实 verify 通过；生成/修复待凭据/profile |
| FR-008 | 部分 | 真实接收/阶段/终态记录；长仿真期间轮询时延待现场验收 |
| FR-009 | 通过 | 原子全局执行槽、busy和同键异payload冲突测试 |
| FR-010 | 部分 | 真实 verify 复用既有 Reviewer/独立副本；其他两入口有适配测试 |
| FR-011 | 部分 | 候选 revision/快照/diff/accept/rollback实现与测试；真实修复尚未执行 |
| FR-012 | 通过（已有与本地verify） | 历史 recorded_candidate、实时 full_input_manifest，RTL/report/VCD绑定 |
| FR-013 | 通过（已有与本地verify） | 两次独立最终复验；merge/退出码/语法结果不能赋最终PASS |
| FR-014 | 通过 | 真实1/222和0/222、9次候选、内部重复提示计数单独说明、原始报告入口 |
| FR-015 | 通过 | 真实固定11信号、缩放/平移/游标、原始x/z与位宽 |
| FR-016 | 通过 | 1125ps、wbck_o_wdat、stats1采样标记，未按raw值重写结论 |
| FR-017 | 通过 | before/after窗口保留；范围外拒绝/提示、缺失信号不补造 |
| FR-018 | 通过（自动化及局部真实） | 静态后备、幂等/刷新/超时/重启测试；实际轮询超时后归档仍可恢复 |
| FR-019 | 部分 | 真实verify前后输入摘要不变、隔离副本；生成/修复真实只读检查待验收，服务模板只读挂载 |
| FR-020 | 通过 | 中文DUT/Reference说明、当前测试范围、文字状态 |
| FR-021 | 待部署 | Caddy/systemd/发布工具已写，私网与生产访问未验证 |
| SC-001 | 通过（本机） | 302ms首屏，1366×768可操作、8个子模块首屏可见 |
| SC-002 | 通过 | 20.6秒显示最终结果、21.3秒回放计划，小于3分钟 |
| SC-003 | 部分 | 10轮替身与上下文通过；真实回答证据质量待模型凭据 |
| SC-004 | 部分 | verify接收58ms，其他入口和长仿真全过程响应仍待验收 |
| SC-005 | 通过 | 验证标签→定位差异两次点击，切换后保留1045–1205ps窗口 |
| SC-006 | 通过（边界自动化） | PASS/FAIL/无报告/语法/绑定冲突的必要测试 |
| SC-007 | 通过 | 真实222采样、0差异；切换trial5后1差异 |
| SC-008 | 通过（自动化及局部真实） | 幂等、刷新、断连补发、依赖缺失、超时；不自动重跑 |
| SC-009 | 待部署 | 尚未在受保护域名执行真实问答与复验 |

## 收尾复核

- 最终本地预览运行在 `http://127.0.0.1:5173/`，API 仅监听本机8000，独立 worker 已启动。
- 使用真实 API 和真实会话打开第二次 verify 的操作卡：显示“实时执行结果”、独立复验0/222、对应真实VCD；报告内有 system_verify: PASS，浏览器 pageerror 为0。此检查未再次发起模型或仿真；截图位于 `/tmp/rtl-studio-live.png`。
- 最新预检明细：backend_cli=true、backend_auth=true、backend_profile=false、kg=true、model_credentials=false；没有将“能找到CLI/已登录”当作指定profile已就绪。
- 最后会话恢复/模块选择改动后，访问边界2项与对话/波形浏览器2项复测通过；TypeScript/build再次通过，构建JS 26,437 bytes。
- `stage-release.sh ... --dry-run` 在本机验证完整dist，共33文件；shell语法与Python编译检查通过。未写 `/srv` 或任何服务器目录。
- `git diff --check` 通过；没有提交或发布代码。原有用户未跟踪目录未删除或覆盖。
- `.specify/extensions.yml` 不存在，无 before/after implement 扩展hook可执行。
- 任务进度：42/48。6项未完成均明确保留：T025、T042、T043、T044、T046、T048。

## 2026-10-16：E203 结论核对及三个新增案例

用户直接运行 E203 `merged` 的结果为 PASS（0/222），与本工作台此前两次真实独立复验一致。页面中的“修复前 · trial 5”对应另一份历史候选，真实失败1/222；最终版本仍为通过。当前 merged 的核心模块与 accepted/final 历史树一致，仅多出 config.v，不能因整树摘要不同就否认其验证结果。已增加明确的历史失败说明及“查看最终通过结果”按钮，默认仍展示最终复验。

另修正系统报告解析：AES/SDC 的真实归档输出含 `system_verify: PASS`，没有 Hint 总数行。旧解析会将其归为 unverified；现在受信验证器明确结论有效，采样总数与不匹配数保持 null，页面标明“报告未记录采样统计”。已有非零不匹配、FAIL 或编译错误仍不能被 PASS 覆盖。

新增案例的规格、规划、受测 generated 完整树、输入清单、报告、VCD 和 testbench SHA256 归档在 `configs/rtl_demo_cases.evidence.json`。全新独立工作区复用现有 SystemSimReviewer，三个实际执行均完成 PASS，marker_status=verified，实际 VCD 与对应历史来源 SHA256 一致：

| 案例 | 本次真实 validation_id | RTL SHA256 前缀 | VCD SHA256 前缀 |
| --- | --- | --- | --- |
| aes_cipher_system_hard | run-3f05bb15c66a4fa98d4d320015a86b6a-final-check | 28c7a1c71c2e | 995f70de59b7 |
| aes_inv_cipher_top_system | run-1297d31513724fed8c18765b69e170e5-final-check | 73da5c913bd4 | da61cb066237 |
| sdc_controller_system | run-0219db46668b462c996dd3121bf51a37-final-check | 51435ffc2ae4 | 94285e1f5ac2 |

本次完整输入清单指纹分别为 `3b2343ef0d46031c9fe4fd8fedf7feb3a247372310060c5d555d6aca98432b91`、`444043fc9182dc7e1f04631225cd704265dd9ed537bfe30e227a525b14033a39`、`d501469c8ee52f8e02f86eb4c97ca07bdbbb868ae9f0b9c95636dcd4c2d25d5e`。本地操作记录位于忽略目录 `.rtl-demo/catalog-live-validation.json`；原始输入和产物保留在各自 run 下，没有调用模型或修改原 RTL/参考设计/测试平台。历史包保持 recorded_candidate，实际新验证使用 full_input_manifest，两者不互相冒充。

界面只增加顶部任务选择器，仍是常驻对话和三标签。各例使用独立会话、cookie 和上下文；跨案例操作、同幂等键切换案例会被拒绝。AES/SDC 显示各自真实信号组，不借用 E203 的写回信号。三个新增案例只归档最终结果，无修复前配对和候选次数，不生成虚构修复故事。AES 加密的历史归档缺少完整 stage1 契约，直接修复该历史版本会明确要求从预置规格新建运行，不将空 io 的残缺契约作为完整接口使用。

SDC 的真实波形到119660ps，解析23932个采样标记，无失败。静态导出为4个精确时间窗口，各窗口变化数不超过20000，浏览器可输入70000定位到69900–70100ps；未删除边沿或降采样。AES 两例同样按其真实 testbench 布局解析，而不是沿用 E203 stats1 布局。

追加验收：

- 后端 `pytest tests/rtl_web/ -q`：38通过，含真实四例导入、无统计 PASS/错误冲突、案例隔离、接口契约完整性及多案例发布回滚。TestClient 在受限环境卡于 asyncio 唤醒，改在允许本地 socket 的环境运行后通过；未改产品代码绕过访问约束。保留一条 Starlette/httpx 弃用提示。
- Vitest：3通过；TypeScript检查和Vite构建通过，JS约30.81KB（gzip12.54KB）。
- Playwright：6通过，覆盖新增三例切换、真实波形、SDC远端窗口、E203历史失败说明以及原对话/回放/波形回归。最终静态包版本更新后新增案例两项再次通过。首屏141ms，完整回放19624ms，计划21300ms；仅为本地展示时间。
- 发布 dry-run：完整dist共101文件；四例索引与各案例manifest均纳入发布，更新与回滚不会把它们误判为不可变内容冲突。只在本地临时目录测试；没有SSH、写生产目录或更改Caddy。
- 新增静态包使用独立bundle ID保存元数据变更，未覆盖已有不可变证据。浏览器截图保存在忽略目录 `web/rtl-demo/test-results/`。

使用更新后的 quickstart 导出四例，重启API/worker并刷新页面即可查看。原有模型凭据、指定Codex profile及服务器私网参数的缺失仍然存在，不宣称真实模型问答/生成/修复或线上部署验收完成。原6项待验收任务保留，新增T049～T053完成，总进度47/53。

## 2026-10-16：修复后台离线时无法输入对话

截图对应 `chat.ts` 中将 textarea.disabled 绑定到会话/后台连通状态的行为。已解除输入禁用；发送仍要求有效会话和连接。草稿按案例保存在 sessionStorage，刷新、切换任务、重连失败后不丢失；发送请求完成时仅清除原提交文本，保留等待期间输入的新草稿。

新增手动“重新连接”：首次静态后备后可恢复会话、health、事件订阅与轮询，保留当前浏览上下文，草稿不自动发送。轮询断开与恢复同步更新连接提示。中文输入法的 isComposing/keyCode 229 回车不会触发发送。

本次验收：Vitest 3通过，TypeScript检查和Vite构建通过，Playwright 8通过。新增两项覆盖离线真实可编辑、草稿刷新/案例隔离、重连失败、后台恢复后发送、IME确认不误发、等待响应期间编辑新草稿与刷新不重发。模型和传输使用测试替身，仅用于交互契约；没有声称完成真实模型问答。截图实测1366×768中输入框和重连按钮可见。只读探测本机8000当前无API监听，实际发送需按quickstart启动API；未改服务器或模型凭据。

## 2026-10-16：真实交互链路打通

上述“API未启动”和“模型凭据缺失”已在本次本机联调中解除。已启动真实API/单worker，沿用用户现有Vite；最终 `http://127.0.0.1:5173/api/health` 返回200，chat.available=true、verify.available=true、worker=true。生成/修复的指定Codex profile仍未就绪；线上尚未部署。

发现并修复真正的前后端契约问题：恢复会话时selection包含browsing_mode，前端将它展开进context_ref，真实API因extra=forbid返回422。上下文现改为明确字段白名单，浏览器会话恢复、发送消息和执行请求不再夹带页面状态。此前浏览器替身没有按真实API schema检查请求，因此没有捕获此错误；补充状态单测和浏览器请求断言，另做真实链路验收。

真实浏览器通过对话发送“重新验证当前设计”，API接受、worker实际仿真，网页打开本次实时结果：

- operation：`op-6bb850d56be24064ad99b7d05d7d4302`。
- validation：`run-978b3fa0ec774c7fbcbb5384479ee8ea-final-check`，PASS，0/222，binding_level=full_input_manifest。
- 输入指纹：`c49f4d430b05b73d4bd42af9ad44c52c51f24bf9b8f7873d74df41239d7fcd9c`；VCD：`798397b37c1c87dc1b5aa2d8d9797fbccc8e7f3e31089da21635cbf96e1a6a8a`。
- 本机记录 `.rtl-demo/live-interaction-verify.json`；截图 `.rtl-demo/live-interaction-verify.png`。没有使用验证替身。

用户指定的模型配置起初为环境占位符，后已包含实际凭据；直接沿用该配置，未替换模型或端点。经用户明确批准向 `https://www.inroi.shop/v1` 发送当前设计证据进行两轮问答。真实验收发现上游stream错误及追问非JSON格式问题后，Web问答采用完整JSON响应、一次有界传输重试，历史assistant按同样JSON格式传递。现有OpenAI兼容客户端新增可选response_format透传，未配置时保持原有行为；原Agent流式接收与重试语义仍通过回归。

最终连续两轮均answered，每轮2个合法证据引用：第一轮解释E203职责，第二轮结合上下文正确指出 `e203_exu_muldiv`。session为 `session-48c9717a53304e2ebe6bc3d12825df67`，message分别为 `message-00abcf855cc34d689028e80df9cda833` 和 `message-faf9df05ab134919b69fabf1ad2dac63`。刷新后回复仍在，page_errors=[]；记录 `.rtl-demo/live-chat-check.json`。真实两轮证明问答可用，不等同于原T025的完整10轮验收全部完成。

新增 `scripts/rtl_demo/run-local.sh`：同一环境预检、导出四例、启动API/worker/Vite；`--no-web`复用已有Vite，`--env-file`支持需要环境变量的既有配置，`--require-chat`阻止问答依赖不齐时当作完整演示启动。环境文件不执行shell，日志权限600，退出只清理本次启动的进程组。已实际用 `--no-web` 启动并保持本机API/worker在线。API设置8秒优雅退出上限，避免事件长连接无限阻塞服务重启。会话恢复时滚动到最新消息，并验证其位于可见区域。

追加检查：Web后端40项通过；Agent SDK/问答格式回归19项通过（MockTransport，不产生外部请求）；Vitest4项通过；浏览器全量8项通过，最终滚动修复后对话/重连3项再次通过；TypeScript/build与shell语法、编译、diff检查通过。原有datetime.utcnow及Starlette/httpx弃用提示保留。静态包已在本机暂存，未写服务器目录。

线上复核：首次SSH严格校验因无已知ED25519记录失败；随后用独立 `.rtl-demo/ssh_known_hosts` 和accept-new建立首次记录，后续strict=yes连接成功。实际Caddyfile证实design当前只有静态文件服务，没有/api反代；注释的10.0.0.10:3000为示例。公网机2核/1870MiB，内网地址172.16.220.253；28989实为CAD Responses API，不属于RTL服务，未改动。dev账号sudo需要密码，因此/etc/caddy和/srv的发布仍需root按handoff处理。域名HTTPS探测在本执行环境TLS握手失败，不能据此断言用户站点离线。

完整静态发布包已实际上传到 `/home/dev/deepvalleychip-site/releases/interactive-20261016-r2/design/`，远端用release.json逐一校验101文件SHA256均通过，包含四例正确bundle指针；没有上传模型配置/密钥，未切换Caddy服务目录或修改线上路由。handoff没有大内存计算机的实际地址或连通方式，需要补齐后才能接入私网API并经design域名完成真实问答/仿真验收，不能将本机成功写成线上成功。
