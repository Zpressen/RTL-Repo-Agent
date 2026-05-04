# RTL Impl Level 增量改造计划

## Summary

按当前约束，目标是“最大化复用现有 `impl_level` 代码与 agent 流程，只做 RTL 定向增量改造”，不新起平行目录，不重写主编排。

核心原则：

- 保留 `ImplBuilder -> FileDesigner -> FuncDesigner -> TaskPlanner` 主链路。
- 保留现有 Design + Review agent 模式，不改 agent 框架。
- 优先在现有类中加 `rtl_metadata` 分支和少量数据字段扩展。
- 只把明显绑死 Python `class/function/ast` 的位置改成“RTL 模式可旁路 / 可替换”。

---

## Key Changes

### 1. `ImplBuilder` 继续作为唯一入口

- 保留 `impl_builder.py` 的阶段结构不变：
  `create_initial_rpg -> build_skeleton -> build_graph -> plan_all_tasks`
- 已有的 RTL 判定 `_is_rtl_repo()` / `_should_preserve_rtl_blueprint()` 继续沿用。
- `build_skeleton()` 保持现有 seeded skeleton 逻辑，不改 agent 流程。
- `build_graph()` 和 `plan_all_tasks()` 仍然调用现有 `FuncDesigner` / `TaskPlanner`，但在内部加 RTL 模式分支，而不是新增一套外部 builder。

### 2. RPG 与 Skeleton 做小扩展，不重构

- 继续复用现有 `RPG` / `Node` / `NodeMetaData` / `RepoSkeleton` / `FileNode`。
- 只给 `NodeMetaData` 增加一个通用 `attrs` 字段，用来装 RTL 专有信息：
  - `bucket`
  - `file_kind`
  - `responsibility`
  - `owned_modules`
  - `depends_on_files`
  - `related_req_ids`
  - `related_test_ids`
  - `related_prop_ids`
  - `related_node_ids`
  - `related_code_anchor_ids`
  - `related_hint_ids`
- `create_initial_rpg()` 不推翻现有树构建逻辑：
  - 继续从 `Component[].refactored_subtree` 建 feature tree
  - 但在 RTL 模式下，把 `rtl_metadata.file_specs` 同步写入 file 节点 metadata
- 不改 `global_repo_rpg.json` 的整体框架，只增强节点 metadata，避免影响下游读写代码。

### 3. `FileNode` / `ParsedFile` 做 RTL 容错，而不是推翻 unit 机制

- 当前最大问题是 `FileNode` 构造时总会调用 `ParsedFile(code, path)`，而 `ParsedFile` 只会 `ast.parse`。
- 这里不重做 parser，只做最小改动：
  - 对 `.sv`、`Makefile`、shell 脚本等非 Python 文件直接跳过 Python AST 解析
  - 这些文件的 `units=[]`
- 这样可以保住现有 `RepoSkeleton`、序列化、路径查找、任务分发逻辑，不会因为 RTL 文件内容导致异常。
- RTL 的实现单元不从 `FileNode.units` 来，而从 `rtl_metadata.file_specs/module_specs` 补入。

### 4. `FuncDesigner` 复用现有 orchestrator，替换其 RTL 输入语义

- 保留 `FuncDesigner.run()` 的三阶段结构：
  - `build_data_flow()`
  - `design_base_classes()`
  - `design_interfaces()`
- RTL 模式下分别做如下改造。

#### 4.1 `build_data_flow()`

- 优先复用现有 `DataFlowAgent` 入口和 review 流程。
- 仅修改 prompt/tool 输入语义：
  - 从“Python 子树间数据流”改为“RTL 文件/模块依赖流”
  - `source` / `target` 允许是 bucket 或 file path，不再只按功能子树名称
- 如果 `rtl_metadata.file_specs.depends_on_files` 已经足够确定，可直接先生成 deterministic data_flow，再让 agent 只做补充或校验。
- 目标是少改 agent 框架，多改 prompt 与 env 组装。

#### 4.2 `design_base_classes()`

- 不删除这个阶段，但 RTL 模式下重定义其产物：
  - 不再生成 Python base class
  - 改为生成“shared RTL definitions”
  - 主要目标文件是 package、shared macros、typedef/enum/constants 归属
- 复用现有 `BaseClassAgent` 与 review 流程，仅替换 prompt、校验逻辑和输出约束。
- 输出格式仍沿用 `file_path + code`，但代码内容变成 SystemVerilog/package stub。

#### 4.3 `design_interfaces()`

- 这是最关键的复用点。
- 保留 `InterfaceAgent` 的单文件迭代 orchestration，不改其“按 file order 逐个处理”的外壳。
- RTL 模式下把“interface”定义为：
  - module port list
  - parameter list
  - package exports
  - TB harness / driver task contract
  - script CLI contract
- 不再要求 `ParsedFile.units` 提供 class/function。
- 改为在 RTL 模式下用 `rtl_metadata.file_specs` 和 `module_specs` 构造 `units_to_features` / `units_to_code` 的替代输入：
  - unit key 采用 `module:<name>`、`package:<name>`、`tb:<file>`、`script:<file>`
  - unit spec 文本来自 `responsibility + owned_modules + related_* ids + depends_on_files`
- `InterfaceAgent` 的 tool 和 env 保持原模式，但其参数模型在 RTL 模式下允许提交“RTL contract/code stub”而不是 Python function/class。
- 现有只接受 `class/function` 的过滤逻辑需要改成：
  - Python 模式保持原样
  - RTL 模式接受 `rtl_module / rtl_package / testbench / script` unit kinds

### 5. `TaskPlanner` 保留，但把 unit 语义泛化

- 保留 `TaskPlannerAgent`、`TaskPlanningEnv`、`TaskBatch` 的框架。
- 最小必要改动如下。

#### 5.1 `TaskBatch`

- 保留 `units_key`
- 将 `unit_to_code` 泛化为 `unit_to_spec`
- 为兼容旧逻辑，在数据类中同时保留：
  - `unit_to_code` 作为老字段
  - `unit_to_spec` 作为新字段
- RTL 模式优先写 `unit_to_spec`，SWE 模式继续写 `unit_to_code`

#### 5.2 `TaskPlanner`

- 保留“按 subtree -> file -> units 规划 batch”的主逻辑。
- RTL 模式下不再依赖 `file_code + Python units`，而是依赖：
  - file-level RTL contract
  - module/package ownership
  - dependency order
  - related req/test/prop ids
- prompt 改为规划 RTL implementation batches：
  - module implementation
  - package definitions
  - tb implementation
  - scripts/build integration
- `_add_special_batches()` 改成 RTL 语义：
  - subtree verification batch
  - final repo validation batch
- 不再生成“module APIs integration tests”这种 Python 文案。

---

## Tests

### 1. `ImplBuilder` RTL 路径回归

- 现有 `repo_data.json` 可走通 `build_skeleton -> build_graph -> plan_all_tasks`

### 2. `FileNode` 非 Python 容错

- `.sv` / `Makefile` / `.sh` 文件构造不触发 `ast.parse` 异常

### 3. `FuncDesigner` RTL 模式

- `build_data_flow()` 产出合法 DAG，且能反映 `depends_on_files`
- `design_base_classes()` 仅向 package/shared file 写 RTL stub，不污染其他文件
- `design_interfaces()` 能为每个 RTL 文件产出至少一个 unit contract

### 4. `TaskPlanner` RTL 模式

- 所有 RTL 文件都能生成 batch
- batch 顺序 obey file dependency
- special batches 为 RTL verification 语义

### 5. 产物校验

- `skeleton.json`
- `global_repo_rpg.json`
- `graph_result.json`
- `tasks_result.json`

都保持现有文件格式主体不崩，只扩展字段。

---

## Assumptions

- 本轮只规划到任务规划层，不包含后续 code generation executor 改造。
- 以现有 `rtl_outputs/rtl_spec_/.zerorepo/repo_data.json` 为主样例做设计。
- 不新增平行的 `rtl_impl_level/` 目录；优先在现有 `impl_level` 类和 prompt 中加 RTL 分支。
- 不大改 agent 框架，只允许：
  - prompt 替换
  - env 输入替换
  - tool 参数/校验扩展
  - Python-only 过滤逻辑加 RTL 条件分支




结合现在这套 agent 框架，最合理的改法不是“把 RTL 当成另一套系统重写”，而是把 **确定性信息前移，agent 只处理真正需要语义判断的部分**。

当前问题的本质是：`impl_level` 的 agent 外壳没问题，但喂给它的上下文仍然是 SWE/Python 语义。像这次 `DataFlowAgent` 看到的 `Functional Graph Overview` 只剩 bucket 空壳，就是因为它读的是 [global_repo_rpg.json](/home/mokita/RPG-ZeroRepo/rtl_outputs/rtl_spec_/.zerorepo/global_repo_rpg.json) 这种 feature-tree RPG，而不是 RTL 真正关心的 file/module graph。这个输入一错，后面 agent 再强也只是在空上下文上猜。

我建议按下面这个边界改，最符合现有框架，也最稳。

**1. 保留 agent 框架，改 agent 前面的“上下文构造层”**

不要先动 `AgentwithReview`、`ToolHandler`、review loop。这些机制本身是健康的。  
应该优先改的是 [impl_builder.py](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/impl_builder.py)、[designer.py](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/func_design/designer.py) 这一层，让 RTL 模式下传给 agent 的上下文变成：

- seeded skeleton 文件树
- `rtl_metadata.file_specs`
- `rtl_metadata.module_specs`
- `depends_on_files`
- `owned_modules`
- `related_req_ids` / `related_test_ids` / `related_prop_ids`

也就是说，先产出一个 **canonical RTL context**，再让现有 agent 消费它。  
不要让 agent 再从 feature tree 里反推文件关系。

**2. DataFlow 阶段要“半确定性”，而不是纯生成**

[DataFlowAgent](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/func_design/agents/data_flow_agent.py) 这层最适合保留，但职责要改：

- 确定性的部分：
  - 文件列表
  - bucket
  - `depends_on_files`
  - top/package/module/tb/script 的层次
- agent 负责的部分：
  - 给每条边补 `data_id`
  - 补 `data_type`
  - 补 `transformation`
  - 检查 DAG 是否符合 RTL 语义

也就是先构造 candidate edges，再让 agent“命名和审查”，而不是让它从零发明图。  
这比现在直接让它从空 overview 猜数据流合理得多。

**3. Interface 阶段继续保留，但把“interface”从 Python stub 改成 RTL contract**

最该改的是 [interface_agent.py](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/func_design/agents/interface_agent.py)。  
现在它默认 interface = Python function/class，这是不对的。但它“按文件逐个设计 + review + tool 输出”的流程本身是可以保留的。

RTL 模式下建议把 interface 重新定义为：

- `rtl_module`: port/parameter/interface contract
- `rtl_package`: typedef/enum/const export contract
- `testbench`: stimulus/checker/scoreboard contract
- `script`: build/run contract

然后：

- 不再依赖 `ParsedFile.units`
- `units_to_features` 和 `units_to_spec` 直接由 `file_specs + module_specs` 构造
- agent 输出的也不是 Python stub，而是 RTL contract/stub text

这属于“换输入语义”，不是“换框架”。

**4. BaseClass 阶段不要删，改成 shared definitions 阶段**

[base_class_agent.py](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/func_design/agents/base_class_agent.py) 现在名字是 SWE 命名，但阶段价值还在。  
RTL 下它最适合承担：

- package 内容草案
- shared typedef / enum / params
- 公共宏或 helper task/function 的归属建议

所以不要删这层，也不要新开 phase。  
直接把 prompt 和校验从 “Python base classes” 改成 “shared RTL definitions” 最合理。

**5. TaskPlanner 要保留，只把 unit 载荷泛化**

[task_planner.py](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/plan_tasks/task_planner.py) 的整体分批思路可以留。  
但它现在依赖 `units_to_code`，这个对 RTL 不成立。

合理改法是：

- 保留 `units_key`
- 新增 `unit_to_spec`
- RTL 模式下按 file/module/package/tb/script 生成 unit
- 任务描述围绕 contract 和验证目标写，而不是围绕函数实现写

这样后面的 task batching、priority、state tracking、TaskManager 都还能复用。

**6. 最不应该先改的是 RPG 主体结构和 agent 框架**

从工程风险看，我不建议第一步就去重做 `RPG` 的层级模型，也不建议重构 `AgentwithReview`。  
更合理的是：

- 先让 RTL 模式下的 graph context 和 unit context正确
- 再让现有 agent 流程在正确上下文上运行
- 最后如果确实发现 `RPG` 的 `feature/category/subcategory` 语义长期妨碍 RTL，再单独收敛模型

换句话说，先修“输入语义错位”，不要先修“框架形式”。

如果你要一个一句话结论：

**合理的改法是：保留现有 agent 流程，把 RTL 的确定性结构信息在 `FuncDesigner/TaskPlanner` 前面整理成 canonical context，agent 只负责补语义、补 contract、做 review，而不是让 agent 从 feature-tree RPG 反推 RTL 架构。**

如果你愿意，我下一步可以把 [RTL_IMPL_LEVEL_PLAN.md](/home/mokita/RPG-ZeroRepo/zerorepo/rpg_gen/impl_level/RTL_IMPL_LEVEL_PLAN.md) 改成更贴近这个思路的版本，把“哪些地方做 deterministic adapter，哪些地方继续交给 agent”写得更细。