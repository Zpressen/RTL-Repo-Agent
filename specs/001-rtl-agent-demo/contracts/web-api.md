# Web API Contract v1

本文件定义拟实现的接口，不表示已有接口上线。浏览器只访问 `https://design.deepvalleychip.cn` 同源路径；开发环境由 Vite 转发 `/api`。Caddy 使用 handle 保留前缀，后台路由本身带 `/api`。

## 访问与通用约定

- Caddy 为整个 design 域名提供共享演示访问保护。每个后台请求还须带由 Caddy 覆盖写入的网关凭据；浏览器不持有此凭据或模型密钥。
- 会话通过 Secure/HttpOnly/SameSite=Strict cookie 关联；接口检查资源属于当前演示会话。POST 接受 application/json、允许的 Origin 和 `X-Demo-Request: 1`，不允许跨站调用写操作。非浏览器本机验收可使用明确启用的开发模式；生产模式禁止默认开放。
- 成功响应包含 request_id；错误统一 `{error:{code,message,request_id,active_operation_id?}}`。错误文本不能返回服务器密钥、环境变量或未脱敏traceback。
- 会话、消息和操作的创建请求带 `Idempotency-Key`。同键同payload返回原结果，同键异payload为409；不会因重连重放POST。
- 统计缺失为null；仿真tick在服务端为整数，在JSON中使用十进制字符串，避免浏览器数值精度损失。时间范围是 `[start_ticks,end_ticks)`。
- 浏览器传实体ID，不传本地路径、模型配置、命令或任意模块源；artifact_id只能映射到已登记白名单。

## 端点

| 方法与路径 | 输入 | 输出及行为 |
| --- | --- | --- |
| GET /api/health | 无 | API存活、bundle/chat/verify/generate/fix能力与不可用原因；不返回密钥或完整系统配置 |
| GET /api/cases | 无 | 四个固定案例及其可用状态 |
| GET /api/cases/{case_id} | 固定注册case_id | 案例简介、默认bundle、模块摘要、已记录validation引用 |
| POST /api/sessions | `{case_id:"e203"}` 或其他已注册案例 | 201，session与默认context，设置案例专属cookie；幂等重试不另建会话，同键跨案例409 |
| GET /api/sessions/{id} | 可选after_message_sequence | 会话快照、已保存消息、活动operation、last_event_id |
| POST /api/sessions/{id}/messages | text（1～4000字符）, context_ref, client_message_id | 202，message_id与received状态；异步解析/回答/发起动作，经SSE更新；同会话已有replying时409 chat_busy |
| PATCH /api/sessions/{id}/selection | browsing_mode, run_id, version_id, validation_id | 校验引用后保存浏览选择；不修改正在运行操作的目标，不触发执行 |
| POST /api/sessions/{id}/operations | kind, context_ref, source_message_id? | 202，operation_id与accepted状态；固定三种kind；全局忙时409 busy，缺依赖503，目标不清422 |
| GET /api/operations/{id} | 无 | 状态、阶段、结果引用、verdict或错误；不自动执行恢复 |
| GET /api/runs/{id} | 无 | 来源模式、阶段、版本、验证与修复尝试引用 |
| GET /api/versions/{id}/modules | 无 | 模块列表与所选版本的代码artifact引用 |
| GET /api/versions/{id}/diff | base_version_id | 同案例、来源明确的只读差异；基准不可比返回409 |
| GET /api/validations/{id} | 无 | RTL版本、采样统计、报告入口、comparison_policy与waveform状态 |
| GET /api/validations/{id}/waveform | start_ticks,end_ticks,signal_group=key | 本次验证的原始变化和采样marker，见evidence契约 |
| GET /api/artifacts/{id}/content | 无 | 白名单脱敏报告或RTL文本；不存在404，私有artifact403 |
| GET /api/sessions/{id}/events | Last-Event-ID 或 after | SSE，按事件ID补发当前会话可见事件 |

`operations` 与自然语言动作调用同一校验/调度服务。前端常态使用对话，操作接口供已解析意图和验收使用，不增加独立任务创建页面。

生成操作仅接受case_id与当前案例目标；verify必须指定完整可执行version_id；fix必须指定同版本的失败系统validation_id。verify与fix从历史版本发起时创建实时运行副本，保留source引用，不把历史记录原位变成实时记录。

## 对话结果

问答子进程只返回以下决策结构，服务器校验后登记或拒绝：

```json
{
  "kind": "answer",
  "text": "该乘除法模块保存迭代状态，并与共享算术资源配合。",
  "context_ref": {"case_id":"e203","run_id":"recorded-run","version_id":"before","validation_id":"before-check"},
  "evidence_refs": [{"artifact_id":"planning-summary","module_id":"e203_exu_muldiv"}],
  "action": null
}
```

kind仅允许 answer/clarify/open_artifact/generate_and_verify/verify/fix。open_artifact只改变展示；执行意图的action携带实体ID，没有shell或路径。回答中的证据引用必须在可见context中存在；验证统计由服务端真实记录提供，模型不能修改PASS或指标。无法核对的引用不链接为证据，回复说明不足。

动作目标有歧义时kind=clarify，等待回复，不创建operation。普通模型回答超时/失败生成可重试错误消息；不回退为固定“成功”回复。

## SSE

Content-Type 为 text/event-stream，Cache-Control 为 no-cache。每15秒发送一次注释heartbeat，每会话一个连接。

```text
id: 142
event: operation.updated
data: {"event_id":142,"session_id":"s1","operation_id":"op1","run_id":"live1","origin":"live","state":"running","stage":"verifying"}
```

事件类型包括 message.received/message.updated、operation.accepted/operation.updated、stage.updated、artifact.available、validation.completed 和 snapshot.required。先持久化再推送；客户端按event_id去重，不按到达时间推断顺序。

Last-Event-ID优先于初始after；补发不可用或cursor过期时发送snapshot.required，由GET会话快照重新同步。事件只更新所属operation/run；用户正在浏览历史时显示实时操作提示，不强制替换历史视图。断连后自动恢复观察，不POST新任务。

## 静态回放后备

前端读取 `/cases/index.json` 和 `/cases/{case_id}/manifest.json`，指向不可变bundle子目录。四个固定ID为 `e203`、`aes_cipher_system_hard`、`aes_inv_cipher_top_system`、`sdc_controller_system`。URL参数 `?case=` 选择案例；请求通过 `X-Demo-Case` 指定浏览案例，health使用同名 `case_id` 查询参数，会话路由以已保存的会话案例为准。上下文与会话必须属于同一案例；其他案例的运行不能成为操作目标。后台不可用时继续浏览历史规划、代码、报告和波形；对话输入给出不可用说明，保留已显示内容，不提供伪实时回答或假操作。

预置回放按bundle事件顺序运行，压缩节奏是独立replay_delay_ms，不能显示为原始wall time。切入实时执行时保留历史会话证据并清晰显示模式。

## CLI 边界（拟新增）

- `python -m zerorepo.rtl_web.cli preflight --config PATH --json`：检查路径、版本、bundle、worker与实际依赖导入，不默认发起模型或付费请求。
- `python -m zerorepo.rtl_web.cli import-case --config PATH --case e203 --source PATH --bundle-id e203-demo-v1`：导入并交叉核对证据；同ID不同内容拒绝覆盖。
- `python -m zerorepo.rtl_web.cli export-static --config PATH --bundle-id e203-demo-v1 --out PATH`：只导出展示白名单文件，写manifest与内容hash。
- `python -m zerorepo.rtl_web.cli prepare-cases --config PATH --out web/rtl-demo/public/cases`：一次导入并导出四个固定案例与目录索引。单例命令可传 `--case`。
- `python -m zerorepo.rtl_web.cli serve --config PATH --host ADDRESS --port 8000`：启动单Uvicorn API；生产不使用reload。
- `python -m zerorepo.rtl_web.worker --config PATH`：唯一worker，读取数据库操作，启动固定runtime入口。

命令仅由受信管理员或服务使用，HTTP不暴露任意CLI执行能力。
