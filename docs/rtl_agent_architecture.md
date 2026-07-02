# ZeroRepo RTL Agent 系统架构文档

> **版本**: v2.0 — 基于 2026-06-20 代码库分析（含 RepoReAct 重构更新）
> **作者**: 系统架构分析
> **范围**: `/zerorepo/rtl_impl/` 完整子系统

---

## 目录

1. [系统概述](#1-系统概述)
2. [顶层架构](#2-顶层架构)
3. [RTL 知识图谱子系统](#3-rtl-知识图谱子系统)
4. [Module Planner 规划管线](#4-module-planner-规划管线)
5. [Debug Agent 调试子系统](#5-debug-agent-调试子系统)
6. [RepoReAct Runner 仓库级自主 ReAct 调试环](#5b-reporeact-runner仓库级自主-react-调试环) (NEW — v2)
7. [Trace Report 追踪报告](#5c-trace-report追踪报告)
8. [KG Agent 知识图谱查询子系统](#6-kg-agent-知识图谱查询子系统)
9. [Retrieval Agent 检索子系统](#7-retrieval-agent-检索子系统)
10. [工具系统设计](#8-工具系统设计)
11. [上下文管理设计](#9-上下文管理设计)
12. [记忆系统设计](#10-记忆系统设计)
13. [模型与格式化层](#11-模型与格式化层)
14. [完整任务协作流程](#12-完整任务协作流程)
15. [持久化与检查点机制](#13-持久化与检查点机制)
16. [错误处理与韧性设计](#14-错误处理与韧性设计)
17. [配置系统](#15-配置系统)
18. [附录：文件索引](#16-附录文件索引)

---

## 1. 系统概述

### 1.1 项目定位

ZeroRepo RTL Agent 是一个 **从自然语言规范到可综合 SystemVerilog RTL 代码的全自动生成与调试系统**。它接收 Markdown 格式的硬件设计规范（可附带框图/流程图/时序图等图片），通过多阶段 LLM 协作管线，最终产出经过 Verilator 仿真验证的可综合 RTL 代码。

### 1.2 核心能力

| 能力 | 描述 |
|------|------|
| **规范理解** | 从 Markdown 规范+图片中提取接口、时序、控制流、数据通路等结构化契约 |
| **架构规划** | 自动将规范分解为模块层级，生成仓库骨架和模块骨架 |
| **代码生成** | 基于规划结果，按子任务逐步生成 SystemVerilog RTL 代码 |
| **仿真验证** | 使用 Verilator 进行语法检查与功能仿真 |
| **自动调试** | 基于 VCD 波形追踪、知识图谱切片、LLM 驱动的迭代修复循环 |
| **知识积累** | 将代码结构、仿真结果持久化到 Neo4j 图数据库，支持跨任务查询 |

### 1.3 技术栈

- **语言**: Python 3.10+
- **LLM 框架**: AgentScope (ReAct Agent)
- **图数据库**: Neo4j (Bolt 协议)
- **RTL 解析**: tree-sitter-verilog
- **仿真引擎**: Verilator
- **波形分析**: vcdvcd (VCD 解析)
- **数据建模**: Pydantic v2

---

## 2. 顶层架构

### 2.1 子系统划分

整个 `rtl_impl` 系统由 **七个核心子系统** 组成，呈层次化协作关系：

```
┌─────────────────────────────────────────────────────────────────┐
│                     RTL Agent 系统架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────┐  ┌──────────────────────┐               │
│  │   Module Planner     │  │    Retrieval Agent    │               │
│  │   (6-stage pipeline) │──│    (context selector) │               │
│  └──────────┬──────────┘  └──────────────────────┘               │
│             │                                                      │
│             │ Stage6: merge + debug                                │
│             ▼                                                      │
│  ┌─────────────────────┐  ┌──────────────────────┐               │
│  │    Debug Agent       │  │     KG Agent          │               │
│  │  (workdir + oracle)  │──│   (query + record)    │               │
│  └──────────┬──────────┘  └──────────┬───────────┘               │
│             │                         │                             │
│             │ mismatch detected       │ cypher queries              │
│             ▼                         ▼                             │
│  ┌─────────────────────────────────────────────────┐              │
│  │           RepoReAct Runner (NEW)                 │              │
│  │   repository-level autonomous ReAct debug loop   │              │
│  │   11 tools: read/search/KG/VCD/check/patch/      │              │
│  │   correct + evidence gate + rollback              │              │
│  └──────────────────────┬──────────────────────────┘              │
│                         │                                          │
│                         │ verilator sim + trace                     │
│                         ▼                                          │
│  ┌─────────────────────────────────────────────────┐              │
│  │              RTL Knowledge Graph                 │              │
│  │    (Neo4j: code structure + sim results)         │              │
│  └─────────────────────────────────────────────────┘              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 子系统职责矩阵

| 子系统 | 核心职责 | 关键文件 |
|--------|---------|---------|
| **RTL Knowledge Graph** | RTL 代码解析、图数据库构建与查询 | `rtl_kg/`, `rtl_kg_service.py` |
| **Module Planner** | 6 阶段规范→代码规划管线 | `module_planner/` |
| **Debug Agent** | 工作目录准备、oracle TB 拷贝、语法修复、初始仿真 | `debug_agent/` |
| **RepoReAct Runner** (NEW) | 仓库级自主 ReAct 调试环：观察→诊断→patch→验证→回滚 | `repo_react/` |
| **KG Agent** | 知识图谱模板化查询与结果写入 | `kg_agent/` |
| **Retrieval Agent** | 为代码生成/合并阶段检索相关规范片段 | `retrieval_agent/` |

### 2.3 数据流向图

```
Spec (.md + images)
    │
    ▼
[Stage 1: Ingest & Extract] ─── contracts.json, modules.json
    │
    ▼
[Stage 2: Repo Skeleton] ─── repo_skeleton.json
    │
    ▼
[Stage 3: Module Skeletons] ─── module_skeletons.json + .md skeleton docs
    │
    ▼
[Stage 4: Spec Blocks + Module Plans] ─── spec_blocks.json, module_plans.json
    │                                        │
    │                          ┌─────────────┘
    │                          ▼
    │               [Retrieval Agent] ─── block_spec_retrieval_json/
    │
    ▼
[Stage 5: Codegen] ─── stage5_codegen.json (per-module fragments)
    │
    ▼
[Stage 6: Merge] ─── merged .sv files
    │
    ▼
[ModuleDebugRunner] ─── 准备 debug workdir, oracle TB, support.sv
    │
    ├── pre-debug syntax/interface repair (LLM 驱动, 最多 5 次)
    ├── 初始 SimReviewer.review()
    │   ├── PASS → 结束, 记录结果到 KG
    │   └── FAIL (has mismatches) → 进入 RepoReActRunner
    │
    ▼
[RepoReActRunner] ─── 仓库级自主 ReAct 调试环 (v2)
    │
    ├── 工具集: read_context, search_context, query_rtl_kg,
    │   read_spec, retrieve_spec_block, list_vcd_signals, probe_vcd,
    │   run_check, route_debug_context, read_long_term_memory,
    │   apply_patch, replace_block, record_correction
    │
    ├── 子代理: DebugInvestigator (独立上下文, 只读调查员)
    │   └── 主代理通过 route_debug_context 启动, 返回 <3000字符分析报告
    │
    ├── Evidence gate: patch 前必须满足六道关卡
    ├── apply_patch: 自动 snapshot → lint → sim → trace → 回滚判断
    ├── record_correction: 写 planning_corrections/ overlay, 不改原文件
    ├── Observation budget: 最多 16 次只读调用后强制行动
    ├── Three-tier compaction: Light(刷新) → Checkpoint(清空+快照) → Deep(削减)
    │
    ├── PASS → 复制 rtl.sv 到 merged_file, 记录 SIMULATION PASS 到 KG
    └── max_steps_exceeded/give_up/error → 记录失败原因到 KG
    │
    ▼
[KG Agent] ─── SimulationResult 节点 + HAS_SIM_RESULT 边写入 Neo4j
    │
    ▼
Final verified RTL (.sv files) + KG state
```

---

## 3. RTL 知识图谱子系统

### 3.1 设计目标

RTL 知识图谱是整个系统的 **结构化记忆核心**。它将 RTL 代码仓库转化为可查询的图结构，为 Agent 提供对代码库的精确、结构化的理解能力。

### 3.2 图谱本体 (Ontology)

#### 节点类型 (12 种)

| 节点类型 | Neo4j Label | 含义 | 示例 |
|---------|------------|------|------|
| `RepoNode` | `Repo` | 仓库根节点 | `name: "my_cpu"` |
| `FileNode` | `File` | 文件/目录节点 | `path: "rtl/alu.sv"` |
| `ModuleNode` | `Module` | Verilog 模块定义 | `name: "alu", sl: 10, el: 85` |
| `PackageNode` | `Package` | SystemVerilog package 定义 | `name: "my_pkg"` |
| `InstanceNode` | `Instance` | 模块实例化点 | `name: "u_adder"` |
| `PortNode` | `Port` | 模块端口 | `name: "clk", dir: "input"` |
| `SignalNode` | `Signal` | 内部信号 | `name: "counter", decl_kind: "reg"` |
| `ParamNode` | `Param` | 参数/局部参数 | `name: "WIDTH", pkind: "parameter"` |
| `AlwaysBlockNode` | `AlwaysBlock` | always 过程块 | `bkind: "ff"` |
| `AssignNode` | `Assign` | 连续赋值语句 | `lhs_short: "result"` |
| `GenerateNode` | `Generate` | generate 块骨架 | `gkind: "for"` |
| `FuncNode` | `Func` | 模块内函数声明 | `name: "clog2"` |

#### 关系类型 (10 种)

| 关系类型 | 方向 | 含义 |
|---------|------|------|
| `CONTAINS` | Repo→File, File(dir)→File | 文件系统包含关系 |
| `DEFINES` | File→Module/Package | 文件定义模块/包 |
| `HAS` | Module→Port/Signal/Param/Always/Assign/Generate/Func | 模块拥有子元素 |
| `INSTANTIATES` | Module→Instance | 模块包含实例化 |
| `OF_MODULE` | Instance→Module | 实例化指向被实例化的模块 |
| `CONNECTS` | Instance→Signal/Port/Expr | 实例端口连接 |
| `DRIVES` | Always/Assign→Signal/Port | 驱动关系 (仅 LHS) |
| `INCLUDES` | File→File | ``` `include ``` 引用 |
| `IMPORTS` | Module/File→Package | SystemVerilog import |
| `CALLS` | Always/Assign→Func | 函数调用关系 |

### 3.3 图谱构建流程

```
KnowledgeGraphRTL.build(repo_root)
│
├── 1. 创建 Repo 节点 (uid = repo_name@commit_sha)
├── 2. DFS 遍历目录树
│   ├── 为每个目录/文件创建 File 节点
│   └── 创建 CONTAINS 边 (带 order 属性)
├── 3. 对每个 RTL 文件, 调用 RTLFileGraphBuilder.build_file_graph()
│   ├── tree-sitter-verilog 解析 AST
│   ├── 提取模块声明 → Module 节点 + DEFINES 边
│   ├── 提取端口列表 → Port 节点 + HAS 边
│   ├── 提取参数声明 → Param 节点 + HAS 边
│   ├── 提取内部信号 → Signal 节点 + HAS 边
│   ├── 提取 always 块 → AlwaysBlock 节点 + HAS 边 + DRIVES 边
│   ├── 提取 assign 语句 → Assign 节点 + HAS 边 + DRIVES 边
│   ├── 提取模块实例化 → Instance 节点 + INSTANTIATES 边 + CONNECTS 边
│   ├── 提取函数声明 → Func 节点 + HAS 边
│   ├── 提取函数调用 → CALLS 边
│   ├── 提取 generate 块 → Generate 节点 + HAS 边
│   ├── 提取 package 声明 → Package 节点 + IMPORTS 边
│   └── 提取 import 语句 → IMPORTS 边
├── 4. 后处理 (Post-pass resolution)
│   ├── _resolve_of_module(): Instance → Module (按 module_ref 匹配)
│   ├── _resolve_imports(): 将占位 Package 节点替换为实际 Package 节点
│   └── _resolve_includes(): 解析 `include 创建 INCLUDES 边
└── 5. 文本回退 (text fallback)
    └── 对 tree-sitter 无法解析的模块, 用正则表达式提取并补充节点
```

### 3.4 核心设计决策

#### 3.4.1 精简的 DRIVES 关系 (LHS-only)

系统只记录 **左值 (LHS) 驱动关系**，不展开完整的表达式 AST。这样做的原因：
- **避免图爆炸**: 完整 AST 会导致节点数指数增长
- **保留可追溯性**: LHS 信息足够支持 COI (Cone of Influence) 反向追踪
- **与调试流程对齐**: 调试时主要关心"谁驱动了这个信号"

#### 3.4.2 双解析器策略

```
优先级 1: tree-sitter-verilog (AST-based)
    ↓ 失败时
优先级 2: 正则表达式文本回退 (text-based fallback)
```

文本回退解析器 (`_fallback_*` 方法族) 能处理 tree-sitter 不兼容但 Verilator 合法的 RTL 代码，确保系统韧性。

#### 3.4.3 稳定唯一标识符 (UID)

每个节点/边都有稳定的 UID，格式为 `repo_uid:kind:name:path[:sl:el]`，支持：
- Neo4j MERGE 去重
- 跨管道阶段引用
- 增量更新

### 3.5 RTL KG Service (服务封装层)

`RTLKgService` 是对底层 KG 的服务化封装：

```
RTLKgService
├── 连接管理: Neo4jConnection (Bolt)
├── 初始化: initialize() → 验证连接, 创建模式约束
├── 快照同步: sync_plan_snapshot() / refresh_repo_files()
│   ├── 构建增强快照 (_build_augmented_snapshot)
│   ├── 文本回退补充 (_augment_snapshot_with_text_fallback)
│   ├── 按规划骨架过滤 (_filter_snapshot_to_planned_skeleton)
│   └── 注入规划元数据 (file_kind, implementation_status 等)
├── 查询接口: query(cypher, params, limit)
│   ├── 只读强制 (禁止 CREATE/MERGE/SET/DELETE/CALL db.*)
│   ├── 自动 repo_uid 注入
│   └── 自动 LIMIT 追加
├── 批量上下文: build_batch_context(batch)
│   ├── 文件元数据查询
│   ├── 模块信息查询
│   └── 实例关系查询
└── 查询工具: QueryRtlKgTool (Agent 可调用的工具封装)
```

### 3.6 Neo4j 摄入器

`RTLNeo4jIngestor` 负责将内存中的图数据批量写入 Neo4j：

- **批量 UNWIND**: 按标签/关系类型分组，使用 `UNWIND $rows AS row MERGE` 模式
- **模式管理**: `ensure_schema()` 自动创建唯一性约束和常用索引
- **两种模式**:
  - `full`: 先按 `repo_uid` 分区删除，再全量摄入
  - `delta`: MERGE 增量更新
- **值规范化**: 自动将 dict/list 转为 JSON 字符串，截断超长文本，处理 Path 等非基本类型

---

## 4. Module Planner 规划管线

### 4.1 总体设计

Module Planner 是系统的 **中央规划引擎**，采用 **6 阶段流水线** 架构，将自然语言规范逐步转化为可综合的 RTL 代码。每个阶段产出结构化 JSON 产物，下游阶段消费上游产物。

### 4.2 阶段详解

#### Stage 1: 规范摄取与契约提取 (Ingest & Extract)

**Agent**: `Stage1Agent`
**输入**: Markdown 规范文件 + 图片
**输出**: `Stage1ContractsArtifact` (contracts.json + modules.json)

```
任务:
├── 解析 Markdown 规范文本 → SpecFragment 列表
├── 预扫描图片 → ImagePrescan + ImageCard
├── 提取实体别名 → EntityAliasGroup
├── 构建文档组织画像 → DocumentOrganizationProfile
├── 提取接口契约 → InterfaceContract (ports, directions, widths)
├── 提取时序契约 → TimingContract (clock, reset, latency)
├── 提取控制契约 → ControlContract (FSM states, transitions)
├── 提取数据通路契约 → DatapathContract
├── 提取结构契约 → StructureContract (submodule hints)
├── 提取规划事实 → PlanningFactsContract
└── 构建项目记忆卡 → ProjectMemoryCard
```

**核心 Schema**:
- `InterfaceContract`: 端口名称、方向、位宽、角色、含义
- `TimingContract`: 时钟名、边沿、复位行为、各输出延迟周期数
- `ControlContract`: 控制条件、状态转换、计数器规则
- `DatapathContract`: 中间对象、路径注解

#### Stage 2: 仓库骨架规划 (Repo Skeleton)

**Agent**: `Stage2Agent`
**输入**: Stage1 contracts + modules
**输出**: `Stage2RepoSkeletonArtifact` (repo_skeleton.json)

```
任务:
├── 确定模块实例化层次结构
├── 为每个模块分配 File 文件
├── 建立模块间依赖关系
└── 生成全局不变量 (GlobalInvariants)
```

**核心 Schema**:
- `RepoModuleSkeleton`: 模块名、负责文件、子实例列表、端口列表
- `SkeletonHierarchyEdge`: 父子模块关系

#### Stage 3: 模块骨架生成 (Module Skeleton)

**Agent**: `Stage3Agent`
**输入**: Stage2 repo skeleton + modules
**输出**: `Stage3ModuleSkeletonArtifact` (module_skeletons.json + .md docs)

```
任务 (每个模块):
├── 生成模块接口声明 (端口、参数)
├── 生成内部信号声明
├── 生成 always_ff / always_comb / assign 块骨架
├── 为每个块标注目标功能 (block_label, block_kind)
├── 生成子模块实例化骨架
├── 输出 Markdown 文档 (module_skeleton_docs/)
└── 输出结构化 JSON (module_skeleton_json/)
```

**核心 Schema**:
- `ModuleSkeletonExport`: 完整的 SystemVerilog 骨架文本 + 结构化块列表
- `StructuralBlock`: block_id, block_kind (decl/ff/comb/assign/inst), raw_text
- `BlockBehaviorOverlay`: purpose, code_shape, retrieval_focus

#### Stage 4: 规范块分配与模块计划 (Spec Blocks + Module Plans)

**Stage 4 分为两个子阶段:**

##### 4a. Spec Blocks (规范块切分)

**Agent**: `Stage4SpecBlocksAgent`
**输入**: Stage3 skeletons + 原始规范
**输出**: `Stage4SpecBlocksArtifact` (spec_blocks.json)

```
任务:
├── 将原始规范文本切分为独立的 SpecBlock
├── 每个 SpecBlock 包含 block_id, text, 相关端口/参数
├── 标注 interface_block 和 implementation_block
└── 建立 SpecBlock → Module 的映射
```

##### 4b. Module Plans (模块实现计划)

**Agent**: `Stage4ModulePlanAgent`
**输入**: Stage3 skeletons + SpecBlocks
**输出**: `Stage4ModulePlansArtifact` (module_plans.json + 每个模块的计划 JSON)

```
任务 (每个模块):
├── 为每个骨架块匹配相关 SpecBlock (通过 Retrieval Agent)
├── 生成候选实现方案 (ModuleCandidate × N)
├── 多维度评估 (checklist scoring):
│   ├── 接口兼容性
│   ├── 时序正确性
│   ├── 控制逻辑完整性
│   ├── 数据通路正确性
│   └── 代码可实现性
├── 两两对比 (PairwiseTieBreak)
├── 选择最优方案 → FinalModulePlan
└── 将计划分解为子任务 (ModulePlanSubtask)
```

**评估体系**:
- `CHECKLIST_DIMENSIONS`: 5 个评估维度
- `CHECKLIST_RUBRIC`: 每个维度的评分标准
- `CHECKLIST_ANSWER_SCORES`: "yes"/"partial"/"no"/"unknown" → 数值分数
- `compute_dimension_scores()`: 维度得分计算
- `compute_macro_score()`: 综合评分

#### Stage 5: 逐子任务代码生成 (Codegen)

**Agent**: `Stage5Agent`
**输入**: Stage4 module plans + spec_blocks + stage3 skeletons
**输出**: `Stage5CodegenArtifact` (stage5_codegen.json + per-module fragment .sv + fragment contracts)

```
任务 (每个模块):
├── 检查是否为 define-only 模块 (sd_defines 等)
│   ├── is_define_only_module() 检测
│   └── 如果是 → copy_official_define_file() 从 RealBench 直接复制
│        └── 写入 global_defines_manifest.json
│
├── 对每个子任务 (ModulePlanSubtask):
│   ├── 选择相关规范块 (_select_spec_blocks)
│   ├── 选择模块接口规范块 (_select_interface_spec_blocks)
│   ├── 读取 Module Skeleton "Module Frame" 段
│   ├── 构建 prompt (CURRENT_SUBTASK + SELECTED_SPEC_BLOCKS +
│   │   MODULE_INTERFACE_SPEC_BLOCKS + PREVIOUS_MODULE_SNIPPETS)
│   ├── LLM 生成 SubtaskCodeArtifact
│   │   └── 包含 code + FragmentContract (writes/reads/clocking/reset/latency/assumptions)
│   ├── 自动提取 Fragment Contract (_extract_fragment_contract)
│   │   └── 从代码中自动提取 writes/reads/clocking 作为 fallback
│   ├── upsert 子任务代码到 fragment 文件 (STAGE5_SUBTASK_BEGIN/END 标记)
│   └── 写入 fragment contracts (workspace/fragments/{module}_contracts.json)
│
├── 质量验证:
│   ├── 禁止 unpacked array 声明
│   ├── 禁止多维信号引用
│   ├── 禁止 generate/genvar
│   └── 代码不能包含 Markdown fences 或 stage5 标记注释
└── 输出: workspace/fragments/{module}_fragments.v + {module}_contracts.json
```

**新增功能: Fragment Contract**

每个子任务生成时自动附带结构化契约:

```json
{
  "subtask_id": "...",
  "target": "...",
  "spec_refs": ["..."],
  "contract": {
    "writes": ["sig_a", "sig_b"],
    "reads": ["sig_c"],
    "clocking": "posedge clk",
    "reset_behavior": "synchronous reset to 0",
    "hold_behavior": "holds previous value when !en",
    "latency": "one-cycle",
    "assumptions": ["dependent on upstream valid signal"]
  }
}
```

契约数据被 Stage6 Semantic Merge 用于静态检查（多 writer 冲突检测等）。

**新增功能: Define-Only 模块处理**

`global_defines.py` 模块自动识别并处理纯宏定义模块:
- 通过模块名后缀 (`_defines`) 或 `repo_notes` 中的标记词检测
- 从 RealBench 官方源直接复制，不经过 LLM 生成
- 写入 `workspace/global_defines_manifest.json` 供 Stage6 使用

#### Stage 6: 语义合并 (Semantic Merge + Raw Fallback)

**Agent**: `Stage6MergeAgent`
**输入**: Stage5 fragments + fragment contracts + stage3 skeletons + spec + KG
**输出**: `Stage6MergeArtifact` (merged .sv files in workspace/merged/)

```
任务 (每个模块):
├── 检查是否为 define-only 模块
│   └── 如果是 → copy_official_define_file() 直接复制, 跳过合并
│
├── 准备上下文:
│   ├── MergeContextRetriever: 选择合并所需规范块
│   │   └── 缓存到 merge_retrieval_json/{module}.json (支持 resume)
│   ├── 可选 KG 子模块上下文:
│   │   ├── 若 retrieval 请求 KG → 查询子模块接口 + 参数 + 仿真状态
│   │   ├── 附加子模块完整代码 (verified + small enough 时)
│   │   └── 缓存到 merge_child_context_json/{module}.json
│   ├── Global Defines 上下文:
│   │   ├── 检测 global defines 模块
│   │   ├── 读取已生成的 defines 文件
│   │   └── 提取活跃 `define 值作为权威数据注入 prompt
│   └── 读取 module_skeleton "Module Frame" 段
│
├── 语义合并 (Stage6MergeRunner — SafeReActAgent + 6 个工具) [优先路径]:
│   ├── 渐进式初始 prompt (仅索引, 不含完整 spec/fragments)
│   ├── Agent 按 workflow 使用工具:
│   │   ├── read_merge_context(kind) × 8:
│   │   │   fragments, fragment_contracts, module_plan, module_skeleton,
│   │   │   spec, kg_child_context, global_defines, learned_merge_rules
│   │   ├── inspect_rtl_structure(target="draft")
│   │   │   └── 解析: includes, module_count, outputs, blocks, driver_map,
│   │   │       output_drivers, forbidden_wildcard_always, assignment convention
│   │   ├── run_static_rtl_check(target="draft")
│   │   │   └── 验证: 单 module, required includes, 无通配符 always,
│   │   │       输出驱动检查, Stage5 多 writer 冲突, 赋值惯例
│   │   ├── run_lint(target="draft") → Verilator lint
│   │   ├── generate_merge_draft(code, reason, expected_effect)
│   │   │   ├── Evidence gate: must have read fragments + spec + global_defines
│   │   │   ├── 自动注入 required includes
│   │   │   ├── Pre-check lint (Verilator fatal error → reject)
│   │   │   └── 写入 workspace/merge_drafts/{module}_draft.v
│   │   └── commit_merge_draft(reason)
│   │       ├── Evidence gate: must have draft + inspected structure
│   │       ├── Final check: static_rtl_check + lint
│   │       └── 复制 draft → workspace/merged/{module}.v
│   ├── 跨模块学习: read_merge_context(kind="learned_merge_rules")
│   │   └── 加载前序模块的 merge report (已合并模块的经验)
│   ├── Observation budget: 最多 16 次只读调用后强制行动
│   └── Journal: workspace/merge_journal/{module}/
│       ├── merge_trace.jsonl (完整 ReAct 对话追踪)
│       ├── draft_journal.jsonl (draft 生成/提交记录)
│       └── snapshots/ (draft 前后快照)
│
├── Raw Merge Fallback [降级路径]:
│   ├── 当 ReAct agent 初始化失败/循环异常时触发
│   ├── 一次性 LLM 调用 + Verilator lint 检查
│   ├── 语法错误 → 写入 stage6_syntax_repair/{module}.json 诊断
│   │   └── 标记 delegated_to: "ModuleDebugRunner.repo_react_syntax"
│   └── 语法修复责任移交给 RepoReActRunner
│
├── Merge Report: workspace/merge_reports/{module}_merge_report.json
│   ├── signal_ownership, always_block_responsibility
│   ├── static_check_summary, lint_summary
│   └── draft_committed, total_action_calls
└── 输出: workspace/merged/{module}.v
```

**Semantic Merge 工具集:**

| 工具 | 类型 | 功能 | 证据门槛 |
|------|------|------|---------|
| `read_merge_context` | Readonly | 读取 8 种合并上下文 | - |
| `inspect_rtl_structure` | Readonly | 解析 RTL 结构 (includes/block/driver_map/赋值风格) | - |
| `run_static_rtl_check` | Readonly | 静态结构验证 (module 数量/multi-driver/通配符 always/多 writer) | - |
| `run_lint` | Readonly | Verilator lint 检查 | - |
| `generate_merge_draft` | Action | 生成合并草稿 → draft 文件 | 必须已读 fragments + spec + global_defines |
| `commit_merge_draft` | Action | 提交草稿 → merged 文件 | 必须已生成 draft + inspected structure + static_check pass + lint pass |

**Semantic Merge vs Raw Merge 对比:**

| 维度 | Semantic Merge (优先) | Raw Merge (降级) |
|------|----------------------|-----------------|
| 决策模型 | SafeReActAgent + 6 工具渐进式 | 一次性 LLM 调用 |
| 验证方式 | read → draft → inspect → check → lint → commit | 生成后 lint, 失败则委派 |
| 错误处理 | Agent 自行分析失败原因并修改 draft | 委派给 RepoReActRunner syntax repair |
| 跨模块学习 | learned_merge_rules | 不支持 |
| 草稿管理 | draft_journal.jsonl + snapshots | 直接写入 merged |
| 回滚 | draft 被 reject 后可重新生成 | N/A |

### 4.3 PlannerRunner 执行引擎

`PlannerRunner` 是整个管线的 **编排器 (Orchestrator)**：

```
PlannerRunner.run(task_input, resume, end_stage)
│
├── 阶段调度: stage1 → stage2 → stage3 → stage4 → stage5 → stage6
├── 断点续传: 每个阶段支持 resume (检查已有产物有效性)
├── 增量运行: stage3/stage4 支持 run_incremental (逐模块推进)
├── 质量门控: 每个阶段输出经过 validate_quality()
├── KG 同步: stage1 后 sync_plan_snapshot(), stage6 后记录仿真结果
└── 产物持久化: 所有中间产物写入 output_root/
```

**产物目录结构**:
```
outputs/
├── contracts.json
├── modules.json
├── repo_skeleton.json
├── module_skeletons.json
├── spec_blocks.json
├── module_plans.json
├── module_skeleton_docs/          # Markdown 骨架文档
├── module_skeleton_json/          # 结构化骨架 JSON
├── module_plan_json/              # 每个模块的实现计划
├── block_spec_retrieval_json/     # 规范块检索结果
├── merge_retrieval_json/          # Stage6 合并规范检索结果 (NEW)
├── merge_child_context_json/      # Stage6 KG 子模块上下文 (NEW)
├── stage5_codegen.json
├── stage6_merge.json
├── stage6_syntax_repair/          # Stage6 语法诊断 (委派给 RepoReAct)
├── merge_reports/                 # Stage6 语义合并报告 (NEW)
├── planning_corrections/          # RepoReAct 规划修正 overlays
├── global_defines_manifest.json   # 全局宏定义清单 (NEW)
│
workspace/
├── fragments/                     # Stage5 per-module fragment .v + contracts
│   ├── {module}_fragments.v
│   └── {module}_contracts.json    # Fragment contracts (NEW)
├── merged/                        # Stage6 最终合并 .sv 文件
│   └── {module}.v
├── merge_drafts/                  # Stage6 语义合并草稿 (NEW)
│   └── {module}_draft.v
├── merge_journal/                 # Stage6 语义合并日志 (NEW)
│   └── {module}/
│       ├── merge_trace.jsonl
│       ├── draft_journal.jsonl
│       └── snapshots/
├── merge_reports/                 # Stage6 合并报告 (NEW)
│   └── {module}_merge_report.json
├── global_defines_manifest.json   # 全局宏定义清单 (NEW)
├── repo_react/                    # RepoReAct 调试日志
│   └── {module}/
│       ├── react_trace.jsonl
│       ├── patch_journal.jsonl
│       ├── correction_journal.jsonl
│       └── snapshots/
└── debug/                         # ModuleDebugRunner 调试工作目录
    └── {module}/
        ├── rtl.sv, tb.sv, support.sv
        ├── contract.json
        ├── trace_report.json
        └── repo_react_memory_snapshot.json
```

---

## 5. Debug Agent 调试子系统

### 5.1 总体设计

Debug Agent 在 v2 架构中的角色已重新定义。它**不再包含功能修复逻辑**，而是负责 **调试环境的准备和前处理**：

- 查找 oracle verification 目录（黄金测试平台来源）
- 准备 `debug/<module>/` 工作目录（复制 rtl.sv, tb.sv, support.sv）
- Pre-debug 语法/接口修复（LLM 驱动，最多 5 次尝试）
- 初始仿真（SimReviewer）
- 若初始仿真通过 → 直接结束
- 若初始仿真有 mismatch → **委托给 RepoReActRunner** 进行功能修复

功能修复（原 RTLEditor debug loop）已被 **RepoReActRunner** 完全替代。

### 5.2 ModuleDebugRunner

`ModuleDebugRunner` 是 Planner 管线中调用调试的 **标准入口**，负责环境准备和流程编排：

```
run_module(module_name, merged_file, task, spec_text, contract_json)
│
├── 1. 解析 oracle 目录
│   ├── 直接查找: oracle_root/<module_name>/verification/
│   └── 动态查找: oracle_root/<subdir>/<module_name>/verification/
├── 2. 准备调试工作目录 (_prepare_workdir)
│   ├── 复制 merged RTL → rtl.sv
│   ├── 查找并复制黄金 testbench → tb.sv
│   ├── 收集子模块文件 → support.sv
│   ├── 复制 `include 引用的文件
│   ├── 写入 contract.json 和 stage1_contract.json
│   └── 写入 debug_input_manifest.json
├── 3. 语法修复 (_repair_debug_workspace_syntax)
│   ├── 构建 support_interface_index (子模块接口索引)
│   ├── 构建 macro_table (宏定义表)
│   ├── 最多 5 次 LLM 驱动的语法修复尝试
│   │   ├── 每次: Verilator lint → 提取错误 → LLM 修复 → 重新 lint
│   │   └── 日志记录每次尝试 (pre_debug_syntax_repair.json)
│   └── 修复原则: support.sv 是权威子模块接口来源，只修改 rtl.sv
├── 4. 初始仿真 (SimReviewer)
│   ├── PASS → 返回 ModuleDebugResult(status="pass")
│   ├── FAIL (mismatch_count > 0) → 调用 _run_repo_react()
│   └── FAIL (mismatch_count <= 0) → 返回 ModuleDebugResult(status="fail")
└── 5. 结果处理
    ├── pass → 复制 rtl.sv 回 merged_file
    └── 记录结果到 KG (通过 initial_result_recorder 和 kg_result_writer)
```

### 5.3 Support Interface Index（子模块接口索引）

`_build_support_interface_index()` 是语法修复的关键辅助数据。它解析 `support.sv` 中所有子模块的接口声明：

```json
{
  "source": "debug/<module>/support.sv",
  "modules": {
    "sub_fifo": {
      "name": "sub_fifo",
      "parameters": [{"name": "WIDTH", "default": "8"}],
      "ports": [
        {"name": "clk", "direction": "input", "width": ""},
        {"name": "wr_en", "direction": "input", "width": ""}
      ],
      "declaration": "module sub_fifo #(parameter WIDTH=8) (input clk, input wr_en, ...);"
    }
  }
}
```

此索引被注入到 pre-debug 语法修复 prompt 中，确保 LLM 不会：
- 连接不存在的端口
- 传递不存在的参数
- 对子模块实例化使用错误的参数覆盖

### 5.4 状态保持

`ModuleDebugRunner` 仍然产出 `ModuleDebugResult`（状态协议不变）：

| 状态 | 含义 |
|------|------|
| `disabled` | RTL 调试被配置禁用 |
| `skipped` | Oracle 目录未找到 |
| `pass` | 初始仿真直接通过（无需调试） |
| `fixed` | RepoReActRunner 成功修复（原 RTLEditor 逻辑） |
| `fail` | 调试尝试后仍失败 |
| `error` | 调试过程中发生异常 |

### 5.5 TopAgent（旧独立入口，保留不动）

`TopAgent` 是 Debug Agent 的旧独立入口，采用多 Agent 协作模式（Architect → Verifier → Coder → Debugger）。在 v2 架构中：
- **planner 主路径不再使用** TopAgent
- TopAgent 对 RTLEditor 的引用保留不动（避免扩大影响面）
- 作为独立 RTL 生成实验的参考入口保留

### 5.6 RTLEditor（旧实现，保留为参考）

`RTLEditor` 及其 `_EditSession` 是 v1 的固定 block-edit 调试器实现。在 v2 架构中：
- **planner 主路径不再调用** RTLEditor
- 文件保留不删除，作为旧路径/参考实现
- 所有新调试流量走 RepoReActRunner

---

## 5b. RepoReAct Runner（仓库级自主 ReAct 调试环）

> **这是 v2 架构的核心新增子系统**，完整替代了 v1 中 RTLEditor 的固定 block-edit 调试循环。

### 5b.1 设计哲学

RepoReAct Runner 将调试模型从 **"固定流水线步骤"** 转变为 **"自主仓库观察与证据驱动修复"**：

| 维度 | v1 RTLEditor | v2 RepoReActRunner |
|------|-------------|-------------------|
| **编辑模型** | 固定 block-edit（替换预解析的 always/assign 块） | 自由行范围 patch（可改任意 RTL 行） |
| **观察范围** | 仅当前模块的 trace_report + suspect blocks | 全仓库（RTL、TB、spec、stage artifacts、KG、VCD） |
| **行动决策** | 硬编码流水线步骤（读 block → 改 block → 仿真） | LLM 自主决策（观察 → 诊断 → patch/correction/stop） |
| **证据门槛** | 无强制要求 | 三要素 gate：必须已读 RTL + trace/sim + TB/spec/KG |
| **回滚策略** | mismatch 显著增加时回滚 | lint fail / mismatch 增加 / fail_time 提前 / 过多 neutral 均回滚 |
| **规划修正** | 不支持 | `record_correction` 写 overlay，不修改原始文件 |

### 5b.2 核心组件

```
repo_react/
├── __init__.py          # 导出 RepoReActRunner, RepoReActInput, RepoReActResult
├── runner.py            # RepoReActRunner: SafeReActAgent + 11 个注册工具
├── tools.py             # RepoReActTools: 所有工具的实现逻辑 + RepoReActToolState
├── schemas.py           # Pydantic 模型: Diagnosis, Patch, Correction, StepRecord, SimSnapshot
├── prompt.py            # SYSTEM_PROMPT + build_initial_prompt + build_continue_prompt + build_compact_prompt
└── journal.py           # RepoReActJournal: JSONL 日志 + 文件快照
```

### 5b.3 工具集（11 个工具）

#### 观察工具（Readonly Tools）

| 工具 | 功能 | 关键约束 |
|------|------|---------|
| `read_context` | 统一读仓库树、文件、行范围、spec、TB、stage artifact、trace_report、repair_journal | 8 种 kind，路径必须在 allowed roots 内 |
| `search_context` | 正则搜索 RTL/TB/spec/all | scope 过滤，最多 50 结果 |
| `query_rtl_kg` | 固定模板 KG 查询（4 种类型） | 仅允许 `module_interface`/`module_instances`/`instance_connections`/`signal_drivers` |
| `read_spec` | 读取原始规范文档 | 支持 path 或 spec_paths |
| `retrieve_spec_block` | 从 spec_blocks.json 按 block_id 或 query 检索 | 仅当前模块 |
| `list_vcd_signals` | 列出 VCD 信号名（支持 pattern/scope 过滤） | 需要 wave.vcd |
| `probe_vcd` | 采样 VCD 信号值（单时间点或时间窗口） | 最多 16 个信号，支持 edge 过滤 |
| `run_check` | 运行 lint / module_sim / trace_summary | top_sim 和 wave_window 标记为 unsupported_in_v1 |
| `read_memory` | 读修复记忆（snapshot / repair_journal / failed_directions / promising_directions） | 不消耗 observation budget |

#### 行动工具（Action Tools）

| 工具 | 功能 | 关键约束 |
|------|------|---------|
| `apply_patch` | 唯一 RTL 修改入口 | 自动 snapshot → lint → sim → trace → 回滚判断；默认仅修改当前 debug RTL |
| `record_correction` | 写 planning_corrections/ overlay | 不修改原始 stage artifact；必须先读过 stage_artifact |

### 5b.4 Evidence Gate（证据门槛）

`apply_patch` 执行前强制通过三要素证据检查：

```
apply_patch 前置条件:
├── observed_rtl = True          (必须已读取当前 RTL 文件)
├── observed_trace_or_sim = True (必须已读取 trace_report 或仿真结果)
└── observed_tb_or_spec_or_kg = True (必须已读取 TB / spec / KG 之一)
```

不满足任一条件 → `apply_patch` 返回 `status="rejected"`，reason 说明缺失哪类证据。

### 5b.5 Observation Budget（观察预算）

防止 Agent 陷入无限观察循环：

- **预算**: 最多 16 次连续只读工具调用（可通过 `ZEROREPO_REACT_READONLY_BUDGET` 环境变量配置）
- **重置**: 每次 `apply_patch`、`replace_block` 或 `record_correction` 后重置为 0；Checkpoint Compact 和 Deep Compact 也重置
- **超限行为**: 返回 `observation_budget_exhausted` 错误，附带当前记忆摘要，强制 agent 立即行动或 `generate_response`
- **渐进施压**: `build_continue_prompt` 在预算接近上限时注入 `ACTION PRESSURE` 提示

### 5b.6 回滚规则

| 条件 | 行为 |
|------|------|
| Lint 失败 | 必回滚 |
| mismatch_count 增加 | 必回滚 |
| first_fail_time 提前 | 必回滚 |
| mismatch=0 但 sim 仍 fail | 必回滚（module_sim_failed_without_mismatch_count） |
| 连续 2 次 neutral patch | 回滚（too_many_neutral_patches） |
| Pass 且 mismatch=0 | 保留，结束调试 |
| mismatch 降低 / fail_time 后移 | 保留（improved），继续 ReAct |

### 5b.7 上下文包与记忆系统

RepoReAct 使用 **上下文包（Context Pack）** 作为 Agent 状态的核心载体：

```json
{
  "task_frame": { "current_target", "top_diagnosis", "protected_invariants", "unsafe_directions", "next_action_hint" },
  "timing_evidence": { "signal", "time", "edge", "ref", "dut", "sampling_mode", "driver_assignment_kind", "block_id", "line_range" },
  "evidence_pack": [ up to 5 EvidenceItems with short summaries ],
  "causal_memory": { "repair_ledger_summary", "promising_directions", "protected_invariants", "unsafe_directions", "selected_long_term_memories", "negative_patterns" },
  "active_working_set": { "active_hypotheses", "pinned_evidence", "pinned_code_slices", "waveform_facts", "rejected_hypotheses", "next_edit_candidates", "missing_evidence" },
  "raw_artifacts": { file path references }
}
```

上下文包在每次 Light/Checkpoint/Deep 压缩时自动更新，并在每步 continue prompt 中注入。Agent 可在诊断 JSON 中显式声明工作集内容（假设、证据、候选编辑），系统自动累积到 active_working_set 中。

持久化日志：
```
workspace/repo_react/<module>/
├── react_trace.jsonl            # 完整 ReAct 对话追踪
├── patch_journal.jsonl          # 每次 patch 的结构化记录（含 per-signal metric delta）
├── correction_journal.jsonl     # 每次 record_correction 记录
├── debug_context_pack.json      # 当前上下文包快照
├── context_packs/pack_NNN.json  # 每轮生成的上下文包归档
├── evidence/                    # 证据文件目录
├── snapshots/                   # patch 前后 RTL 快照
└── initial_context.json         # 初始上下文
```

### 5b.8 调查子代理 (DebugInvestigator)

主代理可通过 `route_debug_context` 工具启动一个独立的 LLM 调查子代理。子代理在**自己的独立上下文窗口**中调用最多 6 次只读工具，收集定向证据（根据 focus_signals/focus_blocks/missing_evidence 参数），最终返回一份 <3000 字符的纯文本分析报告。

子代理工具权限与主代理观察层相同（12 个只读工具），但有硬性约束：不可提议 patch、不可修改代码。当 LLM 不可用时降级为确定性规则脚本。详见 `repo_react/context.py`。

### 5b.9 长期记忆系统 (RTLMemory)

跨会话的长期记忆以 Markdown 文件形式存储在 `workspace/rtl_memory/` 下，按四种类型分目录：`cases/`（修复案例）、`patterns/`（负面模式）、`corrections/`（规划修正）、`rules/`（合并规则）。每条记忆由 YAML 元数据头（20 个索引字段）和结构化 Markdown 正文组成。`MEMORY.md` 是自动维护的人类可读索引。

写入通过确定性规则蒸馏器（`RTLMemoryDistiller`）在每次 patch/correction/merge 后自动触发。召回采用 LLM 语义选择为主、规则多维打分为降级的双层架构。选中的记忆以摘要形式进入上下文包；Agent 可通过 `read_long_term_memory(path)` 按需获取完整原文。详见 `rtl_memory/` 子系统。

### 5b.10 Planning Corrections（规划修正）

`record_correction` 允许 Agent 在不修改原始 stage artifact 的情况下记录上游规划问题：

```
output_root/planning_corrections/
├── correction_journal.jsonl     # 所有 correction 的时序日志
├── plan_overrides.json          # wrong_contract / wrong_module_plan / wrong_retrieval
├── interface_overrides.json     # wrong_interface
├── timing_overrides.json        # wrong_timing
└── dependency_overrides.json    # wrong_dependency
```

**Correction 类型**:
- `wrong_contract`: Stage1 合同有误
- `wrong_module_plan`: Stage4 模块计划有误
- `wrong_interface`: 接口定义有误
- `wrong_timing`: 时序假设有误
- `wrong_dependency`: 模块间依赖关系有误
- `wrong_retrieval`: 规范块检索选择有误

已知 corrections 在每轮 ReAct prompt 中自动注入（通过 `load_known_corrections()`）。

### 5b.11 RepoReActRunner 主循环

```
chat(inp: RepoReActInput) → RepoReActResult
│
├── 1. 初始化
│   ├── reset() agent 记忆
│   ├── 创建 RepoReActJournal (workspace/repo_react/<module>/)
│   ├── 创建 RepoReActToolState (持有 SimSnapshot, 观察标志)
│   ├── 创建 RepoReActTools (所有工具逻辑)
│   └── 构建初始 trace_summary (build_trace_report)
│
├── 2. 发送初始 prompt
│   ├── build_initial_prompt(module_name, rtl_path, spec, contract, sim_excerpt, trace, corrections, memory)
│   └── agent(Msg("user", first_prompt))
│
├── 3. 主循环 (最多 max_steps 轮)
│   ├── 检查 last_sim.is_pass → 提前退出
│   ├── 检查 _needs_compact_checkpoint → compact agent memory
│   ├── build_continue_prompt(memory_summary, readonly_calls, max_readonly_calls)
│   │   └── 包含 observation_budget 状态 + ACTION PRESSURE
│   ├── agent(Msg("user", continue_prompt))
│   ├── 提取 diagnosis JSON（从 assistant 回复中解析）
│   └── 写入 react_trace.jsonl
│
├── 4. 返回结果
│   ├── status = "pass" | "max_steps_exceeded"
│   └── RepoReActResult(status, is_pass, rtl_code, steps, action_calls, ...)
│
└── 5. 清理
    ├── persist_memory_snapshot()
    └── clear_memory_safely(agent)
```

### 5b.12 三层上下文压缩 (Three-Tier Context Compaction)

采用渐进式压缩策略，根据 Agent 的实际状态动态选择压缩强度：

| 层级 | 触发条件 | 操作 | 保留 |
|------|---------|------|------|
| **Light Consolidation** | 8次只读调用 或 24K字符 或 新写入 | 不删除对话，仅刷新上下文包 | 全部对话历史 + 最新摘要 |
| **Checkpoint Compact** | 3次写入 或 96K字符 (需已有真实差异数据) | 清空对话，注入结构化快照 | 任务框架+时序证据+证据摘要+因果记忆+活跃工作集 |
| **Deep Compact** | 2次Checkpoint已达 或 160K字符 或 预算≤20% | 同Checkpoint但摘要大幅削减 | 仅核心数据，evidence_pack全删，工作集减半 |

**关键守卫**：Checkpoint 需要 Agent 已获取真实 DUT/ref 差异数据才触发，确保 Agent 在形成初步诊断之前不会被强制清除对话历史。Deep 仅在极端困境下启动，强制 Agent 基于有限精选数据做出最终决策。

### 5b.13 Diagnosis 结构

每轮 Agent 应在采取行动前输出结构化 diagnosis：

```json
{
  "failure_type": "timing_bug | local_logic_bug | interface_bug | plan_bug | unknown",
  "suspected_module": "fifo_ctrl",
  "suspected_files": ["rtl/fifo_ctrl.sv"],
  "suspected_signals": ["data_out", "empty"],
  "evidence_summary": [
    "trace shows data_out lagging expected by 1 cycle",
    "VCD probe confirms wr_ptr updates on correct edge"
  ],
  "next_action": "patch | read_more | record_correction | stop"
}
```

### 5b.14 与 ModuleDebugRunner 的集成

`ModuleDebugRunner._run_editor()` 已被替换为 `_run_repo_react()`：

```python
def _run_repo_react(self, *, sim_reviewer, spec_text, workdir, sim_output,
                    mismatch_count, contract_json, task, module_name,
                    merged_file, spec_source_path, behavior_source):
    # 构建 RepoReActInput
    repo_input = RepoReActInput(
        module_name=module_name,
        workspace_root=self.workspace_root,
        debug_workdir=workdir,
        rtl_path=workdir / "rtl.sv",
        merged_file=merged_file,
        output_root=output_root,
        repo_root=self.repo_root,
        spec_text=spec_text,
        contract_json=contract_json,
        sim_failed_log=sim_output,
        initial_mismatch_count=int(mismatch_count),
        max_steps=int(self.config.max_trials),
    )
    runner = RepoReActRunner(cfg, sim_reviewer=sim_reviewer, ...)
    result = await runner.chat(repo_input)
    return bool(result.is_pass), result.rtl_code, int(result.action_calls)
```

**外部协议完全不变**: `ModuleDebugRunner.run_module()` 仍然返回 `ModuleDebugResult`，stage6_merge.json 的 debug_files schema 不变。

---

## 5c. Trace Report（追踪报告）

> Trace Report 在 v2 中保持核心地位，被 RepoReActRunner 在初始化时调用，以及在每次 module_sim 后自动刷新。

`build_trace_report()` 从仿真失败日志和 VCD 波形中提取结构化诊断信息。

### 5c.1 输入

- `rtl_path`: 当前 RTL 文件
- `sim_log_json`: Verilator 仿真输出 (stdout + stderr)
- `output_dir`: 包含 `wave.vcd` 和 `tb.sv` 的工作目录
- `kg_service` (可选): 用于跨模块动态切片

### 5c.2 输出结构

```json
{
  "fail_time": 150,
  "total_mismatches": 3,
  "first_failure": {"sig": "data_out", "expected": "x", "actual": "z"},
  "fail_outputs": [...],
  "alignment_diagnosis": {
    "data_out": {
      "best_alignment": "dut_lag1",
      "match_rate_dut_lag1": 0.95
    }
  },
  "value_backtrace": {
    "chains": [{
      "sig": "data_out",
      "expected": "42",
      "actual": "00",
      "chain": [{
        "signal": "data_out",
        "driver_block_id": "A3",
        "assignment_id": "A3.S1",
        "lhs_value": "00",
        "classification": "lhs_matches_rhs_continue_upstream",
        "reason": "LHS matches the current RHS value..."
      }]
    }]
  },
  "diagnostic_narrative": ["FIRST FAILURE: data_out failed: expected=42, actual=00..."],
  "suspect_blocks": [
    {"id": "A3", "kind": "always", "clocking": "seq", "writes": ["data_out"], "start_line": 45, "end_line": 52}
  ],
  "timing_hints": {"data_out": {"actual_matches_prev_expected": true, "prev_t": 140, "t": 150}}
}
```

### 5c.3 诊断维度

1. **失败信号提取**: 解析仿真输出中的 mismatch hint 行，提取最早失败时间和失败信号列表
2. **对齐诊断**: 比较 dut/ref 信号时序对齐，计算 lag1/lead1 对齐率，检测 1-cycle 移位
3. **值回溯**: 从失败输出信号沿赋值链反向追踪，对每个驱动分配采样 RHS 值和条件值
4. **动态切片**: 从失败信号沿驱动图反向传播（可选地使用 KG DRIVES + DEBUG_READS 跨模块切片）
5. **时序提示**: 检测 actual 是否匹配 previous expected (1-cycle 延迟)

---

## 6. KG Agent 知识图谱查询子系统

### 6.1 设计定位

KG Agent 是位于 Debug Agent 和 RTL Knowledge Graph 之间的 **查询抽象层**，将常见的调试查询模式封装为模板化方法。

### 6.2 KGRetriever

`KGRetriever` 提供 **固定模板的 Cypher 查询方法**：

| 方法 | 查询模板 | 功能 |
|------|---------|------|
| `get_child_module_context(parent)` | `GET_CHILD_MODULE_CONTEXT` | 获取父模块的所有子实例及其接口 |
| `get_module_interface(module)` | `GET_MODULE_INTERFACE` | 获取模块端口、参数、仿真状态 |
| `get_instance_context(parent, child, inst)` | `GET_INSTANCE_CONTEXT` | 获取实例的连接详情 |
| `get_signal_debug_context(module, signal)` | `GET_SIGNAL_DEBUG_CONTEXT` | 获取信号及其所有驱动源 |
| `get_failure_context(error_log, module)` | `GET_FAILURE_MODULE_STATUS` + others | 从错误日志提取信号名并获取综合调试上下文 |

### 6.3 信号名提取

`KGRetriever._extract_signal_names()` 使用三层正则模式从仿真日志中提取信号名：
1. `signal <name>` 模式
2. `fail/mismatch: <name>` 模式
3. `<name>_dut` / `<name>_ref` 模式

### 6.4 ModuleResultWriter

`ModuleResultWriter` 负责将 **模块生成和调试结果持久化到 KG**：

```
record_module_result(module_name, merged_file, debug_result)
│
├── 1. 构建 ModuleSimulationStatus 对象
├── 2. 更新本地状态文件 (rtl_kg_module_statuses.json)
├── 3. 触发 KG 文件刷新 (refresh_repo_files)
└── 4. 摄入 SimulationResult 节点和 HAS_SIM_RESULT 边到 Neo4j
```

**SimulationResult 节点属性**:
- `status`: pass/fixed/fail/error/skipped/disabled
- `passed`: boolean
- `mismatch_count`: 不匹配数量
- `debug_trials`: 调试尝试次数
- `final_rtl_path`: 最终 RTL 文件路径
- `trace_report_path`: 追踪报告路径
- `sim_output_path`: 仿真输出路径

---

## 7. Retrieval Agent 检索子系统

### 7.1 设计定位

Retrieval Agent 解决了 **上下文窗口有限** 的问题：当规范文本很大时，不可能将所有规范块都塞入 LLM 上下文。它使用 LLM 驱动的选择性检索，为每个代码生成/合并任务选择最相关的规范片段。

### 7.2 BlockSpecRetriever (Stage 4/5 使用)

**功能**: 为每个骨架块选择相关的规范块

```
select_block_spec_refs(module_name, module_spec, module_skeleton, skeleton_blocks)
│
├── 1. 构建候选规范块列表 (block_id + text)
├── 2. 构建必需块列表 (含 structured_context: purpose, code_shape, retrieval_focus)
├── 3. LLM 推理: 为每个 skeleton block 选择相关 spec blocks
├── 4. 验证结果: schema version, module name, count match, ref validity
└── 5. 失败时回退到全量规范 (fallback_result)
```

**验证规则**:
- interface_block refs 必须被引用（特别是第一个 declaration 块必须包含接口规范）
- 所有 spec_refs 必须存在于候选列表中
- selection 数量必须与 skeleton_blocks 数量匹配

### 7.3 MergeContextRetriever (Stage 6 使用)

**功能**: 为合并阶段选择必要的规范块

与 BlockSpecRetriever 类似，但额外考虑：
- `generated_fragments`: 已生成的代码片段
- `dependency_context`: 模块间依赖关系
- `use_kg_child_context`: 是否需要从 KG 获取子模块上下文

---

## 8. 工具系统设计

### 8.1 工具分层

系统中有三个层次的工具：

#### 8.1.1 基础设施工具

| 工具 | 位置 | 功能 |
|------|------|------|
| `run_bash_command` | `bash_tools.py` | 安全执行 bash 命令，返回 (bool, CommandResult JSON) |
| `check_syntax` | `sim_reviewer.py` | Verilator lint-only 语法检查 |
| `sim_review` | `sim_reviewer.py` | 完整的 Verilator 编译+仿真流程 |

#### 8.1.2 Agent 工具 (Tool API)

Agent 通过 AgentScope 的 `Toolkit` 机制注册工具函数：

**QueryRtlKgTool** (`rtl_kg_service.py`):
```python
class QueryRtlKgTool(Tool):
    name = "query_rtl_kg"
    # 只读 Cypher 查询，自动注入 repo_uid scope
    # 禁止写操作 (CREATE/MERGE/SET/DELETE/CALL db.*)
```

**RepoReAct 工具集** (通过 `Toolkit.register_tool_function()` 注册):

*观察工具 (Readonly Tools):*

| 工具 | 功能 | 关键约束 |
|------|------|---------|
| `read_context` | 统一读取：仓库树、文件、行范围、spec、TB、stage artifact、trace_report、repair_journal | 8 种 kind；路径限制在 allowed roots |
| `search_context` | 正则搜索 RTL / TB / spec / all | scope 过滤；最多 50 结果 |
| `query_rtl_kg` | 固定模板 KG 查询（4 种） | `module_interface` / `module_instances` / `instance_connections` / `signal_drivers` |
| `read_spec` | 读取原始规范文档 | 支持 path 或 spec_paths |
| `retrieve_spec_block` | 从 spec_blocks.json 检索规范块 | 按 block_id 或 query |
| `list_vcd_signals` | 列出 VCD 信号名 | 支持 pattern/scope 过滤 |
| `probe_vcd` | 采样 VCD 信号值 | 单时间点或时间窗口；最多 16 信号 |
| `run_check` | lint / module_sim / trace_summary | top_sim 和 wave_window → unsupported_in_v1 |
| `read_memory` | 读修复记忆 | snapshot / repair_journal / failed_directions / promising_directions |

*行动工具 (Action Tools):*

| 工具 | 功能 | 关键约束 |
|------|------|---------|
| `apply_patch` | 唯一 RTL 修改入口 | 自动 snapshot → lint → sim → trace → 回滚；最多 2 patches |
| `record_correction` | 写 planning_corrections/ overlay | 不修改原始 stage artifact；必须先读过 stage_artifact |

*旧实现工具 (v1 RTLEditor — 保留不动，新路径不再使用):*
- `list_suspect_blocks()`, `read_block(block_id)`, `replace_block(block_id, new_code)`
- `read_rtl_context()`, `read_lines(start, end)`, `apply_patch_set(patches)`
- `run_simulation()`, `probe_compare(pairs, range, edge)`

#### 8.1.3 设计约束

- **只读安全**: Cypher 查询禁止写操作
- **操作原子性**: 每次编辑后立即语法检查 + 仿真验证
- **自动回滚**: 编辑导致退化时自动撤销
- **速率限制**: `apply_patch_set` 每次只接受 1 个 patch
- **范围限制**: `read_lines` 最多 160 行，`probe_vcd` 最多 16 个信号

### 8.2 工具执行模式

#### RepoReAct 执行模式

```
Agent call tool → runner._tool_* handler → RepoReActTools method → result
                                               │
                                               ├── 状态更新 (observed_* 标志)
                                               ├── 日志写入 (react_trace.jsonl)
                                               ├── readonly counter 递增
                                               └── ToolResponse 返回
```

**关键设计约束**:
- **只读安全**: KG 查询限制为 4 种固定模板，禁止自由 Cypher
- **路径限制**: `read_context` 和 `search_context` 只能访问 allowed_read_roots 下的文件
- **编辑限制**: `apply_patch` 默认仅允许修改当前 debug RTL（v1 限制）
- **回滚机制**: 每次 patch 后自动 lint/sim/trace 验证，退化时回滚
- **速率限制**: `apply_patch` 每次最多 2 个 patch；`record_correction` 必须先读过 stage_artifact
- **观察预算**: 连续超过 8 次只读调用后，系统拒绝进一步的只读操作，强制 agent 行动或结束

#### Evidence Gate（证据门槛）

```
apply_patch 前置条件:
├── observed_rtl = True          (必须已读取当前 RTL 文件)
├── observed_trace_or_sim = True (必须已读取 trace_report 或仿真结果)
└── observed_tb_or_spec_or_kg = True (必须已读取 TB / spec / KG 之一)
```

#### 旧 RTLEditor 执行模式 (v1, 保留为参考)

```
Agent call tool → _tool_* handler → _EditSession method → result
                                       │
                                       ├── 语法检查 (check_syntax)
                                       ├── 仿真运行 (sim_reviewer.review)
                                       ├── 状态更新 (trace_report refresh)
                                       └── 日志记录 (repair_journal append)
```

---

## 9. 上下文管理设计

### 9.1 三层上下文层次

系统采用 **三层上下文管理** 策略：

| 层次 | 载体 | 生命周期 | 内容 |
|------|------|---------|------|
| Pipeline Context | stage_context (PlanningContextProvider) | 管线全局 | 项目类型、历史产物、全局约束 |
| Stage Context | partial_artifacts | 单阶段 | 所有上游阶段的产物 (contracts, skeletons, plans) |
| Agent Context | InMemoryMemory + Context Pack | 单次 LLM 调用 | 系统提示 + 对话历史 + 上下文包摘要 |

### 9.2 上下文包 (Context Pack)

RepoReAct 使用上下文包作为 Agent 状态的核心载体，包含六个部分：任务框架（当前目标、诊断、保护项、禁止方向）、时序证据（第一分歧点的精确记录）、证据摘要（最多 5 条压缩项）、因果记忆摘要（修复账本、有希望方向、长期记忆）、活跃工作集（Agent 声明的假设/证据/候选编辑）、原始 artifact 路径引用。

初始 prompt 故意不注入完整 spec/contract/corrections/memory 原文，仅通过上下文包中的路径引用和结构化摘要呈现。每步 continue prompt 刷新上下文包为最新版本并注入观察预算倒计时。上下文包是上下文压缩后唯一幸存的知识载体。

### 9.3 三层上下文压缩

详见 [5b.12 三层上下文压缩](#5b12-三层上下文压缩-three-tier-context-compaction)。

### 9.4 KG 上下文注入

通过 `build_batch_context()` 方法，管道在处理每个 batch 时自动注入 KG 查询结果（文件元数据、模块信息、实例关系）。

---

## 10. 记忆系统设计

### 10.1 短期记忆（Session 级）

#### AgentScope Memory
每个 ReAct Agent 使用 `InMemoryMemory` 管理对话记忆，通过 `clear_memory_safely()` 在压缩时重置。

#### 上下文包作为工作记忆
Agent 的修复状态通过上下文包（Context Pack）实时维护：任务框架、时序证据、因果记忆摘要（修复账本、受保护项、禁止方向、有希望方向、长期记忆）、活跃工作集。上下文包在每步循环中刷新，在压缩后作为唯一幸存的信息载体。

#### 短期持久化
| 存储位置 | 内容 |
|---------|------|
| `repo_react/<module>/react_trace.jsonl` | 完整 ReAct 对话追踪 |
| `repo_react/<module>/patch_journal.jsonl` | 每次 patch 的结构化记录（含 per-signal metric delta） |
| `repo_react/<module>/correction_journal.jsonl` | 每次 record_correction 记录 |
| `repo_react/<module>/debug_context_pack.json` | 当前上下文包快照 |
| `repo_react/<module>/context_packs/` | 每轮生成的上下文包归档 |
| `repo_react/<module>/evidence/` | 证据文件 + evidence_index.jsonl |
| `repo_react/<module>/snapshots/` | patch 前后 RTL 文件快照 |

### 10.2 长期记忆（跨 Session 级）

RTLMemory 子系统以 Markdown 文件形式存储在 `workspace/rtl_memory/`，按四种类型分目录：

| 类型 | 目录 | 内容 |
|------|------|------|
| 修复案例 | `cases/` | improved/passed 的正面经验 |
| 负面模式 | `patterns/` | regressed/syntax_failed 的失败教训 |
| 规划修正 | `corrections/` | 上游规划阶段的错误记录 |
| 合并规则 | `rules/` | Stage6 结构性经验 |

每条记忆由 YAML 元数据头（20 个索引字段：module/signals/failure_type/alignment/confidence/trigger/anti_trigger 等）和结构化 Markdown 正文组成。`MEMORY.md` 是自动维护的人类可读索引。

**写入**：通过确定性规则蒸馏器（`RTLMemoryDistiller`）在每次 patch/correction/merge 后自动触发。只有 passed/improved/regressed/syntax_failed 写入，neutral 忽略。

**召回**：采用 LLM 语义选择为主、规则多维打分为降级的双层架构。选中的记忆以摘要形式进入上下文包（body_excerpt 前 2400 字符 + 结构化元数据）；Agent 可通过 `read_long_term_memory(path)` 按需获取完整原文。

### 10.3 跨会话 KG 记忆

通过 Neo4j 图数据库实现跨会话的知识持久化：SimulationResult 节点记录每个模块的仿真历史，DEBUG_READS 关系记录调试会话中的读依赖。

---

## 11. 模型与格式化层

### 11.1 模型配置

```python
@dataclass(frozen=True)
class OpenAIConfig:
    model: str = "gpt-5.2"
    api_key: str | None
    base_url: str | None
    organization: str | None
    reasoning_effort: str | None  # low/medium/high/xhigh/max
    stream: bool = False
    generate_kwargs: dict  # temperature, top_p, max_completion_tokens, extra_body
```

支持通过环境变量配置:
- `OPENAI_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- `OPENAI_ORGANIZATION`, `OPENAI_EXTRA_BODY`

### 11.2 模型工厂

`make_openai_model(cfg)` → `UsageTrackingModel(OpenAIChatModel(...))`

`UsageTrackingModel` 是一个 **装饰器包装**，自动累计所有 LLM 调用的 input/output token 使用量。

### 11.3 多模型格式化器

系统支持三种消息格式化器，根据模型自动选择：

| 格式化器 | 适用模型 | 特性 |
|---------|---------|------|
| `OpenAIChatFormatter` | 默认 (GPT 系列) | 标准 OpenAI API 格式 |
| `DeepSeekReasoningChatFormatter` | DeepSeek 系列 | 保留 `reasoning_content` (thinking blocks) |
| `Llama4ChatFormatter` | Llama 4 系列 | 将 tool_result 转为 user 消息 (不支持 tool role) |

### 11.4 SafeReActAgent

继承 `ReActAgent`，增加 `generate_response` 的容错处理：
- 如果模型返回 dict 而非 string，自动 JSON 序列化
- 确保 agent 总能干净地终止

---

## 12. 完整任务协作流程

### 12.1 端到端流程

以下展示一个完整的 "规范 → 验证 RTL" 任务流程：

```
Phase 0: 初始化
├── 加载 LLM 配置 (OpenAI/DeepSeek/Llama)
├── 初始化 Neo4j 连接 (如果启用)
├── 构建/加载 RTL Knowledge Graph
└── 初始化 PlannerRunner

Phase 1: 规范理解 (Stage 1)
├── PlannerTaskInput(spec_md_files=[...], spec_images=[...])
├── Stage1Agent.run()
│   ├── 解析 Markdown → SpecFragments
│   ├── 预扫描图片 → ImageCards
│   ├── 提取接口/时序/控制/数据通路契约
│   └── 构建项目记忆卡
├── build_module_organized_artifact() → modules.json
└── KG snapshot sync (post_skeleton)

Phase 2: 架构规划 (Stage 2-3)
├── Stage2Agent.run() → RepoSkeleton (模块层次结构)
├── Stage3Agent.run_incremental() → ModuleSkeletons (每个模块的代码骨架)
│   ├── For each module:
│   │   ├── 生成接口声明
│   │   ├── 生成内部信号
│   │   ├── 生成 always/assign 块骨架
│   │   ├── 生成子模块实例化
│   │   └── 输出 .md 文档 + .json 结构
│   └── 支持断点续传 (resume_cursor)
└── KG snapshot sync (post_skeleton)

Phase 3: 详细规划 (Stage 4)
├── Stage4SpecBlocksAgent.run() → SpecBlocks (规范块切分)
├── Stage4ModulePlanAgent.run_incremental() → ModulePlans
│   ├── For each module:
│   │   ├── BlockSpecRetriever: 为每个骨架块选择相关规范
│   │   ├── 生成 N 个候选方案
│   │   ├── Checklist 多维度评估
│   │   ├── PairwiseTieBreak 两两对比
│   │   ├── 选择最优方案
│   │   └── 分解为子任务 (ModulePlanSubtasks)
│   └── 支持断点续传
└── KG snapshot sync (post_module_plan)

Phase 4: 代码生成 (Stage 5)
├── Stage5Agent.run_incremental()
│   ├── For each module in module_order:
│   │   ├── [define-only 模块] → 从 RealBench 直接复制官方文件
│   │   │   └── 写入 global_defines_manifest.json
│   │   ├── For each subtask in module_plan.subtasks:
│   │   │   ├── 选择相关规范块 + 接口规范块
│   │   │   ├── 读取 Module Skeleton "Module Frame"
│   │   │   ├── LLM 生成 SubtaskCodeArtifact (code + FragmentContract)
│   │   │   ├── 自动提取 Fragment Contract (writes/reads/clocking)
│   │   │   ├── Upsert 到 fragment 文件 (STAGE5_SUBTASK_BEGIN/END)
│   │   │   └── 追加到 {module}_contracts.json
│   │   └── 质量验证: 禁止 unpacked array/multi-dim/generate
│   └── 输出: workspace/fragments/{module}_fragments.v + _contracts.json
└── KG refresh (post_codegen)

Phase 5: 合并与验证 (Stage 6)
├── Stage6MergeAgent.run_module()
│   ├── [define-only 模块] → 跳过合并, 直接使用已复制的官方文件
│   │
│   ├── 准备上下文:
│   │   ├── MergeContextRetriever → merge_retrieval_json/{module}.json
│   │   ├── KG 子模块上下文 (可选) → merge_child_context_json/{module}.json
│   │   ├── Global defines 上下文 (提取活跃 define 值)
│   │   └── Module Skeleton "Module Frame"
│   │
│   ├── [优先] Semantic Merge (Stage6MergeRunner):
│   │   ├── 渐进式初始 prompt (仅索引, 不含完整 spec)
│   │   ├── ReAct 循环 (最多 8 步):
│   │   │   ├── Agent 自主: read_merge_context × 8 kinds
│   │   │   ├── Agent 自主: inspect_rtl_structure / run_static_rtl_check / run_lint
│   │   │   ├── Agent draft: generate_merge_draft (evidence gate → pre-check lint)
│   │   │   │   └── 自动注入 required includes
│   │   │   ├── Agent commit: commit_merge_draft (final check → copy to merged/)
│   │   │   └── Observation budget: 16 次只读调用后强制行动
│   │   ├── 跨模块学习: read learned_merge_rules (前序模块的经验)
│   │   └── 输出: workspace/merged/{module}.v + merge_journal + merge_report
│   │
│   └── [降级] Raw Merge Fallback:
│       ├── 一次性 LLM 调用, Verilator lint
│       ├── 语法错误 → stage6_syntax_repair/{module}.json (委派标记)
│       └── 语法修复责任移交给 RepoReActRunner
│
├── ModuleDebugRunner.run_module() [环境准备 + 前处理]
│   ├── Oracle TB + support.sv, pre-debug syntax repair, 初始仿真
│   └── Mismatch → RepoReActRunner (仓库级自主 ReAct 调试)
│
└── 输出: Stage6MergeArtifact + KG state + RepoReAct journals

Phase 6: 产出
├── 合并后的 .sv 文件
├── 仿真通过的模块列表
├── 调试报告 (trace_report.json, repair_journal.json)
└── KG 中的仿真状态记录
```

### 12.2 Agent 间通信协议

Agent 之间 **不直接通信**，而是通过以下方式间接协作：

1. **文件系统**: tb.sv, rtl.sv, trace_report.json, support.sv, support_interface_index.json
2. **结构化对象**: Pydantic BaseModel 产物在各阶段间传递
3. **知识图谱**: 仿真结果、模块状态通过 Neo4j 共享（SimulationResult 节点）
4. **工作目录**: 每个模块的 `debug/<module>/` 作为共享工作空间
5. **RepoReAct Journal**: `workspace/repo_react/<module>/` 下的 JSONL 日志和快照（NEW）
6. **Planning Corrections**: `output_root/planning_corrections/` 下的 overlay JSON（NEW）

### 12.3 并发与隔离

- **Stage 3-5**: 逐模块增量处理 (支持 resume)
- **Stage 6**: 逐模块串行处理 (debug 需要独占 Verilator)
- **KG 写入**: 使用 Neo4j 事务隔离
- **工作目录**: 每个模块独立的 debug workdir

---

## 13. 持久化与检查点机制

### 13.1 产物持久化

所有 Planner 产物通过 **原子写入** (tmp 文件 + rename) 持久化：

```python
tmp_path = path.with_name(f"{path.name}.tmp")
with open(tmp_path, "w") as f:
    json.dump(payload, f)
tmp_path.replace(path)  # 原子替换
```

### 13.2 断点续传 (Resume)

`PlannerRunner.run(resume=True)` 支持在每个阶段复用已有产物：

```
Stage 1: 检查 contracts.json 是否存在且通过 validate_quality()
Stage 2: 检查 repo_skeleton.json
Stage 3: 检查 module_skeletons.json + resume_cursor
Stage 4: 检查 spec_blocks.json 和 module_plans.json + resume_cursor
Stage 5: 检查 fragment 文件是否包含所有 STAGE5_SUBTASK_BEGIN/END 标记
Stage 6: 检查 merged .sv 是否存在且通过 Verilator 语法检查
```

每个阶段的 resume 检查包含：
1. 文件存在性
2. JSON 格式有效性
3. Pydantic 模型验证
4. 语义质量验证 (validate_quality)
5. 完整性检查 (如 fragment 标记)

### 13.3 KG 状态持久化

```
RTLKgService
├── state_path: rtl_kg_state (连接状态)
├── manifest_path: rtl_kg_manifest (同步事件日志)
└── Neo4j 图数据库 (代码结构 + 仿真结果)
```

---

## 14. 错误处理与韧性设计

### 14.1 分层错误处理

```
Level 1: 语法错误 (Verilator --lint-only)
├── 自动 LLM 驱动修复 (pre-debug syntax repair)
├── 最多 5 次修复尝试
└── 每次尝试记录详细日志

Level 2: 仿真不匹配 (Simulation mismatch)
├── Trace Report 自动诊断
├── Value Backtrace 定位根因
├── Dynamic Slicing 缩小搜索空间
└── RTLEditor 迭代修复 (最多 max_trials 次)

Level 3: 解析错误 (LLM output parsing)
├── JSON repair (repair_json_payload)
├── 最多 max_parse_attempts 次重试
└── 失败后抛出 ValueError

Level 4: 质量错误 (Quality validation)
├── 最多 max_quality_attempts 次重试
├── 接受最佳努力结果 (best-effort fallback)
└── 记录残余质量问题

Level 5: 系统错误 (Exceptions)
├── debug_runner 中 allow_failure=True 时容忍
├── KG mode="optional" 时 KG 写入失败不阻塞
├── 完整错误日志 (module, stage, exception type + message)
└── 继续处理下一个模块
```

### 14.2 韧性策略

| 策略 | 应用场景 | 机制 |
|------|---------|------|
| **文本回退解析** | tree-sitter 无法解析的 RTL | 正则表达式回退 |
| **全量规范回退** | 检索失败 | fallback_result() → 使用所有 spec blocks |
| **最佳努力质量** | 质量检查多次失败 | allow_best_effort_quality_fallback=True |
| **自动回滚** | 编辑导致退化 | mismatch count 显著增加时回滚 |
| **黄金 TB 回退** | LLM 生成的 TB 有问题 | 回退到 goldentestbench |
| **RTL 重新生成** | 编辑循环前给一次重新生成机会 | `set_failed_trial()` → 重新生成 |

---

## 15. 配置系统

### 15.1 配置层次

```
1. 代码默认值 (OpenAIConfig.model = "gpt-5.2")
2. 环境变量 (OPENAI_MODEL, OPENAI_API_KEY, ...)
3. Planner LLM Config (LLMConfig 对象)
4. RTL Debug Config (ZEROREPO_RTL_DEBUG_* 环境变量)
5. KG Config (rtl_agent_root, neo4j.*, batch_size, ...)
```

### 15.2 关键配置项

#### RTL Debug 配置

| 环境变量 | 默认值 | 描述 |
|---------|--------|------|
| `ZEROREPO_RTL_DEBUG` | `1` | 启用/禁用 RTL 调试 |
| `ZEROREPO_RTL_DEBUG_ORACLE_ROOT` | `/home/mokita/RealBench` | 黄金测试平台根目录 |
| `ZEROREPO_RTL_DEBUG_MAX_TRIALS` | `10` | 最大调试尝试次数 |
| `ZEROREPO_RTL_DEBUG_ALLOW_FAILURE` | `0` | 是否允许调试失败不崩溃 |
| `ZEROREPO_RTL_DEBUG_TOOLCHAIN_BIN` | `""` | Verilator 工具链路径 |

#### KG 配置

```python
{
    "enabled": True/False,
    "mode": "optional" | "required",
    "neo4j": {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "neo4j123456"
    },
    "batch_size": 2000,
    "default_query_limit": 25,
    "max_query_rows": 100
}
```

#### Tree-sitter 配置

| 环境变量 | 描述 |
|---------|------|
| `RTL_TS_LANG_SO` | 预编译的 tree-sitter 共享库路径 |
| `RTL_TS_GRAMMAR_DIR` | tree-sitter-verilog 语法仓库路径 |
| `RTL_TS_LANG_NAME` | 语言名称 (默认: verilog) |

---

## 16. 附录：文件索引

### 16.1 完整文件清单

```
zerorepo/rtl_impl/
├── __init__.py                          # 包入口 (延迟导入)
├── rtl_kg_service.py                    # KG 服务封装 + QueryRtlKgTool
│
├── rtl_kg/                              # RTL 知识图谱核心
│   ├── __init__.py                      # 导出 KnowledgeGraphRTL, RTLNeo4jIngestor 等
│   ├── graph_types_rtl.py               # 节点/边类型定义 (12 种节点, 10 种关系)
│   ├── rtl_knowledge_graph.py           # 图谱构建器 (DFS 遍历 + 后处理)
│   ├── rtl_file_graph_builder.py        # 单文件 tree-sitter 解析器
│   ├── neo4j_ingest.py                  # Neo4j 批量摄入器
│   ├── ingest_rtl_kg_to_neo4j.py        # CLI 摄入工具
│   └── ast_extract_example.py           # AST 提取示例
│
├── module_planner/                      # 6 阶段规划管线
│   ├── __init__.py                      # 导出所有 schema 和 runner
│   ├── planner_runner.py                # 管线编排器
│   ├── interfaces.py                    # PlanningContextProvider/ArtifactSink 协议
│   ├── module_organizer.py              # 模块组织 (Stage1 → ModuleOrganization)
│   ├── compat.py                        # 向后兼容适配器
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseStageAgent (LLM 调用 + 解析修复 + 质量修复)
│   │   ├── stage1_agent.py              # 规范摄取与契约提取
│   │   ├── stage2_agent.py              # 仓库骨架规划
│   │   ├── stage3_agent.py              # 模块骨架生成
│   │   ├── stage4_agent.py              # Stage4 基础类
│   │   ├── stage4_spec_blocks_agent.py  # 规范块切分
│   │   ├── stage4_module_plan_agent.py  # 模块实现计划
│   │   ├── stage5_agent.py              # 逐子任务代码生成 (v2: +FragmentContract +define-only)
│   │   ├── stage6_merge_agent.py        # 代码合并 (v2: +Semantic Merge +global defines +KG child)
│   │   ├── stage6_semantic_merge.py     # Stage6 ReAct Merge Runner (NEW)
│   │   └── global_defines.py            # 官方 define 文件处理 (NEW)
│   ├── prompts/                         # 每个阶段的 LLM 提示模板
│   ├── schemas/                         # 所有阶段的 Pydantic 数据模型
│   │   ├── common.py, atoms.py          # 基础类型 + 原子类型
│   │   ├── contracts.py                 # Stage1 契约模型
│   │   ├── repo_skeleton.py             # Stage2 仓库骨架模型
│   │   ├── module_skeleton.py           # Stage3 模块骨架模型
│   │   ├── module_plan.py               # Stage4 模块计划模型
│   │   ├── spec_blocks.py               # Stage4 规范块模型
│   │   ├── codegen_plan.py              # Stage5/6 代码生成+合并模型 (NEW: FragmentContract)
│   │   ├── artifacts.py                 # 阶段产物聚合模型
│   │   └── responsibility.py            # 责任分配模型
│   └── utils/                           # LLM 客户端、JSON 修复、日志等
│
├── debug_agent/                         # 调试子系统（环境准备 + 前处理）
│   ├── __init__.py                      # 导出 ModuleDebugRunner, RtlDebugConfig
│   ├── debug_runner.py                  # 模块调试运行器（v2: 委托给 RepoReActRunner）
│   ├── top_agent.py                     # 多 Agent RTL 生成循环 (TopAgent, 旧独立入口, 保留)
│   ├── rtl_editor.py                    # 交互式 RTL 编辑器 (RTLEditor + _EditSession, 旧实现, 保留)
│   ├── architect_agent.py               # 合同生成 Agent (ArchitectAgent)
│   ├── sim_reviewer.py                  # Verilator 仿真接口 (SimReviewer + check_syntax)
│   ├── trace_report.py                  # 追踪报告生成器 + VCD 探测工具 (被 RepoReAct 复用)
│   ├── trace_slicer.py                  # RTL 块解析 + 动态切片 (被 RepoReAct 复用)
│   ├── kg_debug_reads.py                # KG 驱动的调试读依赖 (被 RepoReAct 复用)
│   ├── contract_linter.py               # 合同 JSON 格式验证器
│   ├── adapters.py                      # Planner→Debug 适配 (配置转换 + 数据构建)
│   ├── agents.py                        # SafeReActAgent + 内存清理工具
│   ├── model.py                         # 模型工厂 + 多格式化器 + UsageTracking
│   ├── config.py                        # OpenAI 配置数据类 + 加载函数
│   ├── bash_tools.py                    # 安全 Bash 命令执行
│   ├── utils.py                         # 文本处理工具 (clip_text, extract_json 等)
│   └── Debug_agent.md                   # 设计文档
│
├── repo_react/                          # 仓库级自主 ReAct 调试环 (NEW — v2 核心)
│   ├── __init__.py                      # 导出 RepoReActRunner, RepoReActInput, RepoReActResult
│   ├── runner.py                        # RepoReActRunner: SafeReActAgent + 11 个注册工具
│   ├── tools.py                         # RepoReActTools: 全部工具实现 + RepoReActToolState
│   ├── schemas.py                       # Pydantic 模型: Diagnosis, Patch, Correction, StepRecord, SimSnapshot
│   ├── prompt.py                        # SYSTEM_PROMPT + initial/continue/compact prompt builders
│   └── journal.py                       # RepoReActJournal: JSONL 日志 + before/after snapshots
│
├── kg_agent/                            # KG 查询子系统
│   ├── __init__.py
│   ├── kg_retriever.py                  # 模板化 KG 查询 (KGRetriever)
│   ├── kg_query_templates.py            # 固定 Cypher 查询模板
│   ├── module_result_writer.py          # 仿真结果写入 (ModuleResultWriter)
│   └── schemas.py                       # ModuleSimulationStatus
│
└── retrieval_agent/                     # 检索子系统
    ├── __init__.py
    ├── block_spec_retriever.py           # 规范块检索 (Stage4/5)
    ├── merge_context_retriever.py        # 合并上下文检索 (Stage6)
    ├── schemas.py                        # 检索结果 Schema
    ├── utils.py                          # 检索工具函数
    └── prompts/                          # 检索 LLM 提示模板
```

### 16.2 关键数据流总结 (v2)

```
输入: Spec (.md + images)
  │
  ├──[Stage1]──► contracts.json + modules.json ──► [KG sync]
  ├──[Stage2]──► repo_skeleton.json
  ├──[Stage3]──► module_skeletons.json + .md docs
  ├──[Stage4]──► spec_blocks.json + module_plans.json
  │                  │
  │                  └──[BlockSpecRetriever]──► block_spec_retrieval_json/
  ├──[Stage5]──► stage5_codegen.json + fragment .sv files
  ├──[Stage6]──► Merged .sv files
  │                  │
  │                  ├──[MergeContextRetriever]──► selected spec refs
  │                  └──[ModuleDebugRunner]──► debug workdirs
  │                        │
  │                        ├──► Oracle TB + support.sv
  │                        ├──► Pre-debug syntax repair (≤5 LLM attempts)
  │                        ├──► Initial SimReviewer.review()
  │                        │
  │                        └──► [RepoReActRunner] (NEW — replaces RTLEditor)
  │                              │
  │                              ├──► Initial trace_report (build_trace_report)
  │                              ├──► ReAct loop (max_steps rounds):
  │                              │   ├── read_context / search_context / query_rtl_kg
  │                              │   ├── read_spec / retrieve_spec_block
  │                              │   ├── list_vcd_signals / probe_vcd
  │                              │   ├── run_check (lint / module_sim / trace_summary)
  │                              │   ├── read_memory (snapshot / journal / directions)
  │                              │   ├── apply_patch (snapshot → lint → sim → trace → rollback)
  │                              │   └── record_correction → planning_corrections/
  │                              │
  │                              ├──► react_trace.jsonl + patch_journal.jsonl
  │                              ├──► correction_journal.jsonl + *_overrides.json
  │                              ├──► snapshots/ (step_NNN_before/after)
  │                              └──► repo_react_memory_snapshot.json
  │
  ├──[ModuleResultWriter]──► Neo4j SimulationResult + HAS_SIM_RESULT
  │
  └── 输出: Verified .sv files + KG state + RepoReAct journals
```

### 16.3 v1 → v2 架构变更摘要

#### 调试子系统 (debug_agent → repo_react)

| 维度 | v1 | v2 |
|------|----|----|
| **调试模型** | RTLEditor: 固定 block-edit 流水线 | RepoReActRunner: 仓库级自主 ReAct |
| **观察范围** | 当前模块 trace_report + suspect blocks | 全仓库 (RTL / TB / spec / stage artifacts / KG / VCD) |
| **编辑模式** | replace_block / apply_patch_set (固定 block) | apply_patch (自由行范围) |
| **证据要求** | 无强制前置条件 | 三要素 gate (RTL + trace + TB/spec/KG) |
| **规划修正** | 不支持 | record_correction → planning_corrections/ |
| **观察预算** | 无限制 | 连续 8 次只读后强制行动 |
| **回滚策略** | mismatch 显著增加 | lint fail / mismatch↑ / fail_time↓ / 2×neutral |
| **日志系统** | repair_journal.json | react_trace.jsonl + patch_journal.jsonl + correction_journal.jsonl |
| **快照** | 无 | step_NNN_before/after 完整 RTL 副本 |
| **Toolkit 工具数** | 10 (RTLEditor) | 11 (RepoReAct) |
| **外部协议** | ModuleDebugResult 不变 | **完全兼容** |

#### 代码生成子系统 (Stage 5)

| 维度 | v1 | v2 |
|------|----|----|
| **Fragment 追踪** | 仅 STAGE5_SUBTASK_BEGIN/END 标记 | 标记 + FragmentContract (writes/reads/clocking/reset/latency/assumptions) |
| **契约持久化** | 无 | workspace/fragments/{module}_contracts.json |
| **Contract 提取** | LLM 输出 (可选) | 自动代码分析 fallback (_extract_fragment_contract) |
| **语法约束** | 无特殊限制 | 禁止 unpacked array / multi-dim / generate/genvar |
| **Define-Only 处理** | 不支持 | 自动检测 + 从 RealBench 直接复制 |
| **模块骨架上下文** | 未使用 | 提取 "Module Frame" 段注入 prompt |

#### 代码合并子系统 (Stage 6)

| 维度 | v1 | v2 |
|------|----|----|
| **合并模型** | 一次性 LLM 调用 | Semantic Merge (ReAct Agent + 6 工具) 优先, Raw Merge 降级 |
| **工具集** | 无 | read_merge_context × 8, inspect_rtl_structure, run_static_rtl_check, run_lint, generate_merge_draft, commit_merge_draft |
| **证据门槛** | 无 | draft 前必须读 fragments + spec + global_defines; commit 前必须 inspected + checks pass |
| **Required Includes** | 未处理 | 自动检测 + 自动注入 + static check 验证 |
| **Global Defines** | 未处理 | 官方文件直接复制 + manifest + 活跃值提取注入 prompt |
| **KG 子模块上下文** | 不支持 | 可选检索 (接口 + 参数 + 仿真状态 + 完整代码) |
| **跨模块学习** | 不支持 | learned_merge_rules (前序模块 merge report) |
| **草稿管理** | 直接写入 merged | draft → inspect → check → lint → commit 渐进式 |
| **回滚** | 不可回滚 | draft reject 后可重新生成 |
| **观察预算** | 无限制 | 连续 16 次只读后强制行动 |
| **语法修复** | Stage6 自己重试 | **委派给** RepoReActRunner (syntax repair mode) |
| **日志系统** | 无 | merge_trace.jsonl + draft_journal.jsonl + snapshots + merge_report |
| **Define-Only 处理** | 不支持 | 自动检测 + 跳过合并 + 直接使用官方副本 |

---

> **文档结束** — 本文档基于对 `/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/` 目录下全部 Python 源文件的详细阅读与分析，涵盖约 60 个源文件、超过 15,000 行代码。文档系统性地描述了 RTL Agent 的架构设计、组件职责、协作流程、数据模型、工具系统、上下文管理、记忆机制、错误处理与配置管理等各个方面。
