# RTL 实现级 Pipeline（4 阶段 MVP 版）

> 面向：项目级 RTL Spec2Repo
>
> 用途：
> 1. 给人看：说明为什么这样拆阶段、每阶段解决什么问题。
> 2. 给 Codex 看：作为直接可实现的任务文档，指导代码生成与工程落地。
>
> 设计原则：**先做最关键、最能跑通的一版**。不追求一开始就把所有图结构、优化器、增量演化、复杂验证都做全，而是优先保证：
> - 能从 spec 稳定抽取硬约束
> - 能形成模块级实现边界
> - 能按依赖顺序分批生成代码
> - 能通过门禁做局部修复

---

## 0. 为什么要压缩成 4 个阶段

之前那种 8 阶段拆法，更像“完整研究版架构设计”，适合后续扩展，但不适合第一版实现。  
对于你现在的目标——**先把一个项目级 RTL spec2repo agent 跑通**——真正关键的只有 4 件事：

1. **把 spec 里的硬约束锁死**，避免 agent 自由发挥。
2. **把 RTL 的模块边界和依赖关系定下来**，避免生成时结构漂移。
3. **把实现任务拆成可执行的 DAG**，避免一次性生成整个 repo 失控。
4. **把验证和修复做成闭环**，避免写完才发现全仓库崩掉。

所以第一版 pipeline 只保留下面 4 个阶段：

```text
Phase 1  SpecFacts & Contract Grounding
Phase 2  Module Graph Construction
Phase 3  Task DAG Planning & Staged Code Generation
Phase 4  Gate-Driven Verification & Local Repair
```

这 4 个阶段已经足够支撑一个可运行的 MVP。

---

## 1. 这条 4 阶段 pipeline 解决什么问题

### 1.1 适用前提

默认输入 spec 已经像你当前的模板这样，至少包含：

- Meta / toolchain / coding style
- Goals / Non-goals
- System Context
- Interfaces & Contracts
- Parameters
- Functional Requirements
- Register Map / CSR
- Timing & Microarchitecture
- Repository Blueprint
- Verification Plan
- Build & Run
- Acceptance Criteria
- Implementation Nodes（可选但强烈建议）

这意味着：

- **文件结构已经基本给定**
- **不需要再做文件结构设计**
- pipeline 的重点变成：**实现级约束落地、模块级规划、任务编排、门禁修复**

### 1.2 为什么这比 ZeroRepo 原始实现级更适合 RTL

ZeroRepo 的实现级步骤偏向 SWE：

- file structure design
- data flow design
- base class abstraction
- interface design

这套抽象面向的是：

- file
- class
- function
- method
- API

但 RTL 项目的核心对象是：

- module
- port
- parameter
- package
- signal / bus
- instance hierarchy
- FSM / datapath
- testbench / assertions / scripts

所以 RTL 第一版实现最该保留的，不是 SWE 的“文件/类/函数”视角，而是：

- **契约视角**：端口、参数、协议、复位、时序语义
- **结构视角**：模块依赖、实例层级、文件归属
- **执行视角**：分阶段任务、门禁、局部修复

---

## 2. 总体设计概览

```text
RTL Spec
  │
  ▼
Phase 1: SpecFacts & Contract Grounding
  │
  ▼
Phase 2: Module Graph Construction
  │
  ▼
Phase 3: Task DAG Planning & Staged Code Generation
  │
  ▼
Phase 4: Gate-Driven Verification & Local Repair
  │
  ▼
Generated RTL Repo
```

每个阶段都只做一件最关键的事：

- **Phase 1**：把 spec 变成不会漂移的事实表。
- **Phase 2**：把事实表变成模块级图表示。
- **Phase 3**：把模块图变成实现任务和代码生成顺序。
- **Phase 4**：把生成结果放到门禁下验证，不过就局部修复。

---

## 3. Phase 1：SpecFacts & Contract Grounding

### 3.1 目标

把 spec 中的自然语言、表格、约束项，统一整理成一组**可程序引用的硬事实**。  
这一步不生成代码，只解决一个问题：

> 后续所有 agent 和代码生成步骤，引用的是同一套约束，而不是各自从原始 markdown 里自由理解。

### 3.2 输入

- 原始 spec markdown
- 可选：仓库蓝图中的文件路径列表

### 3.3 输出

- `SpecFacts`
- `HardConstraints`
- `OpenDecisions`
- `AcceptanceGates`

### 3.4 这一步必须抽出的信息

#### A. 工程固定事实

例如：

- 项目名
- top module 名称
- RTL 语言版本
- toolchain
- build / run 入口
- 时钟 / 复位规则
- repo 中各文件的职责

#### B. 模块与接口硬约束

例如：

- 顶层端口名、方向、位宽
- 参数名与默认值
- 协议限制
- CSR 地址与字段规则
- 时序要求
- 状态机必须满足的语义

#### C. 非目标项 / 不可做项

例如：

- 不支持 misaligned access
- 不实现 parity
- 不实现复杂 FIFO 深度动态配置

#### D. 开放决策点

这是第一版非常关键的一类信息。任何会影响行为分叉但在 spec 中没有唯一结论的内容，都要单独列出来，例如：

- FIFO 满时到底是 backpressure 还是 error
- framing error 到底丢弃还是保留数据
- 波特率更新何时生效

这些内容在进入 Phase 2 之前必须被锁死。

### 3.5 阶段门禁

进入 Phase 2 前必须满足：

- 所有 must-have 字段均已抽取
- `OpenDecisions` 为空
- 不存在互相冲突的约束

### 3.6 最小数据结构

```python
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class HardConstraint:
    key: str
    value: str
    source_section: str

@dataclass
class AcceptanceGate:
    name: str
    command: str
    pass_rule: str

@dataclass
class SpecFacts:
    project_name: str
    top_module: str
    rtl_language: str
    toolchain: List[str]
    files: Dict[str, str]              # filepath -> responsibility
    constraints: List[HardConstraint] = field(default_factory=list)
    acceptance_gates: List[AcceptanceGate] = field(default_factory=list)
    open_decisions: List[str] = field(default_factory=list)
```

### 3.7 实现要求

在这一阶段需要生成：

- `spec_parser.py`
- `spec_models.py`
- `constraint_normalizer.py`

最低要求：

- 能把 markdown spec 解析成 `SpecFacts`
- 能检测缺失字段
- 能检测开放决策
- 能把 `Build & Run / Acceptance Criteria` 解析成门禁列表

---

## 4. Phase 2：Module Graph Construction

### 4.1 目标

基于 `SpecFacts` 构建 RTL 的最小实现级图表示。  
第一版不要追求复杂多图系统，只需要建成一张**模块图**，但这张图必须同时能回答 4 个问题：

1. 有哪些模块？
2. 每个模块归属哪个文件？
3. 谁依赖谁、谁实例化谁？
4. 每个模块的契约是什么？

### 4.2 输入

- `SpecFacts`
- spec 中的 `System Context`
- spec 中的 `Interfaces & Contracts`
- spec 中的 `Timing & Microarchitecture`
- spec 中的 `Repository Blueprint`

### 4.3 输出

- `ModuleGraph`
- `CompileOrder`

### 4.4 这一步要建的核心内容

#### A. 模块节点（Module Nodes）

每个模块节点至少要包含：

- 模块名
- 文件路径
- 角色类型
- 端口列表
- 参数列表
- 时钟/复位依赖
- 简短职责描述

角色类型可以先用最小集合：

- `top`
- `control`
- `datapath`
- `primitive`
- `package`
- `tb`

#### B. 依赖边（Dependency Edges）

第一版只保留最关键三类边：

- `instantiates`
- `uses_package`
- `drives_or_consumes`

说明：

- `instantiates`：A 模块例化 B 模块
- `uses_package`：A 依赖 package / include
- `drives_or_consumes`：A 和 B 之间存在关键功能数据或控制关系

#### C. 编译顺序（Compile Order）

第一版不需要复杂调度器，直接根据依赖图做拓扑排序即可。

通常顺序应为：

1. package / shared defs
2. primitive / leaf modules
3. middle modules
4. top module
5. tb / scripts

### 4.5 为什么 Phase 2 是最核心的一步

因为 RTL 生成最容易失败的根因之一，是模块边界不稳。  
只要模块图没定下来，后面的代码生成就会在：

- 接口宽度
- 时序责任
- 信号归属
- 文件内容分配

这些地方不断漂移。

所以第一版最重要的不是“让模型更聪明”，而是**让生成前的结构边界更稳定**。

### 4.6 最小数据结构

```python
from dataclasses import dataclass, field
from typing import List, Literal

RoleType = Literal["top", "control", "datapath", "primitive", "package", "tb"]
EdgeType = Literal["instantiates", "uses_package", "drives_or_consumes"]

@dataclass
class PortSpec:
    name: str
    direction: str
    width_expr: str
    desc: str = ""

@dataclass
class ParamSpec:
    name: str
    default: str
    desc: str = ""

@dataclass
class ModuleNode:
    name: str
    file_path: str
    role: RoleType
    responsibility: str
    ports: List[PortSpec] = field(default_factory=list)
    params: List[ParamSpec] = field(default_factory=list)
    clocks_resets: List[str] = field(default_factory=list)

@dataclass
class ModuleEdge:
    src: str
    dst: str
    edge_type: EdgeType
    desc: str = ""

@dataclass
class ModuleGraph:
    nodes: List[ModuleNode]
    edges: List[ModuleEdge]
```

### 4.7  实现要求

在这一阶段需要生成：

- `module_extractor.py`
- `module_graph.py`
- `topo_sort.py`

最低要求：

- 能从 spec 中抽出模块列表
- 能绑定模块到文件
- 能构建最小依赖图
- 能输出 compile order

---

## 5. Phase 3：Task DAG Planning & Staged Code Generation

### 5.1 目标

把 `ModuleGraph` 变成真正可执行的实现任务，并按顺序驱动代码生成。  
这一步要解决的是：

> 不要一次性生成整个 repo，而是按模块和门禁拆成小步推进。

### 5.2 输入

- `SpecFacts`
- `ModuleGraph`
- `CompileOrder`
- `Implementation Nodes`（如果 spec 提供）

### 5.3 输出

- `TaskDAG`
- 分阶段生成的代码产物

### 5.4 任务拆分原则

第一版任务不要拆得太细，建议按“可单独验证的模块/文件单元”拆。

一个任务至少应包含：

- 任务 ID
- 目标文件
- 目标模块
- 依赖任务列表
- 输入上下文
- 通过标准

### 5.5 推荐任务粒度

建议第一版按下面顺序：

1. `pkg/shared defs`
2. `primitive modules`
3. `uart_tx / uart_rx / baud_gen` 这类叶子行为模块
4. `csr / regs / control` 模块
5. `top integration`
6. `tb / scripts / Makefile`

### 5.6 每个任务给 LLM / Codex 的上下文

不要把全量 spec 每次都塞进去。  
每个任务只给：

- 全局硬约束摘要
- 当前模块契约
- 当前模块相邻依赖节点
- 当前目标文件职责
- 当前 gate 要求

### 5.7 最小任务数据结构

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class TaskSpec:
    task_id: str
    target_file: str
    target_module: str
    depends_on: List[str]
    context_keys: List[str]
    gate_names: List[str]

@dataclass
class TaskDAG:
    tasks: List[TaskSpec]
```

### 5.8 代码生成最小流程

```python
def run_task_codegen(task: TaskSpec, spec_facts, module_graph):
    context = build_codegen_context(task, spec_facts, module_graph)
    code = llm_generate_code(context)
    write_code_to_repo(task.target_file, code)
    return code
```

### 5.9 实现要求

在这一阶段需要生成：

- `task_planner.py`
- `context_builder.py`
- `codegen_driver.py`
- `repo_writer.py`

最低要求：

- 能基于 `CompileOrder` 生成任务列表
- 能为每个任务裁剪上下文
- 能把生成代码写入目标仓库
- 能分批推进，不一次性改完整仓库

---

## 6. Phase 4：Gate-Driven Verification & Local Repair

### 6.1 目标

对每个生成任务或任务批次执行门禁；失败时只对局部进行修复。  
这一阶段是第一版能否真正跑通的关键。

### 6.2 输入

- 当前 repo 状态
- 当前任务或任务批次
- `AcceptanceGates`
- 本轮生成日志

### 6.3 输出

- gate 执行结果
- repair prompt / repair context
- 修复后的代码

### 6.4 推荐门禁顺序

第一版只保留最关键的 4 类：

1. **syntax / lint**
2. **compile / elaboration**
3. **directed simulation**
4. **top-level acceptance check**

### 6.5 局部修复原则

修复时不要把整个 spec 和整个 repo 一次性送回模型。  
只回灌：

- 当前失败任务的模块契约
- 当前失败的 gate 命令与日志
- 当前模块相邻依赖摘要
- 当前文件现有代码

### 6.6 最小修复流程

```python
def run_gate_and_repair(task: TaskSpec, repo_path: str):
    gate_results = run_gates(task, repo_path)
    if all(g.passed for g in gate_results):
        return True

    repair_context = build_repair_context(task, gate_results, repo_path)
    patched_code = llm_repair_code(repair_context)
    apply_patch(task.target_file, patched_code)

    gate_results = run_gates(task, repo_path)
    return all(g.passed for g in gate_results)
```

### 6.7 Gate 结果数据结构

```python
from dataclasses import dataclass

@dataclass
class GateResult:
    gate_name: str
    command: str
    passed: bool
    log_path: str
    summary: str
```

### 6.8 实现要求

在这一阶段需要生成：

- `gate_runner.py`
- `repair_context_builder.py`
- `repair_driver.py`
- `patch_applier.py`

最低要求：

- 能执行 lint / compile / sim 命令
- 能保存日志
- 能基于失败日志构造 repair context
- 能只修当前任务影响的代码

---

## 7. 四阶段之间的接口关系

### 7.1 数据流转

```text
Phase 1 output: SpecFacts
    ↓
Phase 2 output: ModuleGraph + CompileOrder
    ↓
Phase 3 output: TaskDAG + generated repo files
    ↓
Phase 4 output: verified / repaired repo state
```

### 7.2 最小 orchestrator

```python
def run_pipeline(spec_path: str, repo_root: str):
    spec_facts = parse_and_normalize_spec(spec_path)
    assert not spec_facts.open_decisions

    module_graph = build_module_graph(spec_facts)
    compile_order = topo_sort_modules(module_graph)

    task_dag = plan_tasks(spec_facts, module_graph, compile_order)

    for task in task_dag.tasks:
        run_task_codegen(task, spec_facts, module_graph)
        ok = run_gate_and_repair(task, repo_root)
        if not ok:
            raise RuntimeError(f"Task failed after repair: {task.task_id}")

    return True
```

---

## 8. 第一版不要做什么

为了保证 MVP 尽快跑通，下面这些内容建议先不要做：

- 不做复杂多层图数据库
- 不做 proposal-level feature tree
- 不做增量图演化
- 不做复杂 agent 群体协作
- 不做太细粒度的信号级图遍历
- 不做全仓库统一大修复器
- 不做过重的 formal / coverage 自动闭环

这些都可以作为第二版、第三版逐步增强的内容。

---

## 10. 给 ai的直接实现指令

下面这段文字可以直接作为 ai 的任务描述输入。

---

### Codex Task Prompt

实现一个 **RTL Spec2Repo MVP pipeline**，只做 4 个阶段：

1. `SpecFacts & Contract Grounding`
2. `Module Graph Construction`
3. `Task DAG Planning & Staged Code Generation`
4. `Gate-Driven Verification & Local Repair`

要求如下：

- 输入是一份 markdown 格式的 RTL 项目级 spec。
- spec 已经包含 repo blueprint，因此**不要实现文件结构设计器**。
- 先实现最小可运行版本，不要引入数据库、复杂多 agent、增量演化。
- 重点实现：
  - 解析 spec 为 `SpecFacts`
  - 构建 `ModuleGraph`
  - 生成 `CompileOrder`
  - 规划 `TaskDAG`
  - 按任务逐个生成代码
  - 执行 gate
  - 基于失败日志做局部 repair
- 数据结构使用本文件中定义的 dataclass 草案，可按需要扩展。
- 代码目录结构按本文档第 9 节实现。
- `main.py` 需要提供一个从 spec path 启动全流程的 CLI 入口。
- 第一版只要求支持小型 RTL 项目（例如 5~15 个文件）。
- 所有模块都必须带清晰注释和类型标注。
- 先保证可运行和结构清晰，不要过早优化。

---

## 11. 最终结论

这份 4 阶段设计的核心思想可以浓缩成一句话：

> **先把 spec 锁成硬事实，再把事实落成模块图，再把模块图变成任务顺序，最后用门禁驱动局部修复。**

这比一开始就做复杂 8 阶段系统更适合你当前的目标，因为它优先保证的是：

- 结构不漂
- 接口不乱
- 生成可分步推进
- 修复可局部收敛

如果后面第一版效果不错，再往上叠加：

- 更细的 timing / transaction graph
- 更强的 verification coverage binding
- 现有 repo 反向编码为 RPG
- 更复杂的 repair planner

就会自然很多。
