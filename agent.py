# -*- coding: utf-8 -*-
import os
import json
import asyncio
import requests
import base64
import logging
from datetime import datetime
from groq import Groq
from openai import OpenAI
from git_manager import GitManager
from bs4 import BeautifulSoup
from db import init_db, save_history, load_history, save_user_preference, load_user_preference
from vector_store import save_memory, search_memory, search_knowledge, init_knowledge

# ---------- 日志配置 ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- 初始化 ----------
init_db()
init_knowledge()

# ---------- API 客户端 ----------
# NVIDIA NIM（优先，无限 Token）
nvidia_client = None
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if NVIDIA_API_KEY:
    nvidia_client = OpenAI(
        api_key=NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1"
    )
    logger.info("✅ NVIDIA NIM 已配置（无限 Token）")

# Groq（备用）
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger.info("✅ Groq 已配置（备用）")

# ---------- 模型定义（NVIDIA 优先） ----------
MODELS = {
    # NVIDIA 模型（优先，无限 Token）
    "minimax": {
        "provider": "nvidia",
        "name": "minimaxai/minimax-m2.5",
        "description": "⚡ MiniMax M2.5 - 多语言编码最强",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": True
    },
    "glm": {
        "provider": "nvidia",
        "name": "z-ai/glm5",
        "description": "🇨🇳 智谱GLM-5 - 中文能力顶尖",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": True
    },
    "qwen": {
        "provider": "nvidia",
        "name": "qwen/qwen2.5-72b-instruct",
        "description": "🌏 阿里Qwen - 中文强",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": False
    },
    "deepseek": {
        "provider": "nvidia",
        "name": "deepseek-ai/deepseek-v3",
        "description": "🔍 DeepSeek V3 - 推理强",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": True
    },
    # Groq 模型（备用）
    "gpt": {
        "provider": "groq",
        "name": "openai/gpt-oss-120b",
        "description": "🧠 GPT-OSS 120B - 备用",
        "client": groq_client,
        "reasoning": True
    },
    "kimi": {
        "provider": "groq",
        "name": "moonshotai/kimi-k2-instruct",
        "description": "🇨🇳 Kimi K2 - 中文备用",
        "client": groq_client,
        "reasoning": False
    }
}

# 过滤掉 client 为 None 的模型（NVIDIA 未配置时）
MODELS = {k: v for k, v in MODELS.items() if v["client"] is not None}

DEFAULT_MODEL = "minimax" if nvidia_client else "gpt"  # 优先用 MiniMax
MAX_HISTORY = 15
MAX_TOKENS = 600

# ---------- 工具函数 ----------
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

# ---------- GitHub 建站工具 ----------
def create_github_repo(repo_name: str, description: str = "", private: bool = False):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "❌ 未设置 GITHUB_TOKEN"

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {
        "name": repo_name,
        "description": description,
        "private": private,
        "auto_init": True
    }
    resp = requests.post("https://api.github.com/user/repos", headers=headers, json=data)
    if resp.status_code == 422:
        owner = os.getenv("GITHUB_OWNER")
        if not owner:
            user_resp = requests.get("https://api.github.com/user", headers=headers)
            if user_resp.status_code == 200:
                owner = user_resp.json()["login"]
            else:
                return "❌ 无法确定用户名，请设置 GITHUB_OWNER"
        repo_check = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}", headers=headers)
        if repo_check.status_code == 200:
            return f"ℹ️ 仓库已存在：{owner}/{repo_name}"
        else:
            return f"❌ 创建仓库失败：{resp.json().get('message', '未知错误')}"
    if resp.status_code not in (200, 201):
        return f"❌ 创建仓库失败：{resp.status_code} - {resp.json().get('message', '')}"

    repo = resp.json()
    full_name = repo["full_name"]
    return f"✅ 已创建仓库：{full_name}"

def deploy_website(html_code: str, filename: str = "index.html", commit_message: str = "Deploy website", repo: str = None):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "❌ 未设置 GITHUB_TOKEN"

    if repo:
        if '/' in repo:
            owner, repo_name = repo.split('/', 1)
        else:
            owner = os.getenv("GITHUB_OWNER")
            if not owner:
                headers = {"Authorization": f"token {token}"}
                user_resp = requests.get("https://api.github.com/user", headers=headers)
                if user_resp.status_code == 200:
                    owner = user_resp.json()["login"]
                else:
                    return "❌ 无法确定 GitHub 用户名，请设置 GITHUB_OWNER"
            repo_name = repo
    else:
        env_repo = os.getenv("GITHUB_REPO")
        if not env_repo:
            return "❌ 未设置 GITHUB_REPO 且未指定仓库名"
        if '/' in env_repo:
            owner, repo_name = env_repo.split('/', 1)
        else:
            owner = os.getenv("GITHUB_OWNER")
            if not owner:
                return "❌ 未设置 GITHUB_OWNER 且 GITHUB_REPO 格式不正确"
            repo_name = env_repo

    headers = {"Authorization": f"token {token}"}
    repo_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    resp = requests.get(repo_url, headers=headers)
    if resp.status_code != 200:
        return f"❌ 无法获取仓库信息: {resp.status_code} - {resp.json().get('message', '')}"
    default_branch = resp.json().get("default_branch", "main")

    file_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{filename}"
    sha = None
    resp = requests.get(file_url, headers=headers)
    if resp.status_code == 200:
        sha = resp.json()["sha"]

    data = {
        "message": commit_message,
        "content": base64.b64encode(html_code.encode()).decode(),
        "branch": default_branch
    }
    if sha:
        data["sha"] = sha
    resp = requests.put(file_url, headers=headers, json=data)
    if resp.status_code not in (200, 201):
        return f"❌ 提交文件失败: {resp.status_code} - {resp.json().get('message', '')}"

    pages_url = f"https://api.github.com/repos/{owner}/{repo_name}/pages"
    pages_resp = requests.get(pages_url, headers=headers)
    if pages_resp.status_code == 404:
        pages_data = {"source": {"branch": default_branch, "path": "/"}}
        pages_resp = requests.post(pages_url, headers=headers, json=pages_data)
        if pages_resp.status_code not in (200, 201):
            return f"❌ 启用 GitHub Pages 失败: {pages_resp.status_code} - {pages_resp.json().get('message', '')}"

    site_url = f"https://{owner}.github.io/{repo_name}/"
    return f"✅ 网站已部署！访问地址：{site_url}"

# ---------- 工具定义 ----------
TOOLS = [
    {"type": "function", "function": {"name": "get_time", "description": "获取当前时间", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "apply_code_patch", "description": "修改代码", "parameters": {"type": "object", "properties": {"patch_text": {"type": "string"}}, "required": ["patch_text"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取文件", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "联网搜索", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "set_daily_message", "description": "每日定时", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "hour": {"type": "integer"}, "minute": {"type": "integer"}}, "required": ["message", "hour", "minute"]}}},
    {"type": "function", "function": {"name": "set_one_time_reminder", "description": "一次性提醒", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "seconds": {"type": "integer"}}, "required": ["message", "seconds"]}}},
    {"type": "function", "function": {"name": "delete_task", "description": "删除任务", "parameters": {"type": "object", "properties": {"task_description": {"type": "string"}}, "required": ["task_description"]}}},
    {"type": "function", "function": {"name": "list_tasks", "description": "列出任务", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "create_github_repo",
            "description": "在 GitHub 上创建一个新仓库",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string"},
                    "description": {"type": "string"},
                    "private": {"type": "boolean"}
                },
                "required": ["repo_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_website",
            "description": "将 HTML 代码部署到 GitHub Pages",
            "parameters": {
                "type": "object",
                "properties": {
                    "html_code": {"type": "string"},
                    "filename": {"type": "string"},
                    "commit_message": {"type": "string"},
                    "repo": {"type": "string"}
                },
                "required": ["html_code"]
            }
        }
    }
]

# ---------- 系统提示词 ----------
SYSTEM_INSTRUCTION = """
你是 Gemini，一个顶级智能的 Discord 机器人，使用 NVIDIA NIM 平台（无限 Token），中文能力极强。

**核心规则：**
1. 问候（你好、嗨）→ 友好回应
2. 时间（现在几点）→ get_time
3. 搜索（搜索XX）→ search_web
4. 读文件（读取XX）→ read_file
5. 改代码（把XX改成XX）→ apply_code_patch
6. 定时（每天X点、X分钟后）→ set_daily_message / set_one_time_reminder
7. 任务管理（查看任务、删除提醒）→ list_tasks / delete_task

**自动建站规则：**
- 用户说“帮我搭个网站”时，先生成简洁英文仓库名，调用 create_github_repo，再调用 deploy_website

**风格要求：**
- 用中文，简洁精准
- 复杂问题分步骤解释
- 不确定时主动询问

现在开始！
"""

# ---------- Agent 类 ----------
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

    async def _call_model(self, messages, retry=True):
        """调用当前模型，失败时自动切换备用"""
        model = MODELS[self.current_model_key]
        client = model["client"]
        model_name = model["name"]

        params = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": MAX_TOKENS,
            "tools": TOOLS,
            "tool_choice": "auto"
        }
        if model.get("reasoning", False):
            params["reasoning_effort"] = "high"

        try:
            response = client.chat.completions.create(**params)
            return response
        except Exception as e:
            logger.error(f"模型调用失败 ({self.current_model_key}): {e}")
            if retry:
                # 尝试切换到第一个可用的备用模型
                for key in MODELS.keys():
                    if key != self.current_model_key:
                        self.current_model_key = key
                        logger.info(f"切换到备用模型: {key}")
                        return await self._call_model(messages, retry=False)
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
        help_keywords = ["功能", "帮助", "怎么用", "能做什么", "命令", "模型", "介绍", "你会", "你能", "你有什么"]
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
        tool_results = []
        for tc in reply.tool_calls:
            func = tc.function.name
            args = json.loads(tc.function.arguments)

            if func == "apply_code_patch":
                self.pending_patch = args.get("patch_text")
                self.waiting_for_confirmation = True
                return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes"

            elif func == "get_time":
                result = get_time()
                tool_results.append(f"⏰ {result}")

            elif func == "read_file":
                result = read_file(args.get("filepath"))
                tool_results.append(result)

            elif func == "search_web":
                result = search_web(args.get("query"))
                tool_results.append(result)

            elif func == "set_daily_message":
                if not self.bot or not channel:
                    result = "❌ 需要频道信息"
                else:
                    asyncio.create_task(self._schedule_daily_message(
                        str(channel.id), args["message"], args["hour"], args["minute"]
                    ))
                    result = set_daily_message(str(channel.id), args["message"], args["hour"], args["minute"])
                tool_results.append(result)

            elif func == "set_one_time_reminder":
                if not self.bot or not channel:
                    result = "❌ 需要频道信息"
                else:
                    asyncio.create_task(self._schedule_one_time_task(
                        str(channel.id), args["message"], args["seconds"]
                    ))
                    result = set_one_time_reminder(str(channel.id), args["message"], args["seconds"])
                tool_results.append(result)

            elif func == "delete_task":
                result = delete_task(args.get("task_description"))
                tool_results.append(result)

            elif func == "list_tasks":
                result = list_tasks()
                tool_results.append(result)

            elif func == "create_github_repo":
                result = create_github_repo(
                    args.get("repo_name"),
                    args.get("description", ""),
                    args.get("private", False)
                )
                tool_results.append(result)

            elif func == "deploy_website":
                result = deploy_website(
                    args.get("html_code"),
                    args.get("filename", "index.html"),
                    args.get("commit_message", "Deploy website"),
                    args.get("repo")
                )
                tool_results.append(result)

        if self.waiting_for_confirmation:
            return

        combined_result = "\n\n".join(tool_results)
        if not combined_result:
            return "工具未返回结果"

        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        for msg in self.history:
            messages.append({"role": msg["role"], "content": msg["parts"][0]})
        messages.append({"role": "user", "content": f"请用自然的方式回答用户。\n用户问题：{user_input}\n工具结果：{combined_result}"})

        try:
            response = await self._call_model(messages)
            final_reply = response.choices[0].message.content
            self._update_history(user_input, final_reply)
            return final_reply
        except Exception as e:
            logger.error(f"润色失败: {e}")
            self._update_history(user_input, combined_result)
            return combined_result

    async def _schedule_daily_message(self, channel_id, message, hour, minute):
        from vector_store import schedule_daily_message
        await schedule_daily_message(self.bot, channel_id, message, hour, minute)

    async def _schedule_one_time_task(self, channel_id, message, seconds):
        from vector_store import schedule_one_time_task
        await schedule_one_time_task(self.bot, channel_id, message, seconds)

    def _get_help_text(self):
        return """
**🤖 Gemini 智能助手 (NVIDIA 无限 Token)**

**当前模型:** 🧠 MiniMax M2.5 / GLM-5

**斜杠命令:**
`/model minimax/glm/qwen/deepseek/gpt/kimi` - 切换模型
`/reset` - 重置对话
`/help` - 帮助

**功能:**
- 🕐 `现在几点` - 时间
- 🔍 `搜索 关键词` - 联网搜索
- 📄 `读取 bot.py` - 读文件
- ✏️ `把命令前缀改成 $` - 改代码
- ⏰ `10分钟后提醒我` - 提醒
- 📅 `每天9点发消息` - 每日定时
- 📋 `查看任务` - 任务列表
- 🌐 `帮我搭个网站` - 自动建站

直接聊天就行，我会自动理解你的需求!
"""

    def _update_history(self, user_input, reply):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        save_history(self.user_id, self.history)
