import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from agent import Agent

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
agent = Agent()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return
    async with message.channel.typing():
        result = await agent.run(message.content, str(message.author.id))
        if result:
            for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                await message.channel.send(chunk)

@bot.command(name="eval")
async def eval_code(ctx, *, code: str):
    authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
    if str(ctx.author.id) not in authorized:
        return await ctx.send("❌ 无权限")
    try:
        exec_globals = {}
        exec(code, exec_globals)
        result = exec_globals.get("result", "无返回值")
        await ctx.send(f"✅ 执行成功\n```\n{result}\n```")
    except Exception as e:
        await ctx.send(f"❌ 错误：{e}")

bot.run(TOKEN)
