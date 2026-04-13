from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import os
import asyncio

from agent import Agent
from db import load_history, save_history
from config import AUTHORIZED_USERS

app = FastAPI(title="Nexus Bot", version="1.0.0")

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
        <title>Nexus · 智能控制台</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300;14..32,400;14..32,500;14..32,600;14..32,700&display=swap" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: #0a0a0f;
                color: #e8e8f0;
                min-height: 100vh;
            }

            ::-webkit-scrollbar {
                width: 5px;
                height: 5px;
            }
            ::-webkit-scrollbar-track {
                background: #1a1a24;
                border-radius: 10px;
            }
            ::-webkit-scrollbar-thumb {
                background: #3a3a4a;
                border-radius: 10px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #5a5a6a;
            }

            .app {
                display: flex;
                height: 100vh;
                overflow: hidden;
            }

            .sidebar {
                width: 280px;
                background: rgba(18, 18, 26, 0.95);
                backdrop-filter: blur(20px);
                border-right: 1px solid rgba(255,255,255,0.06);
                display: flex;
                flex-direction: column;
                padding: 24px 16px;
                flex-shrink: 0;
            }

            .logo {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 32px;
                padding: 0 12px;
            }
            .logo-icon {
                width: 40px;
                height: 40px;
                background: linear-gradient(135deg, #6366f1, #a855f7);
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
            }
            .logo-text h2 {
                font-size: 18px;
                font-weight: 600;
                letter-spacing: -0.3px;
            }
            .logo-text p {
                font-size: 12px;
                color: #8b8b9b;
                margin-top: 2px;
            }

            .nav-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px 16px;
                border-radius: 12px;
                color: #a1a1b0;
                transition: all 0.2s ease;
                cursor: pointer;
                margin-bottom: 4px;
            }
            .nav-item:hover {
                background: rgba(255,255,255,0.05);
                color: #fff;
            }
            .nav-item.active {
                background: rgba(99,102,241,0.15);
                color: #818cf8;
            }
            .sidebar-footer {
                margin-top: auto;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.06);
            }
            .status-badge {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px 16px;
                background: rgba(0,0,0,0.3);
                border-radius: 12px;
            }
            .status-dot {
                width: 8px;
                height: 8px;
                background: #10b981;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            .main {
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                background: #0d0d12;
            }

            .header {
                padding: 20px 32px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
                background: rgba(13,13,18,0.8);
                backdrop-filter: blur(10px);
            }
            .header h1 {
                font-size: 24px;
                font-weight: 600;
                letter-spacing: -0.5px;
            }
            .header p {
                font-size: 13px;
                color: #8b8b9b;
                margin-top: 4px;
            }

            .content {
                flex: 1;
                overflow-y: auto;
                padding: 24px 32px;
            }

            .stats-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 20px;
                margin-bottom: 28px;
            }
            .stat-card {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 20px;
                transition: all 0.2s ease;
            }
            .stat-card:hover {
                background: rgba(255,255,255,0.05);
                border-color: rgba(99,102,241,0.3);
            }
            .stat-value {
                font-size: 32px;
                font-weight: 700;
                background: linear-gradient(135deg, #fff, #a855f7);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .stat-label {
                font-size: 13px;
                color: #8b8b9b;
                margin-top: 6px;
            }

            .chat-card {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 24px;
                padding: 24px;
                margin-bottom: 28px;
            }
            .chat-title {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 20px;
                font-weight: 500;
            }

            .messages {
                height: 360px;
                overflow-y: auto;
                background: rgba(0,0,0,0.3);
                border-radius: 16px;
                padding: 16px;
                margin-bottom: 20px;
            }
            .message {
                margin-bottom: 16px;
                display: flex;
                animation: fadeIn 0.3s ease;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .user-message { justify-content: flex-end; }
            .bot-message { justify-content: flex-start; }
            .message-content {
                max-width: 70%;
                padding: 10px 16px;
                border-radius: 18px;
                font-size: 14px;
                line-height: 1.5;
            }
            .user-message .message-content {
                background: linear-gradient(135deg, #6366f1, #a855f7);
                color: white;
                border-bottom-right-radius: 4px;
            }
            .bot-message .message-content {
                background: rgba(255,255,255,0.07);
                color: #e0e0e8;
                border-bottom-left-radius: 4px;
            }

            .cursor {
                display: inline-block;
                width: 2px;
                height: 1.2em;
                background-color: #818cf8;
                animation: blink 1s infinite;
                vertical-align: middle;
                margin-left: 2px;
            }
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0; }
            }

            .input-area {
                display: flex;
                gap: 12px;
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 48px;
                padding: 6px 6px 6px 20px;
            }
            .input-area input {
                flex: 1;
                background: transparent;
                border: none;
                padding: 12px 0;
                color: #fff;
                font-size: 14px;
                outline: none;
            }
            .input-area input::placeholder {
                color: #5a5a6a;
            }
            .input-area button {
                background: linear-gradient(135deg, #6366f1, #a855f7);
                border: none;
                padding: 8px 24px;
                border-radius: 40px;
                color: white;
                font-weight: 500;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .input-area button:hover {
                transform: scale(1.02);
                box-shadow: 0 4px 12px rgba(99,102,241,0.4);
            }

            .controls {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-top: 16px;
                align-items: center;
            }
            select {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                padding: 8px 16px;
                border-radius: 40px;
                color: #fff;
                font-size: 13px;
                cursor: pointer;
                outline: none;
            }
            select option {
                background: #1a1a24;
            }
            .btn {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                padding: 8px 16px;
                border-radius: 40px;
                color: #c0c0d0;
                font-size: 13px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .btn:hover {
                background: rgba(255,255,255,0.1);
                color: #fff;
            }
            .btn-danger:hover {
                background: rgba(220,38,38,0.3);
                border-color: rgba(220,38,38,0.5);
                color: #f87171;
            }

            .history-card {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 24px;
                padding: 24px;
            }
            .history-list {
                max-height: 300px;
                overflow-y: auto;
            }
            .history-item {
                padding: 14px 0;
                border-bottom: 1px solid rgba(255,255,255,0.04);
                transition: background 0.2s;
            }
            .history-item:hover {
                background: rgba(255,255,255,0.02);
                padding-left: 8px;
            }
            .history-role {
                font-size: 12px;
                font-weight: 600;
                margin-bottom: 6px;
            }
            .history-role.user { color: #a78bfa; }
            .history-role.bot { color: #60a5fa; }
            .history-content {
                font-size: 13px;
                color: #9ca3af;
                line-height: 1.4;
            }

            .spinner {
                width: 24px;
                height: 24px;
                border: 2px solid rgba(255,255,255,0.2);
                border-top-color: #818cf8;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }

            @media (max-width: 768px) {
                .sidebar { display: none; }
                .content { padding: 16px; }
                .stats-grid { grid-template-columns: 1fr; }
                .message-content { max-width: 85%; }
            }
        </style>
    </head>
    <body>
        <div class="app">
            <div class="sidebar">
                <div class="logo">
                    <div class="logo-icon">✨</div>
                    <div class="logo-text">
                        <h2>Nexus</h2>
                        <p>智能控制台</p>
                    </div>
                </div>
                
                <div class="nav-item active" onclick="switchTab('chat')">
                    <span>💬</span>
                    <span>对话</span>
                </div>
                <div class="nav-item" onclick="switchTab('history')">
                    <span>📜</span>
                    <span>历史记录</span>
                </div>
                
                <div class="sidebar-footer">
                    <div class="status-badge">
                        <div class="status-dot"></div>
                        <span style="font-size: 13px;" id="status-text">在线</span>
                    </div>
                </div>
            </div>

            <div class="main">
                <div class="header">
                    <h1 id="current-model-display">Nexus · MiniMax</h1>
                    <p>智能 AI 助手 | 实时对话 | 多模型切换</p>
                </div>

                <div class="content">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value" id="status-value">●</div>
                            <div class="stat-label">状态</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="model-value">---</div>
                            <div class="stat-label">当前模型</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="history-count">0</div>
                            <div class="stat-label">对话条数</div>
                        </div>
                    </div>

                    <div id="chat-tab">
                        <div class="chat-card">
                            <div class="chat-title">
                                <span>💬</span>
                                <span>实时对话</span>
                            </div>
                            <div class="messages" id="chat-messages">
                                <div style="text-align:center; padding:40px; color:#5a5a6a;">✨ 开始对话吧 ✨</div>
                            </div>
                            <div class="input-area">
                                <input type="text" id="message-input" placeholder="输入消息..." onkeypress="if(event.keyCode==13) sendMessage()">
                                <button onclick="sendMessage()">发送</button>
                            </div>
                            <div class="controls">
                                <select id="model-select">
                                    <option value="minimax">MiniMax M2.5 · 综合最强</option>
                                    <option value="glm">GLM-5 · 中文最强</option>
                                    <option value="deepseek">DeepSeek V3 · 推理强</option>
                                    <option value="qwen">Qwen 2.5 · 中文优秀</option>
                                    <option value="gpt">GPT-OSS 120B · 速度最快</option>
                                    <option value="kimi">Kimi K2 · 中文好</option>
                                </select>
                                <button class="btn" onclick="switchModel()">切换</button>
                                <button class="btn btn-danger" onclick="resetHistory()">重置</button>
                                <button class="btn" onclick="clearChat()">清空</button>
                            </div>
                        </div>
                    </div>

                    <div id="history-tab" style="display: none;">
                        <div class="history-card">
                            <div class="chat-title">
                                <span>📜</span>
                                <span>对话历史</span>
                            </div>
                            <div class="history-list" id="history-list">
                                <div style="text-align:center; padding:40px; color:#5a5a6a;">加载中...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentTab = 'chat';

            function switchTab(tab) {
                currentTab = tab;
                document.getElementById('chat-tab').style.display = tab === 'chat' ? 'block' : 'none';
                document.getElementById('history-tab').style.display = tab === 'history' ? 'block' : 'none';
                document.querySelectorAll('.nav-item').forEach((item, idx) => {
                    if ((tab === 'chat' && idx === 0) || (tab === 'history' && idx === 1)) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                });
                if (tab === 'history') fetchHistory();
            }

            async function fetchStatus() {
                try {
                    const res = await fetch('/api/status');
                    const data = await res.json();
                    const isOnline = data.status === 'online';
                    document.getElementById('status-value').innerHTML = isOnline ? '●' : '○';
                    document.getElementById('status-value').style.color = isOnline ? '#10b981' : '#ef4444';
                    document.getElementById('status-text').textContent = isOnline ? '在线' : '离线';
                    document.getElementById('model-value').textContent = data.model.toUpperCase();
                    document.getElementById('history-count').textContent = data.history_length;
                    document.getElementById('current-model-display').textContent = 'Nexus · ' + data.model.toUpperCase();
                    document.getElementById('model-select').value = data.model;
                } catch(e) { console.error(e); }
            }

            async function fetchHistory() {
                try {
                    const res = await fetch('/api/history');
                    const data = await res.json();
                    const historyDiv = document.getElementById('history-list');
                    if (!data.history || data.history.length === 0) {
                        historyDiv.innerHTML = '<div style="text-align:center; padding:40px; color:#5a5a6a;">暂无对话历史</div>';
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
                
                // 显示用户消息
                const userMsgDiv = document.createElement('div');
                userMsgDiv.className = 'message user-message';
                userMsgDiv.innerHTML = `<div class="message-content">${escapeHtml(message)}</div>`;
                messagesDiv.appendChild(userMsgDiv);
                input.value = '';
                
                // 创建机器人消息占位符
                const botMsgDiv = document.createElement('div');
                botMsgDiv.className = 'message bot-message';
                botMsgDiv.innerHTML = `<div class="message-content"><span class="cursor">▊</span></div>`;
                messagesDiv.appendChild(botMsgDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
                const contentDiv = botMsgDiv.querySelector('.message-content');
                
                try {
                    const response = await fetch('/api/chat/stream', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message })
                    });
                    
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let fullText = '';
                    
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        const chunk = decoder.decode(value);
                        fullText += chunk;
                        contentDiv.innerHTML = escapeHtml(fullText) + '<span class="cursor">▊</span>';
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                    
                    // 移除光标
                    contentDiv.innerHTML = escapeHtml(fullText);
                    
                } catch(e) {
                    contentDiv.innerHTML = '❌ 发送失败';
                }
                
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                fetchStatus();
                if (currentTab === 'history') fetchHistory();
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
                    document.getElementById('chat-messages').innerHTML = '<div style="text-align:center; padding:40px; color:#5a5a6a;">✨ 对话已重置 ✨</div>';
                } catch(e) { alert('重置失败'); }
            }

            function clearChat() {
                document.getElementById('chat-messages').innerHTML = '<div style="text-align:center; padding:40px; color:#5a5a6a;">✨ 聊天界面已清空 ✨</div>';
            }

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            fetchStatus();
            fetchHistory();
            setInterval(fetchStatus, 30000);
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


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式响应接口"""
    async def generate():
        try:
            result = await agent.run(req.message, None)
            for char in result:
                yield char
                await asyncio.sleep(0.01)  # 10ms 一个字
        except Exception as e:
            yield f"错误：{str(e)}"
    
    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """非流式响应接口（备用）"""
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
