# Stage1 / Stage2 本周组会汇报

本文整理为 5 页 PPT 可直接使用的内容，聚焦本周在 `module_planner` 中完成的 `stage1` 和 `stage2` 重构工作。

---

## 第1页：本周工作总览

### 标题
从 Spec 到 Repo Skeleton 的两阶段规划链路重构

### 核心内容
- 目标：把 RTL spec 转成后续可用于仓库骨架生成的结构化中间表示。
- 本周重构了 `module_planner` 的前两阶段：
  - `stage1`：从旧的 fragment-first 流程改成 contract-first 的多轮信息抽取。
  - `stage2`：从旧的 RFU extraction 改成 repo skeleton planning。
- 当前链路变为：
  - `spec markdown -> contracts.json -> modules.json -> repo_skeleton.json`
- 整体设计原则：
  - 只抽文档中明确出现的信息
  - 没有证据就留空
  - 上一阶段输出作为下一阶段主输入

### 建议讲稿
本周我主要做了 `module_planner` 前两阶段的重构。核心目标是把原始 spec 转成更稳定、更可复用的中间表示，服务后续仓库骨架和模块骨架生成。现在整条链路已经从原始 markdown 打通到了 repo-level skeleton。

---

## 第2页：Stage1 重构思路

### 标题
Stage1：多轮 Contract-First 信息抽取

### 核心内容
- `stage1` 现在是 6 轮固定顺序抽取：
  - `structure`
  - `interface`
  - `timing`
  - `control`
  - `datapath`
  - `planning_facts`
- 每轮输入：
  - 完整 spec markdown
  - 当前已经生成的 `contracts.json`
- 每轮输出：
  - 只补本轮对应字段
  - 完成后立即回写同一个 `contracts.json`
- 支持 `resume`
  - 用 `completed_rounds` 和 `stage1_status` 记录增量状态

### 关键改动
- 不再先切 fragment 再做后处理
- 不再默认依赖图片抽取
- 不再保留 `entity_alias_groups`
- 强调“文档无明确证据时字段留空”

### 建议讲稿
`stage1` 现在不是先拆文档再拼记忆，而是按任务类型分 6 轮抽取。这样每一轮职责更清楚，字段边界更稳定，同时可以增量写回和断点续跑。对工程上最重要的一点是，当前抽取策略显式优先，避免了“看起来合理但其实是编的”这类问题。

---

## 第3页：Stage1 输出与中间层设计

### 标题
Stage1 输出：`contracts.json` 与 `modules.json`

### 核心内容
- `contracts.json` 是 stage1 的主输出，包含：
  - `structure_contract`
  - `interface_contracts`
  - `timing_contracts`
  - `control_contracts`
  - `datapath_contracts`
  - `planning_facts`
- `planning_facts` 是本周新增的关键层，包含：
  - `registers`
  - `state_names`
  - `submodule_facts`
  - `local_mappings`
- 然后通过确定性脚本重组得到 `modules.json`
  - 每个模块下面聚合自己的 `interface/timing/control/datapath/planning_facts`
  - 同时保留 `parent_modules / child_modules`

### 价值
- 把“全局扁平 contract”转换成“按 module 组织的事实闭包”
- 后续阶段不需要再全局扫描所有 contract
- 为 repo skeleton planning 和模块骨架生成提供直接输入

### 建议讲稿
`contracts.json` 主要解决“把 spec 里的信息结构化抽出来”的问题，而 `modules.json` 解决“怎么让下一阶段更容易消费”的问题。尤其是新增的 `planning_facts`，它把寄存器、状态名、子模块数量和局部映射规则单独落盘，对后面做骨架生成非常关键。

---

## 第4页：Stage2 重构思路

### 标题
Stage2：从 RFU Extraction 改为 Repo Skeleton Planning

### 核心内容
- 旧 `stage2`
  - 输入是 legacy `Stage1FragmentsArtifact`
  - 目标是提取 RFU（repository functional units）
  - 更偏责任划分，不适合当前新链路
- 新 `stage2`
  - 输入是 `modules.json` / `ModuleOrganizationArtifact`
  - 输出是 `repo_skeleton.json` / `repo_skeleton_v1`
  - 目标是 repo-level 骨架规划
- 新 `stage2` 只做仓库级决策，不做模块内部骨架
  - `file_map`
  - `generation_order`
  - `module kind`
  - `instance_hints`
  - `open_issues`

### 新输出结构
- `top_module`
- `module_order`
- `global_invariants`
- `modules`
- `planning_decisions`
- `open_issues`

### 建议讲稿
这周另一个核心工作是把旧的 stage2 彻底换成 repo skeleton planning。原因是我们前面已经把 stage1 改成了 contract-first 和 modules-first，中间层已经足够支持仓库级规划，所以 stage2 没必要再走旧的 RFU 责任抽取路线，而是应该直接产出下一步真正可用的 repo skeleton。

---

## 第5页：当前结果、价值与下一步

### 标题
当前结果与下一步计划

### 当前结果
- 已经打通的链路：
  - `stage1 -> contracts.json -> modules.json -> stage2 -> repo_skeleton.json`
- `PlannerRunner` 已支持：
  - `end_stage="stage1"`
  - `end_stage="stage2"`
- `stage2` 现在支持：
  - 读取 `modules.json`
  - 一次性输出完整 `repo_skeleton.json`
  - `resume` 时复用已有 `repo_skeleton.json`

### 当前价值
- 建立了稳定的多阶段中间表示
- 阶段边界更清晰：
  - `stage1` 负责抽事实
  - `stage2` 负责做 repo-level 规划
- 后续仓库骨架生成已经有明确输入接口

### 当前限制
- 旧 `stage3` 仍然是 legacy RFU refinement，尚未迁移到新链路
- 当前 `repo_skeleton` 仍停留在 repo-level，未进入 module-internal skeleton
- 质量仍然受 prompt 和 schema 边界设计影响

### 下一步
1. 基于 `repo_skeleton.json` 自动生成仓库目录和 RTL 文件壳。
2. 设计新的 `stage3`，从 repo skeleton 进入 module skeleton planning。
3. 增加 deterministic post-check，进一步降低 LLM 输出波动。

### 建议讲稿
当前这条链路已经把原始 spec 稳定转成了 repo-level skeleton，中间表示是可落地、可调试、可继续演进的。下一步重点不是再扩展 stage1，而是利用 `repo_skeleton.json` 去真正驱动仓库骨架生成，并把后面的 stage3 从 legacy 路径迁移过来。

---

## 附：汇报时可引用的关键文件

- Stage1 主逻辑：
  [stage1_agent.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/agents/stage1_agent.py)
- Stage1 schema：
  [contracts.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/schemas/contracts.py)
- `contracts.json -> modules.json` 重组：
  [module_organizer.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/module_organizer.py)
- Stage2 主逻辑：
  [stage2_agent.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/agents/stage2_agent.py)
- Stage2 prompt：
  [stage2_repo_skeleton.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/prompts/stage2_repo_skeleton.py)
- Stage2 schema：
  [repo_skeleton.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/schemas/repo_skeleton.py)
- 运行入口：
  [planner_runner.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/module_planner/planner_runner.py)
