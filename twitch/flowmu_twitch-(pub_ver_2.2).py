from twitchio.ext import commands
import random
import ai_core
import pyttsx3
from gtts import gTTS
import os
import re
import threading

Botname = "Flow-Mu"
istesting = True
ignore_users = ["StreamElements"]
chat_history = False
chat_tts = False
ai_on = False
chat_tts_lock = False
flowmu_tts = True
conn, c = ai_core.init_db()

if istesting:
    botkey = '****'  # Key used for testing
    chat_channel = 'flowmubot'
    oauth_token = 'oauth:****'
else:
    botkey = '****'  # Key used when streaming
    chat_channel = 'the_insane_lord'
    oauth_token = 'oauth:****'

#   |================================================================|
#   |##################   TTS conf go below  ########################|
#   |================================================================|
tts_read_speed=185

# Chat TTS configuration
chat_tts_engine = pyttsx3.init(driverName='espeak')
chat_tts_engine.setProperty('rate', tts_read_speed)  # Speed of speech
chat_tts_engine.setProperty('volume', 1)  # Volume level (0.0 to 1.0)

tts_skip_event = threading.Event()

def speak_text_pyttsx3(text):
    global tts_thread
    tts_skip_event.clear()
    
    def speak():
        try:
            chat_tts_engine.say(text)
            chat_tts_engine.runAndWait()
        except Exception as e:
            print(f"Error in TTS: {e}")
    
    if tts_thread and tts_thread.is_alive():
        tts_thread.join()
    
    tts_thread = threading.Thread(target=speak)
    tts_thread.start()
    
    while tts_thread.is_alive():
        if tts_skip_event.is_set():
            chat_tts_engine.stop()
            break

# Flow-Mu TTS configuration
def speak_text_gtts(text):
    def speak():
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save("flowmu_output.mp3")
            os.system(f"mpg123 -q flowmu_output.mp3")
        except Exception as e:
            print(f"Error in TTS: {e}")

    if flowmu_tts:
        threading.Thread(target=speak).start()

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

        # Speak the message text if TTS is enabled and not a command
        if chat_tts and not message.content.startswith('?'):
            cleaned_message = clean_message(message.content)
            if cleaned_message:
                speak_text_pyttsx3(f"{message.author.name} says: {cleaned_message}")

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
                if flowmu_tts:
                    speak_text_gtts(response)
                
                # Log AI response if logging is enabled
                if chat_history:
                    ai_core.log_ai_response(conn, c, self.nick, Botname, response)
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

    @commands.command()
    async def tts(self, ctx: commands.Context, task: str = 'x'):
        global chat_tts, chat_tts_lock, tts_skip_event
        task = task.lower()

        if task == 'lock' and ctx.author.name == "the_insane_lord":
            chat_tts_lock = True
            await ctx.send("Chat TTS is now locked.")
        elif task == 'unlock' and ctx.author.name == "the_insane_lord":
            chat_tts_lock = False
            await ctx.send("Chat TTS is now unlocked.")
        elif task == 'skip' and ctx.author.name == "the_insane_lord":
            if tts_thread and tts_thread.is_alive():
                print(f"{ctx.author.name} has skipped the current TTS message")
                tts_skip_event.set()
                await ctx.send("Current TTS message skipped.")
            else:
                await ctx.send("No TTS message to skip.")
        elif task == 'x':
            if chat_tts and not chat_tts_lock:
                chat_tts = False
                await ctx.send("Ok, Steve you don't need to read the chat out loud now.")
            elif not chat_tts and not chat_tts_lock:
                chat_tts = True
                await ctx.send("Hey, Steve can you read the chat out loud?.")


#   bot introduction/testing command
    @commands.command()
    async def hello(self, ctx: commands.Context):
        await ctx.send(f'Hello {ctx.author.name}! I am {Botname}. It is great to be here. When my brain is working I only respond to my name')

#   info command
    @commands.command()
    async def info(self, ctx: commands.Context):
        await ctx.send(f'My name is Flow-Mu I am a AI bot that is a friend for the chat if you want to see how I work then use ?code I am currently in Version 2.2')


#    DnD dice roll
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
    #   handle and manage of the AI
    @commands.command()
    async def ai(self, ctx: commands.Context, task: str = 'x'):
        global ai_on, chat_history, flowmu_tts
        task = task.lower()
        unknown = ['Huh?', 'What?', 'Hey!!', 'Ouch!']
        
        if ctx.author.name == "the_insane_lord":
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
        print(f"AI Command Used\n task is: {task}\n AI status: {ai_on} Ai TTS setting is: {flowmu_tts}")

bot = Bot()
bot.run()
