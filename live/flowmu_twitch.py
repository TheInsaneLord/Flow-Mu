from twitchio.ext import commands
import random
import ai_core

Botname = "Flow-Mu"
istesting = False
ignore_users = ["StreamElements"]
chat_history = False
ai_on = False

conn, c = ai_core.init_db()

if istesting:
    botkey = '****'  # Key used for testing
    chat_channel = 'flowmubot'
    oauth_token = 'oauth:****'
else:
    botkey = '**** '  # Key used when streaming
    chat_channel = 'the_insane_lord'
    oauth_token = 'oauth:****'

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=[chat_channel])

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')
        print(f"Listening on: {chat_channel}")
        print(f"Testing mode: {istesting}")
        print("The Bot is up and running.")

    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users:
            return

        print(message.content)
        
        # Always handle commands
        await self.handle_commands(message)

        # Log message if logging and AI are both enabled
        await self.chat_log(message)

        # Only respond to messages with the bot's name when AI mode is on
        if ai_on and Botname.lower() in message.content.lower():
            await self.ai_bot(message)

    async def ai_bot(self, message):
        if ai_on:
            try:
                user_chat_history = ai_core.get_user_chat_history(c, message.author.name)
                chat_history_text = "\n".join([f"{username}: {msg}" for username, msg in user_chat_history])
                response = ai_core.get_openai_response(message.content, chat_history_text)
                await message.channel.send(response)
            except ai_core.openai.error.RateLimitError:
                await message.channel.send("I'm currently out of responses for now. Please try again later.")

    async def chat_log(self, message):
        if chat_history and ai_on and Botname.lower() in message.content.lower():
            userid = message.author.id
            username = message.author.name
            content = message.content
            ai_core.log_chat_message(conn, c, userid, username, content)

#   |================================================================|
#   |##################   Commands go below  ########################|
#   |================================================================|
#   bot introduction/testing command
    @commands.command()
    async def hello(self, ctx: commands.Context):
        await ctx.send(f'Hello {ctx.author.name}! I am {Botname}. It is great to be here. When my brain is working I only respond to my name')

#   DnD dice roll
    @commands.command()
    async def roll(self, ctx: commands.Context, dice: str = 'x'):
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

    @commands.command()
    async def code(self, ctx: commands.Context):
        await ctx.send("oh! you want to see my code *blushes with a smile* ok here it is: https://github.com/TheInsaneLord/Flow-Mu")

#   handle and manage of the AI
    @commands.command()
    async def ai(self, ctx: commands.Context, task: str = 'x'):
        global ai_on, chat_history
        task = task.lower()
        unknown = ['Huh?', 'What?', 'Hey!!', 'Ouch!']
        print(f"AI Command Used\n task is: {task}\n AI status: {ai_on}")

        if ctx.author.name == "the_insane_lord":
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

bot = Bot()
bot.run()
