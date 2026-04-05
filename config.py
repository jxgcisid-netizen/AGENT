"""
配置文件 - 所有常量、环境变量、路径配置
"""

import os

# ========== 路径配置 ==========
if os.path.exists("/data") and os.access("/data", os.W_OK):
    DATA_DIR = "/data"
else:
    DATA_DIR = os.getcwd()

DB_PATH = os.path.join(DATA_DIR, "bot.db")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# ========== 模型配置 ==========
MAX_HISTORY = 12
MAX_TOKENS = 1200
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MODEL_KEY = "minimax"

# ========== API 客户端 ==========
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east4-gcp")

# ========== Discord 配置 ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AUTHORIZED_USERS = os.getenv("AUTHORIZED_USERS", "").split(",")

# ========== GitHub 配置 ==========
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")

# ========== Pinecone 索引配置 ==========
MEMORY_INDEX = "discord-memories"
KNOWLEDGE_INDEX = "discord-knowledge"
VECTOR_DIM = 384

# ========== 端口配置 ==========
HEALTH_PORT = 8000
WEB_PORT = 8080

# ========== 关键词配置 ==========
HELP_PHRASES = ["你有什么功能", "你会做什么", "怎么用你", "你能做什么", "你有什么用", "功能列表"]

COMPLEX_KEYWORDS = ["同时", "并且", "然后", "接着", "之后", "先", "再", "帮我", "整理", "总结", "分析", "对比", "生成报告"]

SIMPLE_TASKS = ["你好", "现在几点", "搜索", "读取", "改代码", "提醒", "定时", "查看任务", "删除提醒"]
