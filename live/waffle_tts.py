from twitchio.ext import commands
import requests
import subprocess
import re
import threading
import config
import time
import asyncio
import mysql.connector
import os
import json
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
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

# event/allerts
eventsub_status = True
detect_ads = True

# save controls
save_audio = True
save_path = "/home/owen/Music/flow-mu/voice"

# Eleven Labs configuration
use_elevenlab = True
elevenlabs_key = config.elevenlabs_key
elevenlabs_voice_id = config.elevenlabs_voice_id  # Change this to your desired voice ID

# OAuth token and channels
default_chat_channel = 'the_insane_lord'
chat_channels = [default_chat_channel]
oauth_token = config.twitch_bot_oauth

# Twitch EventSub configuration
# Fixed config.py values:
# twitch_bot_id = Flow-Mu dev app client id (e.g. 6sbc****)
# twitch_bot_secrit = Flow-Mu dev app client secret
# twitch_bot_oauth = Flow-Mu bot chat oauth
# twitch_channel_id = broadcaster user ID (numeric, e.g. 131832145)
#
# Note:
# Your personal dev app client_id (e.g. ycjk****) is NOT used here.
# EventSub + OAuth must use the SAME app (Flow-Mu app) that generates the token.
#
# Waffle generates the broadcaster access token at startup.
# The token is stored in memory only and is not saved.

twitch_tts_client_id = config.twitch_bot_id
twitch_tts_client_secret = config.twitch_bot_secrit
twitch_tts_user_token = ""
twitch_tts_refresh_token = ""
twitch_tts_broadcaster_id = getattr(config, "twitch_channel_id", "")
twitch_tts_broadcaster_login = ""
twitch_tts_redirect_uri = "http://localhost"
twitch_tts_scopes = [
    "channel:read:ads",
    "channel:read:redemptions",
    "channel:read:subscriptions",
    "bits:read"
]
ad_message = "Oh, it looks like the ads are here. Take a little break while the stream pauses, okay?"

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

# Twitch token helpers
def build_twitch_auth_url():
    params = {
        "client_id": twitch_tts_client_id,
        "redirect_uri": twitch_tts_redirect_uri,
        "response_type": "code",
        "scope": " ".join(twitch_tts_scopes),
        "state": "waffle_auth"
    }
    return "https://id.twitch.tv/oauth2/authorize?" + urlencode(params)


def get_twitch_auth_code_from_browser():
    auth_url = build_twitch_auth_url()
    print("Opening Twitch authorization page...")
    print(auth_url)
    webbrowser.open(auth_url)

    redirected_url = input("Paste the full redirected localhost URL here: ").strip()
    parsed = urlparse(redirected_url)
    query = parse_qs(parsed.query)

    if query.get("state", [""])[0] != "waffle_auth":
        print("Twitch auth state did not match. Auth cancelled.")
        return ""

    code = query.get("code", [""])[0]
    if not code:
        print("No auth code found in pasted URL.")
        return ""

    return code


def exchange_twitch_code_for_token(code):
    global twitch_tts_user_token, twitch_tts_refresh_token

    try:
        data = {
            "client_id": twitch_tts_client_id,
            "client_secret": twitch_tts_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": twitch_tts_redirect_uri
        }

        r = requests.post("https://id.twitch.tv/oauth2/token", data=data)

        if r.status_code != 200:
            print(f"Failed to exchange Twitch auth code: {r.status_code}, {r.text}")
            return False

        token_data = r.json()
        twitch_tts_user_token = token_data.get("access_token", "")
        twitch_tts_refresh_token = token_data.get("refresh_token", "")

        if not twitch_tts_user_token:
            print("Twitch auth exchange succeeded but no access token was returned.")
            return False

        print("Twitch channel access token generated and stored in memory.")
        return True

    except Exception as e:
        print(f"Error exchanging Twitch auth code: {e}")
        return False


def request_twitch_channel_token():
    code = get_twitch_auth_code_from_browser()
    if not code:
        return False

    if not exchange_twitch_code_for_token(code):
        return False

    return validate_twitch_tts_token()


def validate_twitch_tts_token():
    global twitch_tts_user_token, twitch_tts_broadcaster_id, twitch_tts_broadcaster_login

    if not twitch_tts_user_token:
        print("No Twitch channel access token in memory. Requesting authorization...")
        return request_twitch_channel_token()

    try:
        headers = {"Authorization": f"Bearer {twitch_tts_user_token}"}
        r = requests.get("https://id.twitch.tv/oauth2/validate", headers=headers)

        if r.status_code == 200:
            data = r.json()
            scopes = data.get("scopes", [])
            expires_in = data.get("expires_in", 0)

            print(f"Twitch TTS token valid. Expires in {expires_in} seconds.")
            print(f"Twitch token login: {data.get('login')}")
            print(f"Twitch token user_id: {data.get('user_id')}")

            token_login = data.get("login", "")
            if token_login:
                twitch_tts_broadcaster_login = token_login.lower()

            token_user_id = data.get("user_id", "")
            if token_user_id:
                if twitch_tts_broadcaster_id and twitch_tts_broadcaster_id != token_user_id:
                    print(
                        f"Configured twitch_channel_id '{twitch_tts_broadcaster_id}' does not match "
                        f"authorized user_id '{token_user_id}'. Using authorized user_id."
                    )
                twitch_tts_broadcaster_id = token_user_id

            if "channel:read:ads" not in scopes:
                print("Warning: Twitch TTS token is missing required scope: channel:read:ads")
                return False

            if expires_in < 3600 and twitch_tts_refresh_token:
                return refresh_twitch_tts_token()

            return True

        print(f"Twitch TTS token validation failed: {r.status_code}, {r.text}")

        if twitch_tts_refresh_token:
            return refresh_twitch_tts_token()

        return request_twitch_channel_token()

    except Exception as e:
        print(f"Error validating Twitch TTS token: {e}")
        return False


def refresh_twitch_tts_token():
    global twitch_tts_user_token, twitch_tts_refresh_token

    if not twitch_tts_refresh_token:
        print("No Twitch TTS refresh token available. Re-auth is required.")
        return False

    try:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": twitch_tts_refresh_token,
            "client_id": twitch_tts_client_id,
            "client_secret": twitch_tts_client_secret
        }

        r = requests.post("https://id.twitch.tv/oauth2/token", data=data)

        if r.status_code != 200:
            print(f"Failed to refresh Twitch TTS token: {r.status_code}, {r.text}")
            return False

        token_data = r.json()
        twitch_tts_user_token = token_data["access_token"]
        twitch_tts_refresh_token = token_data.get("refresh_token", twitch_tts_refresh_token)

        print("Twitch TTS token refreshed. Update config.py with the new token if you want it saved after restart.")
        return True

    except Exception as e:
        print(f"Error refreshing Twitch TTS token: {e}")
        return False


# --- EventSub Setup ---
# To add a new EventSub event:
# 1. Add a detect_x toggle near the top with the other event toggles
# 2. Add any required scopes to twitch_tts_scopes (check Twitch docs)
# 3. Add a subscription call inside setup_eventsub_subscriptions()
#    (include correct condition fields like broadcaster_user_id, moderator_user_id, etc.)
# 4. Fill in the handle_x() function with your logic and toggle check (if not detect_x: return)
# 5. Add an elif branch in route_eventsub_notification() if the event type isn't already routed
# 6. Add a ?ev x toggle in the ev() command and update the unknown event message

async def create_eventsub_subscription(session_id, event_type, version, condition, label="EventSub"):
    url = "https://api.twitch.tv/helix/eventsub/subscriptions"
    headers = {
        "Client-ID": twitch_tts_client_id,
        "Authorization": f"Bearer {twitch_tts_user_token}",
        "Content-Type": "application/json"
    }
    data = {
        "type": event_type,
        "version": version,
        "condition": condition,
        "transport": {
            "method": "websocket",
            "session_id": session_id
        }
    }

    try:
        r = requests.post(url, headers=headers, json=data)

        if r.status_code in (200, 202):
            print(f"Subscribed to Twitch {label} EventSub.")
            return True

        print(f"Failed to subscribe to {label} EventSub: {r.status_code}, {r.text}")
        return False

    except Exception as e:
        print(f"Error creating {label} EventSub subscription: {e}")
        return False


async def setup_eventsub_subscriptions(session_id):
    if not twitch_tts_broadcaster_id:
        print("Missing broadcaster user ID. Cannot subscribe to EventSub events.")
        return

    # Currently active EventSub subscriptions
    # Ad EventSub is subscribed whenever EventSub is enabled.
    # detect_ads only controls whether Waffle responds to the event.
    await create_eventsub_subscription(
        session_id=session_id,
        event_type="channel.ad_break.begin",
        version="1",
        condition={"broadcaster_user_id": twitch_tts_broadcaster_id},
        label="ad break"
    )

    # Future EventSub subscriptions can be added here.
    # Example structure:
    # await create_eventsub_subscription(
    #     session_id=session_id,
    #     event_type="channel.follow",
    #     version="2",
    #     condition={
    #         "broadcaster_user_id": twitch_tts_broadcaster_id,
    #         "moderator_user_id": twitch_tts_broadcaster_id
    #     },
    #     label="follow"
    # )


# --- EventSub Event Handlers ---
async def handle_ad_break(bot, event):
    if not detect_ads:
        print("Ad detection disabled. Ignoring ad event.")
        return

    print("EventSub ad break detected.")

    current_chat_channel = chat_channels[0].lower() if chat_channels else ""

    if twitch_tts_broadcaster_login and current_chat_channel != twitch_tts_broadcaster_login:
        print(
            f"Ad break belongs to {twitch_tts_broadcaster_login}, "
            f"but Waffle is currently listening to {current_chat_channel}. Skipping ad TTS."
        )
        return

    if bot.connected_channels:
        channel = bot.connected_channels[0]
        await channel.send(ad_message)
        tts_queue.put((ad_message, True))
        print("Ad break message sent and queued TTS.")
    else:
        print("Ad break detected, but no connected chat channel found.")


async def handle_follow(bot, event):
    # Placeholder for future follow alerts.
    # EventSub type: channel.follow
    pass


async def handle_raid(bot, event):
    # Placeholder for future raid alerts.
    # EventSub type: channel.raid
    pass


async def handle_sub(bot, event):
    # Placeholder for future sub alerts.
    # EventSub types:
    # channel.subscribe
    # channel.subscription.message
    # channel.subscription.gift
    pass


async def handle_redeem(bot, event):
    # Placeholder for future channel point redeem alerts.
    # EventSub types:
    # channel.channel_points_custom_reward_redemption.add
    # channel.channel_points_automatic_reward_redemption.add
    pass


async def route_eventsub_notification(bot, subscription_type, event):
    if subscription_type == "channel.ad_break.begin":
        await handle_ad_break(bot, event)
    elif subscription_type == "channel.follow":
        await handle_follow(bot, event)
    elif subscription_type == "channel.raid":
        await handle_raid(bot, event)
    elif subscription_type in (
        "channel.subscribe",
        "channel.subscription.message",
        "channel.subscription.gift"
    ):
        await handle_sub(bot, event)
    elif subscription_type in (
        "channel.channel_points_custom_reward_redemption.add",
        "channel.channel_points_automatic_reward_redemption.add"
    ):
        await handle_redeem(bot, event)
    else:
        print(f"Unhandled EventSub notification type: {subscription_type}")


async def eventsub_listener(bot):
    if not eventsub_status:
        print("EventSub system disabled. EventSub listener not started.")
        return

    try:
        import websockets
    except ImportError:
        print("Missing Python package: websockets. Install it with: python -m pip install websockets")
        return

    if not validate_twitch_tts_token():
        print("Twitch TTS token is not ready. EventSub detection disabled.")
        return

    websocket_url = "wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds=30"

    while True:
        try:
            async with websockets.connect(websocket_url) as websocket:
                print("Connected to Twitch EventSub WebSocket.")

                async for raw_message in websocket:
                    message = json.loads(raw_message)
                    metadata = message.get("metadata", {})
                    payload = message.get("payload", {})
                    message_type = metadata.get("message_type")

                    if message_type == "session_welcome":
                        session_id = payload["session"]["id"]
                        print(f"EventSub session started: {session_id}")
                        await setup_eventsub_subscriptions(session_id)

                    elif message_type == "notification":
                        subscription = payload.get("subscription", {})
                        event = payload.get("event", {})
                        subscription_type = subscription.get("type", "")
                        await route_eventsub_notification(bot, subscription_type, event)

                    elif message_type == "session_keepalive":
                        pass

                    elif message_type == "session_reconnect":
                        reconnect_url = payload["session"].get("reconnect_url")
                        print("EventSub requested reconnect.")
                        if reconnect_url:
                            websocket_url = reconnect_url
                        break

                    elif message_type == "revocation":
                        print(f"EventSub subscription revoked: {payload}")

        except Exception as e:
            print(f"EventSub WebSocket error: {e}. Reconnecting in 10 seconds.")
            await asyncio.sleep(10)

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
                    old_channel = chat_channels[0]
                    chat_channels = [new_channel]
                    print(f"Updated chat channel to: {chat_channels[0]}")
                    
                    await bot.part_channels([old_channel])
                    await bot.join_channels(chat_channels)
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
            await waffle_following(bot)
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
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}"
            headers = {
                "Content-Type": "application/json",
                "accept": "audio/mpeg",
                "xi-api-key": elevenlabs_key
            }
            data = {
                "text": text,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }

            r = requests.post(url, json=data, headers=headers)
            if r.status_code != 200:
                print(f"Error in ElevenLabs TTS: {r.status_code}, {r.text}")
                return

            with open("flowmu_output.mp3", "wb") as f:
                f.write(r.content)

            p = subprocess.Popen(["mpg123", "-q", "flowmu_output.mp3"])
            while p.poll() is None:
                if tts_skip_event.is_set():
                    p.kill()
                    tts_skip_event.clear()
                    break

            if save_audio:
                try:
                    os.makedirs(save_path, exist_ok=True)
                    ts = time.strftime("%Y%m%d-%H%M%S")
                    dest = os.path.join(save_path, f"{ts}.mp3")
                    with open(dest, "wb") as f:
                        f.write(r.content)
                except Exception as e:
                    print(f"Save error: {e}")

        except Exception as e:
            print(f"Error in ElevenLabs API: {e}")

    if flowmu_tts:
        speak()

# Define the bot class
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=oauth_token,
            prefix='?',
            initial_channels=chat_channels
        )

    async def event_ready(self):
        print("\n--- TTS Bot Ready ---")
        print(f'Logged in as | {self.nick}')
        print(f"Listening on: {chat_channels}")
        print("Bot is ready and running.")
        print("------\n")

    async def event_ad_break(self, payload):
        if not detect_ads:
            print("Ad detection disabled. Ignoring ad break event.")
            return
        if not self.connected_channels:
            print("Ad break detected, but no connected channel found.")
            return

        channel = self.connected_channels[0]
        current_chat_channel = channel.name.lower() if hasattr(channel, 'name') else (chat_channels[0].lower() if chat_channels else "")

        # Only announce ads in the broadcaster's own channel
        if twitch_tts_broadcaster_login and current_chat_channel != twitch_tts_broadcaster_login:
            print(
                f"Ad break belongs to {twitch_tts_broadcaster_login}, "
                f"but current channel is {current_chat_channel}. Skipping ad message."
            )
            return

        await channel.send(ad_message)
        tts_queue.put((ad_message, True))
        print("Ad break detected. Sent ad break message and queued TTS.")

    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users:
            return

        print(f"{message.author.name}: {message.content}")

        is_flowmu = message.author.name.lower() == 'flowmubot'
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


#  ---  Chat Commands ---
    @commands.command()
    async def ad(self, ctx: commands.Context):
        await ctx.send(ad_message)
        tts_queue.put((ad_message, True))
        print(f"Manual ad message sent by {ctx.author.name} and queued TTS.")

    @commands.command()
    async def ev(self, ctx: commands.Context, event: str = 'x'):
        global detect_ads
        event = event.lower()

        if event == 'ad':
            if not eventsub_status:
                await ctx.send("EventSub is disabled. Restart Waffle with eventsub_status = True to use events.")
                return

            detect_ads = not detect_ads
            status = "enabled" if detect_ads else "disabled"
            await ctx.send(f"Ad detection is now {status}.")
            return

        await ctx.send("Unknown event. Available: ad")

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
            waffle_follow = not waffle_follow
            await waffle_following(self)
            status = "enabled" if waffle_follow else "disabled"
            await ctx.send(f"Waffle following is now {status}.")
        else:
            if chat_tts and not chat_tts_lock:
                chat_tts = False
                await ctx.send("Chat TTS disabled.")
            else:
                chat_tts = True
                await ctx.send("Chat TTS enabled.")

async def main():
    bot = Bot()

    # --- SCHEDULERS ---
    print("\n--- Schedulers ---")
    await waffle_following(bot)
    bot.loop.create_task(periodic_check(30, bot))
    print("--- Schedulers Done ---")

    # --- EVENT SUBS ---
    if eventsub_status:
        print("--- EventSub Setup ---")
        validate_twitch_tts_token()
        bot.loop.create_task(eventsub_listener(bot))
        print("--- EventSub Ready ---")
    else:
        print("--- EventSub Skipped (eventsub_status = False) ---")

    # --- BOT RUN ---
    print("\n--- Bot Starting ---")
    await bot.start()

if __name__ == "__main__":
    # --- STARTUP FUNCTIONS ---
    print("--- Startup Functions ---")
    elab_check()
    print("--- Startup Functions Done ---")

    # --- RUN ---
    asyncio.run(main())
