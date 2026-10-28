# Implementation Plan: RTL Agent 单机安全部署

**Branch**: `main`（实际Git分支；逻辑特性标识`002-secure-agent-deploy`） | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

**Input**: 部署规格及[文件与环境清单](deployment-inventory.md)。本轮完成Phase 0/1设计，不安装服务器、不发布、不生成tasks.md。setup-plan脚本返回的BRANCH是逻辑特性名；`git branch --show-current`仍为main。

## Summary

将现有单页工作台、API、单worker及完整RTL运行链部署到`39.107.243.176`，由同机Caddy保护入口，后台仅监听`127.0.0.1:8000`。保留常驻对话和架构/代码/验证三标签；主站、www及28989上的CAD服务保持原样。浏览器不直接连接模型、Neo4j或执行进程。

重点落实分层白名单发布、四例私有历史证据初始化、目标机重建环境、执行隔离、持续运行和正式域名验收。沿用Planner、SystemDebugRunner、SystemSimReviewer、LLMClient、Store和波形绑定。约2GB内存能否承载完整链路由实测门禁决定，静态展示或问答成功不能代替完整交付。

## Technical Context

**Language/Version**: Web和Agent各建独立CPython 3.13.11环境，以当前两者实测版本为基线；TypeScript/Vite前端在本地构建。目标glibc 2.32环境验证解释器及native依赖，不能复制本机venv。

**Primary Dependencies**: 现有FastAPI/Uvicorn/Pydantic/PyYAML/vcdvcd；当前provider的LLMClient/SDK；Planner/Debug/Codex CLI及指定profile；Neo4j/tree-sitter；Verilator以本地已验证5.044为首选基线、g++/make/git；现有Caddy/systemd；新增bubblewrap用于任务文件系统隔离。服务器不需要前端Node构建环境；若选定Codex分发方式依赖Node，单独计入Agent工具链。

**Storage**: 本机持久SQLite WAL及artifact/snapshot文件；新增seed、发布与验收清单。Neo4j使用独立生产目录，由当前任务重建运行图，不搬本机整库。

**Testing**: pytest契约/集成测试、既有前端/浏览器检查、干净目录演练、四例真实仿真、真实多轮问答与生成/修复、服务/主机重启和回退演练。替身测试不代替真实能力验收。

**Target Platform**: Alibaba Cloud Linux 3单机，现状2核/1870MiB、约32GB可用磁盘；root安装系统服务，普通rtl-demo账户运行。实际systemd/cgroup/命名空间能力需预检，不假设最新文档全部适用。

**Project Type**: 既有Web服务和Agent的部署适配；不新增编排平台或账号管理产品。

**Performance Goals**: 接收消息3秒内反馈；问答预算120秒；普通浏览p95≤5秒；结果5秒内可见；服务恢复60秒，主机基础依赖就绪后120秒；回退≤5分钟。详细口径沿用SC-001～012。

**Constraints**: 全局最多1个RTL任务、默认1个模型问答，两者可并行；编译并发1；保留当前模型和required KG；原始规格/TB/参考只读；不迁移开发私有状态；不以root常驻运行Agent。

**Scale/Scope**: 四例、少量受邀观看者、一名演示者、三类受控执行入口；无需另一台计算机地址。

## Constitution Check

`.specify/memory/constitution.md`尚未填写，没有已批准原则；不将模板示例当作政策。以下门禁来自本功能规格。

| 门禁 | 研究前 | Phase 1后 | 设计依据 |
| --- | --- | --- | --- |
| 网页简洁、复用现有链路 | PASS | PASS | 无新增页面/算法，集中部署适配 |
| 历史/实时、版本/报告/波形可追溯 | PASS | PASS | seed闭包、输入清单和输出校验 |
| 公开/私有分离、最小权限 | PASS | PASS | 分层包、认证、固定挂载白名单 |
| 保护原站点/CAD及权限边界 | PASS | PASS | design限定变更、独立端口、发布回退 |
| 不删必需能力掩盖失败 | PASS | PASS | 就绪和真实验收分别记录 |

设计通过不表示目标环境验收通过。实施阶段各门禁失败即保留未完成状态。

## Project Structure

### Documentation (this feature)

```text
specs/002-secure-agent-deploy/
├── spec.md
├── deployment-inventory.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── deployment.md
    └── runtime.md
```

下一阶段由speckit-tasks生成tasks.md，本轮不创建。

### Source Code (repository root)

包含拟新增文件，尚未实现：

```text
zerorepo/rtl_web/
├── api.py / chat.py / chat_runtime.py  # 全局问答准入、最小子进程环境
├── cli.py / settings.py               # seed命令、每例配置、预检
├── store.py / artifacts.py            # 批量幂等导入、恢复与校验
├── seed.py                           # 新增：私有历史数据导入/导出
├── sandbox.py                        # 新增：固定挂载与job描述符
├── tool_bridge.py                    # 新增：当前任务受信MCP工具桥接
└── runtime.py / worker.py             # 脱离共享Store、隔离执行、可信归档
zerorepo/rtl_impl/
├── codex_debug/runner.py              # 统一真实profile解析与预检
├── codex_debug/mcp_server.py          # 工具桥接客户端，保留既有工具语义
├── rtl_kg/rtl_file_graph_builder.py    # 可写缓存与目标构建路径
└── debug_agent/system_debug_runner.py # 验证器路径/编译并发适配
scripts/rtl_demo/
├── deployment.py                     # 新增：分层发布协调器
├── bootstrap-as-root.sh               # 新增：目标解释器及基础工具准备
├── release.py                        # 复用design静态发布与旧资源保护
└── preflight.sh                      # 扩展退出码与目标环境检查
deploy/rtl_demo/                       # 同机Caddy、系统units/slice、模板
└── package.example.yaml               # 拟新增：脱敏构建输入与上传白名单
requirements-web-prod.in / .txt        # 拟新增：Web生产依赖
requirements-agent-demo.in / .txt      # 拟新增：当前Agent路径生产依赖
tests/rtl_web/                         # seed、打包、隔离、恢复、发布测试
web/rtl-demo/                          # 原工作台，必要的能力/繁忙提示
```

**Structure Decision**: 保持当前包结构；首版保守保留zerorepo运行源码及实际资源，排除开发/生成文件，不盲目重构Agent。依赖精简须有导入和实跑证明，上传项以白名单为准。

## Target Layout and Trust Boundaries

```text
浏览器 -- HTTPS/演示认证 --> 现有Caddy
  /、/assets、/cases -> /srv/deepvalleychip/design
  /api/*           -> 127.0.0.1:8000（保留路径、注入网关校验）
                             |
                        API / 单worker
                             |
                 受控job输入 -> 隔离runtime -> 可信归档
                             |
                    现有模型 / Codex / 仿真 / KG
```

| 目录/资源 | 内容与权限 |
| --- | --- |
| `/home/dev/deepvalleychip-site/releases/<release-id>/` | dev暂存design/runtime/seed/verifier/ops；私有部分限制读取，不直接提供Web服务 |
| `/opt/rtl-agent/candidates/<release-id>/` | root封存的审核副本；dev及服务账户不可写，后续特权脚本只从该副本执行 |
| `/opt/rtl-agent/releases/<release-id>/` | root持有的只读代码、四例规格、元数据与生产环境；venv在最终位置创建 |
| `/opt/rtl-agent/current` | root管理的后台版本指针，服务启动固定实际release路径 |
| `/opt/rtl-agent/oracle/<oracle-id>/` | 四例验证材料及原件/适配摘要，运行账户只读 |
| `/etc/rtl-demo/` | 私有配置与环境文件；root持有，按读取主体0600或0640 |
| `/etc/caddy/rtl-demo.env` | 仅入口密码hash与gateway key，不持有模型秘密 |
| `/var/lib/rtl-demo/` | 生产Store、签名秘密、历史及实时归档；代码升级不替换 |
| `/var/lib/rtl-demo/jobs/<run-id>/` | 当前任务输入、merged、中间输出及专用工具缓存 |
| `/var/lib/rtl-demo/tool-home/` | 本服务自己的合法Codex认证与profile，按需提供必要层 |
| `/var/lib/rtl-demo-kg/` | 独立服务账户的Neo4j持久数据，只监听localhost |

API/可信worker可访问Store；工具子进程不得看到Store、session.key、其他任务、CAD目录或无关配置。bubblewrap使用固定挂载白名单：只读代码/解释器/工具/当前规格/参考，当前任务输出和缓存可写；禁止将宿主根目录整体只读挂入后声称保密。保留Codex workspace-write及MCP验证。若目标机命名空间或嵌套沙箱不兼容，阻止相关能力发布，不去掉隔离继续运行。

KG密码及完整私有descriptor仅可信runtime/MCP连接层可见。Codex模型工具进程使用进一步收窄的挂载与去密环境，通过当前run的受限本地工具桥接调用既有MCP语义；不能持有Neo4j密码后直接读取其他图分区。模型侧不挂参考源码和KG配置，验证仍由可信工具层执行；桥接限定当前run及固定工具，不提供任意Cypher或命令入口。

## Delivery Stages and Gates

### A. 可复现上传包与历史初始化

复用静态构建和release.py，增加分层manifest。构建端完成历史解析，从Store原始记录导出四例引用闭包，包括VCD、snapshot、索引内部tile引用、契约和必要原始审计附件。目标端先验证文件，再事务导入。禁止整体复制.rtl-demo、rtl_outputs、RealBench、venv和configs。

历史契约改用seed索引按run解析；生产配置分别映射四例bundle/spec，不能只改E203顶层字段。AES加密缺历史契约的事实保留，仍可从规格新建生成。门禁：干净目录四例可读、重复导入无变化、冲突无半成品、开发私有状态迁移为0。（FR-005/017/023～025；SC-001/009/011/012）

### B. 目标环境、配置和工具适配

分别锁定Web和当前Agent路径依赖，排除测试工具，保留selected provider、required KG及Planner/Debug。新建3.13.11环境，安装已验证Verilator/g++/make/git及Codex所需工具；不复用CAD环境，不默认安装根requirements。

bootstrap采用审核后的shell入口，先准备root持有的独立uv/Python，再运行Python发布协调器，解决系统默认3.6无法运行部署工具的问题。ops工具清单还必须固定Neo4j发行版及兼容JRE、Codex分发及其运行时、Verilator构建配方和目标架构；这些不是pip锁文件能覆盖的依赖。不得使用开发compose默认密码或公开7474/7687。

验证器采用版本化适配副本：只配置RealBench根、工具路径和编译并发1；记录原件/适配件/实际参数，TB及参考字节不变。目标构建tree-sitter语言库，修复源码旁mkdir，实测AST；统一Codex profile实际解析和预检。KG从当前RTL和规划重建，各run保持唯一绝对路径/分区，不能统一映射为`/work/merged`。

门禁：所有有效路径脱离开发机；四例真实复验；实际KG连接/构图/查询、Codex profile/MCP、嵌套沙箱可用。秘密通过私有配置提供；发布清单不记录秘密值或其hash。（FR-004/010～012/014/026/027；SC-003/009/011/012）

### C. 可信调度、任务隔离与恢复

worker验证会话/案例/版本后生成只读job描述符及输入，runtime不再直接打开共享Store；输出由worker重新校验路径、摘要、verdict和输入完整性后归档。问答增加全局1个调用的事务准入，超额429且不启动模型、不丢草稿；执行保持全局1个，超额409，两者可并行。

worker启动先持独占锁，以启动代际/事务把此前accepted/running标为interrupted；恢复时新执行503，避免中断刚接收请求。replying消息明确中断，不自动重发。SSE仅通知，Store为状态依据，进程回收仅限本任务。

root安装systemd系统服务，代码只读、写入受限、KillMode=control-group；资源slice涵盖worker全部后代。初始CPUQuota=100%、TasksMax=128、编译并发1；内存候选API256MiB、worker768MiB、KG512MiB仅供实测，不是可行性承诺。各上限加现有业务基线和至少256MiB余量不得超过物理内存；不满足即停止完整能力发布并提出同机扩容。核对实际生效的cgroup限制，不仅检查模板。

磁盘初始门槛空闲≥5GiB、单job预算1GiB、job卷总预算8GiB。使用独立有容量上限的job文件系统（优先已支持的项目配额；否则经root审阅创建固定容量专用卷），以硬边界保护宿主盘；应用监测单job预算。四例实测后登记最终预算，不能删原始VCD或既有证据来通过。生产归档另有磁盘水位检查，只清理未引用临时编译产物。

门禁：越界读写及改TB失败；超时/资源超限有真实诊断且不影响原服务；跨会话、重启、重复提交不重复执行。（FR-006～010/013/015/019/021；SC-004～007/009）

### D. 同机入口与受控发布

design全站含静态/API均需演示认证；`/api/*`原样代理loopback，不用handle_path或SPA替代API。覆盖客户端gateway header、移除上游Authorization，保留Origin/Secure cookie/SSE和20KB请求限制。使用目标Caddy版本validate候选完整配置，并以服务同等秘密环境校验；不记录展开值。

dev准备候选及root操作预览；root先将候选复制封存到dev不可写目录，重新核验摘要、审查固定脚本，此后只执行封存副本。root创建独立账户、安装依赖和系统units，准备只读release、私有配置、seed和KG。初次后台可在公网入口开放前以loopback验证；生产更新采用短维护窗口，暂停新请求、明确中断未完成状态，停worker/API，做一致性备份，再安装候选、启动预检、发布静态和入口。无需双活worker。

静态沿用现有design目录和原子文件发布顺序，保留旧hash资源。协调器保存后台指针、静态备份、units和完整Caddy恢复集合。数据库仅允许前后版本都可读取的增加项；回退代码和入口，不恢复旧库覆盖新会话。仅改变design，主站/www及CAD目录/端口不变。（FR-001/003/007/016～022；SC-001/007～010）

### E. 正式域名完整验收

按[quickstart.md](quickstart.md)完成10轮真实问答、四例验证、E203绑定波形、预置规格生成和真实失败版本修复尝试。后两项未收敛可如实失败，环境/依赖故障不算能力验收。执行期间同时完成3轮问答和原业务基线检查；演练SSH断开30分钟、服务重启、主机重启及5分钟回退，开发电脑不提供后台。

发布状态依次staged、prepared、active_unverified、accepted；部分能力可用不提升为accepted。主机重启在维护者安排的验收窗口进行，本计划不触发。全部SC有证据后才宣布交付。（SC-001～012）

## Integration with Existing Feature

实施阶段同步001的deployment.md、quickstart及部署模板，注明本特性替代两机前提；保留原验收事实和未完成项，不覆盖旧UI规格/任务。现有release.py的design路径限制继续保留，协调器不接管主站或CAD。

## Requirement Coverage and Implementation Order

| 阶段 | 需求覆盖 | 主要验证 |
| --- | --- | --- |
| A 打包与seed | FR-005/017/023/024/025 | 四例闭包、hash、隐私排除、幂等/冲突、升级保留 |
| B 环境与路径 | FR-004/010/011/012/014/026/027 | 干净环境、实际工具/解析/profile/KG、四例真实验证 |
| C 执行边界与恢复 | FR-006/008/009/013/015/019/021 | 沙箱、预算、并发、重启中断、无重复执行 |
| D 入口与发布 | FR-001/002/003/007/016/018/020/022 | 保持简洁页面、认证/同源/SSE、原业务保护、发布/回退 |
| E 正式验收 | 全部27条FR，SC-001～012 | 真实交互、三类入口、版本波形、持续运行及所有门禁 |

A先确定可移植输入；B、C可基于契约分别推进，D依赖A/B/C通过准备门禁；E必须在正式入口完成。任务拆分时保留各阶段失败路径与具体代码适配，不以仅有运维模板代替实现。

## Complexity Tracking

无constitution违规。新增seed工具解决证据可移植性，job隔离解决runtime访问共享Store的风险，发布协调器保证代码/入口/状态可恢复；不增加队列服务、数据库产品或网页管理页面。
