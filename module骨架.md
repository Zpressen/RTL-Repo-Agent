```
## 1. 背景

当前 `module_skeleton_v2` 采用 JSON 作为 planner 的主输出，优点是结构清晰、方便校验；但缺点是：
- Structural Skeleton 更像“分析视图”，不像“面向代码生成的主骨架”
- region/role 容易逐渐膨胀成固定 taxonomy
- behavioral 信息已经开始混入 structural 区域
- 与后续 subtask decomposition / retrieval / merge 的连接不够直接

本次改造目标不是推翻现有方案，而是做一次 **LocalV-style 升级**：

- 保留现有流程中的有效部分
- 将主输出从 JSON 切换为 **SkeletonDoc（Markdown DSL）**
- Structural Skeleton 改为 **pseudo-code-first**
- Behavioral Skeleton 改为 **overlay 到 structural blocks**
- JSON 改为可选导出产物，而不是 planner 的第一输出

---

## 2. 改造目标

### 2.1 总目标
将 stage3 的 module skeleton 规划，从“固定 region JSON”升级为“LocalV-style structural skeleton + behavioral overlay + subtask plan”的三层产物。

### 2.2 子目标
1. 让 planner 的主产物更像代码骨架，而不是字段表
2. 允许 structural block label 自由生成，而不是从固定标签闭集中选择
3. 保留极小的粗粒度 `block_kind`，保证系统稳定性
4. 将 behavioral 信息挂载到 block，而不是另起一张平行表
5. 保持与现有 repo_skeleton / module_contract / spec extraction 的兼容
6. 允许从 SkeletonDoc 自动导出 JSON artifact，供后续工具链消费

---

## 3. 非目标

这次改造不做以下事情：
1. 不重写 stage1 / stage2 的信息抽取逻辑
2. 不引入知识图谱
3. 不重写后续 code generation / merge / debug 流程
4. 不追求一次性覆盖所有 RTL module 风格
5. 不在这次改造中解决所有 prompt 优化问题

---

## 4. 核心设计决策

### 4.1 Structural block 的标签策略
采用：
- `block_label`: planner 自由生成
- `block_kind`: 小型固定粗分类

建议 `block_kind` 仅允许以下值：
- `decl`
- `inst`
- `seq`
- `comb`
- `helper`
- `meta`

解释：
- `block_label` 承载任务特异结构，例如 `seq_round_counter`、`comb_round_network`
- `block_kind` 只提供最粗粒度归类，便于 parser / validator / downstream tool 使用

### 4.2 主输出格式
planner 主输出改为 Markdown DSL，命名为：

- `MODULE_SKELETON_DOC v1`

而不是直接输出 JSON。

### 4.3 Behavioral Skeleton 的位置
behavioral 不再与 structural 平行存在，而是：
- 先给出 module-level behavioral summary
- 再对每个 structural block 写 behavioral overlay

### 4.4 JSON 的角色
JSON 不删除，但降级为：
- SkeletonDoc 的导出格式
- downstream 工具的消费格式
- 调试 / 对比 / 存档格式

---

## 5. 新的统一 schema

### 5.1 主格式：SkeletonDoc

​```md
# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: <target module>
- file_path: <planned output path>
- source_refs:
  - module_contract_ref: <optional>
  - repo_skeleton_ref: <optional>
  - spec_ref: <optional>
- planning_note: <1-3 sentences>

---

## 1. Module Frame
​```verilog
module <module_name> (
    // <ports>
);

// <block: ...>
// <block: ...>
// <block: ...>

endmodule
​````

---

## 2. Structural Skeleton

### Block

* block_id: <unique id>
* block_label: <planner-defined label>
* block_kind: <decl | inst | seq | comb | helper | meta>
* required: <true/false>
* purpose: <structural purpose>
* code_shape: <declaration group | always block | assign cluster | function defs | instantiation cluster | mixed>
* depends_on: [<block_id>, ...]
* placeholder:

  ```verilog
  // pseudo-code placeholder
  ```
* must_appear:

  * <required structure or object>
* may_appear:

  * <optional structure or object>
* retrieval_focus:

  * <required spec facts / section types>

### Block

...

---

## 3. Behavioral Overlay

### Module-Level Behavioral Summary

* control_style: <counter_driven | explicit_fsm | flag_driven | mixed | undecided>
* semantic_modes:

  * <mode>: <meaning>
* state_model:

  * object: <name>
    storage_kind: <registered | wire-like | derived>
    representation: <scalar regs | packed vector | array | undecided>
    notes: <optional>
* global_invariants:

  * <must-hold property>
* open_semantic_questions:

  * <uncertainty>

### Block Behavioral Overlay

* block_id: <structural block_id>
* responsibilities:

  * <semantic responsibility>
* timing_semantics:

  * <posedge / comb / one-cycle / final-only / etc.>
* touched_objects:

  * <signals / regs / child outputs>
* coupling_rules:

  * <cross-block dependency>
* forbidden_drift:

  * <things generator should not hallucinate>

### Block Behavioral Overlay

...

---

## 4. Decision Ledger

* chosen_decisions:

  * topic: <topic>
    decision: <decision>
    reason: <reason>
* deferred_decisions:

  * <deferred item>
* structural_risks:

  * <risk>
* behavioral_risks:

  * <risk>

​```

## 8. 对 aes_cipher_top 的期望形态

Codex 在改 prompt / parser / artifact 时，应以 `aes_cipher_top` 为第一个迁移样例。目标不是让 block 名字固定，而是让它自然长出类似下面的结构：

​```verilog
module aes_cipher_top (
    // <ports>
);

// <block: decl_state_and_keys>
// <block: inst_sbox_and_key_expand>
// <block: helper_mixcolumns_gf>
// <block: seq_load_and_counter>
// <block: seq_state_commit>
// <block: comb_round_network>
// <block: seq_final_output_and_done>

endmodule
​````

注意：

* 上面只是示意，不是固定标签模板
* 只要求 block 足够接近真实代码组织
* 不要求 planner 必须生成相同命名

---

## 12. 给 Codex 的执行要求

请按以下原则修改代码与文档：

1. 不要推翻现有 stage1 / stage2 / repo_skeleton 流程
2. 优先做增量兼容改造
3. 主输出改为 Markdown SkeletonDoc，但保留 JSON 导出能力
4. 避免引入大而全的 taxonomy
5. 允许 block label 自由生成
6. behavioral overlay 必须挂在 structural block 上
7. 优先保证 `aes_cipher_top` 单例跑通，再考虑泛化

---

## 13. 预期结果

改造完成后，stage3 应形成如下关系：

* 输入：

  * module_contract
  * repo_skeleton
  * module spec / extracted facts

* planner 主输出：

  * `MODULE_SKELETON_DOC v1`

* parser 输出：

  * structured skeleton object

* exporter 输出：

  * `module_skeleton_v3.json`

这样你就能同时得到：

1. 一个更像 LocalV 的 planning surface
2. 一个比 LocalV 更强的 behavioral overlay
3. 一个仍然能被现有工具链消费的结构化 artifact

​```
```
