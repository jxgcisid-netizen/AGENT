import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from agent import Agent
from flask import Flask
import threading
import time
from functools import wraps

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ========== 性能优化：消息队列 + 限流 ==========
class RateLimiter:
    """简单的限流器"""
    def __init__(self, max_calls=5, time_window=10):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = {}
    
    def is_allowed(self, user_id):
        now = time.time()
        if user_id not in self.calls:
            self.calls[user_id] = []
        # 清理过期记录
        self.calls[user_id] = [t for t in self.calls[user_id] if now - t < self.time_window]
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        self.calls[user_id].append(now)
        return True

rate_limiter = RateLimiter(max_calls=10, time_window=60)  # 每分钟最多10次

# ========== 健康检查服务器 ==========
health_app = Flask('')

@health_app.route('/')
def health():
    return 'OK'

def run_health():
    health_app.run(host='0.0.0.0', port=8000)

threading.Thread(target=run_health, daemon=True).start()

# ========== Discord Bot ==========
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)
user_agents = {}
user_channels = {}

# 消息队列（异步处理，避免阻塞）
message_queue = asyncio.Queue()
queue_worker_running = True

async def message_worker():
    """后台处理消息队列"""
    while queue_worker_running:
        try:
            message, user_id, channel = await asyncio.wait_for(message_queue.get(), timeout=1)
            agent = get_agent(user_id)
            result = await agent.run(message, channel)
            if result:
                await channel.send(result)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"队列处理错误: {e}")

def get_agent(user_id: str) -> Agent:
    if user_id not in user_agents:
        user_agents[user_id] = Agent(user_id)
        user_agents[user_id].set_bot(bot)
    return user_agents[user_id]

def create_embed(title: str, content: str, color: int = 0x00ff00, footer: str = None):
    embed = discord.Embed(title=title, description=content, color=color)
    embed.set_footer(text=footer or "🤖 Gemini 智能助手")
    return embed

@bot.event
async def on_ready():
    print(f"✅ 机器人已登录！")
    print(f"Bot 名称: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"已连接到 {len(bot.guilds)} 个服务器")
    
    # 启动消息队列工作线程
    asyncio.create_task(message_worker())
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ 已同步 {len(synced)} 个斜杠命令")
    except Exception as e:
        print(f"❌ 同步命令失败: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)
    
    user_id = str(message.author.id)
    channel_id = str(message.channel.id)
    
    # 限流检查
    if not rate_limiter.is_allowed(user_id):
        await message.channel.send("⚠️ 你太频繁了，请稍后再试。")
        return
    
    is_mentioned = bot.user in message.mentions
    
    if user_id in user_channels:
        target_channel = user_channels[user_id]
        if channel_id != target_channel and not is_mentioned:
            return
    
    should_respond = False
    content = message.content
    
    if is_mentioned:
        for mention in message.mentions:
            content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "").strip()
        should_respond = True
    
    if message.content.startswith("!"):
        return
    
    if not message.content.startswith("!") and not is_mentioned:
        if user_id in user_channels:
            if channel_id == user_channels[user_id]:
                should_respond = True
        else:
            should_respond = True
    
    if should_respond and content:
        thinking_msg = await message.channel.send("🤔 正在思考...")
        # 使用队列处理，避免阻塞
        await message_queue.put((content, user_id, message.channel))
        # 删除思考消息（实际回复会在队列处理后发送）
        await thinking_msg.delete()

# ... 其余命令保持不变（slash_chat, slash_set, slash_model, slash_reset, slash_help, ping, hello, reset）
