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

# ---------- 日志 ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- 初始化 ----------
init_db()
init_knowledge()

# ---------- API 客户端 ----------
nvidia_client = None
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if NVIDIA_API_KEY:
    nvidia_client = OpenAI(
        api_key=NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1"
    )
    logger.info("✅ NVIDIA NIM 已配置")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger.info("✅ Groq 已配置")

# ---------- 模型定义 ----------
MODELS = {
    "minimax": {
        "provider": "nvidia",
        "name": "minimaxai/minimax-m2.5",
        "description": "🏆 综合最强，代码第一",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": True
    },
    "glm": {
        "provider": "nvidia",
        "name": "z-ai/glm5",
        "description": "🇨🇳 中文最强，工具调用95%+",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": True
    },
    "deepseek": {
        "provider": "nvidia",
        "name": "deepseek-ai/deepseek-v3",
        "description": "🔍 推理强，数学好",
        "client": nvidia_client if nvidia_client else None,
        "reasoning": True
    },
    "qwen": {
        "provider": "nvidia",
        "name": "qwen/qwen2.5-72b-instruct",
        "description": "🌏 阿里Qwen，中文优秀",
        "client": nvidia_client if nvidia_client else None,
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

MODELS = {k: v for k, v in MODELS.items() if v["client"] is not None}

DEFAULT_MODEL = "minimax" if nvidia_client else "gpt"
MAX_HISTORY = 12
MAX_TOKENS = 1200

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

# ---------- GitHub 建站 ----------
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

# ---------- 精简系统提示词 ----------
SYSTEM_INSTRUCTION = """
你是 Gemini，顶级智能 Discord 机器人。

## 规则
- 问候 → 友好回应
- 时间 → get_time
- 搜索 → search_web
- 读文件 → read_file
- 改代码 → apply_code_patch
- 定时 → set_daily_message / set_one_time_reminder
- 任务 → list_tasks / delete_task
- 建站 → create_github_repo + deploy_website
- 功能询问（你有什么功能/你会什么）→ 润色知识库回答
- 其他 → 自然对话

## 要求
- 中文回复，简洁精准
- 代码用 ``` 包裹
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
                for key in MODELS.keys():
                    if key != self.current_model_key:
                        self.current_model_key = key
                        logger.info(f"切换到备用模型: {key}")
                        return await self._call_model(messages, retry=False)
            raise

    async def _is_complex_task(self, user_input):
        """判断是否为复杂任务（需要多 Agent 处理）"""
        complex_keywords = [
            "同时", "并且", "然后", "接着", "之后", "先", "再",
            "帮我", "整理", "总结", "分析", "对比", "生成报告",
            "写论文", "做研究", "调研", "收集", "汇总"
        ]
        simple_tasks = ["你好", "现在几点", "搜索", "读取", "改代码", "提醒", "定时", "查看任务", "删除提醒"]
        if any(kw in user_input for kw in simple_tasks):
            return False
        if len(user_input) > 50:
            return True
        if any(kw in user_input for kw in complex_keywords):
            return True
        return False

    async def _multi_agent_run(self, user_input, channel=None):
        """多 Agent 并行处理复杂任务"""
        supervisor_prompt = f"""
        用户需求：{user_input}
        请拆解成 2-4 个独立的子任务，返回 JSON 数组。
        每个子任务应该是简单、可独立执行的操作。
        只返回 JSON，不要其他内容。
        例如：["搜索最新 Python 教程", "总结搜索到的内容", "生成示例代码"]
        """
        try:
            response = await self._call_model([{"role": "user", "content": supervisor_prompt}])
            content = response.choices[0].message.content
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                tasks = json.loads(json_match.group())
            else:
                tasks = json.loads(content)
        except Exception as e:
            logger.error(f"任务拆解失败: {e}")
            return await self._normal_run(user_input, channel)

        if not tasks or len(tasks) == 1:
            return await self._normal_run(user_input, channel)

        async def execute_subtask(task):
            task_prompt = f"你是{task}专家。请执行：{task}\n用中文回复，简洁直接。"
            try:
                resp = await self._call_model([{"role": "user", "content": task_prompt}])
                return resp.choices[0].message.content
            except Exception as e:
                return f"❌ 执行失败: {e}"

        logger.info(f"多 Agent 执行 {len(tasks)} 个子任务: {tasks}")
        results = await asyncio.gather(*[execute_subtask(t) for t in tasks])

        summary_prompt = f"用户原需求：{user_input}\n子任务结果：\n" + "\n---\n".join(results) + "\n请汇总成一份完整的回答，用中文。"
        try:
            summary_resp = await self._call_model([{"role": "user", "content": summary_prompt}])
            summary = summary_resp.choices[0].message.content
            self._update_history(user_input, summary)
            return summary
        except Exception as e:
            combined = "📋 执行结果：\n\n" + "\n---\n".join(results)
            self._update_history(user_input, combined)
            return combined

    async def _normal_run(self, user_input, channel=None):
        """原有的单 Agent 处理流程"""
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

    async def run(self, user_input, channel=None, interaction=None):
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

        # 知识库查询
        help_phrases = ["你有什么功能", "你会做什么", "怎么用你", "你能做什么", "你有什么用", "功能列表"]
        is_asking_help = any(phrase in user_input for phrase in help_phrases)

        if is_asking_help:
            knowledge = search_knowledge(user_input)
            if knowledge:
                knowledge_text = "\n".join(knowledge)
                messages = [{"role": "system", "content": "根据知识库自然回答用户问题，不要直接复制。"}]
                for msg in self.history:
                    messages.append({"role": msg["role"], "content": msg["parts"][0]})
                messages.append({"role": "user", "content": f"知识库：\n{knowledge_text}\n\n用户问：{user_input}"})
                try:
                    response = await self._call_model(messages)
                    reply = response.choices[0].message.content
                    self._update_history(user_input, reply)
                    return reply
                except Exception as e:
                    logger.error(f"润色失败: {e}")
                    return "📚 知识库：\n\n" + "\n---\n".join(knowledge)

        # 判断是否使用多 Agent
        if await self._is_complex_task(user_input):
            logger.info(f"检测到复杂任务，启用多 Agent 模式: {user_input}")
            return await self._multi_agent_run(user_input, channel)
        else:
            return await self._normal_run(user_input, channel)

    async def _handle_tools(self, reply, user_input, channel):
        tool_calls = reply.tool_calls
        if not tool_calls:
            return "工具未返回结果"

        # 检查补丁
        for tc in tool_calls:
            if tc.function.name == "apply_code_patch":
                args = json.loads(tc.function.arguments)
                self.pending_patch = args.get("patch_text")
                self.waiting_for_confirmation = True
                return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes"

        # 并行执行
        async def execute_one(tc):
            func = tc.function.name
            args = json.loads(tc.function.arguments)

            if func == "get_time":
                return get_time()
            elif func == "read_file":
                return read_file(args.get("filepath"))
            elif func == "search_web":
                return search_web(args.get("query"))
            elif func == "set_daily_message":
                if not self.bot or not channel:
                    return "❌ 需要频道信息"
                asyncio.create_task(self._schedule_daily_message(
                    str(channel.id), args["message"], args["hour"], args["minute"]
                ))
                return set_daily_message(str(channel.id), args["message"], args["hour"], args["minute"])
            elif func == "set_one_time_reminder":
                if not self.bot or not channel:
                    return "❌ 需要频道信息"
                asyncio.create_task(self._schedule_one_time_task(
                    str(channel.id), args["message"], args["seconds"]
                ))
                return set_one_time_reminder(str(channel.id), args["message"], args["seconds"])
            elif func == "delete_task":
                return delete_task(args.get("task_description"))
            elif func == "list_tasks":
                return list_tasks()
            elif func == "create_github_repo":
                return create_github_repo(
                    args.get("repo_name"),
                    args.get("description", ""),
                    args.get("private", False)
                )
            elif func == "deploy_website":
                return deploy_website(
                    args.get("html_code"),
                    args.get("filename", "index.html"),
                    args.get("commit_message", "Deploy website"),
                    args.get("repo")
                )
            else:
                return f"未知工具: {func}"

        tasks = [execute_one(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks)
        combined = "\n\n".join(results)

        if len(combined) > 200:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": f"用户问：{user_input}\n工具结果：{combined}\n请自然回答。"})
            try:
                resp = await self._call_model(messages)
                final = resp.choices[0].message.content
                self._update_history(user_input, final)
                return final
            except Exception:
                self._update_history(user_input, combined)
                return combined

        self._update_history(user_input, combined)
        return combined

    async def _schedule_daily_message(self, channel_id, message, hour, minute):
        from vector_store import schedule_daily_message
        await schedule_daily_message(self.bot, channel_id, message, hour, minute)

    async def _schedule_one_time_task(self, channel_id, message, seconds):
        from vector_store import schedule_one_time_task
        await schedule_one_time_task(self.bot, channel_id, message, seconds)

    def _get_help_text(self):
        current = self.current_model_key.upper()
        model_map = {
            "minimax": "🏆 MiniMax M2.5 (综合最强)",
            "glm": "🇨🇳 GLM-5 (中文最强)",
            "deepseek": "🔍 DeepSeek V3 (推理强)",
            "qwen": "🌏 Qwen 2.5 (中文优秀)",
            "gpt": "⚡ GPT-OSS 120B (速度最快)",
            "kimi": "💬 Kimi K2 (中文好)"
        }
        model_display = model_map.get(self.current_model_key, self.current_model_key.upper())

        return f"""
**🤖 Gemini 智能助手**

**当前模型:** {model_display}

**斜杠命令:**
`/model` - 打开模型选择菜单
`/set channel` - 设置专属频道
`/chat` - 在当前频道启用对话
`/reset` - 重置对话历史
`/help` - 显示此帮助

**可用模型:**
- 🏆 **MiniMax M2.5** - 综合最强，代码第一 (NVIDIA)
- 🇨🇳 **GLM-5** - 中文最强，工具调用95%+ (NVIDIA)
- 🔍 **DeepSeek V3** - 推理强，数学好 (NVIDIA)
- 🌏 **Qwen 2.5** - 阿里Qwen，中文优秀 (NVIDIA)
- ⚡ **GPT-OSS 120B** - 速度最快 (Groq)
- 💬 **Kimi K2** - 中文好 (Groq)

**功能:**
- 🕐 `现在几点` - 时间
- 🔍 `搜索 关键词` - 联网搜索
- 📄 `读取 bot.py` - 读文件
- ✏️ `把命令前缀改成 $` - 改代码
- ⏰ `10分钟后提醒我` - 提醒
- 📅 `每天9点发消息` - 每日定时
- 📋 `查看任务` - 任务列表
- 🌐 `帮我搭个网站` - 自动建站
"""

    def _update_history(self, user_input, reply):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        save_history(self.user_id, self.history)
