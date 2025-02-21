from twitchio.ext import commands
import requests
import subprocess
import re
import threading
import config
import time
import asyncio
import mysql.connector
from mysql.connector import Error
from queue import Queue
from datetime import datetime
from gtts import gTTS

# Bot configuration
ignore_users = ["streamelements", "soundalerts"]
no_tts_users = ["the_insane_lord"]
chat_tts = True
chat_tts_lock = False
flowmu_tts = True
waffle_follow = False

# Eleven Labs configuration
use_elevenlab = True
elevenlabs_key = config.elevenlabs_key
elevenlabs_voice_id = config.elevenlabs_voice_id  # Change this to your desired voice ID

# OAuth token and channels
default_chat_channel = 'the_insane_lord'
chat_channels = [default_chat_channel]
oauth_token = config.twitch_oauth

# Queue for managing TTS requests
tts_queue = Queue()
tts_skip_event = threading.Event()

# Check Eleven Labs availability
def elab_check():
    global use_elevenlab
    try:
        url = "https://api.elevenlabs.io/v1/user"
        headers = {"xi-api-key": elevenlabs_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("Eleven Labs connected successfully. Sufficient tokens available.")
            use_elevenlab = True
        else:
            print("Insufficient tokens or connection issue. Using fallback TTS.")
            use_elevenlab = False
    except Exception as e:
        print(f"Error connecting to Eleven Labs: {e}. Using fallback TTS.")
        use_elevenlab = False

# Waffle follow system
async def waffle_following(bot):
    global chat_channels, waffle_follow
    print(f"waffle's follow is set to: {waffle_follow}")

    if not waffle_follow:
        return

    try:
        connection = mysql.connector.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_name
        )
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT `value` FROM `flowmu_settings` WHERE `setting` = 'chat_channel'")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if result and 'value' in result:
                new_channel = result['value']
                if new_channel != chat_channels[0]:  # Only update if the channel changed
                    chat_channels = [new_channel]
                    print(f"Updated chat channel to: {chat_channels[0]}")
                    
                    # Rejoin new channel
                    await bot.part_channels([chat_channels[0]])  # Leave old channel
                    await bot.join_channels(chat_channels)  # Join new channel
                    
            else:
                chat_channels = [default_chat_channel]
                print("No valid chat_channel found in database. Using default chat channel.")
    except Error as e:
        chat_channels = [default_chat_channel]
        print(f"Database connectivity error: {e}. Using fallback settings.")



# Periodic check to update channels
async def periodic_check(interval, bot):
    while True:
        if waffle_follow:
            print("Running periodic check for waffle follow...")
            await waffle_following(bot)  # Ensure it's awaited
        await asyncio.sleep(interval)


# Start the TTS worker thread
def tts_worker():
    while True:
        text, is_flowmu = tts_queue.get()
        if is_flowmu:
            if use_elevenlab:
                speak_text_elevenlabs_flowmu(text)
            else:
                speak_text_gtts_chat(text)
        else:
            speak_text_gtts_chat(text)
        tts_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

# Function to handle chat TTS
def speak_text_gtts_chat(text):
    def speak():
        try:
            tts = gTTS(text=text, lang='en', tld='us', slow=False)
            tts.save("chat_output.mp3")
            process = subprocess.Popen(["mpg123", "-q", "chat_output.mp3"])
            while process.poll() is None:
                if tts_skip_event.is_set():
                    process.kill()
                    tts_skip_event.clear()
                    break
        except Exception as e:
            print(f"Error in TTS: {e}")
    speak()

# Function to handle Flow-Mu TTS using ElevenLabs
def speak_text_elevenlabs_flowmu(text):
    def speak():
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/" + elevenlabs_voice_id
            headers = {"Content-Type": "application/json", "xi-api-key": elevenlabs_key}
            data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}}
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                with open("flowmu_output.mp3", "wb") as f:
                    f.write(response.content)
                process = subprocess.Popen(["mpg123", "-q", "flowmu_output.mp3"])
                while process.poll() is None:
                    if tts_skip_event.is_set():
                        process.kill()
                        tts_skip_event.clear()
                        break
            else:
                print(f"Error in ElevenLabs TTS: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Error in ElevenLabs API: {e}")
    if flowmu_tts:
        speak()

# Define the bot class
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=chat_channels)

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f"Listening on: {chat_channels}")
        print("Bot is ready and running.")

    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users:
            return
        
        print(f"{message.author.name}: {message.content}")

        is_flowmu = message.author.name.lower() == 'flowmubot'.lower()
        print(f"Is Flow-Mu: {is_flowmu}")

        if chat_tts and not message.content.startswith('?') and message.author.name not in no_tts_users:
            cleaned_message = re.sub(r':\w+:', '', message.content).strip()
            if cleaned_message:
                if is_flowmu:
                    print(f"Processing Flow-Mu TTS: {cleaned_message}")
                    tts_queue.put((cleaned_message, True))
                else:
                    print(f"Processing message for TTS: {cleaned_message} (Flow-Mu: {is_flowmu})")
                    tts_queue.put((f"{message.author.name} says: {cleaned_message}", is_flowmu))

        await self.handle_commands(message)

    # TTS toggle command
    @commands.command()
    async def tts(self, ctx: commands.Context, task: str = 'x'):
        global chat_tts, chat_tts_lock, waffle_follow
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
        elif task == 'follow':
            waffle_follow = not waffle_follow  # Toggle the value
            await waffle_following(self)  # Pass the bot instance
            status = "enabled" if waffle_follow else "disabled"
            await ctx.send(f"Waffle following is now {status}.")
        else:
            if chat_tts and not chat_tts_lock:
                chat_tts = False
                await ctx.send("Chat TTS disabled.")
            else:
                chat_tts = True
                await ctx.send("Chat TTS enabled.")


# Initialize and run the bot
bot = Bot()

# Startup functions
elab_check()

async def startup():
    await waffle_following(bot)  # Ensure the bot instance is passed correctly
    bot.loop.create_task(periodic_check(30, bot))  # Start periodic check for channel updates

# Run the bot properly
bot.loop.run_until_complete(startup())  # Ensure startup function executes before bot starts
bot.run()


    
