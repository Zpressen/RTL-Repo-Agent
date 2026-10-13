激活uv环境：
source .zerorepo/bin/activate
bash scripts/run_main.sh

指定单个 RTL spec 文件：
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/ase_cipher/aes_unified_functional_spec.md

指定一个文件夹的spec

bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/sdc


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