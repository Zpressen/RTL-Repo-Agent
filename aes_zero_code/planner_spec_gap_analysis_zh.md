# Planner 提炼信息与原始 Spec 的差异分析

日期：2026-03-30

本文用于分析以下三类信息源对代码生成的影响：

- 原始 spec：
  [aes_unified_functional_spec.md](/home/mokita/RPG-ZeroRepo/rtl_dataset/ase_cipher/aes_unified_functional_spec.md)
- Stage 1 片段化结果：
  [stage1_fragments json](/home/mokita/RPG-ZeroRepo/rtl_outputs/aes_unified_functional_spec/.zerorepo/module_planner/outputs/stage1_fragments/aes_unified_functional_spec.json)
- Stage 2 RFU 抽象结果：
  [stage2_rfu json](/home/mokita/RPG-ZeroRepo/rtl_outputs/aes_unified_functional_spec/.zerorepo/module_planner/outputs/stage2_rfu/aes_unified_functional_spec.json)

## 一句话结论

第一次没有生成通过仿真的代码，不是单一原因，而是三类原因叠加：

1. 原始 spec 本身缺少“可直接对拍”的精确 RTL 时序语义。
2. Stage 2 RFU 进一步把少量时序线索抽象成了高层职责，丢掉了落地实现所需的关键细节。
3. 原始 spec 中有一部分描述与 RealBench 参考实现存在冲突，导致即使忠实实现 spec，也不一定能通过该基准。

## 原始 spec 提供了什么

原始 spec 对“算法层”和“结构层”描述较完整，足以支撑“功能等价的 AES RTL”实现，主要包括：

- 顶层接口名和位宽。
- 状态矩阵是 4x4、按 column-major 映射。
- `SubBytes/ShiftRows/MixColumns/AddRoundKey` 的数学和数据流描述。
- 16 个 S-box、每拍一轮、最终轮跳过 MixColumns。
- `dcnt` 初值 0xB。
- `aes_key_expand_128`、`aes_sbox`、`aes_rcon` 的接口和基本原理。
- `aes_rcon` 的序列值、计数规则、`kld=1` 时输出 0x01000000。

这些信息足以生成“算法正确”的实现，但还不足以唯一确定“与参考 RTL 每拍完全一致”的实现。

## Stage 1 相比原始 spec 的特点

Stage 1 基本是对原始 spec 的结构化切片，保真度较高。

保留下来的关键内容包括：

- 顶层接口表、寄存器表、运算原理、实现细节。
- `aes_key_expand_128` 的 key load、SubWord、Rcon、输出顺序说明。
- `aes_sbox` 的接口、查表实现思路、corner cases。
- `aes_rcon` 的接口、序列、corner cases、输出格式。

因此，如果只看“信息是否还在”，Stage 1 的问题并不大。它的主要问题不是“丢了很多内容”，而是“保留下来的内容依然不够精确到唯一 RTL 实现”。

## Stage 2 相比 Stage 1 的信息损失

Stage 2 的 RFU 把文档压成了职责边界和实现角色，这对规划很有帮助，但对精确代码生成不够。

丢失或弱化最明显的信息包括：

1. 时序关系被职责描述替代了。
   例如 Stage 2 会说“控制 FSM 负责 done 与 dcnt”，但不会给出 `done <= !(|dcnt[3:1]) & dcnt[0] & !ld` 这种真正能过对拍的表达式。

2. 数据通路更新方式被抽象了。
   Stage 2 只说“SubBytes/ShiftRows/MixColumns/AddRoundKey”，不会告诉生成器：
   顶层参考实现其实是“每拍都寄存 text_out 最终轮表达式”，而不是在一个 `FINAL_ROUND` 状态集中写出。

3. key expansion 的逐字更新语义被抽象掉了。
   Stage 2 会说“First word/Second word/Third word/Fourth word 依次 XOR 生成”，但不会保留参考 RTL 那种依赖旧值和非阻塞赋值语义的具体寄存器表达式。

4. reset 和控制极性没有形成硬约束。
   Stage 2 提到了 `rst`、`kld`、`ld`，但没有把“顶层参考实现采用 `if (!rst)`”这种对仿真结果至关重要的语义保存成 machine-actionable 约束。

5. “算法步骤”与“参考时序实现”没有区分。
   Stage 2 默认把“状态机图 + 算法步骤”当作落地实现依据，但参考实现本质上是一个拍级数据路径，不是文档图中那套显式 FSM 编码。

## 第一次失败到底缺了哪些信息

严格说，第一次失败不是单纯“缺一点信号定义”，而是缺少以下几类“不可省略的实现级信息”：

### 1. 缺少可执行的 reset 语义

原始 spec 只说：

- `rst` 是 reset signal
- “initial reset state”
- “reset returns controller to IDLE state”

但没有明确：

- reset 高有效还是低有效
- reset 作用到哪些寄存器
- reset 后是清空数据路径，还是只控制计数器/输出
- reset 对 `done/text_out/ld_r/saxx` 的逐拍行为

这直接导致生成器容易采用“常规高有效同步复位 + 全局清零”的默认写法，而不是 RealBench 参考的低有效同步控制语义。

### 2. 缺少 `done` 的精确拍级定义

spec 和 Stage 1/2 都只给出自然语言：

- encryption complete
- generate completion signal
- done asserted after final round

但对拍真正需要的是：

- `done` 在哪一拍拉高
- 拉高持续多久
- 是否依赖 `ld`
- 是否从 `dcnt` 组合导出

如果没有这类信息，生成器很自然会写成“进入 DONE 状态时拉高一拍”，这在功能层面合理，但在参考对拍里是错的。

### 3. 缺少顶层控制实现的“选型约束”

spec 给了一个五态图：

- `IDLE`
- `INIT_ROUND`
- `ROUND_OP`
- `FINAL_ROUND`
- `DONE`

这会强烈诱导生成器实现显式 FSM。

但 RealBench 参考并没有按这个五态 FSM 直接编码，而是：

- `ld` 触发装载
- `ld_r` 延后一拍完成初始轮密钥加
- `dcnt` 自减控制轮次
- `text_out` 连续按最终轮表达式寄存

也就是说，文档里“状态图”更像行为解释图，不是唯一的 RTL 实现模板。如果 planner 没把“这只是说明图，不是必须照抄的状态编码”标出来，生成器就会走偏。

### 4. 缺少 key expansion 的精确寄存器更新语义

spec 提供了数学算法和自然语言顺序：

- First word
- Second word
- Third word
- Fourth word

但没有明确：

- 这些“current round first word / first two words / first three words”在 RTL 里是组合新值还是旧寄存器值
- 是否依赖非阻塞赋值读取旧值
- `subword` 的字节重排到底如何接线到 `w[3]`

这类信息对“算法等价”实现不是必须的，但对“逐拍对拍一致”是必须的。

### 5. 缺少 `text_out` 的具体更新模式

spec 中“Output Generation”只说最终轮后组织输出并产生完成信号。
它没有明确说明参考 RTL 其实是：

- 每个时钟都更新 `text_out`
- 更新表达式始终采用 `sa_sr ^ w`
- 结果何时有效由全局时序保证，而不是由单独 final-write enable 保证

因此第一次实现成“仅 FINAL_ROUND 写一次 `text_out`”是很自然的，但和参考不一致。

## 哪些问题是 Stage 2 放大的

Stage 2 的问题不是“写错了算法”，而是把“会影响代码选型的细节”压缩掉了。

最典型的放大点有三个：

1. 把“控制逻辑”总结成 FSM 责任边界。
   这会让生成器默认去写显式状态机，而忽略 reference-style datapath control。

2. 把 key expansion 总结成 RotWord/SubWord/Rcon/XOR 引擎。
   这会生成算法正确但时序风格不同的实现。

3. 把输出生成总结成“final round output generation”。
   这会让生成器写成条件触发式输出，而不是持续寄存式输出。

## 原始 spec 与 RealBench 参考的冲突点

这部分最关键，因为它说明：即使 planner 一字不漏保留 spec，也仍然可能过不了基准。

主要冲突点如下：

1. reset 口描述和参考实现冲突。
   spec 上写的是普通 `Reset signal`，并且全局叙述更像高有效 reset。
   RealBench 参考顶层却采用 `if (!rst)` 的低有效同步控制语义。

2. 顶层状态机图和参考 RTL 编码风格冲突。
   spec 明确给了五态图。
   参考顶层没有对应的显式五态寄存器实现。

3. “DONE 状态”叙述和参考输出时序冲突。
   spec 说 `DONE` 状态保持最终结果、拉高 `done`。
   参考 RTL 实际上没有一个独立编码的 `DONE` 状态寄存器。

因此，从 agent 设计角度看，第一次失败并不等于 planner 做错了摘要，而是：

- 你的 spec 本身是“设计说明书”
- RealBench 参考是“具体 RTL 约定”
- 这两者之间还差一层“可执行实现约束”

## 对 planner / codegen 流程的建议

如果你的目标是“从 spec 直接生成能通过现有 benchmark 的 RTL”，建议在 planner 阶段补出以下结构化槽位，而不是只做 RFU 摘要：

1. `semantic_uncertainties`
   明确列出所有无法从 spec 唯一确定的实现点。
   例如：
   reset 极性、done 脉冲宽度、output 更新时机、key expansion 的旧值/新值依赖。

2. `implementation_binding_level`
   区分一条信息是：
   算法约束、结构约束、还是拍级实现约束。
   否则生成器会把说明图误当成强制 RTL 模板。

3. `timing_contracts`
   单独抽取：
   哪些信号是组合的、哪些是寄存的、在哪个时钟边沿更新、更新后何时可见、是否存在 `#1` 风格延迟语义。

4. `reference_conflicts`
   如果后续要接 benchmark/reference，对 planner 增加一步“spec 与参考实现是否冲突”的判别。
   这一步可以把“忠实于 spec”和“忠实于 benchmark”两个目标拆开。

5. `codegen_risk_flags`
   对以下模式打高风险标签：
   状态图存在但缺少状态编码细节、自然语言说“immediately output”、corner case 只写行为不写时机、寄存器更新顺序影响结果。

## 最终判断

对这次任务，正确分析应该是：

- Stage 1 基本忠实保留了 spec，问题不在“切片丢字句”。
- Stage 2 为了模块规划做了高层抽象，但抽掉了过仿真所需的实现级时序细节。
- 更根本的问题是：原始 spec 并不能唯一决定一个与 RealBench 参考逐拍一致的 RTL。
- 第一次生成失败，主要不是 AES 算法理解错了，而是缺少 benchmark-compatible 的实现级约束，并且 spec 中的状态机叙述反而把生成过程引到了一个“合理但不对拍”的实现方向。
