# Contract：页面导航、故事查询与对话

状态：设计契约，待实现。现有 API 和会话机制继续使用；本次无 PPA 测量和图形接口。

## 1. 页面契约

主导航为“设计工作台 / 持续优化 / 经验闭环”，共享顶部案例选择、连接状态和右侧常驻对话。设计工作台内部保留“架构 / 代码 / 验证”标签，优化与经验拥有独立页面，不再加入同一排标签。

- 优化：标题“RI：在验证约束内改进设计”；“PPA 数据待接入”；一句说明“后续将展示同条件实验的真实测量与版本依据”。可用文字显示“提出候选 → 功能验证 → 测量比较 → 保留或放弃”。不画带数值坐标的图、不显示改善率/最佳值、不放启动实验按钮。
- 经验：标题“经验驱动改进”；默认一条经验卡和来源/使用/验证/修订摘要，其他条目用简短列表切换。区分未记录、已存档、已提供、已采用及验证结果；收益无对照显示待验证。详情使用原代码、报告、波形入口。
- 四案例分别取数；无经验显示本案例空状态。失败、退役和不完整证据可见；不显示文件数量增长或能力分数。
- 可键盘选择、在 1366×768 下对话可输入；仅浏览不提交问答或运行。静态历史仍可看，真实问答依赖 API 可用。

### 路由与深链接

使用无新增依赖的 hash 路由，页面入口为 `#/workspace`、`#/optimization`、`#/experience`；三个入口仍由现有 Vite 应用承载。查询串保留原 `case`，允许审核公共故事/证据的 ID 和工作台 `panel=architecture|code|verify`。例如：

```text
/?case=e203#/workspace
/?case=e203#/optimization
/?case=e203&story_id=PUBLIC_STORY&memory_revision_id=PUBLIC_REVISION#/experience
/?case=e203&validation_id=PUBLIC_VALIDATION&panel=verify#/workspace
```

上例 ID 是格式示意，不是可用材料。URL 不携带 session/cookie/token、聊天、草稿或私有实体 ID。无 hash 的旧链接默认工作台；未知 route 提示并回到工作台，保留有效案例。hash 在浏览器端解析，不新增服务器路径或 Caddy rewrite。

恢复顺序：显式 URL 页面和公共证据意图 → 同案例会话中兼容的已保存选择 → 页面默认状态；原始 deep link 必须经过归属/哈希/权限校验。显式引用失败时显示证据不可用，不用最近 PASS 替代，也不借会话旧记录满足该链接。仅无证据意图的普通入口才采用默认历史记录。

站内导航、证据跳转使用浏览器历史；刷新、前进/后退恢复对应页面与选择。共享 shell/对话/草稿/消息订阅只初始化一次，页面切换不重新创建会话、重复连接 SSE 或中断正在生成的回复。页面渲染与异步请求绑定案例及当前导航版本，丢弃过期响应，避免快速切换串案例。

“查看对应代码/验证”进入工作台准确 panel 和固定证据；浏览器后退回原经验选择。切案例保留当前页面种类，清除不兼容证据，恢复该案例自己的会话。仅导航或恢复不会发送新的问答或执行操作。

## 2. GET `/api/cases/{case_id}/stories`

返回当前已审核公共故事摘要/公共 DTO。案例无故事也返回 200 及明确空状态，而非伪造空数据成功曲线。

```json
{
  "case_id": "e203",
  "schema_version": "rtl-demo-story-view-v1",
  "story_id": null,
  "fingerprint": null,
  "origin": "historical",
  "optimization": {
    "state": "awaiting_data",
    "message": "PPA 数据待接入",
    "missing_evidence": ["同条件版本测量", "测量报告与功能验证绑定"]
  },
  "experience": {
    "state": "empty",
    "missing_evidence": ["审核后的经验材料"],
    "memories": [],
    "uses": [],
    "lifecycle_events": [],
    "comparisons": []
  }
}
```

此例为合法空响应，不是测量或复用素材。已审核内容按 `data-model.md` 投影；不得带 storage_key、owner/session、内部绝对路径、私有日志或未公开参考源码。

## 3. GET `/api/stories/{story_id}`

返回不可变公共 DTO，供旧会话与稳定引用恢复。仅可读已审核公开故事；不存在或不可访问返回统一 not_found，不泄露私有条目存在性。损坏故事返回 `story_evidence_invalid`，不拼接别的故事补齐。

公共 DTO 内的证据引用通过原 run、validation、artifact 接口访问；引用解析扩大到该故事所有声明的归档运行，仍逐项检查 case/owner/版本归属。不会修改原 Bundle。

## 4. 选择及请求上下文

原 Context 新增可空 `story_id, memory_revision_id, memory_use_id`，以及 `view=workspace|optimization|experience`（省略默认 workspace）；全部显式序列化。Selection 另加 `workspace_panel=architecture|code|verify`，省略默认 architecture。旧 payload 不填仍有效；view/panel 不能改变 origin、权限或 verdict。Selection PATCH 的 schema、显式取字段和存储均需同步，不能只改前端类型。

导航保留兼容的证据关联，聊天同时携带当前 view 和明确选择摘要，不能把前一页的记录冒充当前页结果。运行中消息绑定提交时上下文；随后导航不改变旧消息的引用。

服务端必须拒绝：跨案例 story；revision 不属于 story；use 不属于 revision；选择的 run/version/validation 与明确选中的使用证据冲突；借用他人会话材料。缺失对应材料返回可解释的 `story_context_invalid`，不偷偷改成最近 PASS。

刷新可恢复仅有 story/revision 的选择，不再要求 version_id 存在。切到来源/使用验证时，读取记录的 `Run.origin`；额外归档 run 不能因为不等于原主 run 而标实时。

本次不接受 campaign/trial 操作字段，未来 PPA 接入另扩展契约。操作种类仍只有原 verify/generate_and_verify/fix，沿用原准入与具体版本要求；选择经验本身不会启动修复。

## 5. 对话

使用原 message POST 和响应，不新增模型服务。证据 payload 添加选中 revision/use 的有限公开摘要、准备状态与已授权 artifact 引用。模型必须区分存档、检索、提供、实际采用、验证及收益；当前无 PPA 时明确暂无结果。

问答例：

- “这条经验来自哪里，后来实际用过吗？”
- “这个版本为什么修订，有什么验证依据？”
- “现在有 PPA 优化结果吗？”

回答只引用现有 allowed refs；没有公开证据不生成引用或成功结论。历史材料的问答可以实时生成，但不能称为刚执行了一次优化或学习。私有聊天不自动沉淀到公共故事。

## 6. 静态回退与发布一致性

`cases/{case_id}/stories/manifest.json` 保存公共 DTO 的 story_id/fingerprint 及公开证据索引；API 和静态身份一致才可混用。同一发行版的额外历史代码、报告和波形 tile 闭包必须一起导出。

无 API 时只浏览归档，原对话草稿可继续输入，发送状态按既有连接提示处理；不返回假回复。指纹不匹配则提示材料版本不一致，不混合两个发行版。无故事的旧 seed 使用上述空状态。
