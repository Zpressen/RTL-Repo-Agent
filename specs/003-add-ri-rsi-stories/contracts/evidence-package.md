# Contract：审核导入、seed 与部署闭包

状态：拟定契约，待实现。复用原文件存储和五层发布，不新增松散故事上传服务。

## 1. 维护者 CLI

在现有 `python -m zerorepo.rtl_web.cli` 下增加以下命令；均需 `--config`、`--case`，只允许维护者在可信终端执行，不暴露对应 HTTP 写接口。

| 命令 | 参数 | 行为 |
| --- | --- | --- |
| review-memory | --source reviewed-memory.json；可选 --dry-run | 校验已审核 revision/生命周期材料及来源，追加可信账本；不调用模型、不修改旧 revision |
| validate-stories | --source reviewed-story.json | 只读检查完整性、公开范围、证据闭包和可展示状态 |
| import-stories | --source reviewed-story.json；可选 --dry-run、--activate | 默认只写不可变 story/新增历史证据；显式 activate 才切本案例公共根。dry-run 永不修改根 |

所有命令只报告 ID、数量、状态、错误码及缺口，不打印正文、凭据或私有路径。成功 0；校验失败 3；运行异常非零。dry-run 与正式导入使用同一校验路径。review-memory 只接收维护者已审核的 manifest，不把模型声明的 approved 当作审核。

`reviewed-memory.json` 包含固定 revision 内容、原始来源引用及摘要、审核决定、适用范围、修订原因/新证据和可选 parent；关联文件使用相对源根的白名单路径。只接收本项目/当前授权范围，不能重标其他会话私有内容为公共。

`reviewed-story.json` 是维护者组装的导入 manifest，含 StoryBundle、所需额外 historical records、文件列表、原始/公开摘要和审核范围。已存在的记录可引用但必须内容相同；不存在的引用必须随输入材料提供。不能依赖导入机器上偶然存在的完整工作区。

## 2. 导入校验

先全量验证后提交，不允许半个故事进入 active 根：

1. 严格 schema、案例一致性、未知字段/格式版本拒绝；本次 optimization 只能 awaiting_data。
2. 每个文件大小与 SHA256、RTL 完整树、report/verifier/VCD 绑定；禁止 symlink、绝对路径、上级穿越和未声明文件。
3. 所有实体引用存在且类型一致；run/version/validation/波形相互匹配；跨案例、跨会话材料拒绝。
4. 区分客观验证和 legacy reported 字段；无法证明的阶段不升级。只有 UI fixture 的材料禁止作为公共故事激活。
5. 公共正文逐字段白名单；检测秘密、私有路径、参考设计私有源码与其他访客信息。内容扫描不是授权替代，必须有维护者审核范围。
6. 同 ID 异内容冲突在写入前整体拒绝；重复内容幂等。使用临时存储和数据库事务，失败不改公共根；恢复后不得留下可达的半成品。

公开派生摘要与原始材料分别保存摘要和 provenance；原始文件 exposure=private，公开 DTO/可展示 artifact 为 display。通用字段删除函数不能代替正文审核。

## 3. Historical seed v2

顶层目录仍严格为 `seed.json + files/`。保持 v1 原规则；新增 v2 使用判别 schema，不把 v2 默认字段写回旧 seed 后重算旧 ID。

| 项 | v1 | v2 |
| --- | --- | --- |
| schema_version | rtl-demo-seed-v1 | rtl-demo-seed-v2 |
| 案例根 | 原 cases | 原 cases 保留 |
| 故事根 | 无 | 可选 stories: case_id → story_id |
| record kinds | bundle/run/version/validation/artifact | 原五种 + story |
| 闭包起点 | 案例 Bundle | 案例 Bundle + 声明故事根 |

引用遍历必须识别 story 内嵌经验、use、revision 的所有 typed refs，不能仅靠字段名后缀猜测；波形索引/tiles 和额外归档 run 也进入闭包。排除不可达垃圾、会话表、聊天、操作队列、owner 不为空的私有记录。维护者审核后的公共副本与私有来源保留明确映射，不搬运整个用户数据库。

原 `export-seed/import-seed` 命令扩展读取/导出 v2；无故事的旧数据仍可按 v1 导出并通过旧测试。有 active story 时输出 v2，不允许静默丢掉故事。读入前全量校验；导入 seed 与切 active 根按既有发布事务管理，不能覆盖访客会话数据库。

v2 私有 seed 可包含声明所需的私有审核报告；它们只服务可信审计，不进入静态公共目录。既有 verifier/参考资源仍按原私有 verifier 层管理，避免故事包重复公开。

## 4. 静态导出

扩展原 export-static / prepare-cases，按 active story 生成案例内 stories manifest 和公共 DTO；闭包包括故事额外历史的 display 代码、报告及波形索引/tiles。没有公开权限的证据显示“材料未公开”，不生成可访问 URL，也不借另一条 PASS 补齐。

服务端与静态必须比对 story_id + 公共 fingerprint。指纹不符时拒绝混用。只读浏览可离线，真实问答仍通过原后端。

## 5. 服务器传输边界

| 既有层 | 本次增量 |
| --- | --- |
| design | 前端构建产物及审核公共故事/证据，位于 Agent 站发行版 |
| runtime | 新故事/经验适配源码及原必要运行模块；无依赖升级 |
| seed | 完整 v1 或 v2 私有历史证据闭包 |
| verifier | 继续原验证资源，无 PPA 工具链 |
| ops | 原部署与校验脚本的 seed 兼容更新 |

不传 specs、tests、.git、node_modules、完整 rtl_outputs、全局 memory 原始目录、Codex 私有日志、会话数据库、模型配置/密钥、SSH 材料。本次没有 Liberty、OpenSTA/Yosys 安装或 PPA 常驻服务。

部署目标仍是 `agent.deepvalleychip.cn`，后端只监听回环/受控私网，沿用 Caddy。`design.deepvalleychip.cn` 及主站/www 不变。新发行版 manifest 必须包含当前有效修复，不能用旧快照覆盖线上增量。

回退按 release+对应 seed+active 根整体选择；旧后端不读取 v2。保留旧公共故事以恢复原会话，私有会话数据不回滚覆盖。实施前后检查原四案例、波形、对话及原站路由；本规划不执行服务器操作。
