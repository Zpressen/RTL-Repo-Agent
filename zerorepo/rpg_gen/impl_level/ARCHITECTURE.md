# Impl Level 架构与运行流程详解

## 一、整体架构概览

`impl_level` 是 RPG (Repository Project Generation) 系统的第三层，负责将功能需求转换为可执行的代码实现。该层级采用**三层 Agent 协作架构**，逐步完成从文件结构设计到具体接口设计再到任务规划的完整流程。

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ImplBuilder (入口编排器)                                   │
│                                    run() 方法驱动整个流程                                     │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        流程阶段                                               │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  Stage 1: Skeleton Building          Stage 2: Graph Building         Stage 3: Task Planning  │
│  (文件结构设计)                       (功能图设计)                    (任务规划)                │
│                                                                                              │
│  ┌─────────────────┐                ┌─────────────────┐              ┌─────────────────┐     │
│  │  FileDesigner   │                │  FuncDesigner   │              │  TaskPlanner    │     │
│  │                 │                │                 │              │                 │     │
│  │ RawSkeletonAgent│                │ DataFlowAgent   │              │ TaskBatch       │     │
│  │       ↓         │                │       ↓         │              │    ↓            │     │
│  │GroupSkeletonAgent│               │ BaseClassAgent  │              │ TaskManager     │     │
│  │                 │                │       ↓         │              │                 │     │
│  │                 │                │ InterfaceAgent  │              │                 │     │
│  └─────────────────┘                └─────────────────┘              └─────────────────┘     │
│           │                                │                                   │             │
│           ▼                                ▼                                   ▼             │
│    RepoSkeleton                    RPG (with data flow)              List[TaskBatch]         │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、数据流转总览

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    输入数据                                                 │
│                                                                                             │
│   repo_data.json (从 Phase2Contracts 转换而来)                                              │
│   └─ repository_name, repository_purpose, Component[], rtl_metadata{}                     │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                               ImplBuilder.run()                                             │
│                                                                                             │
│   1. create_initial_rpg() → RPG (功能节点树)                                                │
│                                                                                             │
│   2. build_skeleton() → RepoSkeleton (文件骨架)                                            │
│      └─ FileDesigner.run()                                                                │
│         ├─ RawSkeletonAgent.generate_raw_skeleton()                                         │
│         └─ GroupSkeletonAgent.group_subtree_features() (按功能区分)                         │
│                                                                                             │
│   3. build_graph() → RPG (带数据流的完整图)                                                 │
│      └─ FuncDesigner.run()                                                                 │
│         ├─ DataFlowAgent.build_data_flow()                                                 │
│         ├─ BaseClassAgent.design_base_classes()                                            │
│         └─ InterfaceAgent.design_interfaces() (按文件迭代)                                  │
│                                                                                             │
│   4. plan_all_tasks() → List[TaskBatch] (任务批次)                                         │
│      └─ TaskPlanner.plan_all_batches()                                                     │
│         └─ TaskPlannerAgent.plan_all_tasks()                                               │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    输出数据                                                 │
│                                                                                             │
│   1. RepoSkeleton          - 文件树结构，包含每个文件的元信息                               │
│   2. RPG (global_rpg.json) - 完整功能图，包含节点、边、数据流                               │
│   3. List[TaskBatch]       - 任务批次列表，包含每个文件的实现任务                           │
│   4. 状态文件 (task_manager_state.json)                                                    │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、各阶段详细说明

### Stage 1: Skeleton Building (文件骨架设计)

**目的**: 将功能区域映射为具体的文件结构和目录组织

**核心组件**: `FileDesigner`

**输入数据**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `repo_name` | `str` | 仓库名称 |
| `repo_info` | `str` | 仓库目的描述 |
| `Component[].name` | `str` | 组件名称 |
| `Component[].refactored_subtree` | `dict` | 重构后的功能子树 |

**输出数据**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `RepoSkeleton` | `对象` | 文件树结构 |
| `RPG` | `对象` | 更新后的功能图 |

#### Stage 1.1: RawSkeletonAgent (原始骨架生成)

**职责**: 根据功能区域列表生成顶层目录结构

**核心方法**: `generate_raw_skeleton()`

**Agent 流程**:
```
输入: RPG (包含功能区域列表)
    │
    ▼
LLM (RAW_SKELETON Prompt)
    │
    ├─ 生成目录结构字典
    │   例: {"src": {"ml": ["MLAlgorithms"], "data": ["DataProcessing"]}, "tests": [], "docs": []}
    │
    ▼
output: raw_skeleton_dict + name_to_path_map
```

**Prompt 模板** (`raw_skeleton.py`):
- `RAW_SKELETON`: 指导 Agent 创建顶层目录结构
- `RAW_SKELETON_REVIEW`: 四维度评审 (功能分组、桥接组件、独有分配、语义命名)
- `RAW_SKELETON_TOOL`: 工具定义 `generate_raw_skeleton`

**关键约束**:
- 使用 snake_case 命名
- 禁止 `module`, `misc`, `temp` 等模糊名称
- 每个功能区域只能出现在一个顶层目录下

#### Stage 1.2: GroupSkeletonAgent (特性分组)

**职责**: 将子树的叶特性分配到具体文件

**核心方法**: `group_subtree_features()`

**Agent 流程** (按每个功能区域迭代):
```
输入: 当前骨架树 + 剩余未分配特性
    │
    ▼
LLM (GROUP_SKELETON Prompt)
    │
    ├─ 调用 assign_features_to_files 工具
    │   输出: {"file_path": [feature1, feature2, ...], ...}
    │
    ▼
更新骨架树，递归处理子目录
    │
    ▼
输出: 完整骨架树 + 更新的 RPG
```

**Prompt 模板** (`group_skeleton.py`):
- `GROUP_SKELETON`: 指导 Agent 将特性分配到文件
- `GROUP_SKELETON_REVIEW`: 五维度评审 (文件范围、结构组织、模块化、命名、结构合理性)
- `ASSIGN_FEATURES_TO_FILES_TOOL`: 工具定义 `assign_features_to_files`

**关键约束**:
- 每个文件必须有清晰、专注的职责
- 禁止 `other`, `misc`, `temp` 等文件名
- 禁止增量命名模式 (`_a.py`, `_b.py`)

---

### Stage 2: Graph Building (功能图设计)

**目的**: 在骨架基础上设计组件间的数据流、基类和接口

**核心组件**: `FuncDesigner`

**输入数据**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `RepoSkeleton` | `对象` | 文件骨架 |
| `RPG` | `对象` | 功能图 |
| `LLMConfig` | `对象` | LLM 配置 |

**输出数据**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `RepoSkeleton` | `对象` | 更新后的骨架 (包含接口代码) |
| `RPG` | `对象` | 完整功能图 (包含数据流) |
| `graph_results` | `dict` | 各阶段执行结果 |

#### Stage 2.1: DataFlowAgent (数据流构建)

**职责**: 构建组件间的数据流图 (DAG)

**核心方法**: `build_data_flow()`

**Agent 流程**:
```
输入: RepoSkeleton + RPG (包含功能区域)
    │
    ▼
LLM (COMPONENT_DATA_FLOW Prompt)
    │
    ├─ 生成数据流边列表
    │   [{"source": "子树A", "target": "子树B", "data_id": "...", "data_type": "...", "transformation": "..."}]
    │
    ▼
output: data_flow (边列表)
```

**Prompt 模板** (`data_flow.py`):
- `COMPONENT_DATA_FLOW`: 指导 Agent 设计数据流
- `COMPONENT_DATA_FLOW_REVIEW`: 四维度评审 (数据完整性、流程逻辑、转换清晰度、覆盖度)
- `GENERATE_DATA_FLOW_TOOL`: 工具定义 `generate_data_flow`

**关键约束**:
- 数据流必须是 DAG (无环图)
- 禁止创建 2 节点或多节点环

#### Stage 2.2: BaseClassAgent (基类设计)

**职责**: 设计可复用的基础类和全局数据结构

**核心方法**: `design_base_classes()`

**Agent 流程**:
```
输入: 数据流图 + 功能区域信息
    │
    ▼
LLM (DESIGN_BASE_CLASSES Prompt)
    │
    ├─ 生成基类代码
    │   [{"file_path": "path", "code": "python_code"}]
    │
    ▼
output: base_classes (代码列表)
```

**Prompt 模板** (`base_class.py`):
- `DESIGN_BASE_CLASSES`: 指导 Agent 设计基类
- `DESIGN_BASE_CLASSES_REVIEW`: 四维度评审 (设计质量、可复用性、抽象级别、接口清晰度)
- `GENERATE_BASE_CLASS_TOOL`: 工具定义 `generate_base_classes`

**关键约束**:
- 最小化抽象原则：只在消除明确重复时添加
- 区分"功能基类"和"全局数据结构"

#### Stage 2.3: InterfaceAgent (接口设计)

**职责**: 为每个文件设计函数/类接口

**核心方法**: `design_interfaces()`

**Agent 流程** (按每个文件迭代):
```
输入: FileNode + 数据流图 + 基类信息
    │
    ▼
LLM (DESIGN_ITF Prompt)
    │
    ├─ 生成接口代码
    │   [{"features": ["feature_path"], "code": "interface_code"}]
    │
    │   接口要求: imports + signature + docstring + pass
    │
    ▼
output: interfaces (接口代码列表)
```

**Prompt 模板** (`design.py`):
- `DESIGN_ITF`: 指导 Agent 设计接口
- `DESIGN_ITF_REVIEW`: 六维度评审 (功能对齐、结构完整性、文档质量、接口风格、可扩展性、数据流一致性)
- `DESIGN_INTERFACE_TOOL`: 工具定义 `design_itfs_for_feature`

**关键约束**:
- 避免大型单体接口
- 按逻辑分组功能
- 单一职责原则

---

### Stage 3: Task Planning (任务规划)

**目的**: 将设计好的接口拆分为可执行的任务批次

**核心组件**: `TaskPlanner`

**输入数据**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `RPG` | `对象` | 完整功能图 |
| `graph_results` | `dict` | 包含 subtree_order |
| `LLMConfig` | `对象` | LLM 配置 |

**输出数据**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `List[TaskBatch]` | `List` | 任务批次列表 |

#### Stage 3.1: TaskPlannerAgent (任务规划)

**职责**: 将接口实现拆分为批次

**核心方法**: `plan_all_tasks()`

**Agent 流程** (按每个文件迭代):
```
输入: file_path + RPG + subtree + units_to_feature + units_to_code
    │
    ▼
LLM (BATCH_PLANNER Prompt)
    │
    ├─ 6步推理过程
    │   1) 枚举所有单元
    │   2) 识别单元依赖关系
    │   3) 将相关单元聚类
    │   4) 验证无重复
    │   5) 确定拓扑顺序
    │   6) 验证无遗漏
    │
    ├─ plan_task_batches 工具
    │   输出: [{"task": "...", "units": [...], "priority": 0}, ...]
    │
    ▼
output: List[TaskBatch]
```

**Prompt 模板** (`task_planner.py`):
- `BATCH_PLANNER`: 指导 Agent 规划批次

#### TaskBatch 数据模型

```python
@dataclass
class TaskBatch:
    task_id: str                    # 唯一标识符
    task: str                       # GitHub 风格任务描述
    file_path: str                  # 目标文件路径
    units_key: List[str]            # 该批次包含的单元键列表
    unit_to_code: Dict[str, str]    # 单元键到代码的映射
    unit_to_features: Dict[str, List]  # 单元键到特征的映射
    priority: int = 0               # 优先级 (数字越小越高)
    subtree: str = ""               # 功能区域
    task_type: str = "implementation"  # 任务类型
```

**任务类型**:
- `implementation`: 常规代码实现
- `integration_test`: 集成测试 (优先级 1000)
- `final_test_docs`: 综合测试和文档 (优先级 2000)

---

## 四、数据模型详解

### 4.1 RepoSkeleton (仓库骨架)

```python
class RepoSkeleton:
    root: DirectoryNode              # 根目录节点
    path_to_node: Dict[str, RepoNode]  # 路径到节点的映射
```

**DirectoryNode**:
```python
class DirectoryNode(RepoNode):
    name: str                       # 目录名
    path: str                       # 相对路径
    children: List[RepoNode]        # 子节点列表
```

**FileNode**:
```python
class FileNode(RepoNode):
    name: str                       # 文件名
    path: str                       # 相对路径
    code: str                       # 代码内容 (接口阶段为接口代码)
    feature_paths: List[str]        # 分配给此文件的特性路径
```

### 4.2 RPG (仓库功能图)

```python
class RPG:
    repo_name: str                   # 仓库名称
    repo_info: str                   # 仓库目的
    repo_node: Node                  # 根节点
    nodes: Dict[str, Node]           # 所有节点
    edges: List[Edge]                # 边列表
    data_flow: List[DataFlow]        # 数据流 (Stage 2 新增)
```

**Node**:
```python
class Node:
    id: str                          # 唯一标识
    name: str                        # 节点名称
    level: int                       # 层级 (1=顶层)
    meta: NodeMetaData               # 元数据
```

**Edge**:
```python
class Edge:
    source: str                      # 源节点 ID
    target: str                      # 目标节点 ID
    relation: str                    # 关系类型
```

**DataFlow** (Stage 2 生成):
```python
class DataFlow:
    source: str                      # 源子树
    target: str                      # 目标子树
    data_id: str                     # 数据标识符
    data_type: str                   # 数据类型
    transformation: str              # 转换描述
```

---

## 五、关键文件清单

| 文件路径 | 说明 |
|---------|------|
| `impl_builder.py` | 入口编排器，管理整个 impl_level 流程 |
| `file_design/designer.py` | FileDesigner，骨架设计编排器 |
| `file_design/agents/raw_skeleton_agent.py` | RawSkeletonAgent |
| `file_design/agents/group_skeleton_agent.py` | GroupSkeletonAgent |
| `file_design/prompts/raw_skeleton.py` | 原始骨架 Prompt |
| `file_design/prompts/group_skeleton.py` | 特性分组 Prompt |
| `func_design/designer.py` | FuncDesigner，功能设计编排器 |
| `func_design/agents/data_flow_agent.py` | DataFlowAgent |
| `func_design/agents/base_class_agent.py` | BaseClassAgent |
| `func_design/agents/interface_agent.py` | InterfaceAgent |
| `func_design/prompts/data_flow.py` | 数据流 Prompt |
| `func_design/prompts/base_class.py` | 基类设计 Prompt |
| `func_design/prompts/design.py` | 接口设计 Prompt |
| `plan_tasks/task_planner.py` | TaskPlanner + TaskPlannerAgent |
| `plan_tasks/task_batch.py` | TaskBatch 数据模型 |
| `plan_tasks/task_manager.py` | TaskManager (任务执行，非本阶段) |

---

## 六、Agent 模式总结

每个 Agent 都遵循统一的 **Design + Review** 模式：

```
┌─────────────────────────────────────────────────────────┐
│                    Agent 设计模式                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   Design Prompt ──▶ LLM ──▶ Tool (output_xxx)           │
│         │               │              │                 │
│         │               │              ▼                 │
│         │               │         Tool Result            │
│         │               │              │                 │
│         │               ▼              │                 │
│         │          Review Prompt ──▶ LLM                 │
│         │                              │                 │
│         │                              ▼                 │
│         │                         Review Result          │
│         │                              │                 │
│         │                              ▼                 │
│         │                         是否通过? ──No──▶ 重试  │
│         │                              │                 │
│         └──────────Yes────────────────┘                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**工具定义规范**:
- 每个工具都有明确的输入输出格式
- 使用 Pydantic 模型验证
- 包含示例和约束说明

---

## 七、RTL 改造要点

如果要改造为 RTL 代码实现，需要关注：

1. **Prompt 模板**: 将 Python 相关的描述改为 SystemVerilog
2. **数据流模型**: RTL 中是 `logic`, `signal`, `bus` 等类型
3. **接口设计**: 改为 module 定义、port 定义、interface 定义
4. **基类设计**: 改为 package、typedef、class 等结构
5. **任务批次**: RTL 实现任务可能需要考虑综合、仿真等不同目标
