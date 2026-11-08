项目介绍、环境配置和完整运行说明见 [README.md](README.md)。

网页 demo 与交互工作台已迁移至 `/home/mokita/RTL-Studio`。

启动：`cd /home/mokita/RTL-Studio && ./start.sh`。
迁移说明见 [docs/rtl-studio-migration.md](docs/rtl-studio-migration.md)。

## 原 Agent 命令

激活uv环境：
source .zerorepo/bin/activate
bash scripts/run_main.sh

指定单个 RTL spec 文件：
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/ase_cipher/aes_unified_functional_spec.md

指定一个文件夹的spec

bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/sdc

按阶段停止和继续（启动脚本默认开启恢复）：

```bash
# 规划：Stage4 门控通过后停止
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/sdc --plan

# 生成：完成各模块生成、合并、语法检查与有限次数修复，系统 debug 前停止
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/sdc --generate

# 继续语法修复和系统 debug
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/sdc

# 批量运行到规划阶段
bash scripts/run_main.sh --plan
```

`--plan` 和 `--generate` 互斥，可以放在规格参数前后。模块语法修复次数耗尽后会继续下一个模块，生成完成不代表全部语法通过；待修复模块记录在 `generate/metadata/stage6_merge.json` 中，后续运行原命令继续处理。规划门控、代码生成或合并失败仍报错。直接运行 `main.py` 时需指定 `--phase rtl_planner`，续跑需加 `--resume`。

规划 harness 升级后，旧 Stage1—Stage4 会重新生成。新运行在 `plan/state/execution/` 保存候选和局部修复状态，超时后重跑同一命令即可恢复；API 用量与耗时见 `plan/metrics.json`，逐次请求记录见 `plan/state/request_usage.jsonl`。一般生成首正文等待为 240 秒；Stage3 骨架生成/修复为 480 秒，确认收到推理内容后使用 900 秒推理阶段上限，单次逻辑请求总预算为 1200 秒。重试与退避共享总预算，空事件不能延长等待。此次等待策略调整不触发已有有效规划重建。

规划修复提示会共享重复证据和 schema，保留全部唯一来源及约束。字符预算仍为 `max_prompt_chars: 256000`，最终消息大小与超限原因保存在执行检查点的 `prompt_budget` 中；已有候选可继续恢复，不会因这次提示组装修复而全部重建。

Stage4 首次规划提示也对任务契约、规格和 KG 使用无损共享，保留完整骨架 Markdown。若此前在 Stage4 提示大小检查处失败，重跑原命令即可按来源校验恢复已完成的模块计划；无需删除输出或添加 `--force-rebuild`。

Stage3 来源字段修复支持证据 ID，由程序复制已核验原文；同一响应中独立义务的有效修复可以分别保留。
有持续校验进展时可在节点预算内超过原来的三次内容尝试，连续两次无进展后不再延长。
本次修复不改变规划策略或初始输入指纹，重跑同一命令可复验失败检查点中的补丁并继续剩余字段；不需要清理案例目录。


不传参数时：
按 `rtl_dataset` 目录中的 `.md` 文件名排序顺序依次执行


  model: "deepseek-v4-pro"
  max_tokens: 65536
  temperature: 0.6
  reasoning_effort: "high"
  provider: "openai"
  api_key: "${DEEPSEEK_API_KEY}"
  base_url: "https://api.deepseek.com"

  model: "gpt-6.1-sol"
  max_tokens: 65536
  temperature: 0.6
  reasoning_effort: "high"
  provider: "openai"
  api_key: "${ZEROREPO_API_KEY}"
  base_url: "https://www.inroi.shop/v1"

  model: "gpt-5.6-sol"
  max_tokens: 65536
  temperature: 0.6
  reasoning_effort: "high"
  provider: "openai"
  api_key: "${ZEROREPO_API_KEY}"
  base_url: "https://xtoken.work/v1"
