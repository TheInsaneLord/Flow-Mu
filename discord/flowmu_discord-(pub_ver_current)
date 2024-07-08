import discord
from discord.ext import commands
import random
import ai_core

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="?", case_insensitive=True, intents=intents)

istesting = False
ignore_users = ["streamelements"]
chat_history = False
ai_on = False
Botname = "Flow-Mu"

conn, c = ai_core.init_db()

# If the bot is testing
if istesting:
    key = '****'
else:
    key = '****'

# Removing help
bot.remove_command('help')
print("Bot is loading...\nConnecting to Discord...")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name='/I am Flow-Mu a AI pal'))
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)
    print(f"Bot running as: {bot.user.name}")
    print(f"Testing mode: {istesting}")    
    print("Loading Done")
    print(" ")
    print("The bot is up and running")
    print(" ")

@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.name in ignore_users:
        return

    print(message.content)

    # Log message if logging and AI are both enabled
    await chat_log(message)

    # Only respond to messages with the bot's name when AI mode is on
    if ai_on and Botname.lower() in message.content.lower():
        await ai_bot(message)

    await bot.process_commands(message)

async def ai_bot(message):
    if ai_on:
        try:
            user_chat_history = ai_core.get_user_chat_history(c, message.author.name)
            chat_history_text = "\n".join([f"{username}: {msg}" for username, msg in user_chat_history])
            response = ai_core.get_openai_response(message.content, chat_history_text)
            await message.channel.send(response)
            
            # Log AI response if logging is enabled
            if chat_history:
                ai_core.log_ai_response(conn, c, str(bot.user.id), Botname, response)
        except ai_core.openai.error.RateLimitError:
            await message.channel.send("I'm currently out of responses for now. Please try again later.")

async def chat_log(message):
    if chat_history and ai_on and Botname.lower() in message.content.lower():
        userid = str(message.author.id)
        username = message.author.name
        content = message.content
        ai_core.log_chat_message(conn, c, userid, username, content)

#   |================================================================|
#   |##################  Commands go below  ########################|
#   |================================================================|

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.hybrid_command(name="info", help="Gives you information on the bot", with_app_command=True)
async def info(ctx):
    embed = discord.Embed(title="Insane_L Bot", description="to help make things easier on the server.", color=0x98B1B7)

    embed.add_field(name="invite:", value="The insane lord")
    embed.add_field(name="Coder:", value="The insane lord")
    embed.add_field(name="Version:", value="2.2")

    await ctx.send(embed=embed)

@bot.hybrid_command(name="roll", pass_context=True)
async def roll(ctx, dice: str = 'x'):
    dice_list = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20']
    dice = dice.lower()

    if dice == 'x':
        await ctx.send("Hey!! you have to pick a dice. What am I meant to roll?")
    elif dice in dice_list:
        num = int(dice.strip('d'))
        print(f"Dice picked: {dice}, number set: {num}")
        result = random.randint(1, num)
        await ctx.send(f"Hey, here is what you got: {result}")
    else:
        await ctx.send(f"Sorry, I don't have that dice. I do have these: {', '.join(dice_list)}")

#   show the code on GitHub
@bot.hybrid_command(name="code", pass_context=True)
async def code(ctx):
    await ctx.send("oh! you want to see my code *blushes with a smile* ok here it is: https://github.com/TheInsaneLord/Flow-Mu")


@bot.hybrid_command(name="ai", pass_context=True)
async def ai(ctx, task: str = 'x'):
    global ai_on, chat_history
    task = task.lower()
    unknown = ['Huh?', 'What?', 'Hey!!', 'Ouch!']
    authorised = ["266550586298597379"]

    if str(ctx.author.id) in authorised:
        if task == 'x':
            if ai_on:
                await ctx.send('Hey look, a large magnet... my brain feels funny.')
                ai_on = False
                chat_history = False
            else:
                await ctx.send("OK! I will turn on my brain.")
                ai_on = True

        elif task == 'log' and not chat_history and ai_on:
            await ctx.send("Flow-Mu remembers all there is no escape.")
            chat_history = True

        elif task == 'log' and chat_history and ai_on:
            await ctx.send("Oh no! They have a magnet I will forget what is said.")
            chat_history = False

        elif task == 'status':
            await ctx.send("Here is the current status for my AI settings.")
            await ctx.send(f"My AI is set to: {ai_on}. My chat history is set to: {chat_history}")

        else:
            await ctx.send("Hmm, I don't know that one. Perhaps you meant to say one of these options: log, status")
    else:
        await ctx.send(random.choice(unknown))
        print(f"AI Command Used\n task is: {task}\n AI status: {ai_on}")

bot.run(key)
