"""
模型定义 - 所有 AI 模型的配置
"""

import os
from groq import Groq
from openai import OpenAI
from config import GROQ_API_KEY, NVIDIA_API_KEY, DEFAULT_MODEL_KEY

# ========== API 客户端初始化 ==========
groq_client = Groq(api_key=GROQ_API_KEY)

nvidia_client = None
if NVIDIA_API_KEY:
    nvidia_client = OpenAI(
        api_key=NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1"
    )

# ========== 模型定义 ==========
MODELS = {
    "minimax": {
        "provider": "nvidia",
        "name": "minimaxai/minimax-m2.5",
        "description": "🏆 综合最强，代码第一",
        "client": nvidia_client,
        "reasoning": True
    },
    "glm": {
        "provider": "nvidia",
        "name": "z-ai/glm5",
        "description": "🇨🇳 中文最强，工具调用95%+",
        "client": nvidia_client,
        "reasoning": True
    },
    "deepseek": {
        "provider": "nvidia",
        "name": "deepseek-ai/deepseek-v3",
        "description": "🔍 推理强，数学好",
        "client": nvidia_client,
        "reasoning": True
    },
    "qwen": {
        "provider": "nvidia",
        "name": "qwen/qwen2.5-72b-instruct",
        "description": "🌏 阿里Qwen，中文优秀",
        "client": nvidia_client,
        "reasoning": False
    },
    "gpt": {
        "provider": "groq",
        "name": "openai/gpt-oss-120b",
        "description": "⚡ GPT-OSS 120B，速度最快",
        "client": groq_client,
        "reasoning": True
    },
    "kimi": {
        "provider": "groq",
        "name": "moonshotai/kimi-k2-instruct",
        "description": "💬 Kimi K2，中文好",
        "client": groq_client,
        "reasoning": False
    }
}

# 过滤掉 client 为 None 的模型
MODELS = {k: v for k, v in MODELS.items() if v["client"] is not None}

AVAILABLE_MODELS = list(MODELS.keys())

if DEFAULT_MODEL_KEY in MODELS:
    DEFAULT_MODEL = DEFAULT_MODEL_KEY
else:
    DEFAULT_MODEL = AVAILABLE_MODELS[0] if AVAILABLE_MODELS else "gpt"
