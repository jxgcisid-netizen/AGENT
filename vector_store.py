import os
import json
import hashlib
import numpy as np
import pinecone
import requests
import time

# ========== 路径配置 ==========
if os.path.exists("/data") and os.access("/data", os.W_OK):
    DATA_DIR = "/data"
else:
    DATA_DIR = os.getcwd()

# ========== Pinecone 配置 ==========
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east4-gcp")

MEMORY_INDEX = "discord-memories"
KNOWLEDGE_INDEX = "discord-knowledge"
VECTOR_DIM = 384

# 初始化 Pinecone
if PINECONE_API_KEY:
    pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
    
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    
    if MEMORY_INDEX not in existing_indexes:
        print(f"创建索引: {MEMORY_INDEX}")
        pc.create_index(
            name=MEMORY_INDEX,
            dimension=VECTOR_DIM,
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(2)
    memory_index = pc.Index(MEMORY_INDEX)
    
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
    """获取文本的 embedding（384 维，归一化）"""
    hash_val = hashlib.md5(text.encode()).hexdigest()
    emb = []
    for i in range(VECTOR_DIM):
        idx = i % len(hash_val)
        val = int(hash_val[idx], 16) / 15.0
        emb.append(float(val))
    
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = [float(x / norm) for x in emb]
    return emb

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
        "机器人名称：Nexus Bot，功能包括查询时间、联网搜索、读取文件、修改代码、定时提醒",
        "可用模型：gpt（智商最高、速度最快）、kimi（中文最好）、deepseek（推理强）、qwen（中文强）",
        "使用方法：私聊直接发消息，服务器里 @机器人 发消息，用 /model 切换模型",
        "斜杠命令：/model 切换模型，/reset 重置对话，/help 查看帮助",
        "功能示例：'现在几点'查时间、'搜索 Python'联网搜索、'读取 bot.py'读文件、'把命令前缀改成 $'改代码"
    ]
    for doc in docs:
        add_knowledge(doc)
    print("✅ 知识库初始化完成")

# 定时任务存储
scheduled_tasks = {}
one_time_tasks = {}
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

def save_tasks():
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump({
                "scheduled": scheduled_tasks,
                "one_time": one_time_tasks
            }, f)
    except Exception as e:
        print(f"保存任务失败: {e}")

def load_tasks():
    global scheduled_tasks, one_time_tasks
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r") as f:
                data = json.load(f)
                scheduled_tasks = data.get("scheduled", {})
                one_time_tasks = data.get("one_time", {})
    except Exception as e:
        print(f"加载任务失败: {e}")

load_tasks()
