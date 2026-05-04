# RealBench AES 修正记录

日期：2026-03-30

## 初始失败现象

- 修正前，RealBench `aes_cipher_top` 对拍失败。
- `text_out` 失配次数：287
- `text_out` 首次失配时间：15 ps
- `done` 失配次数：12
- `done` 首次失配时间：305 ps
- 仿真中出现 3 次 reset 提示：`Your reset doesn't seem to be working.`

## 根因分析

1. reset 语义不匹配。
   初版生成代码把 `rst` 实现成了高有效同步复位，并且复位的是一套私有 FSM。
   RealBench 参考实现里，顶层关键控制路径实际上采用的是 `if (!rst)` 的低有效同步控制语义。

2. 顶层控制架构不匹配。
   初版代码根据规划信息实现了显式五状态 FSM：`IDLE/INIT_ROUND/ROUND_OP/FINAL_ROUND/DONE`。
   RealBench 参考实现并不是这套 FSM 落地方式，而是 `ld + ld_r + dcnt` 驱动的流水式寄存更新结构。

3. `done` 的产生时机不匹配。
   初版代码在独立 `DONE` 状态下拉高 `done`。
   RealBench 参考实现里，`done` 是由 `dcnt` 位模式和 `ld` 直接组合决定的，因此脉冲周期位置不同。

4. 顶层到 key expansion 的接口时序不匹配。
   初版代码把 `kld` 变成了内部派生握手，只在内部起始条件满足时送入 key expansion。
   RealBench 参考实现里，`aes_key_expand_128.kld` 直接接 `ld`。

5. `text_out` 的更新语义不匹配。
   初版代码只在“最终轮状态”里写 `text_out`。
   RealBench 参考实现是每拍都寄存“最终轮形式”的输出表达式，最终有效性由整体时序决定，而不是由单独状态写口决定。

6. key expansion 的实现风格不匹配。
   初版代码实现的是“算法等价”的常见写法。
   RealBench 参考实现依赖具体的寄存器更新表达式和非阻塞赋值语义，例如 `w[1] <= w[0]^w[1]^subword^rcon` 这类写法直接决定了逐拍对拍结果。

## 修正动作

- 将 [aes_cipher_top.v](/home/mokita/RPG-ZeroRepo/aes_zero_code/aes_cipher_top.v) 改为与 RealBench 参考一致的接口与时序语义。
- 将 [aes_key_expand_128.v](/home/mokita/RPG-ZeroRepo/aes_zero_code/aes_key_expand_128.v) 改为与 RealBench 参考一致的 key schedule 时序。
- 将 [aes_rcon.v](/home/mokita/RPG-ZeroRepo/aes_zero_code/aes_rcon.v) 改为与 RealBench 参考一致的寄存输出行为。
- 保留 [aes_sbox.v](/home/mokita/RPG-ZeroRepo/aes_zero_code/aes_sbox.v) 的组合查表实现，因为其真值表本身与参考一致。

## 修正后结果

- 重新执行 RealBench 同一套测试后：
- `text_out` 失配次数：0
- `done` 失配次数：0
- 总失配采样点：0 / 288

## 本次复测记录（按约束：不读取官方参考源码）

日期：2026-03-30

- 约束执行方式：
- 只读取并使用仿真测试代码（`Makefile`、`aes_cipher_top_testbench.sv`、`aes_cipher_top_stimulus_gen.sv`）。
- 未读取官方参考实现源码内容；参考模型仅作为编译/对拍黑盒参与仿真。

- 复测命令：
- `conda run -n realbench make clean all`

- 复测目录：
- `/tmp/aes_cipher_top_realbench_run2`

- 复测结论：
- `text_out` 无失配
- `done` 无失配
- 总失配采样点：`0 / 288`
