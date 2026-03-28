import os
import requests

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "https://cloud.dify.ai/v1")

def query_knowledge(question: str) -> str:
    """查询知识库"""
    if not DIFY_API_KEY:
        return None
    
    try:
        response = requests.post(
            f"{DIFY_BASE_URL}/chat-messages",
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "inputs": {},
                "query": question,
                "response_mode": "blocking",
                "user": "discord-bot"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("answer")
        else:
            print(f"知识库查询失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"知识库错误: {e}")
        return None
