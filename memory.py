import os
import numpy as np
import pinecone
import requests
import hashlib

# Pinecone 配置
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east4-gcp")
INDEX_NAME = "discord-memories"

# 初始化 Pinecone
if PINECONE_API_KEY:
    pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
    
    # 创建索引（如果不存在）
    if INDEX_NAME not in pc.list_indexes().names():
        pc.create_index(
            name=INDEX_NAME,
            dimension=1536,  # OpenAI embedding 维度
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
        )
    index = pc.Index(INDEX_NAME)
    print("✅ Pinecone 已配置")
else:
    index = None
    print("⚠️ Pinecone 未配置")

def get_embedding(text: str) -> list:
    """获取文本的 embedding（使用 Groq embedding 或模拟）"""
    # 简化版：用 Groq embedding（需要额外 Key）
    # 这里用简单哈希模拟，实际使用时建议用 OpenAI 或 Groq embedding API
    import hashlib
    hash_val = hashlib.md5(text.encode()).hexdigest()
    # 生成一个伪 embedding（实际应用需要真实的 embedding 模型）
    return [float(int(hash_val[i:i+2], 16)) / 255 for i in range(0, 32, 2)] + [0] * 1504

def save_memory(user_id: str, text: str, metadata: dict = None):
    """保存记忆到 Pinecone"""
    if not index:
        return
    
    memory_id = f"{user_id}_{hashlib.md5(text.encode()).hexdigest()[:16]}"
    embedding = get_embedding(text)
    
    index.upsert(vectors=[{
        "id": memory_id,
        "values": embedding,
        "metadata": metadata or {"text": text, "user_id": user_id}
    }])

def search_memory(user_id: str, query: str, top_k: int = 3) -> list:
    """搜索相关记忆"""
    if not index:
        return []
    
    query_embedding = get_embedding(query)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        filter={"user_id": user_id},
        include_metadata=True
    )
    
    memories = []
    for match in results.matches:
        if match.metadata and 'text' in match.metadata:
            memories.append(match.metadata['text'])
    return memories
