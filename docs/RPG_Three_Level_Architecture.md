# RPG-ZeroRepo 三层级代码生成架构详解

本文档基于论文 [RPG: A Repository Planning Graph for Unified and Scalable Codebase Generation](docs/2509.16198.pdf) 的方法论，详细阐述 ZeroRepo 框架中提议级构建(Proposal-Level)、实现级构建(Implementation-Level)和基于图的代码生成(Graph-Guided Code Generation)三个层级的实现细节。

---

## 整体架构概览

```
用户需求 (User Query)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│  提议级构建 (Proposal-Level Construction)                     │
│  - Feature Selection (特征选择)                               │
│  - Feature Refactoring (特征重组织)                          │
│  输出: 功能图 (Functionality Graph)                          │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│  实现级构建 (Implementation-Level Construction)                │
│  - File Structure Design (文件结构设计)                      │
│  - Data Flow Design (数据流设计)                              │
│  - Base Class Design (基类设计)                               │
│  - Interface Design (接口设计)                                │
│  输出: 仓库规划图 (RPG)                                      │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│  基于图的代码生成 (Graph-Guided Code Generation)              │
│  - Topological Traversal (拓扑遍历)                          │
│  - TDD Code Generation (测试驱动开发)                        │
│  输出: 完整代码库                                            │
└───────────────────────────────────────────────────────────────┘
```

---

## 第一层级: 提议级构建 (Proposal-Level Construction)

### 核心目标
将用户的高级需求翻译为连贯的功能图(Functionality Graph)，包含两个关键步骤:
1. **特征选择**: 从大规模特征树中选择相关功能
2. **特征重组织**: 将选中的特征重组为模块化的子图

### 涉及文件

```
zerorepo/rpg_gen/prop_level/
├── prop_builder.py                    # 主协调器
├── select_feature/                     # 特征选择模块
│   ├── select_agent.py                # 特征选择Agent
│   ├── prompt.py                      # 选择提示词
│   └── faiss_db.py                    # FAISS向量数据库
└── refactor_feature/                   # 特征重组织模块
    ├── refactor_agent.py              # 特征重组织Agent
    └── prompt.py                       # 重组织提示词
```

### 1.1 特征选择 (Feature Selection)

#### 核心机制: Explore-Exploit 搜索策略

论文提出使用 **EpiCoder Feature Tree** (150万+软件功能的本体树) 作为知识库，通过探索-利用(Explore-Exploit)策略选择与用户需求对齐的功能子集。

**选择过程:**

```python
# zerorepo/rpg_gen/prop_level/select_feature/select_agent.py

class FeatureSelectAgent:
    def iterate_feature_tree(self, repo_data):
        """
        迭代式特征树生成:
        1. Exploitation: 检索与用户目标最对齐的top-k特征路径
        2. Exploration: 扩展到未访问的本体区域以确保多样性
        """
        # 两种策略的候选特征由LLM过滤并整合到子树中
```

**关键参数:**
- `explore_conditions`: [5, 8, 5, 4, 5] 控制探索广度
- `select_max_iterations`: 迭代次数
- `overlap_pct`: 特征重叠容忍度

#### FAISS 向量检索

```python
# zerorepo/rpg_gen/prop_level/select_feature/faiss_db.py

class FaissDocDB:
    """基于FAISS的向量数据库，用于高效特征检索"""

    def search(self, query_embedding, top_k):
        """语义相似性检索"""
```

每个特征节点被嵌入为向量，其完整层次路径作为元数据存储在向量数据库中。这保证了语义相似性和结构上下文的同时保留。

### 1.2 特征重组织 (Feature Refactoring)

#### 核心机制: 子树规划 + 特征分配

```python
# zerorepo/rpg_gen/prop_level/refactor_feature/refactor_agent.py

class FeatureRefactorAgent:
    def refactor_feature_tree(self, feature_tree, repo_data):
        """
        两步重组织流程:
        1. 子树规划: 确定子树的名称、数量和目的
        2. 特征分配: 将特征路径分配到对应子树
        """
```

**输出结构:**
```json
{
  "Component": [
    {
      "name": "data_loading",
      "purpose": "数据加载和处理",
      "refactored_subtree": {
        "file_operations": ["read_csv", "read_json", "read_excel"],
        "preprocessing": ["normalize", "standardize"]
      }
    }
  ]
}
```

---

## 第二层级: 实现级构建 (Implementation-Level Construction)

### 核心目标
基于功能图构建完整的仓库规划图(RPG)，包含:
1. 文件结构设计 (Skeleton Building)
2. 数据流设计 (Data Flow Encoding)
3. 基类设计 (Base Class Abstraction)
4. 接口设计 (Adaptive Interface Design)

### 涉及文件

```
zerorepo/rpg_gen/impl_level/
├── impl_builder.py                    # 主协调器
├── file_design/                        # 文件结构设计
│   ├── designer.py                    # 文件设计器
│   ├── agents/
│   │   ├── raw_skeleton_agent.py      # 原始骨架Agent
│   │   └── group_skeleton_agent.py    # 特征分组Agent
│   └── prompts/
│       ├── raw_skeleton.py             # 原始骨架提示词
│       └── group_skeleton.py          # 分组提示词
├── func_design/                        # 函数设计
│   ├── designer.py                    # 函数设计器
│   ├── agents/
│   │   ├── data_flow_agent.py         # 数据流Agent
│   │   ├── base_class_agent.py        # 基类Agent
│   │   └── interface_agent.py         # 接口Agent
│   └── prompts/
│       ├── data_flow.py               # 数据流提示词
│       ├── base_class.py              # 基类提示词
│       └── design.py                  # 接口设计提示词
└── plan_tasks/                         # 任务规划
    ├── task_planner.py                # 任务规划器
    ├── task_batch.py                   # 任务批次
    └── task_manager.py                 # 任务管理器
```

### 2.1 文件结构设计 (File Structure Design)

#### 两阶段设计流程

```python
# zerorepo/rpg_gen/impl_level/file_design/designer.py

class FileDesigner:
    def run(self, skeleton_result_path, agent_result_path):
        """
        阶段1: 生成原始高层布局 (Raw Skeleton)
        - 使用 RawSkeletonAgent 生成初步文件结构

        阶段2: 特征分组 (Feature Grouping)
        - 使用 GroupSkeletonAgent 将特征路径映射到文件
        """
```

**阶段1: 原始骨架生成**

```python
# zerorepo/rpg_gen/impl_level/file_design/agents/raw_skeleton_agent.py

class RawSkeletonAgent:
    """基于RPG生成仓库的原始文件结构"""

    def generate_raw_skeleton(self):
        """
        输出示例:
        {
          "data_loading": ["load_csv", "load_json", "preprocess"],
          "algorithms": ["kmeans", "svm", "decision_tree"],
          "evaluation": ["accuracy", "precision", "recall"]
        }
        """
```

**阶段2: 特征分组**

```python
# zerorepo/rpg_gen/impl_level/file_design/agents/group_skeleton_agent.py

class GroupSkeletonAgent:
    """将功能特征分组到具体文件"""

    def group_subtree_features(self, tree_root, subtree_name):
        """
        根据语义相关性将叶子特征聚类到文件:
        - 独立特征 → 独立函数
        - 相互依赖的特征 → 共享类的方法
        """
```

### 2.2 数据流设计 (Data Flow Encoding)

```python
# zerorepo/rpg_gen/impl_level/func_design/agents/data_flow_agent.py

class DataFlowAgent:
    """设计模块间和模块内的数据流边"""

    def generate_data_flow(self):
        """
        全局级别: 连接子图根节点的数据流边
        例如: data_loading → preprocessing → algorithms → evaluation

        局部级别: 文件间的依赖顺序
        """
```

**数据流编码类型:**
- **模块间流(Inter-module)**: 连接不同子模块的输入输出
- **模块内流(Intra-module)**: 同一模块内文件的执行顺序

### 2.3 基类设计 (Base Class Abstraction)

```python
# zerorepo/rpg_gen/impl_level/func_design/agents/base_class_agent.py

class BaseClassAgent:
    """抽象跨模块的通用接口模式"""

    def generate_base_classes(self):
        """
        例如: 将各种算法统一在 BaseEstimator 基类下
        确保预处理、评估模块的标准化交互

        class BaseEstimator:
            def fit(self, X, y): pass
            def predict(self, X): pass
        """
```

### 2.4 接口设计 (Interface Design)

```python
# zerorepo/rpg_gen/impl_level/func_design/agents/interface_agent.py

class InterfaceAgent:
    """为每个文件设计完整的接口"""

    def design_file_interface(self, file_node, tgt_subtree):
        """
        自适应接口映射:
        - 独立特征 → 独立函数
        - 相关特征 → 类的成员方法
        - 考虑已实现的文件作为上下文
        """
```

**拓扑排序处理:**

```python
# zerorepo/rpg_gen/impl_level/func_design/designer.py

class FuncDesigner:
    def _build_subtree_dependency_order(self, data_flow):
        """
        Kahn算法实现拓扑排序:
        1. 构建依赖图
        2. 计算入度
        3. 按依赖顺序处理子树
        """
```

---

## 第三层级: 基于图的代码生成 (Graph-Guided Code Generation)

### 核心目标
根据已构建的RPG，通过拓扑遍历生成完整代码库。

### 涉及文件

```
zerorepo/rpg_gen/base/
├── rpg/
│   ├── rpg.py                         # RPG核心类
│   ├── dep_graph.py                   # 依赖图
│   └── util.py                        # 工具函数
├── agent/
│   ├── agent.py                       # Agent基类
│   └── env.py                         # 环境定义
├── node/
│   ├── node.py                        # 节点定义
│   ├── skeleton.py                    # 仓库骨架
│   └── util.py                        # 节点工具
└── unit/
    ├── code_unit.py                   # 代码单元
    ├── replace_content.py             # 内容替换
    └── snippt_builder.py             # 代码片段构建
```

### 3.1 RPG 核心结构

```python
# zerorepo/rpg_gen/base/rpg/rpg.py

@dataclass
class Node:
    id: str
    name: str
    level: int                          # 层级 (repo=0, component=1, file=2, class/func=3+)
    node_type: NodeType                  # DIRECTORY, FILE, CLASS, FUNCTION, METHOD
    meta: NodeMetaData                   # 元数据 (路径、描述、内容)

class RPG:
    """Repository Planning Graph"""

    def add_node(self, node: Node):
        """添加节点"""

    def add_edge(self, parent: Node, child: Node):
        """添加边 (父子关系)"""

    def topological_sort(self):
        """拓扑排序确保依赖优先"""
```

### 3.2 节点类型

```python
# zerorepo/rpg_gen/base/rpg/util.py

class NodeType(Enum):
    DIRECTORY = "directory"              # 目录节点
    FILE = "file"                       # 文件节点
    CLASS = "class"                     # 类节点
    FUNCTION = "function"                # 函数节点
    METHOD = "method"                   # 方法节点
    FEATURE = "feature"                  # 功能节点
```

### 3.3 代码生成流程

```python
# zerorepo/rpg_gen/base/agent/agent.py

class BaseAgent:
    def run(self, task, max_steps=20):
        """
        Agent执行循环:
        1. LLM生成下一个动作
        2. 执行工具调用
        3. 环境反馈
        4. 迭代直到完成或达到最大步数
        """
```

**测试驱动开发 (TDD) 流程:**

```
┌─────────────────────────────────────────┐
│  遍历RPG拓扑顺序                         │
│  (确保依赖先实现)                        │
└─────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│  叶子节点 → 生成测试用例                  │
│  (从任务规范派生)                        │
└─────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│  实现函数/类                              │
│  (基于测试)                             │
└─────────────────────────────────────────┘
            │
            ▼
    ┌───────┴───────┐
    │  测试通过?    │
    └───────┬───────┘
       Yes │ No
    ┌──────┴──────┐
    ▼             ▼
┌───────┐   ┌────────────┐
│ 提交  │   │  调试修复   │
└───────┘   └────────────┘
```

### 3.4 RPG 引导的定位与编辑

```python
# 基于已构建的RPG进行精确定位和编辑

"""
当处理实现或调试请求时:
1. 在RPG中定位目标节点
2. 编辑关联代码
3. 验证修改
"""
```

---

## 完整流程示例

以生成一个机器学习仓库为例:

### Step 1: 提议级

**输入:** "生成一个机器学习仓库"

**特征选择:**
- 检索到: `data_processing/load_data`, `ml/classification`, `evaluation/metrics`
- 探索扩展: 添加 `visualization/plotting`, `preprocessing/feature_scaling`

**特征重组织:**
```json
{
  "Component": [
    {"name": "data_loading", "features": ["load_csv", "load_json", "preprocess"]},
    {"name": "models", "features": ["kmeans", "svm", "random_forest"]},
    {"name": "evaluation", "features": ["accuracy_score", "confusion_matrix"]}
  ]
}
```

### Step 2: 实现级

**文件结构:**
```
src/
├── data_loading/
│   ├── data_loader.py
│   └── preprocess.py
├── models/
│   ├── clustering.py
│   └── classification.py
└── evaluation/
    └── metrics.py
```

**数据流:**
```
data_loading → models → evaluation
```

**基类:**
```python
class BaseEstimator:
    def fit(self, X, y): pass
    def predict(self, X): pass
```

### Step 3: 代码生成

按拓扑顺序生成:
1. `data_loader.py` (被其他模块依赖)
2. `preprocess.py`
3. `clustering.py`, `classification.py` (继承BaseEstimator)
4. `metrics.py` (最终模块)

每个文件通过TDD验证后提交。

---

## 核心配置

```yaml
# configs/zerorepo_config.yaml

prop_level:
  feature_selection:
    max_iterations: 30
    explore_conditions: [5, 8, 5, 4, 5]
  refactoring:
    max_iterations: 20

impl_level:
  skeleton:
    max_steps: 20
  data_flow:
    max_steps: 10
  base_classes:
    max_steps: 10
  interfaces:
    max_steps: 10

code_generation:
  max_debug_iterations: 8
```

---

## 总结

RPG-ZeroRepo 的三层架构实现了:

1. **提议级**: 从150万级特征树中，通过Explore-Exploit策略选择与用户需求对齐的功能，并重组织为模块化结构

2. **实现级**:
   - 构建文件级骨架
   - 设计跨模块数据流
   - 抽象基类确保接口一致性
   - 自适应接口映射

3. **代码生成级**:
   - 基于RPG拓扑遍历
   - TDD驱动实现
   - 增量扩展保持稳定性

这种方法相比纯自然语言规划的优势在于:
- 结构化表示减少歧义
- 显式依赖关系确保一致性
- 持久化图结构支持长期规划
- 可扩展到大规模代码库生成
