from twitchio.ext import commands
import random
import ai_core
from gtts import gTTS
import os
import re
import threading
import subprocess
from queue import Queue

Botname = "Flow-Mu"
bot_accept_names = ["flow-mu", "@flow-mu", "@flowmubot", "@Flow-Mu Bot#7224", "@Flow-Mu Bot"] # Names AI will resond to
istesting = True
ignore_users = ["streamelements", "flowmubot"]
no_tts_users = ["the_insane_lord"]
auth_user = ["the_insane_lord", "sniperheartwolf"]
chat_history = False
chat_tts = False
ai_on = False
chat_tts_lock = False
flowmu_tts = True
conn, c = ai_core.init_db()
random_reply = True
random_reply_chance = 0

if istesting:
    botkey = '****'  # Key used for testing
    chat_channels = ['flowmubot']
    oauth_token = 'oauth:****'
else:
    botkey = '****'  # Key used when streaming
    chat_channels = ["the_insane_lord", "sniperheartwolf", "whaitjeezus"]
    oauth_token = 'oauth:****'

if istesting:
    debug = True
    chat_history = False
else:
    debug = False

#   |================================================================|
#   |##################   TTS conf go below  ########################|
#   |================================================================|
# Queue for managing TTS requests
tts_queue = Queue()

def tts_worker():
    while True:
        text, is_flowmu = tts_queue.get()
        if is_flowmu:
            speak_text_gtts_flowmu(text)
        else:
            speak_text_gtts_chat(text)
        tts_queue.task_done()

# Start the TTS worker thread
threading.Thread(target=tts_worker, daemon=True).start()

# Chat TTS configuration
def speak_text_gtts_chat(text):
    def speak():
        try:
            tts = gTTS(text=text, lang='en', tld='us', slow=False)
            tts.save("chat_output.mp3")
            process = subprocess.Popen(["mpg123", "-q", "chat_output.mp3"])
            while process.poll() is None:  # Poll process to see if it's still running
                if tts_skip_event.is_set():
                    process.kill()
                    tts_skip_event.clear()
                    break
        except Exception as e:
            print(f"Error in TTS: {e}")
    speak()

# Flow-Mu TTS configuration
def speak_text_gtts_flowmu(text):
    def speak():
        try:
            tts = gTTS(text=text, slow=False)
            tts.save("flowmu_output.mp3")
            process = subprocess.Popen(["mpg123", "-q", "flowmu_output.mp3"])
            while process.poll() is None:  # Poll process to see if it's still running
                if tts_skip_event.is_set():
                    process.kill()
                    tts_skip_event.clear()
                    break
        except Exception as e:
            print(f"Error in TTS: {e}")
    if flowmu_tts:
        speak()

def clean_message(message):
    # Remove emotes and commands
    if message.startswith('?'):  # Skip if the message is a command
        return ""
    message = re.sub(r':\w+:', '', message)
    return message.strip()

# TTS thread and event for skipping
tts_thread = None
tts_skip_event = threading.Event()

#   |================================================================|
#   |##################   Bot code below  ###########################|
#   |================================================================|

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=chat_channels)

    async def chat_log(self, message):
        if chat_history and ai_on and Botname.lower() in message.content.lower():
            userid = message.author.id
            username = message.author.name
            content = message.content
            ai_core.log_chat_message(conn, c, userid, username, content)


    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')
        print(f"Listening on: {chat_channels}")
        print(f"Testing mode: {istesting}")
        print("The Bot is up and running.")

    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users or message.author.name == self.nick:
            return

        print(message.content)

        # Speak the message text if TTS is enabled, not a command, and the user is not in the no_tts_users list
        if chat_tts and not message.content.startswith('?') and message.author.name not in no_tts_users:
            cleaned_message = clean_message(message.content)
            if cleaned_message and message.author.name not in no_tts_users:
                tts_queue.put((f"{message.author.name} says: {cleaned_message}", False))

        # Always handle commands
        await self.handle_commands(message)

        # Log message if logging and AI are both enabled
        await self.chat_log(message)

        # Check if the message is not a command and only respond to non-command messages with the bot's name or if random reply chance met
        if not message.content.startswith('?'):
            if random_reply and ai_on:
                random_reply_chance = random.randint(0, 100)
                if debug:
                    print(f"The chance of a random reply is: {random_reply_chance}")
            else:
                random_reply_chance = 0

            if ai_on and (any(name in message.content.lower() for name in bot_accept_names) or random_reply_chance < 5):
                await self.ai_bot(message)


    async def ai_bot(self, message):
        if ai_on:
            try:
                # Fetch the complete chat history
                user_chat_history = ai_core.get_user_chat_history(c, message.author.name)
                chat_history_text = "\n".join([f"{username}: {msg}" for username, msg in user_chat_history])
                
                # Get the AI response including the chat history
                response = ai_core.get_openai_response(message.content, chat_history_text)
                
                # Check if the AI has already responded to the message
                if not ai_core.has_responded_to_message(c, message.author.name):
                    # Split the response into multiple parts if it exceeds 500 characters
                    for i in range(0, len(response), 500):
                        await message.channel.send(response[i:i+500])
                    
                    # Use TTS for the AI response if enabled
                    if flowmu_tts:
                        tts_queue.put((response, True))
                    
                    # Log the AI response if logging is enabled
                    if chat_history:
                        ai_core.log_chat_message(conn, c, self.nick, Botname, response, is_response=True)
            except ai_core.openai.error.RateLimitError:
                await message.channel.send("I'm currently out of responses for now. Please try again later.")

#   |================================================================|
#   |##################   Commands go below  ########################|
#   |================================================================|

# TTS toggle command
    @commands.command()
    async def tts(self, ctx: commands.Context, task: str = 'x'):
        global chat_tts
        global chat_tts_lock
        task = task.lower()
        
        if task == 'lock' and ctx.author.name in auth_user:
            chat_tts_lock = True
        elif task == 'unlock' and ctx.author.name in auth_user:
            chat_tts_lock = False
            await ctx.send()

        elif task == 'skip':
            print(f"{ctx.author.name} has skipped the current TTS message")
            await ctx.send(f"TTs has been skipyed by {ctx.author.name}")
            tts_skip_event.set()

        if task == 'x':
            if chat_tts and not chat_tts_lock:
                chat_tts = False
                await ctx.send(f"Ok, Steve you don't need to read the chat out loud now.")
            else:
                chat_tts = True
                await ctx.send(f"Hey, Steve can you read the chat out loud?.")

#   bot introduction/testing command
    @commands.command()
    async def hello(self, ctx: commands.Context):
        await ctx.send(f'Hello {ctx.author.name}! I am {Botname}. It is great to be here. When my brain is working I only respond to my name')

#   info command
    @commands.command()
    async def info(self, ctx: commands.Context):
        await ctx.send(f'My name is Flow-Mu I am a AI bot that is a compain for the chat if you want to see how I work then use ?code I am curently in Version 2.3')


#    DnD dice roll
    @commands.command()
    async def roll(self, ctx: commands.Context, dice: str = 'x'):
        dice_list = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20']
        dice = dice.lower()

        if dice == 'x':
            await ctx.send("Hey!! you have to pick a dice. What am I meant to roll?")
        elif dice in dice_list:
            num = int(dice.strip('d'))
            if debug == True:
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
        global ai_on, chat_history, flowmu_tts
        task = task.lower()
        unknown = ['Huh?', 'What?', 'Hey!!', 'Ouch!']
        
        if ctx.author.name in auth_user:
            if task == 'x':
                if ai_on:
                    await ctx.send('Hey look, a large magnet... my brain feels funny.')
                    ai_on = False
                    chat_history = False
                    flowmu_tts = False
                else:
                    await ctx.send("OK! I will turn on my brain.")
                    ai_on = True
            elif task == 'tts' and flowmu_tts:
                await ctx.send("Sure I won't say stuff out loud.")
                flowmu_tts = False
            elif task == 'tts' and not flowmu_tts:
                await ctx.send("YEY I can speak now!!")
                flowmu_tts = True
            elif task == 'log' and not chat_history and ai_on:
                await ctx.send("Flow-Mu remembers all there is no escape.")
                chat_history = True
            elif task == 'log' and chat_history and ai_on:
                await ctx.send("Oh no! They have a magnet I will forget what is said.")
                chat_history = False
            elif task == 'status':
                await ctx.send("Here is the current status for my AI settings.")
                await ctx.send(f"My AI is set to: {ai_on}. My chat history is set to: {chat_history}. My TTS is set to: {flowmu_tts}")
            else:
                await ctx.send("Hmm, I don't know that one. Perhaps you meant to say one of these options: log, status")
        else:
            await ctx.send(random.choice(unknown))
        if debug == True:
            print(f"AI Command Used\n task is: {task}\n AI status: {ai_on} Ai TTS setting is: {flowmu_tts}")

bot = Bot()
bot.run()
