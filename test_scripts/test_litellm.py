import os
from litellm import completion
import litellm


# 配置你的 LLM 服务
os.environ["OPENAI_API_KEY"] = "sk-Ks7aCV899LpHE3RO3ylALA"

# LLM_KEY = "sk-Ks7aCV899LpHE3RO3ylALA"
# LLM_URL = "https://wattllm.service.ai-next.bigwatt.cn/v1"
# LLM_MODEL = "openai/Qwen3-Next-80B-A3B-Instruct"

LLM_KEY = os.environ.get("DEEPSEEK_API_KEY", "H5LZKxzadTtkM9A3iDXUabRjI9xCa01bMP2IOiWH5rV0gtNH")
LLM_URL = "https://www.autodl.art/api/v1"
LLM_MODEL = "openai/DeepSeek-V4-Flash"

response = completion(
    # model="openai/Qwen3-Next-80B-A3B-Instruct",  # 注意格式：provider/model_name
    model=LLM_MODEL,  # 注意格式：provider/model_name
    messages=[{"role": "user", "content": "你好"}],
    api_base=LLM_URL,
    api_key=LLM_KEY
)

print(response.choices[0].message.content)