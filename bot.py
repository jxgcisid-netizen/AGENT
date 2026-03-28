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

def get_agent(user_id: str) -> Agent:
    if user_id not in user_agents:
        user_agents[user_id] = Agent(user_id)
        user_agents[user_id].set_bot(bot)
    return user_agents[user_id]

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
    
    if not isinstance(message.channel, discord.DMChannel) and bot.user not in message.mentions:
        return
    
    content = message.content
    for mention in message.mentions:
        content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "").strip()
    
    if not content:
        return
    
    async with message.channel.typing():
        try:
            agent = get_agent(str(message.author.id))
            result = await agent.run(content, message.channel)
            if result:
                for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                    await message.channel.send(chunk)
        except Exception as e:
            print(f"错误: {e}")
            await message.channel.send(f"❌ 出错了：{str(e)[:200]}")

@bot.tree.command(name="model", description="切换AI模型")
@app_commands.describe(model="gpt / kimi / deepseek / qwen")
async def slash_model(interaction: discord.Interaction, model: str):
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    result = agent.switch_model(model)
    await interaction.response.send_message(result, ephemeral=True)

@bot.tree.command(name="reset", description="重置对话历史")
async def slash_reset(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    agent = get_agent(user_id)
    agent.history = []
    from db import save_history
    save_history(user_id, [])
    await interaction.response.send_message("✅ 对话已重置", ephemeral=True)

@bot.tree.command(name="help", description="查看所有命令")
async def slash_help(interaction: discord.Interaction):
    help_text = """
**🤖 斜杠命令**

`/model gpt/kimi/deepseek/qwen` - 切换AI模型
`/reset` - 重置对话历史
`/help` - 显示此帮助

**可用模型：**
- `gpt` - 🧠 智商最高，速度最快 (Groq)
- `kimi` - 🇨🇳 中文最好，表达自然 (Groq)
- `deepseek` - 🔍 推理强，数学好 (NVIDIA)
- `qwen` - 🌏 阿里Qwen，中文强 (NVIDIA)

**AI 对话：**
- 私聊直接发消息
- 服务器里 @我 发消息

**功能：**
- 🕐 `现在几点` - 获取时间
- 🔍 `搜索 关键词` - 联网搜索
- 📄 `读取 bot.py` - 读取文件
- ✏️ `把命令前缀改成 $` - 修改代码
- ⏰ `10分钟后提醒我喝水` - 一次性提醒
- 📅 `每天9点发消息：早安` - 每日定时
"""
    await interaction.response.send_message(help_text, ephemeral=True)

if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
