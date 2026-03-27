import os
import google.generativeai as genai

# 配置 Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以回答问题、帮助用户。请用中文回复，保持友好、有帮助的语气。
"""

class Agent:
    def __init__(self):
        self.history = []

    async def run(self, user_input: str, user_id: str) -> str:
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        try:
            # 创建模型实例
            model = genai.GenerativeModel(
                MODEL_NAME,
                system_instruction=SYSTEM_INSTRUCTION
            )
            
            # 开始对话（带历史）
            chat = model.start_chat(history=self.history)
            response = chat.send_message(user_input)
            reply = response.text
            
            # 更新历史
            self.history.append({"role": "user", "parts": [user_input]})
            self.history.append({"role": "model", "parts": [reply]})
            
            return reply
            
        except Exception as e:
            error_msg = str(e)
            print(f"错误: {error_msg}")
            
            if "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                return "❌ Gemini API 配额暂时不可用，请稍后再试。如果是第一次使用，可能需要等待几分钟让 API Key 生效。"
            
            return f"❌ 错误：{error_msg[:200]}"
