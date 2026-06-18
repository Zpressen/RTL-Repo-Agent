# 0. 全局约定（所有表通用）

## 0.1 Repo 快照分区键

- `repo_uid`: string，建议 `"<repo_name>@<commit_sha>"`
  - 所有节点/边都带 `repo_uid`，实现多版本并存、增量更新、跨仓库隔离。

## 0.2 统一主键

- `uid`: string，**全局唯一**（强烈建议所有节点都用 `uid` 做唯一约束）
- `kind`: string，节点类型枚举（便于调试/过滤）

## 0.3 统一源码定位（span）

- 行列统一采用 **1-based**（避免编辑器/日志转换混乱）
- `path`: repo 相对路径
- `sl/el/sc/ec`: 起止行列（可选列）

## 0.4 统一变更检测

- `h`: string（hash）
  - File 节点：文件内容 hash（或 git blob sha）
  - Module/Always/Assign 等：定义范围文本 hash（可选）
  - Expr/CONNECTS：表达式 hash（强烈建议）

## 0.5 扩展字段策略（避免表越来越胖）

- `attrs`: **JSON 字符串**（或 map，如果你习惯 Neo4j map）
  - schema 里只保“高频检索字段”
  - 其余全部进 `attrs`，后续迭代不用改表结构

------

# 1. 节点表设计（Nodes）

## 1.1 Repo

**Label**：`:Repo`

| 字段       | 类型   | 必填 | 说明                            |
| ---------- | ------ | ---- | ------------------------------- |
| `uid`      | string | ✓    | 推荐 = `repo_uid`               |
| `repo_uid` | string | ✓    | `<repo>@<sha>`                  |
| `kind`     | string | ✓    | `"Repo"`                        |
| `name`     | string | ✓    | repo 名                         |
| `attrs`    | json   |      | remote_url/branch/created_at 等 |

**唯一约束**：`Repo(uid)` 或 `Repo(repo_uid)`

------

## 1.2 File（文件/目录统一）

**Label**：`:File`

| 字段       | 类型   | 必填 | 说明                                |
| ---------- | ------ | ---- | ----------------------------------- |
| `uid`      | string | ✓    | `repo_uid:path`                     |
| `repo_uid` | string | ✓    |                                     |
| `kind`     | string | ✓    | `"File"`                            |
| `path`     | string | ✓    | repo 相对路径（目录也有）           |
| `name`     | string | ✓    | basename                            |
| `h`        | string |      | 文件 hash（增量更新）               |
| `attrs`    | json   |      | `{is_dir, lang, role, size, mtime}` |

**索引**：`(repo_uid, path)`；可选 `(repo_uid, name)`

------

## 1.3 Module

**Label**：`:Module`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | 推荐：`repo_uid:mod:<name>:<path>:<sl>`                      |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"Module"`                                                   |
| `name`     | string | ✓    | module 名                                                    |
| `path`     | string | ✓    | 定义文件                                                     |
| `sl`/`el`  | int    | ✓    | module 范围                                                  |
| `h`        | string |      | 范围文本 hash（可选）                                        |
| `attrs`    | json   |      | `{is_sv, timescale, default_nettype, port_sig_hash, param_sig_hash}` |

**索引**：`(repo_uid, name)`；`(repo_uid, path)`

------

## 1.4 Package（可选）

**Label**：`:Package`

| 字段       | 类型   | 必填 | 说明                              |
| ---------- | ------ | ---- | --------------------------------- |
| `uid`      | string | ✓    | `repo_uid:pkg:<name>:<path>:<sl>` |
| `repo_uid` | string | ✓    |                                   |
| `kind`     | string | ✓    | `"Package"`                       |
| `name`     | string | ✓    |                                   |
| `path`     | string | ✓    |                                   |
| `sl/el`    | int    | ✓    |                                   |
| `attrs`    | json   |      | `{exports_short}`                 |

------

## 1.5 Instance（实例化点）

**Label**：`:Instance`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | `repo_uid:inst:<parent_mod_uid>:<inst_name>:<sl>`            |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"Instance"`                                                 |
| `name`     | string | ✓    | inst_name                                                    |
| `path`     | string | ✓    | 所在文件                                                     |
| `sl/el`    | int    | ✓    | 实例化语句范围                                               |
| `attrs`    | json   |      | `{module_ref, gen_path, hier_path?, resolved_module_uid?, conf?}` |

> `hier_path`（可选缓存）：用于“日志层级路径 → 实例”快速匹配。

------

## 1.6 Port（模块端口）

**Label**：`:Port`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | `repo_uid:port:<module_uid>:<name>`                          |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"Port"`                                                     |
| `name`     | string | ✓    | 端口名                                                       |
| `path`     | string |      |                                                              |
| `sl/el`    | int    |      |                                                              |
| `attrs`    | json   |      | `{module_uid, dir, dtype(net/reg/logic), signed, width_expr}` |

------

## 1.7 Signal（模块内部声明级信号）

**Label**：`:Signal`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | `repo_uid:sig:<module_uid>:<name>`                           |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"Signal"`                                                   |
| `name`     | string | ✓    |                                                              |
| `path`     | string |      |                                                              |
| `sl/el`    | int    |      |                                                              |
| `attrs`    | json   |      | `{module_uid, decl_kind(wire/reg/logic), signed, width_expr}` |

> **关键点**：Signal 只做到“声明级”，不做每条语句读写依赖。

------

## 1.8 Param（Parameter/Localparam 合并）

**Label**：`:Param`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | `repo_uid:param:<module_uid>:<name>`                         |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"Param"`                                                    |
| `name`     | string | ✓    |                                                              |
| `path`     | string |      |                                                              |
| `sl/el`    | int    |      |                                                              |
| `attrs`    | json   |      | `{module_uid, pkind(parameter/localparam), value_short, value_hash, width_expr?}` |

------

## 1.9 AlwaysBlock（过程块容器）

**Label**：`:AlwaysBlock`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | `repo_uid:ab:<module_uid>:<sl>`                              |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"AlwaysBlock"`                                              |
| `name`     | string |      | label（如果有）                                              |
| `path`     | string | ✓    |                                                              |
| `sl/el`    | int    | ✓    | 过程块范围                                                   |
| `h`        | string |      | 块文本 hash（可选）                                          |
| `attrs`    | json   |      | `{module_uid, bkind(ff/comb/latch/unknown), sens_short, clk?, rst?}` |

------

## 1.10 Assign（连续赋值）

**Label**：`:Assign`

| 字段       | 类型   | 必填 | 说明                                            |
| ---------- | ------ | ---- | ----------------------------------------------- |
| `uid`      | string | ✓    | `repo_uid:as:<module_uid>:<sl>`                 |
| `repo_uid` | string | ✓    |                                                 |
| `kind`     | string | ✓    | `"Assign"`                                      |
| `path`     | string | ✓    |                                                 |
| `sl/el`    | int    | ✓    |                                                 |
| `h`        | string |      | 表达式 hash（可选）                             |
| `attrs`    | json   |      | `{module_uid, lhs_short, rhs_short, expr_hash}` |

------

## 1.11 Generate（生成块骨架）

**Label**：`:Generate`

| 字段       | 类型   | 必填 | 说明                                                         |
| ---------- | ------ | ---- | ------------------------------------------------------------ |
| `uid`      | string | ✓    | `repo_uid:gen:<module_uid>:<sl>`                             |
| `repo_uid` | string | ✓    |                                                              |
| `kind`     | string | ✓    | `"Generate"`                                                 |
| `name`     | string |      |                                                              |
| `path`     | string | ✓    |                                                              |
| `sl/el`    | int    | ✓    |                                                              |
| `attrs`    | json   |      | `{module_uid, gkind(for/if/case), genvar?, range_short?, label_path?}` |

------

## 1.12 Expr（可选：连接表达式落地）

**Label**：`:Expr`（可选）

| 字段       | 类型   | 必填 | 说明                                               |
| ---------- | ------ | ---- | -------------------------------------------------- |
| `uid`      | string | ✓    | `repo_uid:expr:<hash>` 或带位置信息                |
| `repo_uid` | string | ✓    |                                                    |
| `kind`     | string | ✓    | `"Expr"`                                           |
| `attrs`    | json   |      | `{text_short, text_hash, ref_names?, width_expr?}` |

> 不想加 Expr 节点也行：把 `text_short/text_hash` 放到 CONNECTS 边属性里。

------

# 2. 关系表设计（Edges）

> Neo4j 关系没有“强唯一约束”很麻烦，所以建议：
> **每类关系都可选加 `eid`（edge id）**，写入时用 `MERGE` 保证幂等。

------

## 2.1 CONTAINS（文件树）

- `(:Repo)-[:CONTAINS]->(:File)`
- `(:File)-[:CONTAINS]->(:File)`（目录到子项）

| 属性    | 必填 | 说明                                    |
| ------- | ---- | --------------------------------------- |
| `eid`   |      | `repo_uid:contains:<src_uid>:<dst_uid>` |
| `order` |      | 可选                                    |

------

## 2.2 DEFINES（文件定义 module/package）

- `(:File)-[:DEFINES]->(:Module)`
- `(:File)-[:DEFINES]->(:Package)`

| 属性  | 必填 | 说明                                    |
| ----- | ---- | --------------------------------------- |
| `eid` |      | `repo_uid:defines:<file_uid>:<def_uid>` |

------

## 2.3 INCLUDES（include 追溯）

- `(:File)-[:INCLUDES]->(:File)`

| 属性  | 必填 | 说明               |
| ----- | ---- | ------------------ |
| `eid` |      |                    |
| `raw` |      | include 原串（短） |
| `ok`  |      | 解析是否成功       |

------

## 2.4 IMPORTS（package 依赖）

- `(:Module)-[:IMPORTS]->(:Package)`（或 File->Package）

| 属性  | 必填 | 说明                  |
| ----- | ---- | --------------------- |
| `eid` |      |                       |
| `raw` |      | `import pkg::*;` 摘要 |

------

## 2.5 INSTANTIATES / OF_MODULE（层次骨架）

- `(:Module)-[:INSTANTIATES]->(:Instance)`
- `(:Instance)-[:OF_MODULE]->(:Module)`

**INSTANTIATES 属性：**

| 属性       | 必填 | 说明                      |
| ---------- | ---- | ------------------------- |
| `eid`      |      |                           |
| `gen_path` |      | 可选（generate 层级标签） |

**OF_MODULE 属性：**

| 属性   | 必填 | 说明              |
| ------ | ---- | ----------------- |
| `eid`  |      |                   |
| `conf` |      | 解析置信度（0~1） |

------

## 2.6 HAS（统一的 module 成员关系）

- `(:Module)-[:HAS]->(:Port/:Signal/:Param/:AlwaysBlock/:Assign/:Generate)`

| 属性  | 必填 | 说明                                                         |
| ----- | ---- | ------------------------------------------------------------ |
| `eid` |      |                                                              |
| `k`   | ✓    | 成员类型字符串：`Port/Signal/Param/AlwaysBlock/Assign/Generate` |

> 用 `HAS{k=...}` 替代 6 种 HAS_xxx，关系类型更稳定，后续扩展更省事。

------

## 2.7 CONNECTS（端口级连接：跨模块导航核心）

- `(:Instance)-[:CONNECTS]->(:Signal)` 或 `->(:Port)` 或 `->(:Expr)`
  （建议允许 Signal/Port 两种目标；Expr 可选）

| 属性         | 必填 | 说明                                         |
| ------------ | ---- | -------------------------------------------- |
| `eid`        |      | `repo_uid:conn:<inst_uid>:<p>:<ord or hash>` |
| `p`          | ✓    | 形式端口名（port_name）                      |
| `by`         |      | `named` / `positional`                       |
| `ord`        |      | positional 序号（named 时可空）              |
| `t`          |      | target kind：`signal/port/expr/lit/unknown`  |
| `x`          |      | 连接表达式短摘要（截断如 120）               |
| `h`          |      | 连接表达式 hash（强烈建议）                  |
| `path/sl/el` |      | 连接语句位置（强烈建议）                     |

------

# 3. ✅ 新增：DRIVES（LHS 级轻量驱动，用于结构回溯）

这是你要求的最小补齐：**只做“赋值目标（LHS）”级别**，用于：

- “从 failing signal/port 回溯到写它的 assign / always block”
- “统计多驱动风险（incoming DRIVES 个数）”
- “Top-K suspects 解释链更硬”

------

## 3.1 Assign 驱动信号

- `(:Assign)-[:DRIVES]->(:Signal)`
  -（可选）`(:Assign)-[:DRIVES]->(:Port)`

  > 解决 `output reg out_v; always ... out_v <= ...;` 这类“端口本身就是寄存器变量”的情况：如果没有独立 Signal 声明，也能回溯到 Port。

| 属性        | 必填 | 说明                                  |
| ----------- | ---- | ------------------------------------- |
| `eid`       |      | `repo_uid:drv:<assign_uid>:<dst_uid>` |
| `k`         | ✓    | `"cont"`（连续赋值）                  |
| `cnt`       |      | 写该目标出现次数（一般=1）            |
| `cond_hint` |      | 条件摘要（一般空）                    |

------

## 3.2 AlwaysBlock 驱动信号

- `(:AlwaysBlock)-[:DRIVES]->(:Signal)`
  -（可选）`(:AlwaysBlock)-[:DRIVES]->(:Port)`（同上原因）

| 属性        | 必填 | 说明                                                        |
| ----------- | ---- | ----------------------------------------------------------- |
| `eid`       |      | `repo_uid:drv:<ab_uid>:<dst_uid>:<k>`                       |
| `k`         | ✓    | `"nb"` / `"blk"`（非阻塞/阻塞；若混用可拆两条或用 `"mix"`） |
| `cnt`       |      | 该块内对目标赋值次数（粗略统计）                            |
| `cond_hint` |      | 条件摘要（短）例如 `if(!rst_n)` / `case(state)`             |

> `cond_hint` 不需要精确条件树，只要“最外层门控”摘要即可，给 ranking/解释链加分。

------

## 3.3 DRIVES 的目标选择策略（避免歧义）

当 LHS 是 `a[i]` / `a.b` / `{a,b}` 这类：

- **抽取 base identifier 集合**：
  - `a[i]` → `a`
  - `a.b` → `a`（或 `a.b` 作为扩展字段写进 attrs，但 uid 仍指向 base）
  - `{a,b}` → 两条 DRIVES：分别到 `a`、`b`
- 目标优先级（建议）：
  1. Module 内有同名 `Signal` → 指向 Signal
  2. Module 内有同名 `Port` 且其 dtype 为 reg/logic 且可写 → 指向 Port
  3. 都没有 → 丢到 `attrs.unresolved_lhs[]`（不建边）

这样 DRIVES 永远不会“乱连”，而且增量更新可控。

# DRIVES 边怎么保证连得上：靠“模块内名字解析”

你要构建的 DRIVES（LHS 级）只需要做三件事：

1. **确定“这条赋值属于哪个 module”**
   - assign 语句在 top 的范围内 → module_uid = top
   - always block 在 checker 范围内 → module_uid = checker
2. **从该语句里抽取 LHS 的 base identifier 集合**
   - `assign sum_next = ...` → LHS base = {`sum_next`}
   - `y_r = r_sum;` → LHS base = {`y_r`}
   - `out_v <= in_v;` → LHS base = {`out_v`}
3. **在该 module 的符号表中按名字查找**
    查找顺序建议：
   - 先查 Signal(name=lhs)
   - 找不到再查 Port(name=lhs)（只对“可写端口变量”有意义）
   - 两个都找不到：不连边，记录 unresolved

------

# 4. 约束与索引（Neo4j DDL 建议）

## 4.1 节点唯一约束（推荐全用 uid）

```cypher
CREATE CONSTRAINT repo_uid_unique IF NOT EXISTS FOR (n:Repo) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT file_uid_unique IF NOT EXISTS FOR (n:File) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT module_uid_unique IF NOT EXISTS FOR (n:Module) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT inst_uid_unique IF NOT EXISTS FOR (n:Instance) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT port_uid_unique IF NOT EXISTS FOR (n:Port) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT sig_uid_unique IF NOT EXISTS FOR (n:Signal) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT param_uid_unique IF NOT EXISTS FOR (n:Param) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT ab_uid_unique IF NOT EXISTS FOR (n:AlwaysBlock) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT as_uid_unique IF NOT EXISTS FOR (n:Assign) REQUIRE n.uid IS UNIQUE;
CREATE CONSTRAINT gen_uid_unique IF NOT EXISTS FOR (n:Generate) REQUIRE n.uid IS UNIQUE;
```

## 4.2 常用索引（提高查询）

```cypher
CREATE INDEX module_name_idx IF NOT EXISTS FOR (n:Module) ON (n.repo_uid, n.name);
CREATE INDEX file_path_idx IF NOT EXISTS FOR (n:File) ON (n.repo_uid, n.path);
CREATE INDEX signal_name_idx IF NOT EXISTS FOR (n:Signal) ON (n.repo_uid, n.name);
CREATE INDEX port_name_idx IF NOT EXISTS FOR (n:Port) ON (n.repo_uid, n.name);
```

------

# 5. 这套 Schema 如何支撑“结构回溯”（你关心的落地查询路径）

有了 DRIVES 后，你的 COI backtrace 就变成确定性的图查询：

1. **从 failing (Module, Signal/Port)** 出发
2. 查本模块内：
   - `Signal/Port <-[:DRIVES]- (Assign/AlwaysBlock)`（直接驱动）
3. 若失败点来自子模块输出/端口连接：
   - `parent Instance -[:CONNECTS{p=...}]-> parent Signal/Port`
   - `Instance -[:OF_MODULE]-> child Module`
     继续在 child Module 内重复 2)
4. 结合结构距离 + 类型权重 + 多驱动（incoming DRIVES count）做 Top-K

这条链路不需要 READS，也不需要语句级 AST。

------

# 6. 写入建议（方便你后面写构建代码）

## 6.1 节点写入（幂等）

- `MERGE (n:Label {uid:$uid}) SET n += $props`
- 增量更新：如果 `h` 不变，可以跳过该节点的 L1 重建

## 6.2 边写入（建议带 eid 幂等）

- `MATCH (a {uid:$src}), (b {uid:$dst}) MERGE (a)-[r:REL {eid:$eid}]->(b) SET r += $props`

特别是 `CONNECTS`、`DRIVES`，推荐一定加 `eid`。

