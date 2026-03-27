import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from agent import Agent

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 创建 bot
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)
agent = Agent()
agent.set_bot(bot)

# 存储用户指定的频道
user_channels = {}

@bot.event
async def on_ready():
    print(f"✅ 机器人已登录！")
    print(f"Bot 名称: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"已连接到 {len(bot.guilds)} 个服务器")
    
    # 同步斜杠命令
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
    
    # 检查是否在指定频道对话
    user_id = str(message.author.id)
    channel_id = str(message.channel.id)
    
    # 如果用户设置了指定频道，只在那个频道回复
    if user_id in user_channels:
        target_channel = user_channels[user_id]
        if channel_id != target_channel:
            return  # 不在指定频道，不回复
    
    # 普通消息（不以 ! 开头）交给 Agent 处理
    if not message.content.startswith("!"):
        async with message.channel.typing():
            try:
                result = await agent.run(
                    message.content, 
                    user_id, 
                    message.channel
                )
                if result:
                    for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                        await message.channel.send(chunk)
            except Exception as e:
                print(f"错误: {e}")
                await message.channel.send(f"❌ 出错了：{str(e)[:200]}")

# ========== 斜杠命令 ==========

@bot.tree.command(name="chat", description="在当前位置开始对话")
async def slash_chat(interaction: discord.Interaction):
    """在当前频道启用对话"""
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel_id)
    
    # 清除该用户的频道设置
    if user_id in user_channels:
        del user_channels[user_id]
    
    await interaction.response.send_message(
        f"✅ 已在此频道启用对话。你可以直接发送消息和我聊天啦！\n"
        f"使用 `/set channel` 可以指定其他频道。",
        ephemeral=True
    )

@bot.tree.command(name="set", description="设置对话频道")
@app_commands.describe(channel="要设置的频道")
async def slash_set(interaction: discord.Interaction, channel: discord.TextChannel):
    """设置指定频道为对话频道"""
    user_id = str(interaction.user.id)
    channel_id = str(channel.id)
    
    user_channels[user_id] = channel_id
    
    await interaction.response.send_message(
        f"✅ 已将对话频道设置为 {channel.mention}\n"
        f"以后我只会在这个频道回复你的消息。\n"
        f"使用 `/chat` 可以恢复在当前频道对话。",
        ephemeral=True
    )

@bot.tree.command(name="help", description="查看所有命令")
async def slash_help(interaction: discord.Interaction):
    """显示帮助信息"""
    help_text = """
**🤖 斜杠命令**

`/chat` - 在当前频道启用对话
`/set channel` - 设置指定频道为对话频道
`/help` - 显示此帮助

**基础命令：**
`!ping` - 测试延迟
`!hello` - 打招呼
`!reset` - 重置对话历史

**AI 对话：**
直接发送消息即可与我对话

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
    """重置对话历史"""
    user_id = str(interaction.user.id)
    agent.history = []
    agent.waiting_for_confirmation = False
    agent.pending_patch = None
    
    await interaction.response.send_message(
        "✅ 对话历史已重置",
        ephemeral=True
    )

# ========== 普通命令 ==========

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")

@bot.command()
async def hello(ctx):
    await ctx.send(f"你好 {ctx.author.name}！")

@bot.command()
async def reset(ctx):
    """重置对话历史"""
    agent.history = []
    agent.waiting_for_confirmation = False
    agent.pending_patch = None
    await ctx.send("✅ 对话已重置")

# 运行 bot
if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
