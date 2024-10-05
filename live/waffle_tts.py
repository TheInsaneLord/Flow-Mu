from twitchio.ext import commands
from gtts import gTTS
import subprocess
import re
import threading
from queue import Queue

# Bot configuration
ignore_users = ["streamelements", "soundalerts"]
no_tts_users = ["the_insane_lord"]
chat_tts = True
chat_tts_lock = False
flowmu_tts = True

# OAuth token and channels
chat_channels = ['the_insane_lord']
oauth_token = 'oauth:****'

# Queue for managing TTS requests
tts_queue = Queue()
tts_skip_event = threading.Event()

# Start the TTS worker thread
def tts_worker():
    while True:
        text, is_flowmu = tts_queue.get()
        if is_flowmu:
            speak_text_gtts_flowmu(text)
        else:
            speak_text_gtts_chat(text)
        tts_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

# Function to handle chat TTS
def speak_text_gtts_chat(text):
    def speak():
        try:
            #if clean_message in no_tts_channels: # if cannels message not tts chanel dont play message
                #return
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

# Define the bot class
class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=chat_channels)

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f"Listening on: {chat_channels}")
        print("Bot is ready and running.")

    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users:# or message.author.name == self.nick:
            return
        
        # Debugging: print all message info
        print(f"{message.author.name}: {message.content}")

        # Determine if this is a Flow-Mu message (case-insensitive comparison)
        is_flowmu = message.author.name.lower() == 'flowmubot'.lower()  # Make both lower case for case-insensitive match

        # Debugging to check if Flow-Mu detection is working
        print(f"Is Flow-Mu: {is_flowmu}")  # This should print True for flowmubot messages

        # Handle TTS for chat messages if enabled
        if chat_tts and not message.content.startswith('?') and message.author.name not in no_tts_users:
            cleaned_message = clean_message(message.content)
            if cleaned_message:
                if is_flowmu:
                    # For Flow-Mu, pass only the message without the username
                    print(f"Processing Flow-Mu TTS: {cleaned_message}")
                    tts_queue.put((cleaned_message, True))
                else:
                    print(f"Processing message for TTS: {cleaned_message} (Flow-Mu: {is_flowmu})")
                    tts_queue.put((f"{message.author.name} says: {cleaned_message}", is_flowmu))

        # Handle commands
        await self.handle_commands(message)


    # TTS toggle command
    @commands.command()
    async def tts(self, ctx: commands.Context, task: str = 'x'):
        global chat_tts, chat_tts_lock
        task = task.lower()

        if task == 'lock':
            chat_tts_lock = True
            await ctx.send("Chat TTS is now locked.")
        elif task == 'unlock':
            chat_tts_lock = False
            await ctx.send("Chat TTS is now unlocked.")
        elif task == 'skip':
            tts_skip_event.set()
            await ctx.send(f"TTS skipped by {ctx.author.name}.")
        else:
            if chat_tts and not chat_tts_lock:
                chat_tts = False
                await ctx.send("Chat TTS disabled.")
            else:
                chat_tts = True
                await ctx.send("Chat TTS enabled.")

# Initialize and run the bot
bot = Bot()
bot.run()
