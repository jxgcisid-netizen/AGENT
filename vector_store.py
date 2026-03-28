import os
import hashlib
import numpy as np
import pinecone
import requests
import time

# Pinecone 配置
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east4-gcp")

MEMORY_INDEX = "discord-memories"
KNOWLEDGE_INDEX = "discord-knowledge"
VECTOR_DIM = 384  # 用 384 维，够用且快

# 初始化 Pinecone
if PINECONE_API_KEY:
    pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
    
    # 获取现有索引列表
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    
    # 创建记忆索引（如果不存在）
    if MEMORY_INDEX not in existing_indexes:
        print(f"创建索引: {MEMORY_INDEX}")
        pc.create_index(
            name=MEMORY_INDEX,
            dimension=VECTOR_DIM,
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(2)  # 等待索引创建完成
    memory_index = pc.Index(MEMORY_INDEX)
    
    # 创建知识库索引（如果不存在）
    if KNOWLEDGE_INDEX not in existing_indexes:
        print(f"创建索引: {KNOWLEDGE_INDEX}")
        pc.create_index(
            name=KNOWLEDGE_INDEX,
            dimension=VECTOR_DIM,
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(2)
    knowledge_index = pc.Index(KNOWLEDGE_INDEX)
    
    print("✅ Pinecone 向量存储已配置")
else:
    memory_index = None
    knowledge_index = None
    print("⚠️ Pinecone 未配置")

def get_embedding(text: str) -> list:
    """获取文本的 embedding"""
    # 简单伪 embedding（384 维，归一化）
    hash_val = hashlib.md5(text.encode()).hexdigest()
    emb = []
    for i in range(VECTOR_DIM):
        # 用哈希值生成伪向量
        idx = i % len(hash_val)
        val = int(hash_val[idx], 16) / 15.0
        emb.append(float(val))
    
    # 归一化
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = [float(x / norm) for x in emb]
    return emb

# ========== 记忆功能 ==========
def save_memory(user_id: str, text: str, metadata: dict = None):
    if not memory_index:
        return
    try:
        memory_id = f"{user_id}_{hashlib.md5(text.encode()).hexdigest()[:16]}"
        embedding = get_embedding(text)
        memory_index.upsert(vectors=[{
            "id": memory_id,
            "values": embedding,
            "metadata": metadata or {"text": text, "user_id": user_id}
        }])
    except Exception as e:
        print(f"保存记忆失败: {e}")

def search_memory(user_id: str, query: str, top_k: int = 3) -> list:
    if not memory_index:
        return []
    try:
        query_embedding = get_embedding(query)
        results = memory_index.query(
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
    except Exception as e:
        print(f"搜索记忆失败: {e}")
        return []

# ========== 知识库功能 ==========
def add_knowledge(text: str, metadata: dict = None):
    if not knowledge_index:
        return
    try:
        doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
        embedding = get_embedding(text)
        knowledge_index.upsert(vectors=[{
            "id": doc_id,
            "values": embedding,
            "metadata": metadata or {"text": text}
        }])
        print(f"✅ 添加知识: {text[:50]}...")
    except Exception as e:
        print(f"添加知识失败: {e}")

def search_knowledge(query: str, top_k: int = 3) -> list:
    if not knowledge_index:
        return []
    try:
        query_embedding = get_embedding(query)
        results = knowledge_index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        docs = []
        for match in results.matches:
            if match.metadata and 'text' in match.metadata:
                docs.append(match.metadata['text'])
        return docs
    except Exception as e:
        print(f"搜索知识失败: {e}")
        return []

def init_knowledge():
    """初始化知识库"""
    if not knowledge_index:
        return
    
    try:
        stats = knowledge_index.describe_index_stats()
        if stats.total_vector_count > 0:
            print(f"知识库已有 {stats.total_vector_count} 条数据，跳过初始化")
            return
    except:
        pass
    
    docs = [
        "机器人名称：ROB Bot，功能包括查询时间、联网搜索、读取文件、修改代码、定时提醒",
        "可用模型：gpt（智商最高、速度最快）、kimi（中文最好）、deepseek（推理强）、qwen（中文强）",
        "使用方法：私聊直接发消息，服务器里 @机器人 发消息，用 /model 切换模型",
        "斜杠命令：/model 切换模型，/reset 重置对话，/help 查看帮助",
        "功能示例：'现在几点'查时间、'搜索 Python'联网搜索、'读取 bot.py'读文件、'把命令前缀改成 $'改代码"
    ]
    for doc in docs:
        add_knowledge(doc)
    print("✅ 知识库初始化完成")
