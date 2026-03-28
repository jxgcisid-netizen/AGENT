import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from agent import Agent

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)

# 存储每个用户的 Agent 实例
user_agents = {}

def get_agent(user_id: str) -> Agent:
    """获取或创建用户的 Agent"""
    if user_id not in user_agents:
        user_agents[user_id] = Agent(user_id)
        user_agents[user_id].set_bot(bot)
    return user_agents[user_id]

# 存储用户指定的频道
user_channels = {}

@bot.event
async def on_ready():
    print(f"✅ 机器人已登录！")
    print(f"Bot 名称: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"已连接到 {len(bot.guilds)} 个服务器")
    
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
    
    is_mentioned = bot.user in message.mentions
    
    # 检查频道设置
    if user_id in user_channels:
        target_channel = user_channels[user_id]
        if channel_id != target_channel and not is_mentioned:
            return
    
    should_respond = False
    user_content = message.content
    
    # 处理 @ 提及
    if is_mentioned:
        for mention in message.mentions:
            user_content = user_content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "").strip()
        should_respond = True
    
    # 处理命令
    if message.content.startswith("!"):
        return
    
    # 普通消息
    if not message.content.startswith("!") and not is_mentioned:
        if user_id in user_channels:
            if channel_id == user_channels[user_id]:
                should_respond = True
        
    
    if should_respond and user_content:
        async with message.channel.typing():
            try:
                agent = get_agent(user_id)
                result = await agent.run(user_content, message.author.name, message.channel)
                if result:
                    for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                        await message.channel.send(f"{message.author.mention} {chunk}")
            except Exception as e:
                print(f"错误: {e}")
                await message.channel.send(f"{message.author.mention} ❌ 出错了：{str(e)[:200]}")

# ========== 斜杠命令 ==========

@bot.tree.command(name="chat", description="在当前位置开始对话")
async def slash_chat(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel_id)
    
    if user_id in user_channels:
        del user_channels[user_id]
    
    await interaction.response.send_message(
        f"✅ 已在此频道启用对话。直接发消息我就会回复你（会 @ 你哦）。",
        ephemeral=True
    )

@bot.tree.command(name="set", description="设置对话频道")
@app_commands.describe(channel="要设置的频道")
async def slash_set(interaction: discord.Interaction, channel: discord.TextChannel):
    user_id = str(interaction.user.id)
    channel_id = str(channel.id)
    
    user_channels[user_id] = channel_id
    
    await interaction.response.send_message(
        f"✅ 已将对话频道设置为 {channel.mention}\n以后我只会在这个频道回复你（会 @ 你哦）。",
        ephemeral=True
    )

@bot.tree.command(name="model", description="切换AI模型")
@app_commands.describe(model="模型名称: gpt, kimi, scout")
async def slash_model(interaction: discord.Interaction, model: str):
    """切换模型"""
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    result = agent.switch_model(model)
    await interaction.response.send_message(result, ephemeral=True)

@bot.tree.command(name="help", description="查看所有命令")
async def slash_help(interaction: discord.Interaction):
    help_text = """
**🤖 斜杠命令**

`/chat` - 在当前频道启用对话
`/set channel` - 设置指定频道为对话频道
`/model gpt/kimi/scout` - 切换AI模型
`/help` - 显示此帮助
`/reset` - 重置对话历史

**当前可用模型：**
- `gpt` - 🧠 智商最高，速度最快
- `kimi` - 🇨🇳 中文最好，表达自然
- `scout` - ⚡ 速度极快，智商够用

**基础命令：**
`!ping` - 测试延迟
`!hello` - 打招呼
`!reset` - 重置对话历史

**AI 对话：**
直接发送消息，我会 @ 你并回复

**功能：**
- 🕐 时间查询：`现在几点`
- 🔍 联网搜索：`搜索 关键词`
- 📄 读取文件：`读取 bot.py`
- ✏️ 修改代码：`把命令前缀改成 $`
- ⏰ 一次性提醒：`10分钟后提醒我喝水`
- 📅 每日定时：`每天9点发消息：早安`
- 📋 查看任务：`查看任务`
- ❌ 删除任务：`删除提醒`
"""
    await interaction.response.send_message(help_text, ephemeral=True)

@bot.tree.command(name="reset", description="重置对话历史")
async def slash_reset(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    agent.history = []
    agent.waiting_for_confirmation = False
    agent.pending_patch = None
    save_history(user_id, [])
    
    await interaction.response.send_message(
        "✅ 对话历史已重置",
        ephemeral=True
    )

# ========== 普通命令 ==========

@bot.command()
async def ping(ctx):
    await ctx.send(f"{ctx.author.mention} 🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")

@bot.command()
async def hello(ctx):
    await ctx.send(f"{ctx.author.mention} 你好 {ctx.author.name}！")

@bot.command()
async def reset(ctx):
    user_id = str(ctx.author.id)
    agent = get_agent(user_id)
    agent.history = []
    agent.waiting_for_confirmation = False
    agent.pending_patch = None
    save_history(user_id, [])
    await ctx.send(f"{ctx.author.mention} ✅ 对话已重置")

if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
