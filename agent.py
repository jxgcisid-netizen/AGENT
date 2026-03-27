import os
import json
import asyncio
from datetime import datetime
from groq import Groq
from git_manager import GitManager

# ========== 配置 ==========
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-4-maverick")

# ========== 定时任务管理 ==========
scheduled_tasks = {}

async def schedule_daily_message(bot, channel_id, message, hour, minute):
    """每天定时发送消息"""
    while True:
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if now >= target_time:
            target_time = target_time.replace(day=now.day + 1)
        
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
                print(f"✅ 定时消息已发送: {message}")
        except Exception as e:
            print(f"❌ 发送定时消息失败: {e}")

# ========== 工具函数 ==========
def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    """应用代码补丁并推送至 Git 仓库"""
    try:
        gm = GitManager(repo_path=os.getcwd())
        success = gm.apply_patch(patch_text, commit_message)
        if success:
            return "✅ 代码已修改并推送，Railway 将自动重新部署（约1-2分钟）。"
        return "❌ 修改失败，请检查补丁格式。"
    except Exception as e:
        return f"❌ 错误：{str(e)}"

def get_time() -> str:
    """获取当前时间"""
    now = datetime.now()
    return f"🕐 当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"

def set_daily_message(channel_id: str, message: str, hour: int, minute: int) -> str:
    """设置每日定时消息"""
    task_id = f"{channel_id}_{hour}_{minute}"
    scheduled_tasks[task_id] = {
        "channel_id": channel_id,
        "message": message,
        "hour": hour,
        "minute": minute
    }
    return f"✅ 已设置每日 {hour:02d}:{minute:02d} 在此频道发送消息"

def list_tasks() -> str:
    """列出所有定时任务"""
    if not scheduled_tasks:
        return "📭 当前没有定时任务"
    
    tasks_list = []
    for task_id, task in scheduled_tasks.items():
        tasks_list.append(f"  - 每日 {task['hour']:02d}:{task['minute']:02d}: {task['message'][:50]}")
    
    return "📋 定时任务列表：\n" + "\n".join(tasks_list)

# ========== 工具定义 ==========
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apply_code_patch",
            "description": "应用代码补丁并推送至 Git 仓库，实现自我修改代码",
            "parameters": {
                "type": "object",
                "properties": {
                    "patch_text": {
                        "type": "string",
                        "description": "统一 diff 格式的补丁内容。例如：--- a/bot.py\\n+++ b/bot.py\\n@@ -12,7 +12,7 @@\\n-bot = commands.Bot(command_prefix='!')\\n+bot = commands.Bot(command_prefix='$')"
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "提交信息，描述这次修改的内容"
                    }
                },
                "required": ["patch_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前时间。只有当用户明确询问时间时才调用。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_daily_message",
            "description": "设置每日定时消息，每天固定时间在当前频道发送消息",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "要发送的消息内容"},
                    "hour": {"type": "integer", "description": "小时 (0-23)"},
                    "minute": {"type": "integer", "description": "分钟 (0-59)"}
                },
                "required": ["message", "hour", "minute"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "列出所有已设置的定时任务",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

SYSTEM_INSTRUCTION = """
你是 Discord 机器人，名叫 Gemini（但实际用的是 Groq）。你的职责：

1. **聊天**：正常对话，友好回复。用户说"你好"时问候即可。
2. **查询时间**：只有用户明确说"现在几点"、"时间"、"几点了"时，才调用 get_time 工具。
3. **修改代码**：只有用户明确说"改代码"、"修改"、"把XX改成XX"时，才调用 apply_code_patch 工具。
4. **定时任务**：用户说"每天X点发消息"、"定时发送"时，调用 set_daily_message 工具。
5. **查看任务**：用户说"查看任务"、"列出任务"时，调用 list_tasks 工具。

**重要规则**：
- 不要主动调用任何工具
- 不要猜测用户意图
- 修改代码前必须先展示补丁，等待用户确认（yes/no）
- 使用中文回复，保持友好、有帮助的语气

现在开始！
"""

class Agent:
    def __init__(self):
        self.history = []
        self.pending_patch = None
        self.waiting_for_confirmation = False
        self.bot = None

    def set_bot(self, bot):
        """设置 bot 实例，用于定时任务"""
        self.bot = bot

    async def run(self, user_input: str, user_id: str, channel=None) -> str:
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 处理确认
        if self.waiting_for_confirmation:
            if user_input.lower() in ["yes", "是", "确认", "同意", "y"]:
                result = apply_code_patch(
                    self.pending_patch["patch"],
                    self.pending_patch.get("message", "Self-modify")
                )
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return result
            elif user_input.lower() in ["no", "不", "取消", "n"]:
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return "❌ 已取消修改。"
            else:
                return "请回复 yes 确认修改，或 no 取消。"

        # 重置命令
        if user_input.strip() in ["!reset", "重置", "清除历史"]:
            self.history = []
            self.waiting_for_confirmation = False
            self.pending_patch = None
            return "✅ 对话已重置，历史已清空"

        try:
            # 构建消息
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})

            # 调用 Groq
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
                tools=TOOLS,
                tool_choice="auto"
            )

            reply = response.choices[0].message

            # 处理工具调用
            if reply.tool_calls:
                for tool_call in reply.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if func_name == "apply_code_patch":
                        patch_text = args.get("patch_text", "")
                        commit_msg = args.get("commit_message", "Self-modify")
                        self.pending_patch = {"patch": patch_text, "message": commit_msg}
                        self.waiting_for_confirmation = True
                        return f"📝 补丁预览：\n```diff\n{patch_text}\n```\n是否应用？回复 yes 或 no"

                    elif func_name == "get_time":
                        result = get_time()
                        self._update_history(user_input, result)
                        return result

                    elif func_name == "set_daily_message":
                        if not self.bot or not channel:
                            result = "❌ 定时任务需要 bot 和频道信息"
                        else:
                            channel_id = str(channel.id)
                            message = args.get("message")
                            hour = args.get("hour")
                            minute = args.get("minute")
                            asyncio.create_task(schedule_daily_message(
                                self.bot, channel_id, message, hour, minute
                            ))
                            result = set_daily_message(channel_id, message, hour, minute)
                        self._update_history(user_input, result)
                        return result

                    elif func_name == "list_tasks":
                        result = list_tasks()
                        self._update_history(user_input, result)
                        return result

            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text

        except Exception as e:
            return f"❌ 错误：{str(e)}"

    def _update_history(self, user_input: str, reply: str):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
