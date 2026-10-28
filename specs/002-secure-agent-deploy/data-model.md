# Phase 1 Data Model: 发布、历史初始化与受控任务

关联：[plan.md](plan.md)。复用现有Store，不更换业务实体。以下新增结构为拟实施设计，不表示迁移或数据库表已经存在。

## 1. DeploymentRelease / FileEntry

发布记录放在受限运维状态目录，使用原子JSON更新；不向浏览器返回完整私有manifest。

| 字段 | 类型/约束 |
| --- | --- |
| schema_version / release_id | `rtl-demo-deploy-v1`；ID限定字母数字、下划线、短横线，禁止路径 |
| source_revision / source_dirty | Git提交与构建时dirty标记；dirty发布必须由实际文件摘要标识，不能只以HEAD代表内容 |
| created_at / platform | UTC时间、目标OS/arch/libc、解释器/工具版本 |
| packages | design/runtime/seed/verifier/ops各自manifest摘要 |
| cases | 固定四个case_id → bundle_id、spec hash、seed_id、oracle_id |
| lock_hashes | Web/Agent锁文件及必要工具构建配方摘要 |
| files | FileEntry数组，包内路径唯一 |
| previous_release_id / recovery_set_id | 上一可用发布及备份引用 |
| state / gates | 发布状态、逐项检查结果及证据引用；秘密不进入记录 |

FileEntry字段：`package`、`source_relative_path`、`target_relative_path`、`purpose`、`visibility`、`size_bytes`、`sha256`、`mode`。visibility为`design_protected`、`runtime_private`或`ops_private`。源路径相对于声明的repo/oracle/seed逻辑根，不记录开发机绝对用户名路径；目标路径相对于包根，安装目标由固定包映射决定。实际配置只登记所需变量名，不登记密钥hash或私有文件内容。

验证：禁止绝对/上级/重复/大小写歧义路径、symlink/hardlink、设备/FIFO、未知包及越界提取；安装前重新计算全部大小和摘要。公开包不得出现raw VCD、参考源码、实际配置、session状态或私有附件。归档展开总量先校验再写入。

状态：`staged → prepared → active_unverified → accepted`；任意检查失败可进入`failed`，已切换版本可进入`rolled_back`。只有全部SC证据通过才accepted；能力只部分就绪仍非accepted。

## 2. HistoricalSeed / HistoricalRecord / HistoricalInput

seed是独立私有传输格式，不是SQLite文件或static export。

| 字段 | 约束 |
| --- | --- |
| schema_version / seed_id | `rtl-demo-seed-v1`，内容摘要确定版本 |
| cases | 精确四例，登记活跃bundle与来源evidence摘要 |
| records | `kind,id,payload`；kind仅bundle/run/version/validation/artifact |
| files | 相对storage_key、size、SHA-256；snapshot还保留tree hash和file_manifest |
| historical_inputs | run/case关联的contracts及必要原始审计附件索引 |
| counts / total_bytes | 记录数、文件数、总展开大小，用于导入预检 |
| export_tool_version | 导出器版本，区分历史解释规则变化 |

HistoricalRecord所有原始owner必须NULL。每条记录必须通过四例历史根可达性检查；artifact无origin字段时依据关联run验证，不能因为owner为空就导出全部资料。闭包包括parent_version、模块RTL、报告、DUT/Reference VCD、wave索引JSON内部的tile IDs及其存储文件。历史bundle的public摘要不能替代原始Store payload。

HistoricalInput：`case_id,run_id,kind,artifact_id,expected_sha256,status,seed_id`，kind为contracts或audit；status为present/missing。契约必须与既有evidence摘要一致；AES加密缺失记录保持missing。新增`historical_inputs`索引表，不更改不可变run/version payload来伪造契约。附件使用普通artifact记录，私有可见，不新增通用下载权限。

严禁seed包含sessions/messages/operations/events、owner非空记录、session.key、heartbeat、进程/锁/预检缓存或任意认证目录。原始审计附件如含秘密则拒绝发布并记录缺口，不能偷偷改字节继续声称原始hash一致。

导入：先在临时目录完成引用、文件和摘要验证；按内容寻址安装不可变文件，再在一次事务中登记全部新记录/索引与`seed_imports(seed_id,manifest_sha256,imported_at,release_id)`。相同ID同内容为幂等，相同ID不同内容整体失败。文件不可见于有效记录前不激活，失败孤立临时文件可安全回收。升级只增加历史资料，不清库、不更换session.key、不覆盖生产私有记录。

## 3. CaseDeploymentBinding / EffectiveRuntime

固定注册表仍限定案例及操作；新增服务端`cases`配置覆盖每例`bundle_id/spec/historical_contracts`映射，不接受浏览器传路径、端点或工具命令。oracle相对目录和top/alias继续由注册表及受信发布材料决定。

EffectiveRuntime包括：release_id、repo_root、data_root、oracle_id/root、Web/Agent解释器、工具路径/版本、超时、并发/资源预算、origins、backend profile、KG分区策略及秘密变量名。内部可有绝对服务器路径，用户API只返回安全能力摘要。生产`development=false`，仅正式design origin；环境中`RTL_DEMO_DEVELOPMENT=1`属于发布失败。

## 4. JobDescriptor / JobResult

JobDescriptor由可信worker生成，不直接采用浏览器JSON。字段：schema_version=`rtl-demo-job-v1`、operation_id、run_id、case_id、kind、release_id、source context IDs、input manifests、spec/contract/RTL相对位置及hash、oracle适配hash、运行配置引用、唯一KG分区、budgets、输出目录约定。描述符和已准备输入只读；不携带session cookie、gateway key或共享数据库路径。

worker先完成授权和来源校验，runtime仅消费job，不能再读Store/共享artifact库。保持每run唯一绝对路径；已验证输入分别挂载只读，merged与当前工具工作目录可写。原始规格、参考、TB及历史快照不能通过链接或替代路径写入。

私有KG连接字段不写入模型可读descriptor。可信工具层保留连接信息，模型侧仅持当前run桥接标识/固定工具元数据；桥接作用域与run_id、KG分区、可读写任务根绑定，不能由模型改变。Codex/native shell子进程不继承KG凭据，也不挂载原始参考源码。

JobResult：operation/run/release IDs、技术终态、RTL目录清单、报告/VCD/索引引用、输入manifest、工具和适配记录、开始/结束时间及资源测量。所有结果均为不可信进程输出，worker重新校验路径、内容摘要及输入未变，再复用Artifacts归档；退出0不能直接成为PASS。

任务转移：`accepted → running → completed | failed | timed_out | interrupted`。completed表示链路有有效结果，可包含设计验证fail；环境启动失败为failed，不作为能力验收。此前启动代际的accepted/running恢复为interrupted，显式新请求才可再次运行；不能复用旧幂等键偷偷创建新任务。

## 5. CapabilityCheck / AdmissionLease

能力保留replay/chat/verify/generate/fix，分别记录`readiness`（ready/blocked）、`missing`安全代码、checked_at、release/config/input指纹及`acceptance`（not_run/passed/failed）和证据ID。就绪不等于验收；普通health不发起付费调用，预检缓存不能跨release/配置/工具/材料变化沿用。

全局问答采用持久化事务lease（最多1个），字段：lease_id、message_id、启动代际、进程身份、deadline。准入在接收新调用的同一事务内完成，重试相同幂等请求返回原消息；容量不足返回429且不建立replying或调用模型。API恢复时将旧lease/消息明确中断，不能仅凭超时在旧进程仍存活时释放并发槽。

执行继续使用现有SQLite唯一索引和worker flock；恢复/维护标志阻止新执行进入。预算包括全局并发、timeout、compile_jobs、有效memory/cpu/tasks、job卷总量/单job预算及宿主最低空闲；未证实可生效的限制不能标为ready。

## 6. RecoverySet / AcceptanceRecord

RecoverySet：前后release、实际后台路径、静态备份路径、完整Caddy及其secret环境版本引用、units/drop-ins、兼容schema版本、SQLite一致性备份位置、输入/证据摘要、创建时间。秘密备份受限，不进入一般发布报告。SQLite使用backup API或停止服务后的WAL一致性备份，禁止只复制活动主文件。

回退切旧代码/静态/入口/服务配置，保留新产生的生产会话和证据。schema兼容性失败则拒绝激活，不以恢复旧库解决。不得用旧配置反复轮换session.key。

AcceptanceRecord按SC-001～012登记：目标release、目标host、正式origin、场景、started/finished、结论、真实操作/验证ID、报告/波形hash、资源与原业务对照、证据位置。设计失败可保存真实结果；依赖失败不得勾选生成/修复能力通过。原始诊断私有、对外说明脱敏。
