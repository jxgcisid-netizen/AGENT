import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from agent import Agent

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all(), help_command=None)
agent = Agent()

# 保留这一行！现在 Agent 有 set_bot 方法了
#agent.set_bot(bot)

@bot.event
async def on_ready():
    print(f"✅ 机器人已登录！")
    print(f"Bot 名称: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"已连接到 {len(bot.guilds)} 个服务器")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)
    
    if not message.content.startswith("!"):
        async with message.channel.typing():
            try:
                result = await agent.run(
                    message.content, 
                    str(message.author.id), 
                    message.channel
                )
                if result:
                    for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                        await message.channel.send(chunk)
            except Exception as e:
                print(f"错误: {e}")
                await message.channel.send(f"❌ 出错了：{str(e)[:200]}")

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")

@bot.command()
async def hello(ctx):
    await ctx.send(f"你好 {ctx.author.name}！")

@bot.command(name="helpme", aliases=["commands", "cmds"])
async def help_command(ctx):
    help_text = """
**🤖 Discord Agent 帮助菜单**

**基础命令：**
`!ping` - 测试机器人延迟
`!hello` - 打招呼
`!helpme` - 显示此帮助
`!reset` - 重置对话历史

**AI 对话：**
直接发送消息即可与我对话

**定时任务示例：**
`每天9点发消息：早安` - 设置每日定时提醒
`列出任务` - 查看所有定时任务

有什么我可以帮你的吗？
"""
    await ctx.send(help_text)

@bot.command()
async def reset(ctx):
    """重置对话历史"""
    agent.history = []
    agent.waiting_for_confirmation = False
    agent.pending_patch = None
    await ctx.send("✅ 对话已重置，历史已清空")

@bot.command()
async def eval(ctx, *, code: str):
    authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
    if str(ctx.author.id) not in authorized:
        return await ctx.send("❌ 你没有权限使用此命令。")
    
    try:
        exec_globals = {
            "bot": bot,
            "ctx": ctx,
            "discord": discord,
            "commands": commands,
            "os": os,
        }
        exec(code, exec_globals)
        result = exec_globals.get("result", "无返回值")
        await ctx.send(f"✅ 执行成功\n```python\n{result}\n```")
    except Exception as e:
        await ctx.send(f"❌ 错误：{e}")

if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
