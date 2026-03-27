import os
import google.genai as genai
from google.genai import types
from git_manager import GitManager

# 配置 Gemini 客户端
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# 定义工具函数
def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    """应用代码补丁并推送至 Git 仓库"""
    gm = GitManager(repo_path=os.getcwd())
    success = gm.apply_patch(patch_text, commit_message)
    if success:
        return "✅ 代码已修改并推送，Railway 将自动重新部署。"
    else:
        return "❌ 修改失败，请检查补丁格式。"

# 工具声明（新版 SDK 格式）
tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="apply_code_patch",
                description="应用代码补丁并推送至 Git 仓库。",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "patch_text": types.Schema(
                            type=types.Type.STRING,
                            description="统一 diff 格式的补丁内容"
                        ),
                        "commit_message": types.Schema(
                            type=types.Type.STRING,
                            description="提交信息（默认 'Self-modify'）"
                        )
                    },
                    required=["patch_text"]
                )
            )
        ]
    )
]

# 系统指令
SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以管理自己的代码。当用户要求修改代码（例如改配置、新增功能、修复 bug）时，你应该：
1. 分析当前代码文件
2. 生成所需的补丁（统一 diff 格式）
3. 调用 apply_code_patch 工具来应用补丁
在调用前，向用户展示补丁内容并等待确认。只有在用户明确同意后才执行。
如果用户只是普通对话，则正常回复。
"""

class Agent:
    def __init__(self):
        self.history = []
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools,
            temperature=0.7,
            max_output_tokens=8192,
        )

    async def run(self, user_input: str, user_id: str) -> str:
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 添加用户消息到历史
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))

        # 调用 Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=self.history,
            config=self.config
        )

        # 检查是否有函数调用
        if response.function_calls:
            fc = response.function_calls[0]
            if fc.name == "apply_code_patch":
                # 执行函数
                args = {k: v for k, v in fc.args.items()}
                result = apply_code_patch(**args)
                
                # 添加模型响应（函数调用）
                self.history.append(types.Content(
                    role="model",
                    parts=[types.Part(function_call=fc)]
                ))
                
                # 添加函数响应
                self.history.append(types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result}
                    ))]
                ))
                
                # 获取最终回复
                final_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=self.history,
                    config=self.config
                )
                
                reply = final_response.text
                self.history.append(types.Content(role="model", parts=[types.Part(text=reply)]))
                return reply
            else:
                return f"未知函数调用: {fc.name}"
        else:
            # 无函数调用，直接返回文本
            reply = response.text
            self.history.append(types.Content(role="model", parts=[types.Part(text=reply)]))
            return reply
