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
  api_key: "sk-69b2599638a24105962d6b186788d6ce"
  base_url: "https://api.deepseek.com"

  model: "gpt-5.5"
  max_tokens: 65536
  temperature: 0.6
  reasoning_effort: "high"
  provider: "openai"
  api_key: "sk-8bce642542af301d17a07e0c979514bac29524d8acc922f57bf00325876f3b22"
  base_url: "https://www.inroi.shop/v1"