激活uv环境：
source .zerorepo/bin/activate
bash scripts/run_main.sh

指定单个 RTL spec 文件：
bash scripts/run_main.sh /home/mokita/RPG-ZeroRepo/rtl_dataset/ase_cipher/aes_unified_functional_spec.md

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
  api_key: "sk-c619e5281386c48c5c99b5c4e8412e1b5d3dce62be4703d7b6d8e2e825995b83"
  base_url: "https://mx.free.codesonline.dev/v1"