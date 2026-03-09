### Phase 1. Spec Normalization & Constraint Grounding

#### 4.0 目标

把 spec 中的自然语言与表格信息，转换成统一内部表示。  
目标不是“生成代码”，而是把 spec 变成**一组可引用的工程事实**。

#### 4.1 输入

- 原始 markdown spec
- 用户提供的 repo blueprint
- 项目已有空仓库骨架

#### 4.2 输出

- `SpecFacts`
- `HardConstraints`
- `SoftPreferences`
- `OpenDecisions`
- `AcceptanceGates`

#### 4.3 为什么先做这一步

项目级 RTL spec 往往同时包含：

- 明确约束
- 默认约束
- 文本中提到但未结构化的信息
- 尚未锁死的行为选择

这些东西如果不先做 grounding，后面会造成同一条规则在不同阶段被不同 agent 解释成不同意思。

#### 4.4 关键任务

1. 提取固定事实：
   - top module
   - toolchain
   - language subset
   - reset policy
   - naming rules
   - build / run entry
2. 提取强约束：
   - 非目标项
   - AXI / protocol 限制
   - regmap reset / access / side effects
   - acceptance criteria
3. 提取软偏好：
   - 命名风格
   - 文件职责偏好
   - 代码组织偏好
4. 检测开放决策：
   - TX full 的处理策略
   - framing error 的处理策略
   - byte enable / misaligned 访问策略
5. 要求进入 Phase 1 前：
   - `OpenDecisions == []`

#### 4.5 阶段门禁

- 所有 must-have 字段均已抽取
- 所有开放决策已锁死
- 不存在互相冲突的约束

#### 4.6 输出数据结构

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

Priority = Literal["MUST", "SHOULD", "MAY"]

@dataclass
class HardConstraint:
    key: str
    value: str
    source_section: str

@dataclass
class SoftPreference:
    key: str
    value: str
    source_section: str

@dataclass
class OpenDecision:
    key: str
    options: list[str]
    source_section: str
    required_before_phase: int

@dataclass
class AcceptanceGate:
    gate_id: str
    gate_type: Literal["lint", "compile", "sim", "formal", "custom"]
    command: str
    pass_condition: str

@dataclass
class SpecFacts:
    project_name: str
    rtl_language: str
    toolchain: dict
    top_module: str
    repo_root: str
    hard_constraints: list[HardConstraint] = field(default_factory=list)
    soft_preferences: list[SoftPreference] = field(default_factory=list)
    open_decisions: list[OpenDecision] = field(default_factory=list)
    acceptance_gates: list[AcceptanceGate] = field(default_factory=list)
```

---
延申：


* `SpecFacts`：**项目事实底座**
* `HardConstraints`：**绝对不能违反的规则**
* `SoftPreferences`：**最好遵守、但必要时可让步的偏好**
* `OpenDecisions`：**现在还没定、必须补定的岔路口**
* `AcceptanceGates`：**最后拿什么判断阶段是否过关**

下面我分别展开讲。

---

# 1. `SpecFacts` 是什么？

## 它的本质

`SpecFacts` 是 **整个 spec 经过整理后的统一内部表示**。
它不是单独一种“规则类型”，而是一个 **总容器 / 总对象**，把后面几类东西都挂进去，供后续 Phase 引用。

也就是说，后面的：

* `HardConstraints`
* `SoftPreferences`
* `OpenDecisions`
* `AcceptanceGates`

都可以看成是 `SpecFacts` 里的不同子集合。

---

## 它解决什么问题？

后续 pipeline 里的各个 agent / phase 不应该反复去读原始 markdown，然后各自理解一遍。
否则同一句话可能被理解成不同意思。

所以 `SpecFacts` 的目标是：

> 把原始 spec 变成一个“统一真相源（single source of truth）”。

---

## 它一般包含什么？

比如你这个 RTL 项目里，`SpecFacts` 里至少会有：

* 项目名
* 顶层模块名
* 使用 Verilog 还是 SystemVerilog
* 工具链信息（iverilog / verilator / vcs 等）
* repo 根目录
* blueprint 提供的文件路径
* 解析出的模块列表
* 约束列表
* gate 列表

---

## 用你的场景举例

比如你的 UART 项目，`SpecFacts` 里会像这样：

* `project_name = "axi_uart"`
* `rtl_language = "SystemVerilog"`
* `top_module = "axi_uart_top"`
* `repo_root = "."`
* `toolchain = {"sim": "iverilog", "lint": "verilator --lint-only"}`
* `hard_constraints = [...]`
* `soft_preferences = [...]`
* `open_decisions = [...]`
* `acceptance_gates = [...]`

所以你可以理解为：

**`SpecFacts` 是总账本，其他四个是账本里的不同栏目。**

---

# 2. `HardConstraints` 是什么？

## 它的本质

这是 **必须满足、不能随意改写的硬约束**。

只要违反了硬约束，就说明生成结果和 spec 不一致。
不是“风格不好”，而是“做错了”。

---

## 它解决什么问题？

防止 agent 在后续实现阶段自由发挥过头。

因为 LLM 很容易在不确定时“脑补”，而项目级 RTL 最怕脑补。
所以要明确哪些东西是绝对不能动的。

---

## 它一般包含哪些内容？

在 RTL 项目里，典型硬约束包括：

### 1）功能硬约束

* top module 必须叫某个名字
* 必须支持哪些寄存器
* 必须实现哪些 REQ
* 哪些行为必须发生

### 2）协议硬约束

* AXI-Lite 只支持单拍
* 不支持 burst
* UART 帧格式固定
* ready/valid 规则不能改

### 3）时序/复位硬约束

* reset 是同步还是异步
* reset active high/low
* 配置何时生效
* 某状态位何时清零

### 4）工程硬约束

* 文件必须放在哪
* 必须通过哪些 gate
* 不允许引入哪些依赖
* 语言子集限制

### 5）非目标项

这个很重要。
“明确不做什么” 也属于硬约束。

比如：

* 不支持 parity
* 不支持 FIFO overflow interrupt
* 不支持 byte-enable

这些都应该算 `HardConstraints`。

---

## 例子

比如：

```python
HardConstraint(
    key="reset_policy",
    value="active-low synchronous reset",
    source_section="Interfaces & Contracts"
)
```

或者：

```python
HardConstraint(
    key="axi_lite_burst",
    value="not supported",
    source_section="Non-goals"
)
```

---

## 一句话理解

`HardConstraints` 回答的是：

> **哪些规则是实现时绝对不能违反的？**

---

# 3. `SoftPreferences` 是什么？

## 它的本质

这是 **推荐遵守的偏好**，但不是“违背了就一定错”。

如果硬约束决定“必须做什么”，
那么软偏好决定“最好怎么做”。

---

## 它解决什么问题？

同样一个 RTL 功能，可以有很多写法。
如果你不把偏好抽出来，agent 每次可能风格都不一样，导致：

* 仓库一致性差
* 后续修复难
* 代码风格飘
* 文件职责容易混乱

所以软偏好是为了让仓库生成更稳定、更一致。

---

## 它一般包含哪些内容？

### 1）命名风格

* 参数用全大写还是驼峰
* 状态机状态怎么命名
* 寄存器字段名风格
* module / signal 命名习惯

### 2）代码组织偏好

* combinational / sequential block 分开写
* 一个模块一个文件
* package 放哪
* testbench 放哪

### 3）实现风格偏好

* FSM 用 `typedef enum logic` 还是 `localparam`
* FIFO 尽量独立成 primitive
* helper function 尽量放 package
* CSR side-effect 集中在 regs block

---

## 它和硬约束的区别

比如：

* “top module 必须叫 `axi_uart_top`” → 硬约束
* “状态机最好使用 enum” → 软偏好

一个违反就错，一个违反只是“不优雅”或者“不一致”。

---

## 例子

```python
SoftPreference(
    key="fsm_style",
    value="prefer enum-based state encoding",
    source_section="Coding Style"
)
```

---

## 一句话理解

`SoftPreferences` 回答的是：

> **如果有多种实现方式，系统更倾向哪一种？**

---

# 4. `OpenDecisions` 是什么？

## 它的本质

这是 **spec 里还没有最终锁死的行为分叉点**。

也就是：文档中提到了问题，但没有明确选哪一个答案。

---

## 它为什么特别重要？

这是 Phase 0 里最关键的一类输出之一。
因为如果不先把这些“开放决策”找出来，后面 agent 会自己选一种实现，然后：

* codegen 选 A
* test 生成选 B
* repair 又假设 C

最后系统会在不同阶段互相打架。

---

## 它一般长什么样？

通常是这种情况：

* 文档提到两个或多个可能行为
* 文档自己说“待定”“二选一”“可选”
* 文本描述有歧义，无法唯一推出实现
* 需求之间存在潜在冲突，需要人为定夺

---

## 典型例子

你前面自己举的这些就非常典型：

### 1）TX FIFO 满时怎么办？

* backpressure
* 返回错误
* 丢弃写入

### 2）framing error 时怎么处理？

* 丢弃该字节
* 保留字节并置错误位

### 3）不对齐访问怎么处理？

* ignore
* error response
* undefined / not supported

这些都不应该直接变成 `HardConstraint`，因为它们还没定。
它们要先进入 `OpenDecisions`，等你或上层系统锁死后，再转成 `HardConstraint`。

---

## 为什么要求进入 Phase 1 前 `OpenDecisions == []`

因为 Phase 1 开始就要建模块图和接口契约了。
如果这时候还没定：

* 错误处理策略
* side effect 语义
* 访问非法行为

那么模块边界、状态机逻辑、testbench、甚至 regmap 设计都会漂。

---

## 例子

```python
OpenDecision(
    key="tx_fifo_full_policy",
    options=["backpressure", "slverr", "drop_write"],
    source_section="Interfaces & Contracts",
    required_before_phase=1
)
```

---

## 一句话理解

`OpenDecisions` 回答的是：

> **哪些关键行为现在还没定，继续往后做会导致实现漂移？**

---

# 5. `AcceptanceGates` 是什么？

## 它的本质

这是 **阶段性验收门禁**，也就是“如何判断这一阶段的产物算过关”。

它不是描述设计本身，而是描述 **验证与验收标准**。

---

## 它解决什么问题？

防止 pipeline 只会“生成代码”，却没有明确的停机判断。

没有 gate，agent 可能会一直修、一直补，但不知道什么时候算完成。
有了 gate，系统就知道：

* 什么命令要跑
* 什么结果算通过
* 哪个阶段没过该回滚/修复

---

## 它一般包含什么？

### 1）lint gate

例如：

* `verilator --lint-only ...`
* 无 error

### 2）compile gate

例如：

* `iverilog -g2012 ...`
* 编译成功，返回码 0

### 3）simulation gate

例如：

* 运行 testbench
* stdout 出现 `PASS`
* exit code == 0

### 4）formal gate

如果后面做形式验证，也可以加

### 5）custom gate

例如：

* 检查文件是否存在
* 检查 regmap 是否完整
* 检查某些 assertion 是否覆盖

---

## 它和 Acceptance Criteria 的关系

文档中的自然语言 “Acceptance Criteria” 是人类可读的要求；
`AcceptanceGates` 是把这些要求转成 **可执行 gate**。

比如：

自然语言：

* “lint 无 error”
* “basic loopback sim pass”

转成结构化后就是：

```python
AcceptanceGate(
    gate_id="gate_lint",
    gate_type="lint",
    command="verilator --lint-only rtl/**/*.sv",
    pass_condition="exit_code == 0"
)
```

```python
AcceptanceGate(
    gate_id="gate_loopback_sim",
    gate_type="sim",
    command="make sim TEST=loopback_basic",
    pass_condition="stdout contains PASS and exit_code == 0"
)
```

---

## 一句话理解

`AcceptanceGates` 回答的是：

> **系统要用什么可执行方式判断：当前阶段已经达标，可以继续往下？**

---

# 6. 这 5 个输出之间是什么关系？

这是最重要的一点。
它们不是并列无关，而是有层次关系。

---

## 关系图

### `SpecFacts`

是总对象，里面挂着：

* `HardConstraints`
* `SoftPreferences`
* `OpenDecisions`
* `AcceptanceGates`

---

## 它们各自分工

### `SpecFacts`

负责：

* 统一存储
* 统一引用
* 给后续 phase 当真相源

### `HardConstraints`

负责：

* 限制不能做错的边界

### `SoftPreferences`

负责：

* 在合法空间里选更符合项目风格的实现

### `OpenDecisions`

负责：

* 标记当前不能继续自动化推进的分叉点

### `AcceptanceGates`

负责：

* 判断某阶段是否已完成、是否可进入下一阶段

---

# 7. 你可以把它们想成一个工程控制系统

更直觉一点，可以这样理解：

* `SpecFacts`：项目总档案
* `HardConstraints`：红线
* `SoftPreferences`：推荐路线
* `OpenDecisions`：路口待决策事项
* `AcceptanceGates`：检查站

这个比喻其实很贴合你后面的 agent pipeline。

---

# 8. 在你的 pipeline 里，它们后面分别怎么用？

这部分你后续实现时会特别有用。

### 在 Phase 2（模块图构建）里

主要用：

* `SpecFacts`
* `HardConstraints`
* 已清零后的 `OpenDecisions`

因为建模块图时，最重要的是不能越红线。

---

### 在 Phase 3（任务编排 / codegen）里

主要用：

* `SpecFacts`
* `HardConstraints`
* `SoftPreferences`

因为生成代码时不仅要合法，还要尽量风格一致。

---

### 在 Phase 4（验证 / 修复）里

主要用：

* `AcceptanceGates`
* `HardConstraints`

因为修复时的目标不是“看起来对”，而是“过 gate 且不违反约束”。

---

# 9. 我建议你实现时的小调整

你现在这个设计是对的，但如果你真要一步一步做，我建议你在工程上这样理解：

### `HardConstraints / SoftPreferences / OpenDecisions / AcceptanceGates`

都作为独立列表存在

### `SpecFacts`

除了挂这些列表外，再多挂两类东西：

* `project_facts`：项目基础事实
* `repo_facts`：目录、文件、模块初始蓝图

不然 `SpecFacts` 会有点像“只有元信息的空壳”。

比如你可以后面扩展成：

```python
@dataclass
class ProjectFacts:
    project_name: str
    rtl_language: str
    top_module: str
    repo_root: str

@dataclass
class RepoFacts:
    blueprint_files: list[str]
    expected_modules: list[str]
    build_entry: str
    sim_entry: str
```

然后 `SpecFacts` 里挂这两个对象，会更清晰。

---

完成：
已按你这版 `phase1_plan.md` 完成 Phase1 强化改造，核心目标（Agent-only、完备性门禁、决策自动闭环、Phase2 阻塞）都已落地。

**已实现内容**
- 数据模型扩展与兼容序列化：
  - 新增 `SoftPreference`、`OpenDecision`，扩展 `AcceptanceGate(gate_id, gate_type)`，扩展 `SpecFacts` 新字段（`repo_root/soft_preferences/open_decision_objects/phase1_ready_for_phase2/blocking_issues/coverage_report`）。
  - 文件：[spec_models.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/spec_models.py)
- 门禁语义升级：
  - `phase1_complete` 与 `phase1_ready_for_phase2` 分离。
  - 未决 blocking decision、覆盖缺口、冲突会阻塞进入 Phase2。
  - 文件：[spec_models.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/spec_models.py)
- Agent-only 严格链路：
  - strict 模式默认生效，失败不回退 regex（除非显式放开）。
  - 文件：[designer.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/designer.py), [main.py](/home/mokita/RPG-ZeroRepo/main.py)
- OpenDecision 自动决策（配置驱动）：
  - 新增决策策略模块与 `decision_defaults` 配置；自动 resolved，并可转写为硬约束。
  - 文件：[decision_policy.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/decision_policy.py), [config.yaml](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/config.yaml)
- Prompt/Review 强化：
  - 强制覆盖 REQ/TEST、source_section 追踪、结构化 `open_decision_objects`、增强审查项。
  - 文件：[prompts/__init__.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/prompts/__init__.py)
- Agent 终止逻辑修复：
  - `output_spec_facts` 成功且写入 env 后即终止，避免无效多步循环。
  - 文件：[spec_facts_agent.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/phase1_spec_parsing/spec_facts_agent.py)
- Phase2 前置阻塞：
  - `phase1_ready_for_phase2=false` 时直接阻止 Phase2。
  - 文件：[rtl_impl_builder.py](/home/mokita/RPG-ZeroRepo/zerorepo/rtl_impl/rtl_impl_builder.py)

**本地校验**
- 已通过语法编译检查：`python -m compileall zerorepo/rtl_impl/phase1_spec_parsing zerorepo/rtl_impl/rtl_impl_builder.py`

**你现在可以直接验收**
1. 运行：`bash scripts/run_main.sh`
2. 检查输出：[spec_facts.json](/home/mokita/RPG-ZeroRepo/rtl_outputs/spec_content/.zerorepo/spec_facts.json)
3. 重点看：
- `functional_requirements`、`tests` 是否覆盖 `REQ-*`/`TEST-*`
- `open_decision_objects` 是否已 resolved，`open_decisions` 是否只剩 unresolved 摘要
- `coverage_report` 与 `blocking_issues`
- `phase1_ready_for_phase2` 是否为 `true`

如果你愿意，我下一步可以直接帮你跑一次你当前 `spec_content` 的端到端验收，并逐项对照 `phase1_plan.md` 出一份差距清单。