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

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ========== 性能优化：消息队列 + 限流 ==========
class RateLimiter:
    """简单的限流器，防止用户过度使用"""
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

# 启动健康检查线程
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
                # 如果消息太长，分段发送
                for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                    await channel.send(chunk)
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
    embed.set_footer(text=footer or "🤖 Nexus 智能助手")
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
    
    # 检查频道设置
    if user_id in user_channels:
        target_channel = user_channels[user_id]
        if channel_id != target_channel and not is_mentioned:
            return
    
    should_respond = False
    content = message.content
    
    # 处理 @ 提及
    if is_mentioned:
        for mention in message.mentions:
            content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "").strip()
        should_respond = True
    
    # 处理命令
    if message.content.startswith("!"):
        return
    
    # 普通消息
    if not message.content.startswith("!") and not is_mentioned:
        if user_id in user_channels:
            if channel_id == user_channels[user_id]:
                should_respond = True
        else:
            should_respond = True
    
    if should_respond and content:
        # 发送思考提示
        thinking_msg = await message.channel.send("🤔 正在思考...")
        # 加入队列处理
        await message_queue.put((content, user_id, message.channel))
        # 删除思考消息
        await thinking_msg.delete()

# ========== 斜杠命令 ==========

@bot.tree.command(name="chat", description="在当前位置开始对话")
async def slash_chat(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel_id)
    
    if user_id in user_channels:
        del user_channels[user_id]
    
    embed = create_embed("✅ 对话已启用", "直接发消息我就会回复你！", 0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set", description="设置对话频道")
@app_commands.describe(channel="要设置的频道")
async def slash_set(interaction: discord.Interaction, channel: discord.TextChannel):
    user_id = str(interaction.user.id)
    channel_id = str(channel.id)
    
    user_channels[user_id] = channel_id
    
    embed = create_embed(
        "✅ 频道已设置",
        f"以后我只会在这个频道回复你：{channel.mention}",
        0x00ff00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="model", description="切换AI模型")
@app_commands.describe(model="gpt / kimi / deepseek / qwen")
@app_commands.choices(model=[
    app_commands.Choice(name="🏆 MiniMax M2.5 (综合最强 | 代码第一 | 无限Token)", value="minimax"),
    app_commands.Choice(name="🇨🇳 GLM-5 (中文最强 | 工具调用95%+ | 无限Token)", value="glm"),
    app_commands.Choice(name="🔍 DeepSeek V3 (推理强 | 数学好 | 无限Token)", value="deepseek"),
    app_commands.Choice(name="🌏 Qwen 2.5 (阿里Qwen | 中文优秀 | 无限Token)", value="qwen"),
    app_commands.Choice(name="⚡ GPT-OSS 120B (速度快 | 智商高 | Groq备用)", value="gpt"),
    app_commands.Choice(name="💬 Kimi K2 (中文优秀 | Groq备用)", value="kimi"),
])
async def slash_model(interaction: discord.Interaction, model: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    result = agent.switch_model(model.value)
    
    from agent import MODELS
    model_info = MODELS.get(model.value, {})
    provider = model_info.get("provider", "unknown")
    description = model_info.get("description", "")
    
    if provider == "nvidia":
        platform_text = "✅ 无限 Token，完全免费"
    else:
        platform_text = "⚠️ 有速率限制，建议优先使用 NVIDIA 模型"
    
    embed = discord.Embed(
        title="🤖 模型切换",
        description=f"{result}\n\n**平台:** {provider.upper()}\n**说明:** {description}\n{platform_text}",
        color=0x00ff00 if "✅" in result else 0xff0000
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset", description="重置对话历史")
async def slash_reset(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    agent.history = []
    from db import save_history
    save_history(user_id, [])
    
    embed = create_embed("✅ 已重置", "对话历史已清空", 0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="help", description="查看所有命令")
async def slash_help(interaction: discord.Interaction):
    help_text = """
**🤖 Nexus 智能助手**

**斜杠命令:**
`/model` - 切换AI模型（下拉选择）
`/set channel` - 设置专属频道
`/chat` - 在当前频道启用对话
`/reset` - 重置对话历史
`/help` - 显示此帮助

**可用模型（6个）:**
- **MiniMax M2.5** 🏆 综合最强，代码第一
- **GLM-5** 🇨🇳 中文最强，工具调用
- **DeepSeek V3** 🔍 推理强，数学好
- **Qwen 2.5** 🌏 阿里Qwen，中文优秀
- **GPT-OSS 120B** ⚡ 速度快，备用
- **Kimi K2** 💬 中文好，备用

**对话功能:**
- `现在几点` - 获取时间
- `搜索 关键词` - 联网搜索
- `读取 bot.py` - 读取文件
- `把命令前缀改成 $` - 修改代码
- `10分钟后提醒我` - 一次性提醒
- `每天9点发消息` - 每日定时
- `查看任务` - 查看所有任务
- `帮我搭个网站` - 自动建站

直接发消息就能和我聊天！
"""
    embed = discord.Embed(
        title="📚 帮助中心",
        description=help_text,
        color=0x3498db
    )
    embed.set_footer(text="Nexus 智能助手 | 使用 /model 切换模型")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== 普通命令 ==========

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"延迟: {latency}ms",
        color=0x00ff00 if latency < 200 else 0xffaa00
    )
    await ctx.send(embed=embed)

@bot.command()
async def hello(ctx):
    embed = discord.Embed(
        title="👋 你好！",
        description=f"你好 {ctx.author.name}！有什么可以帮你的吗？",
        color=0x3498db
    )
    embed.set_footer(text="使用 /model 切换模型")
    await ctx.send(embed=embed)

@bot.command()
async def reset(ctx):
    user_id = str(ctx.author.id)
    agent = get_agent(user_id)
    agent.history = []
    from db import save_history
    save_history(user_id, [])
    
    embed = create_embed("✅ 已重置", "对话历史已清空", 0x00ff00)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
