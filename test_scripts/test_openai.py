# openai调用第三方的llm api有点问题，模型名不生效，它默认会去尝试调用gpt-4o然后报错{"error": {"type": "invalid_request_error", "message": "The model `gpt-4o` does not exist."}}
import json
import os
from openai import OpenAI

LLM_KEY = "sk-Ks7aCV899LpHE3RO3ylALA"
LLM_URL = "https://wattllm.service.ai-next.bigwatt.cn/v1"
LLM_MODEL = "Qwen3-Next-80B-A3B-Instruct"

client = OpenAI(api_key=LLM_KEY, base_url=LLM_URL)
# 1. 查看可用模型
print("=== 可用模型列表 ===")
try:
    models = client.models.list()
    for model in models.data:
        print(f"  模型: {model.id}")
        print(f"  详情: {model}")
        print("  ---")
except Exception as e:
    print(f"  获取模型列表失败: {e}")
print(client)
r = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
print(r.choices[0].message.content)