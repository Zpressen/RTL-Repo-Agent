# Quickstart / Validation: RTL Studio 参考布局

日期：2026-10-20。本文是已实现版本的运行和验收指南；五页签、八步回放、对话契约与公开 ZIP 已完成本地验收，尚未上线。不得将测试替身作为投资人真实证据，也不需调用真实模型或运行 RTL 修复。

## 1. 前置条件

- 仓库根目录为 `/home/mokita/RPG-ZeroRepo`。
- 沿用现有 Node 与 `web/rtl-demo/package-lock.json`、`.venv-web` web Python 环境；无需新增前端框架或仿真工具。
- 四案例公开文件已位于 `web/rtl-demo/public/cases`。服务端归档验收需要现有本机导入数据或 tests 的便携 fixture，不需复制私有配置到公开目录。
- Playwright 浏览器及本机系统依赖已经准备。当前机器若需要，可使用已有 `PLAYWRIGHT_BROWSERS_PATH=/home/mokita/RPG-ZeroRepo/.rtl-demo/browser-cache` 和浏览器依赖目录；不要为了测试关闭 TLS 校验。
- 旧 RI/RSI 导航测试已更新为旧地址归一场景。Playwright 配置会自动复用本机 .rtl-demo/browser-cache 与已有浏览器依赖目录，其他环境可手动设置下面的变量。

## 2. 静态页面启动

```bash
cd /home/mokita/RPG-ZeroRepo
npm --prefix web/rtl-demo run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173/?case=e203#/workspace`。后台未运行时应自动浏览历史材料，输入仍可编辑，模型或执行不可用不影响查看。已有 5173 进程时复用原服务，不另启或终止用户的服务。

需要检查现有本地问答/操作接口但不发真实请求时，可使用此前已有启动器：

```bash
bash scripts/rtl_demo/run-local.sh --config configs/rtl_demo.local.yaml --env-file .rtl-demo/runtime.env
```

此命令仅用于后续集成检查，读取本机私有配置；不得展示其中内容。它不代表能力就绪；真实模型、生成与修复按钮本次不点击，自动化必须拦截这些写请求。仅静态改版预览不需要执行该命令。

## 3. 单元、构建及接口回归

```bash
cd /home/mokita/RPG-ZeroRepo
npm --prefix web/rtl-demo test
npm --prefix web/rtl-demo run build
.venv-web/bin/python -m pytest tests/rtl_web/test_case_import.py tests/rtl_web/test_access_boundary.py tests/rtl_web/test_chat_operations.py tests/rtl_web/test_waveform_evidence.py tests/rtl_web/test_catalog.py tests/rtl_web/test_deployment_package.py -q
```

同时运行新增测试：`tests/rtl_web/test_workspace_selection.py`、`test_workspace_chat.py`、`test_evidence_package.py`、`test_evidence_api.py`、`test_evidence_static.py`、`test_evidence_release.py`。预期：新 panel 可保存恢复；现有归档真实性、1125ps 采样标记、权限/脱敏不回归；下载能包含 defines 和 SDC 全部分片，同时拒绝跨案例、私有材料、篡改、危险路径、超限和额外 ZIP。

这些测试使用归档或 fixture；未准备本机来源而跳过的真实归档测试要单独记录，不能把 skipped 写成通过。无需安装 Verilator、启动 KG 或配置新模型凭据来验证本功能。

## 4. 重新生成公开证据材料

本机来源齐备且配置仍指向已有数据时：

```bash
cd /home/mokita/RPG-ZeroRepo
.venv-web/bin/python -m zerorepo.rtl_web.cli prepare-cases --config configs/rtl_demo.local.yaml --out web/rtl-demo/public/cases
npm --prefix web/rtl-demo run build
```

仅导入/导出归档，不运行生成和仿真。当前四案例已有共89个静态 ZIP（E203 46个单次、40个比较；其他各一个单次）和匹配的 evidence_packages 索引。后台不可达时这些 ZIP 仍可下载。实际私有源目录、runtime.env、数据库、raw VCD 和 seed 都不能被拷进 public。

已有便携历史 seed 的环境可沿用现有 import-seed 路径恢复私有归档后再 export-static；seed 本身不是访客下载格式。不要为了准备静态包重新运行 Agent。

## 5. 浏览器回归（无真实模型）

```bash
cd /home/mokita/RPG-ZeroRepo
npm --prefix web/rtl-demo run test:e2e -- tests/e2e/history.spec.ts tests/e2e/waveform.spec.ts tests/e2e/composer.spec.ts tests/e2e/chat.spec.ts tests/e2e/catalog.spec.ts
```

完整浏览器验收可直接运行 `npm --prefix web/rtl-demo run test:e2e`（29 个用例，包含完整修复过程、布局、旧链接、下载和隔离）。需要本机浏览器依赖时可在执行命令前使用：

```bash
export PLAYWRIGHT_BROWSERS_PATH=/home/mokita/RPG-ZeroRepo/.rtl-demo/browser-cache
export LD_LIBRARY_PATH=/home/mokita/RPG-ZeroRepo/.rtl-demo/browser-deps/extracted/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
```

Playwright 用例应明确覆盖 1440×900、1280×800、390×844。静态场景拦截 `/api/**`；对话/操作场景仅返回 fixture，禁止任何未拦截的 messages/operations POST。不使用线上模型验收脚本。

## 6. 人工验收路径

### A. 对照参考排版

- 分别在两种桌面尺寸打开参考稿和新版；检查顶部、细进度条、左八步、中五页签、右指标/动态/输入、深色卡片与绿色强调。
- 规格、架构、RTL、仿真、修复各保存一张新版截图，说明仅由真实案例、选择器和持续对话造成的必要差异。不能用旧白底页面截图代替参考对照。
- 页面不出现 RI、RSI 导航、主导航条或 hero；右侧输入在长消息、长动态时仍位于可视区域。
- 390×844 检查步骤折叠、五页签、对话开关、代码/波形局部滚动，无页面整体横向滚动。

### B. 90 秒 E203 证据演示

1. 默认初始仿真222/222不匹配、首个差异5ps，明确历史记录身份；不自动回放。
2. 查看规格原文与摘要，再查看 9 个规划模块。
3. 打开 RTL 文件清单，核对 10 文件及 e203_defines.v，查看版本/文件 hash。
4. 选择定位与修复，右侧39张候选卡；点击候选4，中央显示真实Diff及18/222结果。
5. 点击候选39，查看相对候选35的真实Diff；修改前1/222、本次0/222，再切最终复验PASS。语法失败候选仅显示代码与错误日志。
6. 确认报告结论不由游标瞬时值替代，缺失根因处说明未记录。

### C. 回放与四案例

- 播放、暂停、继续、从头与手选步骤；只播放已有事件，八步缺失处不伪造完成，不生成原始耗时或现场执行百分比。
- 检查 E203 39 次候选摘要，不显示运行分组或选择器；候选点击直接联动中央证据。
- 切换 AES 加密/解密/SDC：规划模块 3/5/5，各自最终报告和真实波形；无修复前记录及采样统计明确说明，不填零。
- 打开旧 `?case=aes_cipher_system_hard#/optimization`、`#/experience`：进入该案例工作台，不加载故事区；旧 architecture/code/verify 链接和新 spec/repair 刷新、前后退可恢复。

### D. 对话与动态（测试替身）

- 连续三轮提问、引用跳转、跨五页签、断线恢复、IME Enter；草稿及消息保留。
- 发送后立即切换证据或案例，过晚回复保持原上下文，不替换新会话；输入中新草稿不被响应清空。
- 两个浏览器上下文互不看到对话与私有操作。模型不可用但 verify 可用的 fixture 中，普通问题保留草稿，准确的重新验证请求走对应操作一次。
- 动态仅显示来源事件/快照摘要，不出现参考稿写死推理或审批接管承诺；完整浏览/回放没有执行或模型写请求。
- 可控 provider 检查 workspace_panel 与工程证据一致；即使故事数据不可用，普通工作台请求也不依赖 story_view，提示不预设当前页面为 RSI。

### E. 下载

- 下载 E203 单次及前后比较，解压核对 manifest/README、全部 RTL、报告和公开波形；hash 与实际字节一致。
- SDC 含所有四个公开 tiles，包内 index 为相对路径且可追溯来源；没有原始私有 VCD、状态库、会话或私有配置。
- 断开后台后静态包仍可下载；故意错误选择、跨案例、hash 冲突、过大或不可公开记录给出明确错误，不能保存错误页为 ZIP。

## 7. 后续发布核对

只准备候选 release，不在本轮执行上线。上线前同时包含新 dist、rtl_web（含 evidence.py）、ZIP 导出与部署检查脚本；用现有 package.example.yaml/release 流程验收，确认受限 ZIP 可通过，越界 ZIP 被拒绝。

不上传参考稿 vendor、specs、tests、node_modules、私有环境或数据库。不覆盖服务器 data_root、session.key 或模型配置；沿用 agent 域名与同源代理，主站/www/design 不变。保留旧 release 指向用于回滚。

此次升级为新代码与静态材料的增量候选，服务器已有 private seed 和原始 VCD 留在原位，不重走全量初始化，也不因检查全量打包器就重新传输私有层。

验收结果分开记录：参考排版、四案例材料、对话契约、下载/部署包检查、真实模型/修复（本次未执行）。

## 8. 本轮结果

前端单元31/31、完整浏览器29/29与构建通过；最新后端分组结果见validation.md。截图、自动导航计时和 JSON/XML 报告保存在 `.rtl-demo/validation/004-redesign-rtl-studio/`。本地增量候选在 `.rtl-demo/staging/004-redesign-rtl-studio/studio-20261021-r7-recorded-journey/`，其中 HANDOFF.md 明确基础 release 合并、私有状态保留和回滚方式。

浏览器本地预览：`http://127.0.0.1:5173/?case=e203#/workspace`。只启前端时使用真实静态归档，不能据此宣称问答模型或执行环境就绪；持续对话的真实服务连通性本轮未调用模型验证。

### 查看逐步调试轨迹

本地打开 `http://127.0.0.1:5173/?case=e203&panel=repair#/workspace`。左侧选择阶段，右栏 AGENT TRACE 只显示该阶段；选择“自动修复”后展开任一候选，核查修改目标、RTL 文件、语法/仿真、差异信号和接受/回退；第5、第9次可打开详细报告与波形。点击“从头回放”会隐藏尚未到达的候选。其他案例无详细日志时保留缺失说明。

本次补充：前端27项及构建通过；调试投影3项、归档/发布回归29项通过；最终浏览器定向7项通过（此前历史回放1项也通过）。全部使用历史材料/可控接口，未调用真实模型。

2026-10-21 修正：右栏已移除所有阶段并排的重复导航，只随左侧所选阶段展示；中央页签也同步左侧阶段。前端28项与构建、浏览器定向10项通过。

### 点击式 Trace / 按需 AI 对话（2026-10-21）

右侧为当前阶段的摘要卡片和候选卡片，点击后打开详情窗口查看原始调试记录或工具日志，可继续跳转报告和波形；关闭后返回原卡片。详情不再堆叠在右栏。AI对话默认收起，点击顶部“AI 对话”打开；关闭/重新打开及切换页签保留草稿和消息。前端28项、完整浏览器26项及构建通过。

### 完整修复过程（最新）

打开`http://127.0.0.1:5173/?case=e203`。仿真默认初始失败；定位/修复右侧点击候选后，中央显示对应修改、实际基线、报告和前后波形。代码Diff及工具日志按需查看；最终复验为0/222。刷新保留所选候选；既有显式旧链接仍兼容。新在线会话也从初始失败开始，已有访客选择继续恢复。AI对话从顶部打开，默认收起。

最新r7候选同时包含前端、后端增量代码、审核哈希清单和新增私有历史seed。与此前只复用服务器旧种子的说明不同，本次必须先校验基础runtime，再对新增seed执行dry-run和合并；不覆盖状态库、session.key或模型配置。尚未部署到公网；无真实模型验收或新仿真。

### AES 加密完整修复过程（最新）

打开`http://127.0.0.1:5173/?case=aes_cipher_system_hard`，或用顶部任务切换到AES加密。仿真默认原始失败报告，显示text_out/done独立差异计数；下方可筛选离散探针、翻页和跳转差异附近记录。初始及中间完整VCD已被覆盖，表格不代表连续波形，不补填总采样数。

选择定位与修复，右侧8张候选卡联动中央代码Diff、当时诊断假设/预期效果、检查及前后探针。候选4语法失败并回退，候选7退化后回退；候选8对比基线6，修改前done有3次差异，修改后完整真实波形及PASS。最终验证显示保存范围，不把这份报告称为另一独立复验。聊天仍默认收起，AES解密/SDC未补造过程。

当前四案例107个公开ZIP（E20386、AES加密19、另外两例各1）；最新候选r8-aes-history替代r7。新增运行时代码recorded_react_history.py及审核清单rtl_demo_aes_cipher.history.json，与前端及私有新增seed一起部署；seed不能放进静态目录，先dry-run再合并，不覆盖会话密钥/状态库/模型配置。本次只准备本地，公网尚未更新。

### AES 解密完整修复过程（最新）

打开`http://127.0.0.1:5173/?case=aes_inv_cipher_top_system`，或顶部切换AES解密。默认初始失败：text_out 37次差异、done 1次差异；下方为原日志保留的离散探针，完整初始VCD未留存。

进入定位与修复，右侧4张候选卡：1/2为已保留但未独立验证，中央显示代码Diff和修改状态；3显示text_out 34次、done 9次差异及探针，修改前版本2仍显示未验证；4对比实际基线3，展示完整真实波形和PASS。候选刷新及证据下载保留正确身份；最终报告是最后保存的通过结果，非另一次独立复验。

当前公开ZIP117个：E20386、AES加密19、AES解密11、SDC1。最新候选r9-aes-inverse-history替代r8；新增AES解密审核清单、edit_only后端支持与前端要同步发布，私有seed先dry-run再合并，不放进静态目录、不覆盖访客状态或凭据。本次只准备本地材料，公网未更新。

### SDC 完整系统修复过程（最新，2026-10-22）

打开`http://127.0.0.1:5173/?case=sdc_controller_system`，或顶部切换SDC控制器。仿真默认初始失败报告及各输出次数；初始VCD未保留，明确缺失。进入定位与修复，右侧17张候选联动中央真实代码Diff、报告与前后波形。1/2/8/15为回退记录；17对比基线16，修改前sd_dat_out_o 998次差异/40ps，修改后通过；最终独立复验使用独立保存的报告和完整波形。报告无总采样数，页面不以信号次数求和替代。

当前四案例153个公开ZIP：E20386、AES加密19、AES解密11、SDC37。最新本地候选studio-20261022-r10-sdc-history，新增SDC审核清单、报告/VCD输出计数核对代码和完整私有seed；同批部署，先dry-run再合并，保留数据库、session.key、模型配置。私有历史种子约673MiB，有界预算1GiB；不得放入静态目录，公开ZIP上限仍64MiB。此次只更新本地网页与材料，公网未更新。

### 公网查看（已发布，2026-10-22）

直接打开https://agent.deepvalleychip.cn，无需密码或本地启动。顶部切换E203、AES加密、AES解密、SDC；默认初始失败，进入定位与修复点击右侧候选查看对应代码Diff和真实波形/探针，最终复验查看PASS。AI对话从顶部打开，保留原有模型配置与会话隔离；本次未发送真实问题或执行新仿真。

当前发布studio-20261027-r14-availability；Agent后台仍为127.0.0.1:18080，经现有Caddy提供HTTPS。主站/www/design与模型密钥、Agent配置未修改。本地5173预览也可继续使用，但不再是查看新版的必要条件。最新部署与回滚记录见本地`.rtl-demo/deployment/studio-model-chat-20261026/`及服务器同release更新目录；此前发布记录保留。

点击左侧“根因定位”，再点击右侧“修复前 · 候选N”查看当时判断、修改前代码和来源；“查看该次自动修复”进入对应Diff和前后波形。仅提交验证时的理由、未保存独立判断分别说明。定位页证据包下载对应修改前验证，不把本次候选PASS当作修改前结果。

顶部打开AI对话，三个分析按钮和自由提问全部调用真实模型，归档只作为上下文；可连续追问，回复下方标注“AI 模型回答 · deepseek-v4-pro”。历史上直接返回的摘要标为“历史消息 · 归档摘要（未调用模型）”。重新验证、按规格生成两项仍仅显示暂不支持。等待时可继续编辑草稿，回答状态自动刷新；模型故障明确报错。测试入口https://agent.deepvalleychip.cn/?case=e203&v=model-chat-20261026。


### 公网可用性修复（2026-10-27）

当前 r14 修复网关全局连接额度耗尽导致的 Service Unavailable。活动普通请求和实时通知各自限流，空闲 keep-alive 不占活动请求名额；通知连接每 60 秒轮换并按事件游标续传。页面及模型对话路径保持 r13，部署/回滚材料位于 `.rtl-demo/deployment/studio-availability-20261027/` 和服务器 `updates/studio-20261027-r14-availability/`。
