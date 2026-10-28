# Contract: 分层发布与私有历史初始化

关联：[数据模型](../data-model.md)、[实施计划](../plan.md)。以下命令已实现；实际服务器安装与正式验收状态独立记录，不能以工具存在推断已上线。

## 1. 包结构与固定目标

```text
<release-id>/
├── deployment.json
├── design/       # 完整dist及现有release.json
├── runtime/      # 运行源码、四例规格、资源、许可；不含venv/秘密
├── seed/         # seed.json、records、必要私有文件/契约/审计附件
├── verifier/     # 四例受信原件、适配件及其清单
└── ops/          # 生产依赖锁、模板、发布工具和精简运维说明
```

只有design进入`/srv/deepvalleychip/design`。其余按plan固定私有目录安装，不能由manifest自由指定任意宿主路径。实际秘密由服务器独立配置，不进入包。生产解释器、锁定依赖与native工具按目标安装配方建立，不能携带开发venv。.git、specs、开发说明、测试/截图、无关历史输出、模型缓存等不上传；任务Markdown、运行资源和LICENSE是保留例外。

打包对每文件记录来源逻辑根/相对路径、目标相对路径、用途、可见性、大小/hash；记录四例bundle和锁文件。拒绝未列入白名单、私有内容混入design、链接、路径穿越及摘要不符。扫描实际秘密时只报告文件和规则，不打印匹配值。

## 2. seed CLI

```bash
python -m zerorepo.rtl_web.cli export-seed --config CONFIG --out SEED_DIR
python -m zerorepo.rtl_web.cli import-seed --config CONFIG --source SEED_DIR --dry-run
python -m zerorepo.rtl_web.cli import-seed --config CONFIG --source SEED_DIR
```

- export-seed默认只导出注册四例活跃历史bundle，固定闭包规则；输出目录不得存在，不支持任意SQL或会话导出参数。
- import-seed按schema及全部摘要/引用验证，不读取原开发source_output。dry-run不创建Store、签名秘密或文件；正式首次导入才初始化Store。现CLI在命令分派前创建Store，实施时须修正这一副作用。
- 同seed重复导入成功且不改变生产会话/签名秘密；同ID不同内容返回冲突。禁止owner非空记录及运行状态表，文件验证后单事务登记。
- 成功输出仅seed_id、四例bundle IDs、记录/文件数、总大小及dry_run；错误为安全代码和相对文件定位，不输出凭据/正文。

退出码：0成功；2参数/schema/路径错误；3来源/摘要/不可变冲突；4依赖或目标不可访问。失败不激活部分seed。

## 2a. 构建输入及首次bootstrap

`deploy/rtl_demo/package.example.yaml`，实际填写副本留在本地私有目录。字段为schema_version、runtime_config（构建端已审查Store配置）、dist、oracle_root、target_platform、include/exclude白名单及production_locks/toolchain_lock引用。相对路径基于该文件目录解析；四例来自固定注册表，不允许浏览器编辑这些字段。显式include仍必须经过秘密和可见范围检查，不能用一个`**/*`绕过排除规则。

首次工具准备接口：

```bash
bash scripts/rtl_demo/bootstrap-as-root.sh --release RELEASE_DIR --dry-run
bash scripts/rtl_demo/bootstrap-as-root.sh --release RELEASE_DIR
```

root先用受信系统工具将候选复制封存至`/opt/rtl-agent/candidates/<release-id>/`，禁止链接/特殊文件，确保dev及服务账户不可写；重算摘要并审核封存脚本/展开预览，不能直接执行dev可写目录中的脚本。安装时始终读取该封存副本，后续dev暂存变化不影响审核结果。

bootstrap按已锁定来源/版本/摘要取得root持有的uv及独立CPython 3.13.11，固定目标解释器`/opt/rtl-agent/toolchain/bin/python3.13`。同时准备发行版兼容构建工具；不运行dev可写uv二进制作为root，不修改系统默认Python或现有CAD环境。dry-run不下载、不安装、不更改服务；缺特权返回5。后续依赖及服务安装由prepare处理，工具配方记录Neo4j/JRE、Codex及必要运行时、Verilator/native库，不能依赖未锁定latest下载。

## 3. 发布协调器

```bash
python scripts/rtl_demo/deployment.py build --config BUILD_CONFIG --release-id ID --out OUT
python scripts/rtl_demo/deployment.py check --release RELEASE_DIR
python scripts/rtl_demo/deployment.py prepare --release RELEASE_DIR --config SERVER_CONFIG --dry-run
python scripts/rtl_demo/deployment.py prepare --release RELEASE_DIR --config SERVER_CONFIG
python scripts/rtl_demo/deployment.py activate --release-id ID --dry-run
python scripts/rtl_demo/deployment.py activate --release-id ID
python scripts/rtl_demo/deployment.py status --release-id ID
python scripts/rtl_demo/deployment.py rollback --recovery-set RECOVERY_ID --dry-run
python scripts/rtl_demo/deployment.py rollback --recovery-set RECOVERY_ID
```

| 命令 | 权限/效果 | 成功条件 |
| --- | --- | --- |
| build | 构建机普通用户；使用已构建dist、审查后Store、四例oracle与配置模板 | 五层包及hash闭包完整，构建输出不在输入目录内 |
| check | 只读检查已有包，无模型调用/服务重启 | 全文件/案例/可见性/摘要验证通过 |
| prepare | 服务器root；dry-run先生成具体目录/账户/依赖/服务变更预览 | 完整环境、只读release/oracle、私有配置引用和seed准备完；不切正式静态/Caddy |
| activate | 服务器root；只接受prepared版本 | 一致性备份、兼容性检查、维护切换及本机健康检查完成，状态为active_unverified |
| status | 授权维护者；只读安全报告 | 分别显示包、进程、能力和真实验收结果，不能一个healthy概括所有状态 |
| rollback | root；仅使用已登记恢复集合 | 旧代码/静态/入口有效，生产数据保留，失败版本诊断保留 |

prepare为新版本在最终release目录创建两个环境并按hash锁安装，完成native库/工具构建；不可在暂存venv建好后移动。系统Python3.6不能用于该工具，先按运维说明取得独立指定Python。已有生产时prepare不得覆盖其DB/会话密钥或启动第二worker；候选离线依赖/seed验证使用临时新Store，正式新增seed登记在维护切换期间完成。

deployment.py导入层只用标准库，check/status及目标prepare前半段读取deployment.json，不依赖PyYAML或业务包。build在构建Web环境中按需加载YAML；目标prepare先依据JSON安装锁定Web环境，再委托该解释器读取/验证SERVER_CONFIG。不得在Web环境建好前用裸Python导入Settings，否则首次安装会因缺依赖中断。

prepare的candidate门禁核对候选release、临时Store、全部材料与离线依赖，不要求正式worker心跳，也不借用旧release的预检缓存。activate启动后再执行production完整就绪检查，要求API/worker实际release_id与候选一致、四例正式seed和能力齐全；失败则恢复旧版本，不用prepare结果代替。prepared与完整ready明确区分，避免首次部署尚无worker导致准备无法完成。

首次安装准备独立系统units、受限配置、job容量边界、KG服务；没有原生产后台时可先启动loopback做真实预检，仍不得切公网入口。实际secret值不由CLI参数提供，只读取指定受限文件。

activate暂停新请求、明确中断未完成操作，停worker/API、备份、事务登记新增seed、切后台版本、启动预检，再调用已有design-only静态安装并应用评审过的完整Caddy配置。禁止用design示例片段覆盖整份Caddyfile。Caddy验证使用与服务一致环境且不输出展开secret；校验失败不替换有效配置。

保留原Caddy/main/www/CAD基线、旧hash资源和恢复集合。回退不恢复旧DB覆盖新会话；若schema不能被前版本读取，激活前失败。正在运行的Agent必须先终止/明确中断，不能只切symlink让同一进程混用两版源码。

退出码：0命令完成（status还须查看state）；2参数/白名单错误；3hash/版本冲突；4环境/能力未就绪；5需要特权；6应用失败且已恢复；7恢复未完成需维护者处理。非0不标accepted。

## 4. 发布验收状态

prepared仅代表可准备运行；active_unverified代表正式入口已切换但验收未完。accepted必须关联SC-001～012全部证据。身份保护、真实10轮对话、三类执行、四例复验、原业务连续性、重启/回退/升级保留状态缺一不可。人工记录不得覆盖真实失败结论。

## 5. 管理员验收登记

`accept --release-id ID --evidence-index PATH [--dry-run]`仅管理员正式执行。索引为root封存JSON，绑定host=39.107.243.176、origin、release_id及prepare记录的host_id；criteria必须恰含SC-001～012且全部status=passed，各evidence提供安全相对path、size_bytes和sha256。每个证据JSON也绑定同一身份、criterion与status。缺项/篡改/版本或机器不匹配返回4，正式执行再次检查当前symlink、完整生产依赖后才写accepted。dry-run不写记录、不重启或调用模型。
