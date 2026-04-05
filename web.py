from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import os
from typing import Optional

from agent import Agent
from db import load_history, save_history
from config import AUTHORIZED_USERS

app = FastAPI(title="Gemini Bot 控制面板", version="1.0.0")

# 获取第一个授权用户作为默认用户
DEFAULT_USER_ID = AUTHORIZED_USERS[0] if AUTHORIZED_USERS else "admin"
agent = Agent(DEFAULT_USER_ID)

class ChatRequest(BaseModel):
    message: str

class ModelRequest(BaseModel):
    model: str

@app.get("/")
async def root():
    """返回控制面板首页"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gemini Bot 控制面板</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { font-size: 2.5em; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }
            .header p { color: rgba(255,255,255,0.9); margin-top: 10px; }
            
            .card {
                background: rgba(255,255,255,0.95);
                border-radius: 20px;
                padding: 25px;
                margin-bottom: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                transition: transform 0.3s;
            }
            .card:hover { transform: translateY(-5px); }
            .card h3 {
                color: #667eea;
                margin-bottom: 20px;
                font-size: 1.5em;
                border-left: 4px solid #667eea;
                padding-left: 15px;
            }
            
            .status-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
            }
            .status-item {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 15px;
                text-align: center;
            }
            .status-label { font-size: 14px; color: #666; margin-bottom: 10px; }
            .status-value { font-size: 28px; font-weight: bold; color: #667eea; }
            .online { color: #10b981; }
            
            .chat-area { display: flex; flex-direction: column; height: 500px; }
            .messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 15px;
                margin-bottom: 20px;
            }
            .message { margin-bottom: 20px; display: flex; animation: fadeIn 0.3s ease; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .user-message { justify-content: flex-end; }
            .bot-message { justify-content: flex-start; }
            .message-content {
                max-width: 70%;
                padding: 12px 18px;
                border-radius: 20px;
                word-wrap: break-word;
            }
            .user-message .message-content {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .bot-message .message-content {
                background: #e5e7eb;
                color: #333;
            }
            
            .input-area { display: flex; gap: 15px; margin-top: 15px; }
            .input-area input {
                flex: 1;
                padding: 15px;
                border: 2px solid #e5e7eb;
                border-radius: 25px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            .input-area input:focus { outline: none; border-color: #667eea; }
            .input-area button {
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
                transition: transform 0.2s;
            }
            .input-area button:hover { transform: scale(1.05); }
            
            .control-bar {
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                align-items: center;
                margin-top: 15px;
            }
            select {
                padding: 10px 20px;
                border: 2px solid #e5e7eb;
                border-radius: 25px;
                font-size: 14px;
                cursor: pointer;
                background: white;
            }
            .btn-secondary {
                background: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 25px;
                cursor: pointer;
                font-weight: bold;
            }
            .btn-danger { background: #dc2626; }
            
            .history-list { max-height: 400px; overflow-y: auto; }
            .history-item {
                padding: 15px;
                border-bottom: 1px solid #e5e7eb;
                transition: background 0.3s;
            }
            .history-item:hover { background: #f8f9fa; }
            .history-role { font-weight: bold; color: #667eea; margin-bottom: 5px; }
            .history-content { color: #666; font-size: 14px; }
            
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .loading { text-align: center; padding: 20px; color: #999; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Gemini Bot 控制面板</h1>
                <p>智能 AI 助手 | 支持多模型切换 | 实时对话</p>
            </div>
            
            <div class="card">
                <h3>📊 系统状态</h3>
                <div class="status-grid">
                    <div class="status-item">
                        <div class="status-label">机器人状态</div>
                        <div class="status-value online" id="status">检查中...</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">当前模型</div>
                        <div class="status-value" id="current-model">-</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">对话条数</div>
                        <div class="status-value" id="history-count">0</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>💬 实时对话</h3>
                <div class="chat-area">
                    <div class="messages" id="chat-messages"><div class="loading">✨ 开始对话吧 ✨</div></div>
                    <div class="input-area">
                        <input type="text" id="message-input" placeholder="输入消息..." onkeypress="if(event.keyCode==13) sendMessage()">
                        <button onclick="sendMessage()">发送消息</button>
                    </div>
                    <div class="control-bar">
                        <select id="model-select">
                            <option value="minimax">🏆 MiniMax M2.5 (综合最强)</option>
                            <option value="glm">🇨🇳 GLM-5 (中文最强)</option>
                            <option value="deepseek">🔍 DeepSeek V3 (推理强)</option>
                            <option value="qwen">🌏 Qwen 2.5 (中文优秀)</option>
                            <option value="gpt">⚡ GPT-OSS 120B (速度最快)</option>
                            <option value="kimi">💬 Kimi K2 (中文好)</option>
                        </select>
                        <button class="btn-secondary" onclick="switchModel()">切换模型</button>
                        <button class="btn-secondary btn-danger" onclick="resetHistory()">重置对话</button>
                        <button class="btn-secondary" onclick="clearChat()">清空界面</button>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>📜 对话历史</h3>
                <div class="history-list" id="history-list"><div class="loading">加载中...</div></div>
            </div>
        </div>
        
        <script>
            async function fetchStatus() {
                try {
                    const res = await fetch('/api/status');
                    const data = await res.json();
                    document.getElementById('status').textContent = data.status === 'online' ? '✅ 在线' : '❌ 离线';
                    document.getElementById('current-model').textContent = data.model.toUpperCase();
                    document.getElementById('history-count').textContent = data.history_length;
                    document.getElementById('model-select').value = data.model;
                } catch(e) { console.error(e); }
            }
            
            async function fetchHistory() {
                try {
                    const res = await fetch('/api/history');
                    const data = await res.json();
                    const historyDiv = document.getElementById('history-list');
                    if (!data.history || data.history.length === 0) {
                        historyDiv.innerHTML = '<div class="loading">暂无对话历史</div>';
                    } else {
                        historyDiv.innerHTML = data.history.slice().reverse().map(msg => `
                            <div class="history-item">
                                <div class="history-role">${msg.role === 'user' ? '👤 你' : '🤖 机器人'}</div>
                                <div class="history-content">${escapeHtml(msg.content.substring(0, 200))}${msg.content.length > 200 ? '...' : ''}</div>
                            </div>
                        `).join('');
                    }
                } catch(e) { console.error(e); }
            }
            
            async function sendMessage() {
                const input = document.getElementById('message-input');
                const message = input.value.trim();
                if (!message) return;
                
                const messagesDiv = document.getElementById('chat-messages');
                const userMsgDiv = document.createElement('div');
                userMsgDiv.className = 'message user-message';
                userMsgDiv.innerHTML = `<div class="message-content">${escapeHtml(message)}</div>`;
                messagesDiv.appendChild(userMsgDiv);
                input.value = '';
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message bot-message';
                loadingDiv.innerHTML = '<div class="message-content"><div class="spinner"></div></div>';
                messagesDiv.appendChild(loadingDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message })
                    });
                    const data = await res.json();
                    loadingDiv.remove();
                    const botMsgDiv = document.createElement('div');
                    botMsgDiv.className = 'message bot-message';
                    botMsgDiv.innerHTML = `<div class="message-content">${escapeHtml(data.response)}</div>`;
                    messagesDiv.appendChild(botMsgDiv);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    fetchStatus();
                    fetchHistory();
                } catch(e) {
                    loadingDiv.innerHTML = '<div class="message-content" style="background:#fee;color:#c00;">❌ 发送失败</div>';
                }
            }
            
            async function switchModel() {
                const model = document.getElementById('model-select').value;
                try {
                    const res = await fetch('/api/model', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ model: model })
                    });
                    const data = await res.json();
                    alert(data.result);
                    fetchStatus();
                } catch(e) { alert('切换失败'); }
            }
            
            async function resetHistory() {
                if (!confirm('确定要重置对话历史吗？')) return;
                try {
                    const res = await fetch('/api/reset', { method: 'POST' });
                    const data = await res.json();
                    alert(data.result);
                    fetchStatus();
                    fetchHistory();
                    document.getElementById('chat-messages').innerHTML = '<div class="loading">✨ 对话已重置 ✨</div>';
                } catch(e) { alert('重置失败'); }
            }
            
            function clearChat() {
                document.getElementById('chat-messages').innerHTML = '<div class="loading">✨ 聊天界面已清空 ✨</div>';
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            fetchStatus();
            fetchHistory();
            setInterval(fetchStatus, 30000);
            setInterval(fetchHistory, 60000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/status")
async def get_status():
    """获取机器人状态"""
    return {
        "status": "online",
        "model": agent.current_model_key,
        "history_length": len(agent.history)
    }

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """发送消息"""
    try:
        result = await agent.run(req.message, None)
        return {"response": result}
    except Exception as e:
        return {"response": f"错误：{str(e)}"}

@app.post("/api/model")
async def switch_model(req: ModelRequest):
    """切换模型"""
    result = agent.switch_model(req.model)
    return {"result": result}

@app.post("/api/reset")
async def reset_history():
    """重置对话历史"""
    agent.history = []
    save_history(DEFAULT_USER_ID, [])
    return {"result": "✅ 对话已重置"}

@app.get("/api/history")
async def get_history():
    """获取对话历史"""
    history = []
    for msg in agent.history:
        history.append({
            "role": msg["role"],
            "content": msg["parts"][0][:500]
        })
    return {"history": history}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
