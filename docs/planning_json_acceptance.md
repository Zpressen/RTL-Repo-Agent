# JSON 规划链路实现与验收记录

更新：2026-11-07。AES 与 E203 ALU 已使用当前配置的真实模型完成 Stage1—Stage4，门控通过；各自重跑复用未增加 API 请求。此前连接失败记录保留在下文，作为历史诊断，不代表当前验收状态。规划门控不构成功能正确性证明。

最新机器报告：[真实模型验收汇总](../rtl_outputs/_acceptance/api_validation_20261107/validation_report.json)、[AES](../rtl_outputs/_acceptance/api_validation_20261107/aes_inv_cipher_system_hard/acceptance_report.json)、[E203 ALU](../rtl_outputs/_acceptance/api_validation_20261107/e203_exu_alu_system/acceptance_report.json)。另已从保存的候选真实续跑 IFU：11 项必需责任、22 个状态对象、22 项义务及 23 项生成任务通过 Stage4 门控，随后原命令重跑新增 API 请求为 0。[IFU 修复与验证报告](../rtl_outputs/_acceptance/ifu_harness_20261107/report.json)。

IFU 修复上下文不再重复整份 Stage1 派生事实正文，也不在每条来源错误中复制整份允许证据 ID 列表。完整原文目录、RU/状态候选、修复范围及领域校验保留。初始完整上下文继续参与检查点指纹，因而已有候选可续修，规格和事实变化仍会失效。节点检查点记录系统、基础提示、上下文、校验反馈和框架文本的字符分项；超过预算仍明确失败，不截断必要证据。

## 实现状态

- 保留 RU、耦合约束、三候选、双轮排序及分歧裁定。来源统一为 EV 标识，程序展开严格核验的 SourceEvidence。
- Stage1—Stage3 共用 PlanningSession/RequestExecutor，候选、问题及修复范围在后续请求前持久化。修复以结构化实体替换为单位；预算耗尽或连续两次候选与错误不变时明确结束并保留现场。
- Stage3 以 ModuleSkeletonDraft 设计，程序编译骨架 JSON、状态对象、继承契约和 Overlay，渲染五章节 Markdown。主流程不解析或修补 Markdown。
- Stage4 规格映射及任务组装无模型请求，description=purpose、constraints=[]，完整任务契约不截断；无合法来源时失败，无全规格成功降级。
- 门控、恢复、KG、Stage5、Stage6 和离线生成恢复读取 JSON；Markdown 仅为可重建视图。状态、占位符、Overlay 和实际规格文本均可重新核验。旧规划策略不复用，原有案例及 RTL 未迁移、清理或改写。

参考本地 pi `/home/mokita/agent_intership/pi`（`be14d9732`）的 agent-loop、agent-session、session-manager；没有增加 Node/RPC、pi-durable 或模块并行。

## 自动化检查

31 个相关测试文件的回归结果：602 passed、1 skipped，约 255 秒。跳过项需要当前环境未安装的 Verilator。范围包括来源与覆盖门控、JSON 细化、局部修复、候选保护、中断恢复、请求预算、缓存变更、运行断点、Stage5/Stage6、KG、系统修复发布及旧时序流程禁用。

随后对派生块标识、修复统计和未知 usage 补充检查；结果见机器汇总。测试使用模型替身、HTTP 模拟流及临时目录，不构成两个真实案例已跑通的证据。完整仓库测试收集另受两个未找到的模块影响：`zerorepo.rtl_impl.debug_agent.asserter`、`repo_encoder`；上述相关回归集未包含这两项收集错误。

已验证的恢复场景包括：修复请求超时后继续候选；响应已保存但验证提交中断；非法实体替换不能污染候选；来源补充更新指纹后续跑同一候选；Stage4 重建无模型调用；Markdown 编辑不触发重新生成；规格、骨架 JSON、状态所有权或任务契约变化使相关缓存失效。工作台观察器断开不会改变提示词、预算或结果。


## 受控实体修复对照

同一小规格、一次来源错误的替身对照，比较全对象修复策略与 EV 实体修复：

| 策略 | 替身调用数 | 输入字符 | 输出字符 | 完整责任表响应 |
| --- | ---: | ---: | ---: | ---: |
| 全对象修复 | 2 | 36,135 | 12,666 | 2 |
| EV 实体修复 | 2 | 24,213 | 3,578 | 1 |

这是请求执行器对固定替身响应的实测序列化字符统计，不是旧完整系统的真实模型性能测试。服务端 token 均未知，不能据此估算货币或两例真实运行的节省比例。[对照数据](../rtl_outputs/_acceptance/controlled_entity_repair_comparison.json)。

## 已捕获响应的离线回放

| 案例 | 已捕获模块 | 完成新 JSON 编译与任务组装 | 限制 |
| --- | ---: | ---: | --- |
| AES | 6 | 6 | 使用历史响应，不是新模型从 Stage1 开始运行 |
| E203 | 4 | 4 | 所选架构另有 5 个模块没有已完成的历史骨架 |

回放使用精确来源与 EV 映射，包含已有 AMO 表格。修复了规格分块器丢弃纯标题摘录的问题，并保留围栏内文本；未改变来源内容来消除错误。E203 缺少的模块为顶层、regular、muldiv、nice、shared_datapath。

- [AES 回放报告](../rtl_outputs/_acceptance/replay_v2/aes/replay_report.json)
- [E203 回放报告](../rtl_outputs/_acceptance/replay_v2/e203/replay_report.json)

显式回放入口为 `scripts/replay_planning.py`，不会由普通恢复自动调用；输出在独立目录，历史输入只读。

## 2026-11-06 真实模型验收的历史阻塞

当前配置模型为 `deepseek-flash`，目标为 `api.deepseek.com`。当前模型公开配置指纹为 `1033ac40957e0341046bc615bd17e192e1ca96f7cf9128fe0d67fefcc4fca9e3`，不包含 API key 明文。旧尝试的实际配置指纹分别保存在各自报告中。

两例均在 Stage1 请求连接阶段失败，没有取得可验证模型响应或通过的规划门控：

| 案例 | 传输尝试 | 传输重试 | 准备消息字符累计 | 正文字符 | 服务端 token 用量 |
| --- | ---: | ---: | ---: | ---: | --- |
| AES | 2 | 1 | 69,318 | 0 | 未知 |
| E203 | 2 | 1 | 128,038 | 0 | 未知 |

字符统计不是已发送网络字节或 token。两例记录总耗时分别约 365.65、365.43 秒，包括失败请求和环境退出等待，不能用作模型性能比较。此时没有内容修复成功或模型成本节省结论。

沙箱无法解析 `api.deepseek.com`。随后针对 AES 的联网验收申请被自动审批拒绝，理由是尚缺少向该目的地发送规格和规划上下文的明确授权；未通过其他途径绕过。后续需要明确授权和可用网络，才能进行两例空目录 Stage1—Stage4、零新增请求复用及真实响应故障恢复验收。

- [AES 实际尝试记录](../rtl_outputs/_acceptance/planning_v2_20261106/aes_inv_cipher_system_hard/acceptance_report.json)
- [E203 实际尝试记录](../rtl_outputs/_acceptance/planning_v2_20261106/e203_exu_alu_system/acceptance_report.json)
- [机器可读汇总](../rtl_outputs/_acceptance/planning_json_report.json)

这些 blocked 报告仅描述当时失败的连接尝试。后续获得明确授权并联网完成的验收见文首 2026-11-07 报告，不能将历史尝试与成功运行的用量混为一谈。
