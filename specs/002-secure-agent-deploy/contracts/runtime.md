# Contract: 同机入口、能力与受控执行

基础业务API沿用[001 Web API](../../001-rtl-agent-demo/contracts/web-api.md)及[证据契约](../../001-rtl-agent-demo/contracts/evidence.md)。本特性不增加通用远程终端或任意文件接口。新增契约以实现时向后兼容扩展为准。

## 1. 入口和身份

- HTTPS正式origin为`https://design.deepvalleychip.cn`。Caddy对静态、cases和全部API统一演示认证；未授权401，不能读取受保护内容或触发模型/执行。
- `/api/*`以原路径代理`127.0.0.1:8000`；后台不绑定公网/私网接口，不复用28989。不使用handle_path剥离前缀，未知API返回JSON错误而非index.html。
- Caddy覆盖`X-Demo-Gateway-Key`，移除转发给后台的Authorization；客户端不能伪造网关身份。模型密钥不进入Caddy。
- 保持case会话cookie为HttpOnly/Secure/SameSite=strict，POST/PATCH需JSON、批准Origin、`X-Demo-Request: 1`及既有Idempotency-Key规则。生产环境不能启用开发绕过。
- 请求上限统一20,000字节，含缺少Content-Length及流式请求；网关和后台均须有界读取，过大413。原模板20KB需校准为相同字节值。
- SSE路径沿用现API，认证及会话校验一致；代理不缓冲进度。重连从事件ID恢复，不创建模型请求或任务。

## 2. health和能力

保留`GET /api/health?case_id=...`的capabilities/checks结构；新增release_id、checked_at及每能力acceptance/证据引用字段。响应仍需网关认证，不返回绝对路径、配置正文、上游秘密或完整manifest。

available表示当前就绪；acceptance为not_run/passed/failed，二者独立。普通health不进行真实付费调用。generate/fix仅在当前profile、KG构图/查询、parser、验证材料、工具链、sandbox及预算全部就绪时可用。历史特定版本缺契约应由该操作报contracts_missing，不伪造整例缺失或成功。

预检缓存绑定release、非秘密配置指纹、工具/解析库/材料版本和时效；秘密状态仅记录配置存在/认证是否成功，不输出秘密hash。改变部署版本或已声明输入后缓存无效。

既有CLI preflight拟增加`--fail-if-unready`：默认继续输出JSON报告；带该选项时，任一承诺能力未就绪返回退出码4，全就绪返回0。生产完整检查必须核对当前API/worker的release_id及四例正式数据，不能仅凭旧心跳判定。prepare通过协调器执行候选离线门禁，不使用这个要求生产worker的模式；真实能力验收仍单独记录。

## 3. 准入、恢复和错误

沿用消息/操作接口与context_ref白名单。错误统一既有`error.code/message/request_id`；错误详情脱敏。

| 场景 | HTTP/安全代码 | 副作用 |
| --- | --- | --- |
| 无入口资格 | 401 gateway_required或Caddy challenge | 无内容/无调用 |
| 来源/会话/案例不匹配 | 403或既有422 context_mismatch | 无任务 |
| 缺执行幂等标识/字段不合法 | 422 | 无任务 |
| 已有RTL任务 | 409 busy（沿用现有代码） | 无第二执行 |
| 同会话已有回答 | 409 chat_busy（沿用现有代码） | 无第二回答 |
| 全局问答槽已占用 | 429 chat_busy及Retry-After | 无新模型调用，保留草稿 |
| 维护或恢复中 | 503 service_recovering | 不接受新付费请求/任务 |
| 依赖、预算、隔离未就绪 | 503 dependency_unavailable/resource_unavailable | 无不受控执行 |
| 输入摘要变化 | 409 input_changed/contract_changed | 中断并保留诊断 |

幂等重试先查询原记录，返回同一消息/操作；不能因为目前忙碌而重复创建。恢复中旧accepted/running和replying明确interrupted，用户需用新请求显式再试；刷新、SSE重连、进程自启不重跑。API/worker共享恢复代际与准入事务，不能恢复时接入新任务再误中断。

## 4. worker到runtime的内部接口

拟新增runtime入口：

```bash
AGENT_PYTHON -m zerorepo.rtl_web.runtime --job JOB_JSON
```

仅由worker固定argv调用，不用shell、不接受网页命令或路径。job格式见[data-model.md](../data-model.md)，禁止session/gateway秘密及Store路径。旧`--operation/--config`开发入口可保留，但生产必须使用隔离job链路。

worker负责读取授权version/contract并复制当前输入；runtime只见只读描述符和输入、当前可写工作目录、白名单工具/库及必要模型/KG配置。共享Store、其他runs、生产认证总目录不挂载。每run唯一挂载路径，KG分区不碰撞。工具环境按白名单创建，不继承无关业务/开发环境；模型/profile秘密只给需要它的进程，不出现在argv、日志或产物下载中。

runtime输出事件与result文件；worker对照job校验IDs、RTL清单、来源材料/适配hash、报告统计、原始VCD和采样规则后归档。真实PASS必须由受信reviewer结论支持；技术fail有绑定证据仍可作为真实结果，进程退出0不能替代验证。

外层runtime持有KG连接不代表Codex工具能继承这些秘密。现有private descriptor会包含KG配置，实施必须拆分：可信MCP/连接层持有私有配置；Codex子进程看不到该descriptor及参考源码，环境不含KG/站点秘密，通过当前run的本地受限桥接访问既有工具。桥接只接受登记的工具及当前run目标，禁止任意Cypher/路径扩展；MCP接口保留现有客户端语义。验证Codex/native shell无法获得KG密码或查询其他分区，不能仅靠工具提示词限定范围。

## 5. 隔离及资源验收

固定bubblewrap挂载定义随代码评审，不接受浏览器扩展。保留Codex sandbox/MCP；原始规格/TB/参考不可写，merged与必要规划/调试输出可写。子进程不能读其他会话、Store、session.key、CAD目录或系统秘密。

systemd系统单元保护代码并限制worker及后代的CPU/Memory/Tasks；job卷有总容量硬上限，单job/归档水位独立监测。超限结束当前任务并给出原因，回收仅限其拥有的进程/挂载；不重启Caddy/CAD、不删除已有证据。namespace/cgroup/磁盘边界任一未实测生效，不标完整运行能力就绪。
