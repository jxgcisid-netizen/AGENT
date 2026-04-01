import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from agent import Agent

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)
user_agents = {}
user_channels = {}

def get_agent(user_id: str) -> Agent:
    if user_id not in user_agents:
        user_agents[user_id] = Agent(user_id)
        user_agents[user_id].set_bot(bot)
    return user_agents[user_id]

def create_embed(title: str, content: str, color: int = 0x00ff00, footer: str = None):
    """创建美观的 Discord Embed 消息"""
    embed = discord.Embed(title=title, description=content, color=color)
    embed.set_footer(text=footer or "🤖 Gemini 智能助手")
    return embed

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
        async with message.channel.typing():
            try:
                agent = get_agent(user_id)
                result = await agent.run(content, message.channel)
                if result:
                    # 检测结果类型，选择合适的颜色
                    if "✅" in result or "成功" in result:
                        color = 0x00ff00  # 绿色
                    elif "❌" in result or "错误" in result or "失败" in result:
                        color = 0xff0000  # 红色
                    else:
                        color = 0x3498db  # 蓝色
                    
                    # 创建 Embed 消息
                    embed = discord.Embed(
                        title="📢 回复",
                        description=result[:2000],
                        color=color
                    )
                    embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)
                    embed.set_footer(text=f"模型: {agent.current_model_key.upper()}")
                    
                    await message.channel.send(embed=embed)
            except Exception as e:
                print(f"错误: {e}")
                error_embed = discord.Embed(
                    title="❌ 出错了",
                    description=f"```\n{str(e)[:200]}\n```",
                    color=0xff0000
                )
                await message.channel.send(embed=error_embed)

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
@app_commands.describe(model="gpt / deepseek / kimi / qwen")
async def slash_model(interaction: discord.Interaction, model: str):
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    result = agent.switch_model(model)
    
    if "✅" in result:
        color = 0x00ff00
    else:
        color = 0xff0000
    
    embed = create_embed("🤖 模型切换", result, color)
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
**🤖 Gemini 智能助手**

**斜杠命令:**
`/model gpt/deepseek/kimi/qwen` - 切换模型
`/set channel` - 设置专属频道
`/chat` - 在当前频道启用对话
`/reset` - 重置对话历史
`/help` - 显示此帮助

**可用模型:**
- `gpt` - 🧠 智商最高，速度最快
- `deepseek` - 🔍 推理强，数学好
- `kimi` - 🇨🇳 中文最好
- `qwen` - 🌏 阿里Qwen

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
    embed.set_footer(text="Gemini 智能助手 | 随时为你服务")
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
    embed.set_footer(text="直接发消息就能和我聊天")
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
