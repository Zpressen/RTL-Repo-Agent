# Phase 0 Research: 单机部署适配

日期：2026-10-16。范围：[spec.md](spec.md)、[部署清单](deployment-inventory.md)、当前运行及发布代码。研究采用两项只读并行审查：运行/依赖、seed/发布；本轮没有远端修改或模型调用。以下为设计决定，工具版本、凭据和容量是否满足仍需实施验收。

## R1. 同机拓扑与持续运行

- **Decision**：Caddy继续提供HTTPS，API仅`127.0.0.1:8000`，worker独立系统服务；不使用28989，不依赖dev用户会话或第二台机器。
- **Rationale**：现有静态站缺少API代理；服务器已有systemd/Caddy。dev用户无linger，不能将临时SSH进程视为重启可恢复服务。
- **Alternatives considered**：两机要求引入尚不存在的地址前置条件；nohup/user unit无法满足已确认的恢复要求；新增编排平台增加维护面。
- **Evidence**：`deploy/rtl_demo/rtl-demo-api.service`、`rtl-demo-worker.service`、`Caddyfile.design.example`，现有模板需把private-IP改为loopback。

## R2. 白名单分层与保留必要Markdown

- **Decision**：design、runtime、seed、verifier、ops分别登记来源、用途、可见性、size和SHA-256；实际秘密独立提供。首版保守保留运行Python包和资源，排除开发/生成内容。
- **Rationale**：四例规格本身是Markdown；gitignore还会忽略必要VCD/契约，不能以扩展名或版本跟踪状态决定发布。
- **Alternatives considered**：整仓库同步会携带秘密、会话和大量历史；只传dist不能支持交互；只传rtl_web无法启动Agent。
- **Evidence**：`cases.py`固定四例spec/reference；`release.py:stage`构建端读取Git和前端lock，所以Git只需留在构建端。完整路径见deployment-inventory。

## R3. 私有seed而非复制SQLite

- **Decision**：从四例活跃bundle对Store原始records做引用闭包，保留bundle/run/version/validation/artifact及文件、契约索引和必要审计附件。owner必须为空且关联历史运行；新生产Store生成自己的session.key。
- **Rationale**：静态bundle中的public处理会移除storage_key；E203波形索引内部tile也要展开，不能仅看bundle artifact数组。仅有公开JSON无法定位受测snapshot。
- **Alternatives considered**：复制整个SQLite会带走会话/待执行请求；在服务器重跑历史import要求大量开发journal和candidate；只复制文件没有记录绑定。
- **Evidence**：`store.py:31–51,155–193`、`artifacts.py:169–262`、`import_case.py:401–512`、`import_catalog.py:125–181`。现有CLI没有seed导入/导出，需新增。

## R4. 历史契约与每例生产配置

- **Decision**：seed独立contract索引按run/case绑定，历史修复从归档读取并核对审查hash；生产四例配置分别映射bundle/spec，不要求搬原source_output目录。
- **Rationale**：runtime.repair_contracts仍读原`.zerorepo/module_planner/outputs/contracts.json`；Settings.for_case对非E203直接取固定注册值。单改顶层字段不足以迁移四例。
- **Alternatives considered**：保留开发机完整输出路径浪费数据且泄露历史；改写归档内容补造契约破坏证据。AES加密无历史契约，明确拒绝该历史版本修复并允许新建运行。
- **Evidence**：`runtime.py:222–256`、`settings.py:65–78`及两份evidence JSON的契约索引字段。

## R5. 独立环境与依赖锁定

- **Decision**：Web和Agent均以已测CPython 3.13.11新建独立环境，锁定当前真实路径依赖与hash；服务器安装必要工具链，不复用CAD环境。先验证目标wheel/native库，再固化锁文件。bootstrap先准备受信独立Python；发布协调器启动层只依赖标准库，YAML解析延迟到已安装Web环境，避免首次安装循环依赖。
- **Rationale**：系统Python3.6.8不适用；根requirements覆盖过多模块且OpenAI SDK声明与当前实测不一致。不能未经测试直接升级整仓库。
- **Alternatives considered**：复制Conda/venv存在绝对路径和ABI问题；安装全部根依赖带来ML权重和无关provider；只安装Web依赖不支持完整运行。
- **Evidence**：`requirements-web.in`含pytest；当前Web/Agent实测均3.13.11。[uv官方版本管理](https://docs.astral.sh/uv/concepts/python-versions/)支持指定解释器；[依赖同步文档](https://docs.astral.sh/uv/reference/cli/)说明sync按照包含传递依赖的锁定清单构建环境；实际可用版本仍需目标验证。

## R6. 验证器只做可审计的部署适配

- **Decision**：四例验证材料单独只读部署；保留原脚本，生成受审查的版本化适配件，只改根路径、工具路径、编译并发1。输入清单登记两份hash、适配规则、真实命令和工具版本。
- **Rationale**：两例AES写死本机RealBench根；四例脚本携带Conda路径及`-j 4`。全局单worker不能限制编译并行度。
- **Alternatives considered**：建立`/home/mokita`伪装开发环境不具备可移植性；仅环境PATH不能覆盖脚本内部常量；改变TB比较使其通过不可接受。
- **Evidence**：四例本机RealBench脚本及`SystemSimReviewer`包装流程；[Verilator参数文档](https://verilator.org/guide/latest/exe_verilator.html)区分构建并行度和仿真线程。目标首选本地已验5.044，不直接采用文档当前最新版。

## R7. parser、Codex及KG的真实就绪

- **Decision**：统一Codex runner与preflight的profile解析；目标构建tree-sitter库并将缓存移出只读源码；KG从当前RTL/规划重建，保留每run唯一绝对路径/分区，不复制本机Neo4j数据。
- **Rationale**：probe检查`config.toml [profiles]`，runner却要求`<profile>.config.toml`；parser即使设置.so路径也先mkdir源码旁build。无Git时KG repo_uid取路径hash，统一sandbox路径会碰撞。
- **Alternatives considered**：只测codex login、只测KG端口、复制已有.so都不能证明完整链路。不能为省资源禁用required KG。
- **Evidence**：`runtime.py:407–421`、`codex_debug/runner.py:389–432`、`rtl_kg/rtl_file_graph_builder.py:59–100`、`rtl_kg/rtl_knowledge_graph.py:48`、`rtl_kg_service.py`、`codex_debug/session.py:220–243`。

## R8. 隔离真实工具执行

- **Decision**：可信worker准备job描述符与当前输入，runtime脱离Store，通过固定bubblewrap挂载启动；只写当前job，规格/TB/参考只读，其他运行及共享凭据目录不可见。保留Codex本身sandbox与MCP，目标验证嵌套兼容。KG秘密留在可信工具层，Codex进程使用更小挂载/去密环境，通过当前run的固定工具桥接调用MCP，不直接持有数据库凭据或参考源码。
- **Rationale**：目前runtime打开共享Store，systemd的ReadWritePaths整个data_root不能隔离任务间访问；提示词和workspace-write不能独自证明保密边界。
- **Alternatives considered**：仅靠提示词不足；给worker通用sudo/systemd-run权限扩大特权；完整容器平台超出首版需要。
- **Evidence**：`runtime.py:259`、`worker.py:388`、现有units。补充代码审查发现现有私有debug descriptor携带KG配置且Codex继承环境，单一外层沙箱不能隔离图分区，需拆分可信工具连接层。[bubblewrap官方说明](https://raw.githubusercontent.com/containers/bubblewrap/main/README.md)明确其为沙箱构建工具，安全边界取决于调用者设置；故必须测试具体挂载，而不是安装后即宣称隔离完成。内核不支持时阻止能力发布，不回退裸运行。

## R9. 资源预算和准入

- **Decision**：单执行、全局单问答、编译1；systemd CPU/Memory/Tasks边界和有容量上限的job卷。KG独立预算、loopback监听、单独秘密。总预算不得挤占原业务，完整实测失败则报告同机扩容。
- **Rationale**：Neo4j开发compose配置heap最高2GB、pagecache1GB，不适用于当前整机；现有问答只有每会话锁，多会话仍可并发启动Python。
- **Alternatives considered**：无界重试、多个worker、默认开发compose或自动启用swap无法满足原业务保护；缩减KG/生成能力不能代替完整验收。
- **Evidence**：`rtl_kg/docker-compose.dev.yml`、`store.py`并发索引、`chat.py`调用。初始预算见plan，目标测量为准。[systemd资源控制源文档](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.resource-control.xml)说明层级资源限制；[systemd执行配置](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.exec.xml)用于只读/写入边界，实际宿主支持须核对。[Neo4j内存文档](https://neo4j.com/docs/operations-manual/current/performance/memory-configuration/)说明heap、pagecache及其他JVM/系统开销需共同计入，因此不能把小heap数值当作完整进程峰值。

## R10. 恢复、发布和回退

- **Decision**：启动代际下旧accepted/running全部明确interrupted，不自动消费；升级暂停新请求并一致性备份；发布记录代码/静态/Caddy/units恢复集合。schema只做前后兼容增加项，回退不恢复旧DB覆盖新会话。root执行前先封存候选，避免审核后dev目录变化；prepare用临时Store做候选门禁，activate启动后再核对实际release及worker完整就绪，避免首次启动/升级顺序成环。
- **Rationale**：worker.recover目前只处理中断running，随后claim会继续旧accepted；SQLite WAL不能只复制主文件。回退整个旧库将丢失新记录。
- **Alternatives considered**：断线自动重发有重复计费风险；只回退index不能恢复后台/入口；原地覆盖无版本恢复集合不可审阅。
- **Evidence**：`worker.py:115–138,556–574`、`api.py:33–41`、`store.py`、`release.py:150–229`。入口沿用[Caddy认证](https://caddyserver.com/docs/caddyfile/directives/basic_auth)和[反向代理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)；配置采用同源认证、覆盖gateway header和路径保留，实际版本validate后发布。

## Research Resolution

设计选择已完成，没有等待用户回答的设计问题。尚未安装的依赖、服务器服务账户凭据、namespace/cgroup/容量验证和root执行属于实施前置及发布门禁，分别登记，不宣称已通过。后续按[plan.md](plan.md)实施，接口见contracts，验收见quickstart。
