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
from vector_store import save_memory, search_memory, search_knowledge, init_knowledge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()
init_knowledge()

# ========== 配置 ==========
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# NVIDIA 配置（可选，作为备用）
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if NVIDIA_API_KEY:
    nvidia_client = OpenAI(
        api_key=NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1"
    )
else:
    nvidia_client = None

# ========== 智商最高的模型配置 ==========
# 智商排名 (GPQA):
# 1. openai/gpt-oss-120b: ~88分 🏆 智商最高
# 2. deepseek-ai/deepseek-v3: ~85分
# 3. moonshotai/kimi-k2-instruct: ~84.5分
# 4. meta-llama/llama-4-scout-17b-16e-instruct: ~70分

MODELS = {
    "gpt": {
        "provider": "groq",
        "name": "openai/gpt-oss-120b",
        "description": "🧠 智商最高 (GPQA ~88) | OpenAI出品",
        "client": groq_client,
        "reasoning": True  # 支持推理深度
    },
    "deepseek": {
        "provider": "groq",
        "name": "deepseek-ai/deepseek-v3",
        "description": "🔍 推理强 (GPQA ~85) | 数学好",
        "client": groq_client,
        "reasoning": False
    },
    "kimi": {
        "provider": "groq",
        "name": "moonshotai/kimi-k2-instruct",
        "description": "🇨🇳 中文最好 (GPQA ~84.5) | 表达自然",
        "client": groq_client,
        "reasoning": False
    }
}

# 添加 NVIDIA 模型作为备用
if nvidia_client:
    MODELS["qwen"] = {
        "provider": "nvidia",
        "name": "qwen/qwen2.5-72b-instruct",
        "description": "🌏 阿里Qwen | 中文强",
        "client": nvidia_client,
        "reasoning": False
    }

DEFAULT_MODEL = "gpt"  # 默认用智商最高的
MAX_HISTORY = 50

# ========== 工具函数 ==========
def get_time():
    return datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')

def apply_code_patch(patch_text, commit_message="Self-modify"):
    try:
        gm = GitManager(repo_path=os.getcwd())
        if gm.apply_patch(patch_text, commit_message):
            return "✅ 代码已修改并推送，Railway 将自动重新部署。"
        return "❌ 修改失败，请检查补丁格式"
    except Exception as e:
        return f"❌ 错误：{e}"

def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 1900:
                content = content[:1900] + "\n... (截断)"
            return f"📄 {filepath}：\n```python\n{content}\n```"
    except FileNotFoundError:
        return f"❌ 文件不存在: {filepath}"
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

def set_daily_message(channel_id, message, hour, minute):
    from vector_store import scheduled_tasks
    task_id = f"daily_{channel_id}_{hour}_{minute}"
    scheduled_tasks[task_id] = {"channel_id": channel_id, "message": message, "hour": hour, "minute": minute}
    return f"✅ 已设置每日 {hour:02d}:{minute:02d} 在此频道发送消息"

def set_one_time_reminder(channel_id, message, seconds):
    from vector_store import one_time_tasks
    task_id = f"once_{channel_id}_{int(datetime.now().timestamp())}"
    one_time_tasks[task_id] = {"channel_id": channel_id, "message": message, "seconds": seconds}
    if seconds < 60:
        return f"✅ 已设置 {seconds} 秒后提醒：{message}"
    elif seconds < 3600:
        return f"✅ 已设置 {seconds//60} 分钟后提醒：{message}"
    else:
        return f"✅ 已设置 {seconds//3600} 小时后提醒：{message}"

def delete_task(task_description):
    from vector_store import scheduled_tasks, one_time_tasks
    if "每天" in task_description or "每日" in task_description:
        for task_id in list(scheduled_tasks.keys()):
            task = scheduled_tasks[task_id]
            if task_description in task["message"]:
                del scheduled_tasks[task_id]
                return f"✅ 已删除：{task['message']}"
        return "❌ 未找到"
    else:
        count = len(one_time_tasks)
        one_time_tasks.clear()
        return f"✅ 已删除 {count} 个一次性提醒"

def list_tasks():
    from vector_store import scheduled_tasks, one_time_tasks
    result = []
    if scheduled_tasks:
        result.append("📋 每日任务：")
        for t in scheduled_tasks.values():
            result.append(f"  - {t['hour']:02d}:{t['minute']:02d}: {t['message'][:50]}")
    if one_time_tasks:
        result.append("\n⏰ 一次性：")
        for t in one_time_tasks.values():
            sec = t["seconds"]
            if sec < 60:
                result.append(f"  - {sec}秒后: {t['message'][:50]}")
            elif sec < 3600:
                result.append(f"  - {sec//60}分钟后: {t['message'][:50]}")
            else:
                result.append(f"  - {sec//3600}小时后: {t['message'][:50]}")
    return "\n".join(result) if result else "📭 无任务"

# ========== 工具定义 ==========
TOOLS = [
    {"type": "function", "function": {"name": "get_time", "description": "获取当前时间", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "apply_code_patch", "description": "修改代码", "parameters": {"type": "object", "properties": {"patch_text": {"type": "string"}}, "required": ["patch_text"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取文件", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "联网搜索", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "set_daily_message", "description": "每日定时", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "hour": {"type": "integer"}, "minute": {"type": "integer"}}, "required": ["message", "hour", "minute"]}}},
    {"type": "function", "function": {"name": "set_one_time_reminder", "description": "一次性提醒", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "seconds": {"type": "integer"}}, "required": ["message", "seconds"]}}},
    {"type": "function", "function": {"name": "delete_task", "description": "删除任务", "parameters": {"type": "object", "properties": {"task_description": {"type": "string"}}, "required": ["task_description"]}}},
    {"type": "function", "function": {"name": "list_tasks", "description": "列出任务", "parameters": {"type": "object", "properties": {}}}}
]

# ========== 超强系统提示词 ==========
SYSTEM_INSTRUCTION = """你是一个名叫ROB制作的一个机器人，一个顶级智能的 Discord 机器人。

**你的核心能力：**
1. 深度思考 - 用链式推理分析问题
2. 代码理解 - 精通 Python、JavaScript、Go 等
3. 多步骤执行 - 复杂任务自动分解执行
4. 上下文感知 - 记住对话历史，理解意图

**判断规则（按优先级）：**
- 问候（你好、嗨、在吗）→ 友好回应
- 时间（现在几点、时间）→ get_time
- 搜索（搜索、查一下）→ search_web
- 读文件（读取、查看）→ read_file
- 改代码（修改、把XX改成XX）→ apply_code_patch
- 定时（每天X点、X分钟后）→ set_daily_message / set_one_time_reminder
- 任务管理（查看任务、删除提醒）→ list_tasks / delete_task

**风格要求：**
- 用中文，简洁精准
- 复杂问题分步骤解释
- 不确定时主动询问
- 不能乱用技能
- 需要的时候用技能

现在开始！"""

class Agent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history = load_history(user_id)[-MAX_HISTORY:]
        self.pending_patch = None
        self.waiting_for_confirmation = False
        self.bot = None
        
        # 加载用户偏好，默认用智商最高的 GPT
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

    async def _call_model(self, messages):
        """调用当前模型，支持推理深度"""
        model = MODELS[self.current_model_key]
        client = model["client"]
        model_name = model["name"]
        
        # 构建请求参数
        params = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,  # 降低温度，提高准确性
            "max_tokens": 1024,
            "tools": TOOLS,
            "tool_choice": "auto"
        }
        
        # GPT-OSS 支持 reasoning_effort 参数
        if model.get("reasoning", False) and model_name == "openai/gpt-oss-120b":
            params["reasoning_effort"] = "high"  # high = 深度推理
        
        try:
            response = client.chat.completions.create(**params)
            return response
        except Exception as e:
            logger.error(f"模型调用失败: {e}")
            raise

    async def run(self, user_input, channel=None):
        # 确认处理
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

        # 重置命令
        if user_input in ["/reset", "重置"]:
            self.history = []
            save_history(self.user_id, self.history)
            return "✅ 对话已重置"

        # 模型切换命令
        if user_input.startswith("/model"):
            parts = user_input.split()
            if len(parts) == 2:
                return self.switch_model(parts[1])
            keys = ", ".join(MODELS.keys())
            return f"用法: `/model <模型>`\n可用: {keys}\n当前: {self.current_model_key}"

        # 帮助命令
        if user_input in ["/help", "帮助", "help"]:
            return self._get_help_text()

        # 只在明确问功能时查知识库
        help_keywords = ["你有什么功能", "你怎么用", "你能做什么", "命令", "你会什么", "你能干什么"]
        is_asking_help = any(kw in user_input for kw in help_keywords) and len(user_input) < 30
        
        if is_asking_help:
            knowledge = search_knowledge(user_input)
            if knowledge:
                return "📚 知识库：\n\n" + "\n---\n".join(knowledge)

        # 查记忆
        memories = search_memory(self.user_id, user_input)
        context = "\n".join(memories[:2]) if memories else ""

        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            if context:
                messages.append({"role": "user", "content": f"相关记忆：{context}\n\n当前问题：{user_input}"})
            else:
                messages.append({"role": "user", "content": user_input})

            response = await self._call_model(messages)
            reply = response.choices[0].message

            if reply.tool_calls:
                return await self._handle_tools(reply, user_input, channel)

            self._update_history(user_input, reply.content)
            if len(user_input) > 10:
                save_memory(self.user_id, user_input, {"type": "user"})
                save_memory(self.user_id, reply.content, {"type": "bot"})
            return reply.content

        except Exception as e:
            logger.error(f"错误: {e}")
            return f"❌ 错误：{str(e)[:200]}"

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

            elif func == "set_daily_message":
                if not self.bot or not channel:
                    result = "❌ 需要频道信息"
                else:
                    asyncio.create_task(self._schedule_daily_message(
                        str(channel.id), args["message"], args["hour"], args["minute"]
                    ))
                    result = set_daily_message(str(channel.id), args["message"], args["hour"], args["minute"])
                self._update_history(user_input, result)
                return result

            elif func == "set_one_time_reminder":
                if not self.bot or not channel:
                    result = "❌ 需要频道信息"
                else:
                    asyncio.create_task(self._schedule_one_time_task(
                        str(channel.id), args["message"], args["seconds"]
                    ))
                    result = set_one_time_reminder(str(channel.id), args["message"], args["seconds"])
                self._update_history(user_input, result)
                return result

            elif func == "delete_task":
                result = delete_task(args.get("task_description"))
                self._update_history(user_input, result)
                return result

            elif func == "list_tasks":
                result = list_tasks()
                self._update_history(user_input, result)
                return result

        return "未知工具调用"

    async def _schedule_daily_message(self, channel_id, message, hour, minute):
        from vector_store import schedule_daily_message
        await schedule_daily_message(self.bot, channel_id, message, hour, minute)

    async def _schedule_one_time_task(self, channel_id, message, seconds):
        from vector_store import schedule_one_time_task
        await schedule_one_time_task(self.bot, channel_id, message, seconds)

    def _get_help_text(self):
        return """**🤖 Gemini 智能助手**

**当前模型：** 🧠 GPT-OSS 120B（智商最高）

**斜杠命令：**
`/model gpt/deepseek/kimi/qwen` - 切换模型
`/reset` - 重置对话
`/help` - 帮助

**功能：**
- 🕐 `现在几点` - 时间
- 🔍 `搜索 关键词` - 联网搜索
- 📄 `读取 bot.py` - 读文件
- ✏️ `把命令前缀改成 $` - 改代码
- ⏰ `10分钟后提醒我` - 提醒
- 📅 `每天9点发消息` - 每日定时
- 📋 `查看任务` - 任务列表

直接聊天就行，我会自动理解你的需求！"""

    def _update_history(self, user_input, reply):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        save_history(self.user_id, self.history)
