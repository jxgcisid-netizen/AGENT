import os
import json
import asyncio
import requests
from datetime import datetime
from openai import OpenAI
from groq import Groq
from git_manager import GitManager
from bs4 import BeautifulSoup

# ========== 配置 ==========
# 智谱 AI（主用，智商最高）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
if ZHIPU_API_KEY:
    zhipu_client = OpenAI(
        api_key=ZHIPU_API_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4/"
    )
    ZHIPU_MODEL = "glm-4.7-flash"
    print("✅ 智谱 GLM-4.7-Flash 已配置")

# Groq（备用）
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    print("✅ Groq 已配置")

# 确定主用模型
primary_client = None
if ZHIPU_API_KEY:
    primary_client = "zhipu"
    print("🚀 主用模型: 智谱 GLM-4.7-Flash")
elif GROQ_API_KEY:
    primary_client = "groq"
    print("🚀 主用模型: Groq")
else:
    raise Exception("❌ 没有可用的 API Key")

# ========== 定时任务管理 ==========
scheduled_tasks = {}
one_time_tasks = {}

async def schedule_daily_message(bot, channel_id, message, hour, minute):
    while True:
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= target_time:
            target_time = target_time.replace(day=now.day + 1)
        await asyncio.sleep((target_time - now).total_seconds())
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
        except Exception as e:
            print(f"❌ 定时消息失败: {e}")

async def schedule_one_time_task(bot, channel_id, message, seconds):
    await asyncio.sleep(seconds)
    try:
        channel = bot.get_channel(int(channel_id))
        if channel:
            await channel.send(f"⏰ 提醒：{message}")
    except Exception as e:
        print(f"❌ 提醒失败: {e}")

# ========== 工具函数 ==========
def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    try:
        gm = GitManager(repo_path=os.getcwd())
        success = gm.apply_patch(patch_text, commit_message)
        if success:
            return "✅ 代码已修改并推送，Railway 将自动重新部署。"
        return "❌ 修改失败，请检查补丁格式。"
    except Exception as e:
        return f"❌ 错误：{str(e)}"

def get_time() -> str:
    now = datetime.now()
    return f"🕐 当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"

def read_file(filepath: str) -> str:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 1900:
                content = content[:1900] + "\n... (截断)"
            return f"📄 文件 {filepath}：\n```python\n{content}\n```"
    except Exception as e:
        return f"❌ 读取失败: {e}"

def search_web(query: str) -> str:
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

def set_daily_message(channel_id: str, message: str, hour: int, minute: int) -> str:
    task_id = f"daily_{channel_id}_{hour}_{minute}"
    scheduled_tasks[task_id] = {"channel_id": channel_id, "message": message, "hour": hour, "minute": minute}
    return f"✅ 已设置每日 {hour:02d}:{minute:02d} 在此频道发送消息"

def set_one_time_reminder(channel_id: str, message: str, seconds: int) -> str:
    task_id = f"once_{channel_id}_{int(datetime.now().timestamp())}"
    one_time_tasks[task_id] = {"channel_id": channel_id, "message": message, "seconds": seconds}
    if seconds < 60:
        return f"✅ 已设置 {seconds} 秒后提醒：{message}"
    elif seconds < 3600:
        return f"✅ 已设置 {seconds//60} 分钟后提醒：{message}"
    else:
        return f"✅ 已设置 {seconds//3600} 小时后提醒：{message}"

def delete_task(task_description: str) -> str:
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

def list_tasks() -> str:
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
    {"type": "function", "function": {"name": "apply_code_patch", "description": "修改代码", "parameters": {"type": "object", "properties": {"patch_text": {"type": "string"}}, "required": ["patch_text"]}}},
    {"type": "function", "function": {"name": "get_time", "description": "获取时间", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取文件", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "搜索", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "set_daily_message", "description": "每日定时", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "hour": {"type": "integer"}, "minute": {"type": "integer"}}, "required": ["message", "hour", "minute"]}}},
    {"type": "function", "function": {"name": "set_one_time_reminder", "description": "一次性提醒", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "seconds": {"type": "integer"}}, "required": ["message", "seconds"]}}},
    {"type": "function", "function": {"name": "delete_task", "description": "删除任务", "parameters": {"type": "object", "properties": {"task_description": {"type": "string"}}, "required": ["task_description"]}}},
    {"type": "function", "function": {"name": "list_tasks", "description": "列出任务", "parameters": {"type": "object", "properties": {}}}}
]

SYSTEM_INSTRUCTION = """你是 Discord 机器人，中文能力极强。
规则：
- 用户说"现在几点"时调用 get_time
- 说"读取 bot.py"时调用 read_file
- 说"搜索XX"时调用 search_web
- 说"改代码"时调用 apply_code_patch
- 说"每天X点发消息"时调用 set_daily_message
- 说"X分钟后提醒我"时调用 set_one_time_reminder
- 说"删除提醒"时调用 delete_task
- 说"查看任务"时调用 list_tasks
- 修改代码前必须先展示补丁，等用户确认
- 用中文回复"""

class Agent:
    def __init__(self):
        self.history = []
        self.pending_patch = None
        self.waiting_for_confirmation = False
        self.bot = None

    def set_bot(self, bot):
        self.bot = bot

    async def run(self, user_input: str, user_id: str, channel=None) -> str:
        if user_id not in os.getenv("AUTHORIZED_USERS", "").split(","):
            return "❌ 无权限"

        if self.waiting_for_confirmation:
            if user_input.lower() in ["yes", "是", "确认", "y"]:
                self.waiting_for_confirmation = False
                return apply_code_patch(self.pending_patch)
            elif user_input.lower() in ["no", "不", "取消", "n"]:
                self.waiting_for_confirmation = False
                return "❌ 已取消"
            else:
                return "回复 yes 确认，no 取消"

        if user_input in ["!reset", "重置"]:
            self.history = []
            return "✅ 已重置"

        try:
            if primary_client == "zhipu":
                return await self._use_zhipu(user_input, channel)
            else:
                return await self._use_groq(user_input, channel)
        except Exception as e:
            if primary_client == "zhipu" and GROQ_API_KEY:
                print(f"智谱失败: {e}，切换到 Groq")
                return await self._use_groq(user_input, channel)
            return f"❌ 错误：{e}"

    async def _use_zhipu(self, user_input: str, channel=None) -> str:
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        for msg in self.history:
            messages.append({"role": msg["role"], "content": msg["parts"][0]})
        messages.append({"role": "user", "content": user_input})

        resp = zhipu_client.chat.completions.create(
            model=ZHIPU_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
            tools=TOOLS,
            tool_choice="auto"
        )

        return await self._handle_response(resp, user_input, channel)

    async def _use_groq(self, user_input: str, channel=None) -> str:
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        for msg in self.history:
            messages.append({"role": msg["role"], "content": msg["parts"][0]})
        messages.append({"role": "user", "content": user_input})

        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
            tools=TOOLS,
            tool_choice="auto"
        )

        return await self._handle_response(resp, user_input, channel)

    async def _handle_response(self, resp, user_input, channel):
        reply = resp.choices[0].message

        if reply.tool_calls:
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
                        result = "❌ 需要频道"
                    else:
                        asyncio.create_task(schedule_daily_message(self.bot, str(channel.id), args["message"], args["hour"], args["minute"]))
                        result = set_daily_message(str(channel.id), args["message"], args["hour"], args["minute"])
                    self._update_history(user_input, result)
                    return result

                elif func == "set_one_time_reminder":
                    if not self.bot or not channel:
                        result = "❌ 需要频道"
                    else:
                        asyncio.create_task(schedule_one_time_task(self.bot, str(channel.id), args["message"], args["seconds"]))
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

        self._update_history(user_input, reply.content)
        return reply.content

    def _update_history(self, user_input, reply):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
