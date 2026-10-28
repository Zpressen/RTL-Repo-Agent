# Workspace UI / Compatibility Contract

日期：2026-10-20。涵盖 FR-001～021、FR-024/025。不得用参考稿假数据替代真实材料。

## 1. 布局契约

桌面：顶部品牌/案例标签或选择器/当前记录状态/模式/回放/下载，下方 3px 进度条；左八步，中五页签，右指标/动态/对话。CSS grid 三列按 plan 定义，中心最大；页面自身不因 pre/SVG 溢出。高度使用剩余视口，header 换行后仍能正确分配。

右侧顺序：三张小指标卡 → AGENT ACTIVITY 折叠动态 → RTL Agent 消息 → 固定输入。指标为规划模块数、已记录候选次数、案例最终验证，并明确各自统计范围。最终 PASS 不应覆盖当前选中的历史失败状态。动态默认限高，不展示私有工具原文或推理过程；必要时折叠以保证输入可见。

参考稿四种重点色与卡片间距见 plan。五种内容均对照参考，但执行单元真实层次、波形控件和持续对话允许必要差异。无主导航、hero、RI / RSI 入口；不存在 Main.dc.html 链接。

窄屏：顶部可换行；时间线可折叠为步骤选择；证据占主区域，对话可打开收起且不销毁输入内容，输入打开后可达。tabs 可换行或自身滚动；只有代码/波形局部横滚。

## 2. 页签与步骤

canonical panel：spec / architecture / code / verify / repair。中文分别为规格 / 架构 / RTL 代码 / 仿真与波形 / 定位与修复。tablist、tab、tabpanel 语义明确，键盘可操作，选中状态可识别。

八 step_id 与映射见 data-model。点击步骤停回放，若有原事件选择对应位置与已有证据；无事件仅打开该步说明，不改变其他步骤结果。点击候选仅在有合法 validation/version ref 时切换对应证据。

播放只遍历真实事件；source=report_summary 的定位卡是阅读辅助，不自动追加一次历史定位事件。进度=(已播放原事件数)/(原事件总数)，不按八步自动计算，也不充当实时完成率。

从头播放与暂停/继续为分别可达的控制；点击页签不会重新执行任何后台操作。已知最终记录可手动打开，但需标“所选历史记录”，不能改变回放已到达状态。

## 3. 路由与持久选择

新工作台 canonical hash 为 #/workspace。query 可包含 case、panel、step、run_id、version_id、validation_id、module_id；对比可含 before_validation_id，须经过同案例与公开材料核对。公共分享只编码已审核公开 ID，不编码 session、消息、草稿、私有 run。

兼容表：

| 输入 | 归一行为 |
| --- | --- |
| 无 hash / #/workspace | 当前工作台 |
| #/optimization / #/experience | replace 为 #/workspace，保留有效案例和工程证据参数，移除 story/memory 选择 |
| panel=architecture/code/verify | 原义保留 |
| 旧内部 verification | 归一 verify，不继续向服务端发送 |
| panel=spec/repair | 按新枚举保存/恢复 |
| 无效 panel/step | 使用明确默认，不生成未知状态 |
| 显式非法或跨案例证据 ID | 显示证据错误，不静默替换成最终 PASS |

主动页签/步骤/公开证据导航 pushState；回放自动推进与连续波形移动 replaceState 或只改内存，避免污染浏览器历史。URL 公开选择优先于 session 默认；无显式选择再恢复经校验 session，否则当前案例最终验证。私有选择只在现有会话/history.state 保留。

旧故事入口只做归一，不调用 loadStories。当前已导出的四案例无额外 story.runs；额外已公开运行通过既有 validation/run 接口校验，未随版材料离线时说明缺失。

## 4. 现有接口的增量兼容

- Context 增加 workspace_panel 可选字段，五枚举；MessageRequest、OperationRequest 的 context_ref 可携带它，缺省仍合法。
- Selection.workspace_panel 五枚举，保持旧默认 architecture。PATCH 仍含 browsing_mode，服务端沿用 validate_context 校验引用关系。
- 新前端 Context.view 固定 workspace；服务端仍接受已有 optimization/experience 以读取历史数据，不重写旧消息。
- workspace 问答的 evidence 只选择规格、规划、所选版本/验证等工程材料，不无条件读取 story_view；旧的显式经验上下文另设兼容分支。提示按 workspace_panel 聚焦当前证据，不能把新工作台描述为 RSI 页面；历史/实时、采样规则和执行意图约束不变。可控 provider 验收 payload 不含无关故事内容，缺失或损坏的故事不能阻塞普通 workspace 问答。
- 案例/内容/运行/验证/波形、会话/消息/操作及事件接口路径不变，不修改已有能力准入规则。
- version.files 使用 file_manifest 与文件 artifact 映射。module_id 仍使用现有版本所识别的 ID，定义文件不新建伪架构模块。

## 5. 动态、对话与能力

api.subscribe 接收 event type/id 和允许字段，不只调用空 refresh。stage.updated 允许 stage/text（已脱敏摘要）；module.updated 允许 module_id/status；attempt.updated 允许 trial_no/decision/已有 refs；validation.completed 允许验证 ID、kind、verdict；operation 更新只展示 kind/state/stage。字段先核对当前 case/run/session，字符串使用 textContent。

SSE 以 event id 去重/断线续传，持久记录是权威；刷新后可从当前 operation/attempt/validation 快照重建摘要并标 current_snapshot，不凭空恢复未保存的事件发言。最多显示最近 100 条动态。

chat() 只创建一次。页签、步骤、结果刷新不清空 textarea；保留 IME Enter、防重复、pending 消息幂等重试、发送中新草稿不被清空的既有行为。查看旧消息证据必须使用该消息的 context_ref。

能力判定：无 transport/session 时不能发送，输入可编辑；chat available 可发普通问题；准确匹配现有三条显式操作句时看对应 capability，可绕过不可用模型直接使用既有操作路径。其余不明确文本不得为了执行就绪而自动执行。后端错误保留草稿与幂等键。

案例切换继续整页导航并保存当前草稿。迟到回复属于原 session，不能替换新案例消息列表。用户不在消息底部时，不因刷新强制滚动；可提示有新消息。

## 6. 证据展示

规格摘要附公开 source artifact 与可定位段落；没有已有约束提取记录时标为整理摘要。架构来自 planner；文件数来自 file_manifest。

修复页列全部变化文件，新增/删除也可识别。复用 simpleDiff 时必须标“对比片段”，不能标成完整统一补丁；API full diff 与各版本原文保留入口。缺少根因就说明，不请求模型补齐历史。

差异定位来自报告 first_failure_ticks 和已有 fail markers。游标值是波形时刻值，不保证等于采样比较器当次判定值；未知值与采样规则保持现有 contract。最终通过只能来自受信验证报告。

## 7. 最小契约验收

- 四案例实际数据及 E203 trial5/final 严格绑定，AES/SDC 缺失不补造。
- 五 panel 在 URL/Context/Selection 一致，旧三 panel 与旧 hash 可恢复。
- 播放/浏览无 messages/operations 写调用；显式操作只发一次。
- 三轮可控回复、IME、离线草稿、迟到回复、双访客隔离。
- 桌面输入区可见；窄屏无整体横向溢出；五状态截图符合参考。
