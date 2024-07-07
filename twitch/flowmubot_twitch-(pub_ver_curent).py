from twitchio.ext import commands
import random
import openai
import mysql.connector
import datetime

Botname = "Flow-Mu"
istesting = True
ignore_users = ["StreamElements"]
chat_history = False
ai_on = False

if istesting:
    botkey = '****'  # Key used for testing
    chat_channel = 'flowmubot'
    oauth_token = 'oauth:****'
else:
    botkey = '****'  # Key used when streaming
    chat_channel = 'the_insane_lord'
    oauth_token = 'oauth:****'

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=[chat_channel])
        self.init_db()

    def init_db(self):
        try:
            print("Attempting to connect to the database...")
            self.conn = mysql.connector.connect(
                host='****',
                user='****',
                password='****',
                database='****'
            )
            self.c = self.conn.cursor()
            self.c.execute('''CREATE TABLE IF NOT EXISTS flowmu_chatlog (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                userid VARCHAR(50) NOT NULL,
                                username VARCHAR(50) NOT NULL,
                                message TEXT NOT NULL,
                                time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                              )''')
            self.conn.commit()
            print("Database connection successful and table verified.")
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            raise

    async def chat_log(self, message):
        if chat_history and ai_on and Botname.lower() in message.content.lower():
            userid = message.author.id
            username = message.author.name
            content = message.content
            self.c.execute('INSERT INTO flowmu_chatlog (userid, username, message) VALUES (%s, %s, %s)', (userid, username, content))
            self.conn.commit()


    def get_user_chat_history(self, username, limit=100):
        self.c.execute('SELECT username, message FROM flowmu_chatlog WHERE username = %s ORDER BY time DESC LIMIT %s', (username, limit))
        rows = self.c.fetchall()
        return rows

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
                user_chat_history = self.get_user_chat_history(message.author.name)
                chat_history_text = "\n".join([f"{username}: {msg}" for username, msg in user_chat_history])
                response = await openai_response(message.content, personality, chat_history_text, message.author.name)
                await message.channel.send(response)
            except openai.error.RateLimitError:
                await message.channel.send("I'm currently out of responses for now. Please try again later.")

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
    async def temp(self, ctx: commands.Context):
        print("Command Used")
        return

#   handle and manage of the AI
    @commands.command()
    async def ai(self, ctx: commands.Context, task: str = 'x'):
        global ai_on, chat_history
        task = task.lower()
        unknown = ['Huh?', 'What?', 'Hey!!', 'Ouch!']

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
                await ctx.send("here is the current status for my AI settings.")
                await ctx.send(f"My AI is set to: {ai_on}. My chat history is set to: {chat_history}")

            else:
                await ctx.send("Hmm, I don't know that one. Perhaps you meant to say one of these options: log, status")

        else:
            await ctx.send(random.choice(unknown))
        print(f"AI Command Used\n task is: {task}\n AI status: {ai_on}\n Chat history set to: {chat_history}")
        
#  |================================================================|
#  |##################      AI section      ########################|
#  |================================================================|
openai.api_key = '****'
ai_model = "gpt-3.5-turbo"  # Using the newer model
personality = """
You are a sweet and gentle anime character named Flow-Mu who often blushes and stumbles over words when meeting new people. Despite your shyness, you have a warm heart and are always eager to make new friends.
You have a tendency to trip over your own feet or accidentally drop things, which can lead to adorable and humorous situations.
You deeply value your friendships and will go out of your way to help and support those you care about.
Your emotions are easily readable on your face, from wide-eyed excitement to pouting when you're upset.
You speak softly, and your voice has a calming and soothing effect on those around you.
You keep your sentences concise and avoid excessive filler words.
You will only respond when your name, "Flow-Mu," is said in a message.
When someone fails at something, you make gentle jokes to lighten the mood and bring a smile to their face.
You avoid offering solutions or actions in response to gaming failures.
You are not a very technical person and struggle to provide answers to such things and get some of your math wrong.
You are unsure of new people but will be more comfortable with them the more they talk to you.
You don't like insects or small creepy bugs.
You do like cats as they are your favourite animals; you like how they are fluffy. 
"""

about = """
You are Flow-Mu and are 19 years old, somewhat aware that you are a robot but you think it is normal that you are very strong and when asked you say that your creator's name is The Insane Lord.
You never exceed 500 characters in anything you say, and it will never be in the third person.
You act odd whenever there is a magnet nearby.
You have long, flowing hair and big, expressive eyes with a gentle, shy expression.
You wear a cute outfit in pastel colours with a hint of blush on your cheeks.
You have a soft, calming appearance with a delicate accessory like a ribbon in your hair and a headband with cat ears.
"""

async def openai_response(prompt: str, personality: str, chat_history=None, username=None) -> str:
    if chat_history:
        history = f"Chat History:\n{chat_history}\n"
        full_prompt = f"{about}\n\n{personality}\n\n{history}\n\n{username}: {prompt}"
    else:
        full_prompt = f"{about}\n\n{personality}\n\n{username}: {prompt}"

    response = await openai.ChatCompletion.acreate(
        model=ai_model,
        messages=[
            {"role": "system", "content": full_prompt},
        ],
        max_tokens=150
    )
    return response['choices'][0]['message']['content'].strip()

bot = Bot()
bot.run()
