import os
from groq import Groq
from datetime import datetime

# 配置 Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile"

SYSTEM_INSTRUCTION = "你是 Discord 机器人，用中文友好回复。"

class Agent:
    def __init__(self):
        self.history = []

    async def run(self, user_input: str, user_id: str, channel=None) -> str:
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 重置命令
        if user_input.strip() in ["!reset", "重置"]:
            self.history = []
            return "✅ 对话已重置"

        try:
            # 构建消息
            messages = []
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})

            # 调用 API
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )

            reply = response.choices[0].message.content
            
            # 保存历史
            self.history.append({"role": "user", "parts": [user_input]})
            self.history.append({"role": "assistant", "parts": [reply]})
            
            return reply

        except Exception as e:
            return f"❌ API 错误：{str(e)}"
