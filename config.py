"""全局配置"""
import os

# ---------- 路径 ----------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chromadb")
DB_PATH = os.path.join(DATA_DIR, "center.db")

# ---------- 知识库名称 ----------
HISTORY_KB = "history_kb"
MATERIAL_KB = "material_kb"

# ---------- LLM 配置 ----------
# 通过环境变量配置，不硬编码 Key
# 当前使用: Watt LLM / Qwen3-Next-80B
#   $env:DEEPSEEK_API_KEY="sk-Ks7..."   (Watt LLM key)
#   $env:DEEPSEEK_API_URL="https://wattllm.service.ai-next.bigwatt.cn/v1/"
#   $env:DEEPSEEK_MODEL="Qwen3-Next-80B-A3B-Instruct"
#
# 备选 1: DeepSeek 官方
#   $env:DEEPSEEK_API_KEY="sk-e08..."   (DeepSeek key)
#   $env:DEEPSEEK_API_URL="https://api.deepseek.com"
#   $env:DEEPSEEK_MODEL="deepseek-v4-flash"
#
# 备选 2: AutoDL
#   $env:DEEPSEEK_API_KEY="H5LZK..."    (AutoDL key)
#   $env:DEEPSEEK_API_URL="https://www.autodl.art/api/v1/"
#   $env:DEEPSEEK_MODEL="DeepSeek-V4-Flash"

LLM_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_URL = os.environ.get("DEEPSEEK_API_URL", "https://wattllm.service.ai-next.bigwatt.cn/v1/")
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", "Qwen3-Next-80B-A3B-Instruct")

# ---------- 检索参数 ----------
TOP_K = 5
HIGH_SIM = 0.70      # 相似度 >= 此值直接返回历史回答
MEDIUM_SIM = 0.45    # 相似度 >= 此值展示参考

# ---------- 追问 ----------
MAX_FOLLOWUP = 2

# ---------- 服务器 ----------
HOST = "0.0.0.0"
PORT = 8100