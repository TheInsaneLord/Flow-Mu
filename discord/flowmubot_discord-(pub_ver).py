import discord
from discord.ext.commands import Bot
from discord import app_commands
from discord.ext import commands
import random

intents = discord.Intents.default()
intents.message_content=True
intents.members=True
bot = commands.Bot(command_prefix="!", case_insensitive=True, intents=intents)

#   removing help
bot.remove_command('help')
print("Bot is loading...\nConnecting to Discord...")

@bot.event
async def on_ready(pass_context=True):
    await bot.change_presence(activity=discord.Game(name='type !help for commands'))
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)    
    print("Loading Done")
    print(" ")
    print(bot.user.name + " is up and running with no errors")
    print(" ")

#   |================================================================|
#   |##################    code go bellow    ########################|
#   |================================================================|



#   |================================================================|
#   |##################  Commands go bellow  ########################|
#   |================================================================|
#   test command
@bot.command(pass_context=True)
async def ping(ctx):
    await ctx.send("pong")
    #await ctx.auther.send("pong)")

#   info on bot
@bot.hybrid_command(name="info", help="Gives you information on the bot",with_app_command=True)
async def info(ctx):
    embed = discord.Embed(title="Insane_L Bot", description="to help make things eayser on the server.", color=0x98B1B7)

    embed.add_field(name="invite:", value="The insane lord")
    embed.add_field(name="Coder:", value="The insane lord")
    embed.add_field(name="Version:", value="1.0")

    await ctx.send(embed=embed)

#   Dice command
@bot.hybrid_command(pass_context=True)
async def roll(self, ctx:commands.Context, dice:str='x'):
    dice_list = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20']
    dice=dice.lower()

    if dice == 'x':
        await ctx.send("Hey!! you have to pick a dice what am I ment to roll")
        
    elif dice in dice_list:
        num=int(dice.strip('d'))
        print(f"dice picked {dice}, number set {num}")
        range=random.randint(1, num)

        await ctx.send(f"hey here is what you got: {range}")
    else:
        await ctx.send(f"Sorry, I dont have that Dice. I do have these, {dice_list}")

#   Bot Token
bot.run("****")
