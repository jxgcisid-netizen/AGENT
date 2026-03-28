import os
import json
import asyncio
import requests
import logging
from datetime import datetime
from groq import Groq
from openai import OpenAI
from git_manager import GitManager
from bs4 import BeautifulSoup
from db import init_db, save_history, load_history, save_user_preference, load_user_preference
from memory import save_memory, search_memory
from knowledge import query_knowledge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

# ========== 配置 ==========
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
nvidia_client = OpenAI(
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1"
)

MODELS = {
    "gpt": {
        "provider": "groq",
        "name": "openai/gpt-oss-120b",
        "description": "🧠 智商最高，速度最快"
    },
    "kimi": {
        "provider": "groq",
        "name": "moonshotai/kimi-k2-instruct",
        "description": "🇨🇳 中文最好，表达自然"
    },
    "deepseek": {
        "provider": "nvidia",
        "name": "deepseek-ai/deepseek-v3",
        "description": "🔍 推理能力强，数学好"
    },
    "qwen": {
        "provider": "nvidia",
        "name": "qwen/qwen2.5-72b-instruct",
        "description": "🌏 阿里Qwen，中文强"
    }
}

DEFAULT_MODEL = "gpt"
MAX_HISTORY = 50

# ========== 工具函数 ==========
def get_time():
    return datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')

def apply_code_patch(patch_text, commit_message="Self-modify"):
    try:
        gm = GitManager(repo_path=os.getcwd())
        if gm.apply_patch(patch_text, commit_message):
            return "✅ 代码已修改并推送"
        return "❌ 修改失败"
    except Exception as e:
        return f"❌ 错误：{e}"

def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 1900:
                content = content[:1900] + "\n... (截断)"
            return f"📄 {filepath}：\n```python\n{content}\n```"
    except Exception as e:
        return f"❌ 读取失败: {e}"

def search_web(query):
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__a')[:5]:
            title = a.get_text()
            link = a.get('href')
            if link and link.startswith('/'):
                link = 'https://duckduckgo.com' + link
            results.append(f"🔗 {title}\n   {link}")
        return "🔍 搜索结果：\n\n" + "\n\n".join(results) if results else "❌ 无结果"
    except Exception as e:
        return f"❌ 搜索失败: {e}"

TOOLS = [
    {"type": "function", "function": {"name": "get_time", "description": "获取时间", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "apply_code_patch", "description": "修改代码", "parameters": {"type": "object", "properties": {"patch_text": {"type": "string"}}, "required": ["patch_text"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取文件", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "搜索", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
]

SYSTEM_INSTRUCTION = """你是 Discord 机器人。
规则：
- 用户说"现在几点"时调用 get_time
- 说"读取 bot.py"时调用 read_file
- 说"搜索XX"时调用 search_web
- 说"改代码"时调用 apply_code_patch
- 用中文回复"""

class Agent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history = load_history(user_id)[-MAX_HISTORY:]
        self.pending_patch = None
        self.waiting_for_confirmation = False
        self.bot = None
        
        preferred_model, _ = load_user_preference(user_id)
        if preferred_model and preferred_model in MODELS:
            self.current_model_key = preferred_model
        else:
            self.current_model_key = DEFAULT_MODEL

    def set_bot(self, bot):
        self.bot = bot

    def switch_model(self, model_key: str) -> str:
        if model_key not in MODELS:
            keys = ", ".join(MODELS.keys())
            return f"❌ 可用模型: {keys}"
        
        self.current_model_key = model_key
        save_user_preference(self.user_id, model_key, MODELS[model_key]["provider"])
        return f"✅ 已切换到 **{model_key}**\n{MODELS[model_key]['description']}"

    async def _call_groq(self, messages):
        return groq_client.chat.completions.create(
            model=MODELS[self.current_model_key]["name"],
            messages=messages,
            temperature=0.5,
            max_tokens=2048,
            tools=TOOLS,
            tool_choice="auto"
        )

    async def _call_nvidia(self, messages):
        return nvidia_client.chat.completions.create(
            model=MODELS[self.current_model_key]["name"],
            messages=messages,
            temperature=0.5,
            max_tokens=2048,
            tools=TOOLS,
            tool_choice="auto"
        )

    async def run(self, user_input, channel=None):
        if self.waiting_for_confirmation:
            if user_input.lower() in ["yes", "是", "确认", "y"]:
                self.waiting_for_confirmation = False
                result = apply_code_patch(self.pending_patch)
                self._update_history(user_input, result)
                return result
            elif user_input.lower() in ["no", "不", "取消", "n"]:
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return "❌ 已取消"
            else:
                return "回复 yes 确认，no 取消"

        if user_input in ["/reset", "重置"]:
            self.history = []
            save_history(self.user_id, self.history)
            return "✅ 已重置"

        if user_input.startswith("/model"):
            parts = user_input.split()
            if len(parts) == 2:
                return self.switch_model(parts[1])
            keys = ", ".join(MODELS.keys())
            return f"用法: `/model <模型>`\n可用: {keys}\n当前: {self.current_model_key}"

        # 先查知识库
        knowledge_answer = query_knowledge(user_input)
        if knowledge_answer:
            return knowledge_answer

        # 查向量记忆
        memories = search_memory(self.user_id, user_input)
        context = ""
        if memories:
            context = "\n相关记忆：\n" + "\n".join(memories[:2])

        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            if context:
                messages.append({"role": "user", "content": f"历史上下文：{context}\n\n当前问题：{user_input}"})
            else:
                messages.append({"role": "user", "content": user_input})

            provider = MODELS[self.current_model_key]["provider"]
            if provider == "groq":
                response = await self._call_groq(messages)
            else:
                response = await self._call_nvidia(messages)

            reply = response.choices[0].message

            if reply.tool_calls:
                return await self._handle_tools(reply, user_input, channel)

            self._update_history(user_input, reply.content)
            save_memory(self.user_id, user_input, {"type": "user_question"})
            save_memory(self.user_id, reply.content, {"type": "bot_response"})
            return reply.content

        except Exception as e:
            logger.error(f"API错误: {e}")
            return f"❌ 错误：{str(e)}"

    async def _handle_tools(self, reply, user_input, channel):
        for tc in reply.tool_calls:
            func = tc.function.name
            args = json.loads(tc.function.arguments)

            if func == "apply_code_patch":
                self.pending_patch = args.get("patch_text")
                self.waiting_for_confirmation = True
                return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes"

            elif func == "get_time":
                result = get_time()
                self._update_history(user_input, result)
                return result

            elif func == "read_file":
                result = read_file(args.get("filepath"))
                self._update_history(user_input, result)
                return result

            elif func == "search_web":
                result = search_web(args.get("query"))
                self._update_history(user_input, result)
                return result

        return "未知工具调用"

    def _update_history(self, user_input, reply):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        save_history(self.user_id, self.history)
