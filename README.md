# RPG-ZeroRepo

RPG-ZeroRepo 是一个从规格文档生成代码、并结合工具检查和修复结果的 Agent 项目。当前主要使用 **RTL Spec-to-RTL** 流程：读取 Markdown 硬件规格，规划模块结构和局部任务，生成 Verilog/SystemVerilog，再进行语法检查、系统验证和调试。

仓库也保留了基于 Repository Planning Graph（RPG）的通用软件仓库生成代码。下面的环境和运行说明以当前 `rtl_planner` 主线为主。

网页 demo 和交互工作台已拆分至 `/home/mokita/RTL-Studio`。本仓库负责 Agent 核心、CLI、规格数据和原始运行工件；Studio 通过 Python 包依赖调用这里的 Agent。详见 [迁移说明](docs/rtl-studio-migration.md)。

## 项目功能

| 环节 | 主要工作 |
| --- | --- |
| 规格解析 | 从 Markdown 提取设计事实、来源依据和顶层接口 |
| 架构规划 | 建立责任清单，提出并选择模块划分，记录层次和模块间约束 |
| 模块与任务分解 | 检索模块相关规格，生成内部骨架、代码块和局部实现任务 |
| RTL 生成与合并 | 逐任务生成代码片段及实现契约，合并成完整模块 |
| 检查与调试 | 调用语法检查器和配套验证脚本，结合日志、波形、KG 进行定位和修复 |
| 恢复与记录 | 保存阶段工件、输入指纹、候选修改和检查结果，支持经核验的断点恢复 |

```mermaid
flowchart LR
    A[Markdown 规格] --> B[事实与接口]
    B --> C[模块架构]
    C --> D[内部骨架与局部任务]
    D --> E[片段生成与语义合并]
    E --> F[语法与系统验证]
    F --> G[调试与候选验证]
    G --> F
    F --> H[RTL 与运行工件]
```

规划主线包含 Stage1—Stage6。Stage1—Stage4 准备事实、架构、骨架和任务；随后按模块执行 Stage5 片段生成和 Stage6 合并。源码中的阶段完成状态、语法通过状态和功能验证结果需要分别查看。

更详细的实现说明见 [RTL Agent 功能、架构与实现说明](docs/rtl_agent_system_description.md)。该文档包含迁移前的产品层描述，网页路径以本 README 和迁移说明为准。

## 在当前机器上运行

已有 Agent 环境位于仓库根目录的 `.zerorepo/`。在仓库根目录执行：

```bash
cd /home/mokita/RPG-ZeroRepo
source .zerorepo/bin/activate

# 当前机器的 RealBench 环境中提供了 Verilator。
export PATH="/home/mokita/miniconda3/envs/realbench/bin:$PATH"

python --version
verilator --version

# 以 AES 加密规格为例，启动真实的规划、生成和配置中启用的调试。
bash scripts/run_main.sh rtl_dataset/aes_cipher_hard/aes_cipher_system_hard.md
```

运行前确认 [configs/zerorepo_config.yaml](configs/zerorepo_config.yaml) 中的模型、服务地址、凭据、KG 和调试后端适合本次任务。启动生成会调用配置的模型服务。

当前配置选择了 `rtl_kg.enabled: true`、`rtl_kg.mode: required` 和 `rtl_debug.backend: codex`，因此需要 Neo4j 可连接，以及相应调试后端可用。新环境可以先使用下文的最小配置，再接入这些能力。

本机环境核对日期：**2026-11-03**。`.zerorepo/` 使用 Python **3.12.3**；`uv pip check --python .zerorepo/bin/python` 已确认当前安装的 213 个包依赖兼容。这是现有环境检查，不等同于全新安装或真实模型任务验收。

## 新建 Python 环境

### 系统工具

以下命令按 Linux / Bash 编写。

| 工具 | 用途 |
| --- | --- |
| Python | 包元数据要求 Python ≥ 3.11；下方环境步骤使用与本机一致的 3.12 系列 |
| `uv` | 创建虚拟环境、安装和检查 Python 依赖 |
| C/C++ 编译工具、`make` | 编译 tree-sitter 语法库，以及构建 HDL 仿真程序 |
| Verilator | RTL 语法检查和部分系统仿真 |
| Icarus Verilog / `vvp` | 按具体测试脚本需要安装 |
| Neo4j | 启用 RTL KG 时使用；仓库提供 Docker Compose 配置 |
| 外部调试 CLI | 选择 `codex` 调试后端时需要；`repo_react` 使用 Python 侧模型工具循环 |

普通 Agent CLI 不需要 Node.js 或网页的 Python 环境。系统验证还依赖对应任务的测试脚本、TB 和参考资源，详见后文。

### 创建环境并安装 RTL 依赖

在仓库根目录创建独立环境，保留已有 `.zerorepo/`：

```bash
uv venv --python 3.12 .venv-rtl

uv pip install --python .venv-rtl/bin/python \
  "openai==2.24.0" "pydantic==2.12.5" "PyYAML==6.0.3" \
  "agentscope==1.0.7" "mcp==1.27.0" \
  "tree-sitter==0.25.2" "tree-sitter-verilog==1.0.3" \
  "neo4j==6.1.0" "vcdvcd==1.0.6" \
  "httpx==0.28.1" "tiktoken==0.12.0" "json-repair==0.59.5" \
  "networkx==3.6.1" "numpy==2.4.2" \
  "sqlalchemy[asyncio]==2.0.48" "python-dotenv==1.2.2" \
  "pytest==9.0.2"

uv pip install --python .venv-rtl/bin/python --no-deps -e .
uv pip check --python .venv-rtl/bin/python
source .venv-rtl/bin/activate
```

上述直接依赖版本取自当前兼容的 Agent 环境，面向 OpenAI 兼容接口的 RTL 主线；传递依赖未全部锁定，这组命令本次未在空环境中重装验证。选择其他模型 provider 时，还需要相应 SDK；运行通用软件生成、向量检索或评测代码时，需要按其模块补充依赖。

`pyproject.toml` 提供 `zerorepo-agent` 的包注册，目前没有声明完整运行依赖，因此仅执行 `pip install -e .` 不会自动配齐环境。

仓库现有依赖文件的范围如下：

| 文件 | 当前用途与注意事项 |
| --- | --- |
| `requirements.txt` | 历史完整依赖集合，包含 ML、评测和旧版 LlamaIndex 等依赖 |
| `requirements_fixed.txt` | 另一组历史通用依赖，仍保留部分旧版本约束 |
| `zerorepo/rtl_impl/rtl_kg/requirements.txt` | KG 子项目的历史依赖说明，tree-sitter 约束与当前环境不同 |

这些文件不构成当前 RTL 环境的统一锁文件。不要将它们与上面的版本集合混合安装到已有环境中。

## 模型与运行配置

主配置为 [configs/zerorepo_config.yaml](configs/zerorepo_config.yaml)，主要字段如下：

| 配置项 | 作用 |
| --- | --- |
| `llm` | 模型 provider、名称、凭据、服务地址和生成参数 |
| `rtl_module_planner.retrieval_limits` | 规格检索的输入和上下文规模限制 |
| `rtl_module_planner.request_policy` | 按检索、生成及具体阶段控制模型请求等待与重试策略 |
| `rtl_kg` | 是否启用 KG、失败策略和 Neo4j 连接 |
| `rtl_debug` | 是否启用调试、调试后端、验证资源根目录和尝试预算 |
| `prop_level` / `impl_level` / `code_generation` | 通用软件生成及旧流程相关配置 |

### 最小配置示例

可以把下面内容保存为 `/tmp/zerorepo-rtl-basic.yaml`，并替换模型名称和服务地址。此配置用于先运行规划、生成与模块语法检查，关闭 KG 和系统级调试。

```yaml
llm:
  provider: openai
  model: "<your-model>"
  base_url: "<your-openai-compatible-base-url>"
  api_key: "${ZEROREPO_API_KEY}"
  max_tokens: 16384
  temperature: 0.6
  stream: true
  stream_include_usage: true

rtl_kg:
  enabled: false

rtl_debug:
  enabled: false
  backend: repo_react
```

```bash
export ZEROREPO_API_KEY="<your-api-key>"
```

`llm` 的字符串字段支持 `${环境变量名}` 展开。模型、服务地址及参数应与实际提供方支持的配置匹配；`--llm-config` 也可以覆盖模型配置，格式由 `LLMConfig.from_source()` 处理。

CLI 不会自动加载 `.env` 文件，环境变量需要在启动进程前导出。现有主配置按文件中的值读取；设置环境变量只会影响引用该变量的配置或相应 provider 的环境变量回退。README 不包含本机真实凭据。

### 配置 RTL KG

使用仓库提供的开发 Compose 配置启动 Neo4j：

```bash
docker compose -f zerorepo/rtl_impl/rtl_kg/docker-compose.dev.yml up -d neo4j
```

然后在实际使用的 YAML 配置中设置：

```yaml
rtl_kg:
  enabled: true
  mode: required
  neo4j:
    uri: "bolt://127.0.0.1:7687"
    user: "neo4j"
    password: "<与 Neo4j 服务一致的密码>"
```

`mode: required` 会在 KG 初始化失败时停止流程；不需要 KG 的任务可显式配置 `enabled: false`。Neo4j 密码当前按 YAML 原值读取，不使用 `llm` 的环境变量展开逻辑。

RTL 解析器使用 `zerorepo/rtl_impl/rtl_kg/third_party/tree-sitter-verilog/` 中的语法源码。首次调用 `VerilogTreeSitter.get_parser()` 时，如果共享库不存在，会尝试编译到 `zerorepo/rtl_impl/rtl_kg/build/rtl_langs.so`，需要可用的 C 编译器。

| 环境变量 | 用途 |
| --- | --- |
| `RTL_TS_GRAMMAR_DIR` | 指定 tree-sitter Verilog 语法源码目录 |
| `RTL_TS_LANG_SO` | 指定已经编译的语法共享库 |
| `RTL_TS_CACHE_DIR` | 调整语法库构建和缓存目录 |

可单独检查解析器：

```bash
python - <<'PY'
from zerorepo.rtl_impl.rtl_kg.rtl_file_graph_builder import VerilogTreeSitter
tree = VerilogTreeSitter.get_parser().parse(b"module smoke; endmodule")
assert not tree.root_node.has_error
print("Verilog parser OK")
PY
```

更多 KG 操作见 [Neo4j 入库说明](zerorepo/rtl_impl/rtl_kg/README_neo4j_ingest.md)。

### 配置系统验证与调试

完整的系统验证需要匹配当前设计的验证脚本、TB、激励和参考资源。当前适配包含 RealBench 目录约定，默认根目录是 `/home/mokita/RealBench`，它是仓库外的依赖，不会随本仓库自动安装。

```yaml
rtl_debug:
  enabled: true
  backend: repo_react
  oracle_root: "/path/to/RealBench"
  toolchain_bin: "/path/to/verilator/bin"
  max_trials: 30
  allow_failure: false
```

系统验证器会结合规格路径中的项目名和顶层模块名查找 `system_task/<项目或顶层>/verify_test/` 下的配套资源。自定义规格要接入相应验证资源，不能仅靠修改 `oracle_root` 就获得功能验证。

可选调试后端为 `repo_react` 和 `codex`。后者需要可用的外部 CLI、所选 profile 和认证配置；其 Agent 侧接入说明见 [Codex RTL Debug MCP](docs/codex_debug_mcp.md)。普通 CLI 不需要安装 RTL Studio。

常用调试环境变量覆盖项：

| 环境变量 | 作用 |
| --- | --- |
| `ZEROREPO_RTL_DEBUG` | 开关调试，例如 `false` |
| `ZEROREPO_RTL_DEBUG_BACKEND` | `repo_react` 或 `codex` |
| `ZEROREPO_RTL_DEBUG_ORACLE_ROOT` | 覆盖验证资源根目录 |
| `ZEROREPO_RTL_DEBUG_TOOLCHAIN_BIN` | 覆盖调试使用的工具链目录 |
| `ZEROREPO_RTL_DEBUG_MAX_TRIALS` | 覆盖调试尝试预算 |

语法门控失败时的模块修复仍可能使用 RepoReAct；系统调试后端的选择不表示所有模型调用都切换为该后端。

## 运行方式

### 使用现有启动脚本

在仓库根目录、已激活的 Python 环境中执行：

```bash
# 单个规格文件
bash scripts/run_main.sh rtl_dataset/aes_cipher_hard/aes_cipher_system_hard.md

# 将一个目录中的规格作为一个规划任务输入
bash scripts/run_main.sh rtl_dataset/sdc

# 不传参数，按文件名排序处理 rtl_dataset 顶层的 .md 文件
bash scripts/run_main.sh
```

脚本默认选择 `RTL_PIPELINE_MODE=planner`，并附带 `--resume`。不传参数时不会递归枚举所有子目录中的案例；如果要运行某个子目录，请显式传入目录或文件路径。

脚本固定使用 `configs/zerorepo_config.yaml`。使用其他配置或进一步控制参数时，直接运行 `main.py`。

### 直接调用 CLI

使用上文的最小配置：

```bash
python main.py \
  --config /tmp/zerorepo-rtl-basic.yaml \
  --checkpoint rtl_outputs/aes_cipher_system_hard/.zerorepo \
  --repo rtl_outputs/aes_cipher_system_hard \
  --phase rtl_planner \
  --rtl-spec rtl_dataset/aes_cipher_hard/aes_cipher_system_hard.md \
  --log-file rtl_outputs/aes_cipher_system_hard/.zerorepo/zerorepo.log \
  --resume
```

本命令会进行真实模型调用。查看参数帮助使用 `python main.py --help`。

当前 RTL 分支实际将各案例工件写入**当前工作目录**下的 `rtl_outputs/<规格名或目录名>/`，因此建议始终从仓库根目录启动。`--repo` 和 `--checkpoint` 是 CLI 必填参数，但不能据此假定它们会覆盖 RTL 分支内部的案例输出目录。

`--resume` 会核验已有输入和工件后复用阶段结果，不表示已有文件一律跳过。需要重新构建时可使用 `--force-rebuild`，并事先保留需要的运行工件。

**当前 `--dry-run` 的提前返回位于通用软件生成分支；RTL 分支会先执行，因此不能将 `--phase rtl_planner --dry-run` 当作不调用模型的预检命令。**

### 其他保留入口

`main.py` 还提供 `all`、`design`、`implementation`、`rtl`、`rtl_phase1`、`rtl_phase2` 等阶段入口。它们对应通用软件生成或旧 RTL 流程，依赖范围和行为与 `rtl_planner` 不同；上面的轻量 RTL 环境说明不构成这些路径的完整运行保证。

## 输出与恢复

以 `aes_cipher_system_hard` 为例，主要目录如下：

```text
rtl_outputs/aes_cipher_system_hard/
└── .zerorepo/
    ├── zerorepo.log                   # 使用上述 --log-file 时的日志
    ├── module_planner/
    │   └── outputs/
    │       ├── contracts.json         # 事实与顶层接口
    │       ├── stage2_decomposition.json
    │       ├── repo_skeleton.json     # 选中的模块架构
    │       ├── modules.json
    │       ├── module_skeletons.json
    │       ├── spec_blocks.json
    │       ├── module_plans.json
    │       ├── stage5_codegen.json
    │       └── stage6_merge.json
    └── workspace/
        ├── fragments/                # 局部 RTL 与实现契约
        ├── merged/                   # 合并后的 RTL
        └── debug_system/             # 系统检查、候选修改及后端调试记录
```

具体文件随执行阶段和调试后端变化。排查问题时保留该案例的整个 `.zerorepo/`，避免只保留最终 `.v` 文件而丢失恢复和验证依据。仓库根目录的 `.zerorepo/` 是当前机器的 Python 环境，与 `rtl_outputs/<案例>/.zerorepo/` 的运行工件目录含义不同。

## 代码目录

| 路径 | 内容 |
| --- | --- |
| `main.py`、`scripts/run_main.sh` | CLI 和常用启动脚本 |
| `configs/` | 模型、规划、KG、调试和通用流程配置 |
| `rtl_dataset/` | Markdown 规格及部分配套测试 |
| `rtl_outputs/` | 各案例的原始运行输出 |
| `zerorepo/rtl_impl/module_planner/` | Stage1—Stage6 编排、agents、schemas 和 prompts |
| `zerorepo/rtl_impl/retrieval_agent/` | 模块、代码块和合并阶段的规格检索 |
| `zerorepo/rtl_impl/kg_agent/`、`rtl_kg/` | 规划语义图、RTL 结构解析和 Neo4j 集成 |
| `zerorepo/rtl_impl/debug_agent/`、`repo_react/`、`codex_debug/` | 检查、仿真适配和调试后端 |
| `zerorepo/rtl_impl/rtl_memory/` | 调试经验、版本和使用记录 |
| `zerorepo/rpg_gen/`、`rpg_encoder/`、`code_gen/` | 通用 RPG 与代码生成组件 |
| `tests/` | Agent 单元和回归测试；网页测试已迁至 Studio |
| `docs/` | 系统说明、设计报告和迁移记录 |
| `langfuse_local/` | 单独的本地观测示例，说明见其 README |

## 开发检查

已激活 Agent 环境后，可先检查导入和 CLI：

```bash
python main.py --help
python -c 'from zerorepo.rtl_impl.module_planner import PlannerRunner; print("Planner import OK")'
uv pip check --python "$(command -v python)"
```

一组无需提交真实模型任务的回归测试：

```bash
python -m pytest \
  tests/test_runtime_integration.py \
  tests/test_planner_json_escapes.py \
  tests/test_llm_streaming.py \
  tests/test_codex_debug_resume.py \
  tests/test_codex_debug_mcp.py \
  tests/test_codex_memory_adapter.py -q
```

这组测试使用受控输入或模型替身，不代替真实模型、Neo4j 和 HDL 系统验证。更多 planner 测试位于 `tests/test_rtl_module_planner.py`、`tests/test_planner_resume_sources.py` 等文件。

## 常见问题

| 现象 | 检查方向 |
| --- | --- |
| 缺少 `agentscope`、`neo4j` 等模块 | 确认激活的解释器，以及是否只注册了 editable 包而没有安装运行依赖 |
| tree-sitter API 或语言库加载错误 | 核对实际版本、语法源码和共享库；不要混装历史 requirements 中的 tree-sitter 约束 |
| KG 初始化即退出 | 当前是否为 `mode: required`；核对 Neo4j 服务、地址、密码和解析器 |
| 找不到 Verilator | 核对 `PATH`；模块语法检查也需要工具可被直接找到 |
| 找不到系统验证器或参考资源 | 核对 RealBench 路径、规格所属项目和顶层模块对应的验证目录 |
| 模型认证或参数错误 | 核对实际生效的 `llm` 配置、环境变量引用和提供方参数要求 |
| 没有处理期望的案例 | 无参数运行只遍历 `rtl_dataset` 顶层 Markdown；显式指定目标文件或目录 |
| 找不到 `zerorepo.rtl_web` | 网页模块已迁至 RTL Studio；本仓库普通 Agent CLI 不依赖网页模块 |

## 相关文档

- [常用命令](run_command.md)
- [RTL Agent 系统说明](docs/rtl_agent_system_description.md)
- [Planner 局部修复](docs/planner_local_repair.md)
- [RepoReAct 设计说明](docs/reporeact-design-report.md)
- [Codex 调试集成](docs/codex_debug_mcp.md)
- [RTL Studio 迁移说明](docs/rtl-studio-migration.md)
- [MIT License](LICENSE)
