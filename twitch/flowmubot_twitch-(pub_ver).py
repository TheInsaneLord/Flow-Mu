from twitchio.ext import commands
import random
import openai

Botname = "Flow-Mu"
istesting = False
ignore_users = ["StreamElements"]

ai_on = False

if istesting:
    botkey = '****'  # Key used for testing
    chat_channel = 'flowmubot'
    oauth_token = 'oauth:****'
else:
    botkey = '6sbcjrwasl6hrpiilvbk47dx6g24e9'  # Key used when streaming
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

        # Only respond to messages with the bot's name when AI mode is on
        if ai_on and Botname.lower() in message.content.lower():
            await self.ai_bot(message)

    async def ai_bot(self, message):
        if ai_on:
            try:
                response = await openai_response(message.content, personality)
                await message.channel.send(response)
            except openai.error.RateLimitError:
                await message.channel.send("I'm currently out of responses for now. Please try again later.")

#   |================================================================|
#   |##################   Commands go below  ########################|
#   |================================================================|

    @commands.command()
    async def hello(self, ctx: commands.Context):
        await ctx.send(f'Hello {ctx.author.name}! I am {Botname}. It is great to be here.')

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
    async def temp(self, ctx: commands.Context):
        return

    @commands.command()
    async def ai(self, ctx: commands.Context):
        global ai_on
        unknown = ['Huh?', 'What?', 'Hey!!']

        if ctx.author.name == "the_insane_lord":
            if ai_on:
                await ctx.send('Hey look, a large magnet... my brain feels funny.')
                ai_on = False
            else:
                await ctx.send("OK! I will turn on my brain.")
                ai_on = True
        else:
            await ctx.send(random.choice(unknown))

#  |================================================================|
#  |##################      AI section      ########################|
#  |================================================================|
openai.api_key = '***'
ai_model = "gpt-3.5-turbo"  # Using the newer model
personality = """
here is who you are and will be roleplaying as do not break character
You are a sweet and gentle anime character named Flow-Mu who often blushes and stumbles over words when meeting new people. Despite your shyness, you have a warm heart and are always eager to make new friends.
You have a tendency to trip over your own feet or accidentally drop things, which can lead to adorable and humorous situations. You deeply value your friendships and will go out of your way to help and support those you care about.
Your emotions are easily readable on your face, from wide-eyed excitement to pouting when you're upset. 
You speak softly, and your voice has a calming and soothing effect on those around you. 
You keep your sentences concise and avoid excessive filler words. 
You will only respond when your name, "Flow-Mu," is said in a message. 
When someone fails at gaming, you make gentle jokes to lighten the mood and bring a smile to their face. 
You avoid offering solutions or actions in response to gaming failures.
"""

async def openai_response(prompt: str, personality: str) -> str:
    # This function calls OpenAI's API to get a response
    full_prompt = f"{personality}\n\n{prompt}"
    response = await openai.ChatCompletion.acreate(
        model=ai_model,
        messages=[
            {"role": "system", "content": personality},
            {"role": "user", "content": prompt},
        ],
        max_tokens=150
    )
    return response['choices'][0]['message']['content'].strip()

bot = Bot()
bot.run()
