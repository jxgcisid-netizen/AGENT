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

app = FastAPI(title="Nexus Bot 控制面板", version="1.0.0")

DEFAULT_USER_ID = AUTHORIZED_USERS[0] if AUTHORIZED_USERS else "admin"
agent = Agent(DEFAULT_USER_ID)

class ChatRequest(BaseModel):
    message: str

class ModelRequest(BaseModel):
    model: str

@app.get("/")
async def root():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <title>Nexus Bot | 智能控制台</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
                min-height: 100vh;
                color: #fff;
            }

            /* 自定义滚动条 */
            ::-webkit-scrollbar {
                width: 6px;
                height: 6px;
            }
            ::-webkit-scrollbar-track {
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(255,255,255,0.2);
                border-radius: 10px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(255,255,255,0.3);
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }

            /* 头部 */
            .header {
                text-align: center;
                margin-bottom: 40px;
                position: relative;
            }
            .header h1 {
                font-size: 3rem;
                font-weight: 700;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                letter-spacing: -0.5px;
            }
            .header p {
                color: rgba(255,255,255,0.6);
                margin-top: 10px;
                font-size: 1rem;
            }
            .glow {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 300px;
                height: 300px;
                background: radial-gradient(circle, rgba(102,126,234,0.3) 0%, rgba(118,75,162,0) 70%);
                border-radius: 50%;
                z-index: -1;
            }

            /* 卡片 */
            .card {
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                border-radius: 24px;
                padding: 28px;
                margin-bottom: 24px;
                border: 1px solid rgba(255,255,255,0.1);
                transition: all 0.3s ease;
            }
            .card:hover {
                border-color: rgba(102,126,234,0.5);
                transform: translateY(-2px);
            }
            .card h3 {
                font-size: 1.25rem;
                font-weight: 600;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .card h3 i {
                font-size: 1.5rem;
            }

            /* 状态网格 */
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }
            .stat-card {
                background: rgba(0,0,0,0.3);
                border-radius: 20px;
                padding: 20px;
                text-align: center;
                transition: all 0.3s ease;
            }
            .stat-card:hover {
                background: rgba(0,0,0,0.4);
                transform: scale(1.02);
            }
            .stat-value {
                font-size: 2.5rem;
                font-weight: 700;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .stat-label {
                font-size: 0.85rem;
                color: rgba(255,255,255,0.6);
                margin-top: 8px;
            }

            /* 聊天区域 */
            .chat-container {
                display: flex;
                flex-direction: column;
                height: 500px;
            }
            .messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background: rgba(0,0,0,0.2);
                border-radius: 20px;
                margin-bottom: 20px;
            }
            .message {
                margin-bottom: 20px;
                display: flex;
                animation: fadeInUp 0.3s ease;
            }
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            .user-message { justify-content: flex-end; }
            .bot-message { justify-content: flex-start; }
            .message-content {
                max-width: 75%;
                padding: 12px 20px;
                border-radius: 20px;
                font-size: 0.95rem;
                line-height: 1.5;
            }
            .user-message .message-content {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border-bottom-right-radius: 4px;
            }
            .bot-message .message-content {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(5px);
                color: #fff;
                border-bottom-left-radius: 4px;
            }

            /* 输入区域 */
            .input-area {
                display: flex;
                gap: 15px;
                background: rgba(255,255,255,0.05);
                border-radius: 50px;
                padding: 8px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .input-area input {
                flex: 1;
                background: transparent;
                border: none;
                padding: 14px 20px;
                color: white;
                font-size: 1rem;
                outline: none;
            }
            .input-area input::placeholder {
                color: rgba(255,255,255,0.4);
            }
            .input-area button {
                background: linear-gradient(135deg, #667eea, #764ba2);
                border: none;
                padding: 12px 28px;
                border-radius: 40px;
                color: white;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .input-area button:hover {
                transform: scale(1.02);
                box-shadow: 0 4px 15px rgba(102,126,234,0.4);
            }

            /* 控制栏 */
            .controls {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-top: 20px;
                align-items: center;
            }
            select {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                padding: 10px 20px;
                border-radius: 40px;
                color: white;
                font-size: 0.9rem;
                cursor: pointer;
                outline: none;
            }
            select option {
                background: #1a1a2e;
            }
            .btn {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                padding: 10px 20px;
                border-radius: 40px;
                color: white;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .btn:hover {
                background: rgba(255,255,255,0.2);
            }
            .btn-danger:hover {
                background: rgba(220,38,38,0.6);
                border-color: rgba(220,38,38,0.5);
            }

            /* 历史记录 */
            .history-list {
                max-height: 350px;
                overflow-y: auto;
            }
            .history-item {
                padding: 15px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
                transition: background 0.3s ease;
            }
            .history-item:hover {
                background: rgba(255,255,255,0.03);
            }
            .history-role {
                font-weight: 600;
                font-size: 0.8rem;
                margin-bottom: 5px;
            }
            .history-role.user { color: #a78bfa; }
            .history-role.bot { color: #60a5fa; }
            .history-content {
                font-size: 0.85rem;
                color: rgba(255,255,255,0.7);
                line-height: 1.4;
            }

            /* 加载动画 */
            .spinner {
                width: 30px;
                height: 30px;
                border: 2px solid rgba(255,255,255,0.2);
                border-top-color: #667eea;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .loading-text {
                text-align: center;
                padding: 40px;
                color: rgba(255,255,255,0.5);
            }

            /* 响应式 */
            @media (max-width: 768px) {
                .container { padding: 15px; }
                .header h1 { font-size: 2rem; }
                .message-content { max-width: 85%; }
                .controls { justify-content: center; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="glow"></div>
                <h1>✨ Nexus Bot</h1>
                <p>智能 AI 助手 | 实时对话 | 多模型切换</p>
            </div>

            <!-- 状态卡片 -->
            <div class="card">
                <h3><span>📊</span> 系统状态</h3>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value" id="status">---</div>
                        <div class="stat-label">机器人状态</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="current-model">---</div>
                        <div class="stat-label">当前模型</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="history-count">0</div>
                        <div class="stat-label">对话条数</div>
                    </div>
                </div>
            </div>

            <!-- 聊天卡片 -->
            <div class="card">
                <h3><span>💬</span> 实时对话</h3>
                <div class="chat-container">
                    <div class="messages" id="chat-messages">
                        <div class="loading-text">✨ 开始对话吧 ✨</div>
                    </div>
                    <div class="input-area">
                        <input type="text" id="message-input" placeholder="输入消息..." onkeypress="if(event.keyCode==13) sendMessage()">
                        <button onclick="sendMessage()">发送</button>
                    </div>
                    <div class="controls">
                        <select id="model-select">
                            <option value="minimax">🏆 MiniMax M2.5 (综合最强)</option>
                            <option value="glm">🇨🇳 GLM-5 (中文最强)</option>
                            <option value="deepseek">🔍 DeepSeek V3 (推理强)</option>
                            <option value="qwen">🌏 Qwen 2.5 (中文优秀)</option>
                            <option value="gpt">⚡ GPT-OSS 120B (速度最快)</option>
                            <option value="kimi">💬 Kimi K2 (中文好)</option>
                        </select>
                        <button class="btn" onclick="switchModel()">切换模型</button>
                        <button class="btn btn-danger" onclick="resetHistory()">重置对话</button>
                        <button class="btn" onclick="clearChat()">清空界面</button>
                    </div>
                </div>
            </div>

            <!-- 历史记录卡片 -->
            <div class="card">
                <h3><span>📜</span> 对话历史</h3>
                <div class="history-list" id="history-list">
                    <div class="loading-text">加载中...</div>
                </div>
            </div>
        </div>

        <script>
            async function fetchStatus() {
                try {
                    const res = await fetch('/api/status');
                    const data = await res.json();
                    document.getElementById('status').innerHTML = data.status === 'online' ? '<span style="color:#10b981;">● 在线</span>' : '<span style="color:#ef4444;">● 离线</span>';
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
                        historyDiv.innerHTML = '<div class="loading-text">暂无对话历史</div>';
                    } else {
                        historyDiv.innerHTML = data.history.slice().reverse().map(msg => `
                            <div class="history-item">
                                <div class="history-role ${msg.role === 'user' ? 'user' : 'bot'}">${msg.role === 'user' ? '👤 你' : '🤖 机器人'}</div>
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
                loadingDiv.innerHTML = `<div class="message-content"><div class="spinner"></div></div>`;
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
                    loadingDiv.innerHTML = `<div class="message-content" style="background:rgba(220,38,38,0.3);">❌ 发送失败</div>`;
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
                    document.getElementById('chat-messages').innerHTML = '<div class="loading-text">✨ 对话已重置 ✨</div>';
                } catch(e) { alert('重置失败'); }
            }

            function clearChat() {
                document.getElementById('chat-messages').innerHTML = '<div class="loading-text">✨ 聊天界面已清空 ✨</div>';
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
    return {
        "status": "online",
        "model": agent.current_model_key,
        "history_length": len(agent.history)
    }

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        result = await agent.run(req.message, None)
        return {"response": result}
    except Exception as e:
        return {"response": f"错误：{str(e)}"}

@app.post("/api/model")
async def switch_model(req: ModelRequest):
    result = agent.switch_model(req.model)
    return {"result": result}

@app.post("/api/reset")
async def reset_history():
    agent.history = []
    save_history(DEFAULT_USER_ID, [])
    return {"result": "✅ 对话已重置"}

@app.get("/api/history")
async def get_history():
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
