from twitchio.ext import commands
import mysql.connector
from mysql.connector import Error
import random
import config
from threading import Thread
from datetime import datetime
import asyncio

# global varebals
bot_accept_names = ["flow-mu", "@flow-mu", "@flowmubot", "@FlowMuBot","@Flow-Mu Bot#7224", "@Flow-Mu Bot", "flowmu", "flowmubot"] # Names AI will respond to
ignore_users = ["streamelements", "flowmubot", "soundalerts", "nightbot"]
bot_ver = '3.6'

#   |================================================================|
#   |##################   Configuration Below  ######################|
#   |================================================================|

def time_stamp():
    raw_tps = datetime.now().timestamp()
    tsp = datetime.fromtimestamp(raw_tps).strftime("%H:%M:%S")

    return tsp

#   Database stuff
def connect_to_db():
    try:
        connection = mysql.connector.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_name
        )
        if connection.is_connected():
            return connection
    
    except Error as e:
        print(f"Database connectivity error: {e}")
        return None

def get_settings(check):
    global settings
    global db_status

    try:
        # Establish connection to the database
        connection = connect_to_db()
        
        if connection and connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Query to fetch settings
            cursor.execute("SELECT `setting`, `value` FROM `flowmu_settings`")

            # Fetch all results and convert them to a dictionary
            result = cursor.fetchall()  # Use cursor.fetchall() to get all rows
            temp_settings = {row['setting']: row['value'] for row in result}

            # Close cursor and connection
            cursor.close()
            connection.close()

            # Update db_status if connection was successful
            db_status = True

        else:
            # If connection failed, set db_status to False and use fallback settings
            db_status = False
            print("Failed to connect to the database. Using fallback settings.")
            return config.fallback_settings

    except Error as e:  # If an error occurs, use fallback settings
        db_status = False
        print(f"Error fetching settings from database: {e}")
        return config.fallback_settings

    if check:
        # get settings from DB but don't change current settings
        return temp_settings
    else:
        # change and update global settings
        settings = temp_settings
        return settings

def check_settings():
    global settings        
    old_settings = settings.copy()
    new_settings = get_settings(check=True)

    print("checking settings")
    # compair changes from old_settings to new one
    if old_settings != new_settings:  
        # If there's a difference, update the global settings
        print("Settings have changed, updating global settings.")
        settings = get_settings(check=False)  # This will update the global settings
        print("Updated settings:", settings)
        term_print(f"Updated settings: {settings}")

    # If no change then say no change
    print("No settings have changed.")

def send_status():
    # Establish connection to the database
    connection = connect_to_db()
    cursor = connection.cursor()

    try:
        # Check if a status already exists for the bot
        cursor.execute("SELECT * FROM script_status WHERE script_name = %s", ('twitch_bot',))
        result = cursor.fetchone()

        if result:
            # If a record exists, update the status
            cursor.execute(
                "UPDATE script_status SET status = %s WHERE script_name = %s",
                ('running', 'twitch_bot')
            )
            print("Updated status to 'running' for twitch_bot")
        else:
            # If no record exists, insert a new status
            cursor.execute(
                'INSERT INTO script_status (script_name, status) VALUES (%s, %s)',
                ('twitch_bot', 'running')
            )
            print("Inserted new status 'running' for twitch_bot")

        connection.commit()

    except Error as e:
        print(f"Error updating/inserting status: {e}")

    finally:
        # Ensure the cursor and connection are closed properly
        cursor.close()
        connection.close()

def term_print(data):
    tsp = time_stamp()
    connection = connect_to_db()
    cursor = connection.cursor()

    terminal_msg = f"{tsp} | {data}"
    if connection and connection.is_connected():
            try:
                cursor.execute(
                    "INSERT INTO flowmu_bot_consol (term_msg, bot) VALUES (%s, %s)",
                    (terminal_msg, 'flowmu_twitch')
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

    # Ensure the cursor and connection are closed properly
    cursor.close()
    connection.close()

async def send_message(term_msg, message, user_message):
    # databse tabel layout msg_id msg_from msg_to message tabel name 'flowmu_messages'
    # Establish connection to the database
    connection = connect_to_db()
    global bot_accept_names
    global debug_mode
    ai_on = settings.get('ai_on')
    chat_history = settings.get('chat_history')
    random_reply_chance = settings.get('random_reply_chance')
    random_reply = settings.get('random_reply')
    cursor = connection.cursor()
    use_tos = settings.get('use_tos')

    # Check if user is already in the tos_users table
    cursor.execute('SELECT * FROM tos_users WHERE user_id = %s AND platform = %s AND status = 1'
                    , (message.author.id, 'twitch'))
    tos_user = cursor.fetchone()

    if random_reply == 'true':
        roll_chance = random.randint(0, 100)
        print(f"random_reply_chance: {random_reply_chance} chance gen {roll_chance}")
    else:
        roll_chance = 101

    if debug_mode:
        print(f"change to msg: {roll_chance}")
        print(f"Random Reply Chance: {random_reply_chance}, Chance: {roll_chance}")
        print(f"ToS status: {use_tos}")
        print(f"AI status: {ai_on}")
        print(f"Message: {user_message}, Bot Accept Names: {bot_accept_names}")

    # Send to message database

    # no randome reply for non ToS users
    if use_tos == 'true' and not tos_user and roll_chance <= int(random_reply_chance):
            print("User triggered random reply while ToS is active — message dropped.")
            term_print("User triggered random reply while ToS is active — message dropped.")
            cursor.close()
            connection.close()
            return

    # Default message handeling
    elif ai_on and (any(name in user_message.lower() for name in bot_accept_names) or roll_chance <= int(random_reply_chance)):
        response_to_id = 0
        print(tos_user)
        
        if tos_user or use_tos != 'true':
            print("Sending message to Afavoured_channelI Core.") 

            if connection and connection.is_connected():
                # Send to AI                            
                try:
                    cursor.execute(
                        "INSERT INTO flowmu_messages (msg_from, msg_to, message) VALUES (%s, %s, %s)",
                        ('flowmu_twitch', 'ai_core', user_message)
                    )

                    connection.commit()

                except Error as e:
                    print(f"Error sending message to database: {e}")

                # log message to chat hostory for user
                print(f"chat_history: {chat_history}")
                if chat_history == 'true':
                    if connection and connection.is_connected():
                        try:
                            await asyncio.sleep(1) #Let the AI process the las message then add the curent on to history
                            cursor.execute(
                                'INSERT INTO flowmu_chatlog (userid, username, message, is_response, platform, response_to) VALUES (%s, %s, %s, %s, %s, %s)',
                                (message.author.id, message.author.name, user_message, False, 'discord', None)  # 'None' since it's a user message
                            )

                            connection.commit()
                            await asyncio.sleep(1)
                            # Get the message ID for the user
                            cursor.execute(
                                'SELECT id FROM `flowmu_chatlog` WHERE userid = %s ORDER BY id DESC LIMIT 1',
                                (message.author.id,)
                            )

                            result = cursor.fetchone()
                            result_id = result[0] if result else None  # Fetch the latest message ID, set to None if no result
                            response_to_id = int(result_id)
                            
                            print(f"response_to_id: {response_to_id}")

                            cursor.execute(
                                "SELECT msg_id FROM flowmu_messages WHERE msg_from=%s AND msg_to=%s AND user=%s ORDER BY msg_id DESC LIMIT 1",
                                ('flowmu_discord', 'ai_core', message.author.name)
                            )
                            row = cursor.fetchone()
                            message_id = int(row[0]) if row else None
                            print(f"message_id: {message_id}")
                        
                        except Error as e:
                            print(f"Error sending message to database: {e}")             
                
                # After sending the message, check for AI response
                await response(message, response_to_id, message_id) 

        else:
            print("User did not agree to ToS")
            await message.channel.send("I can't speak to peole who haven't agree to my ToS use ?tos link or ?tos agree.")

    # Send consol to web rermeinal
    print("sending message to consol history panel")
    
    cursor.close()
    connection.close()
    term_print(term_msg)
    
async def response(message, response_to_id, message_id):
    ai_response = False
    ai_response_loops = 0
    global bot_info, bot

    chat_history = settings.get('chat_history')
    print("Checking for response from AI Core")
    term_print("Checking for response from AI Core")

    connection = connect_to_db()
    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return

    # Determine target channel
    if message:
        target_channel = message.channel
    else:
        # Twitch periodic check fallback
        if bot.connected_channels:
            target_channel = bot.connected_channels[0]
        else:
            return  # silent fail

    # Normalize message_id
    if message_id in (None, 0, "0"):
        message_id = None
    else:
        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            message_id = None

    # Mode: periodic scan if response_to_id == 1 (your proposed flag)
    periodic_scan = (message is None and response_to_id == 1)

    try:
        while ai_response_loops < 4:
            await asyncio.sleep(5)
            ai_response_loops += 1

            cursor = None
            try:
                cursor = connection.cursor(dictionary=True)

                # --- Fetch pending AI reply ---
                if periodic_scan or message_id is None:
                    # Oldest pending AI reply destined for twitch
                    cursor.execute(
                        """
                        SELECT msg_id, message, response_to_msg_id
                        FROM flowmu_messages
                        WHERE msg_to = %s
                          AND msg_from = %s
                          AND responded = %s
                        ORDER BY msg_id ASC
                        LIMIT 1
                        """,
                        ("flowmu_twitch", "ai_core", False)
                    )
                else:
                    # Match AI reply to a specific original msg_id
                    cursor.execute(
                        """
                        SELECT msg_id, message, response_to_msg_id
                        FROM flowmu_messages
                        WHERE msg_to = %s
                          AND msg_from = %s
                          AND responded = %s
                          AND response_to_msg_id = %s
                        ORDER BY msg_id ASC
                        LIMIT 1
                        """,
                        ("flowmu_twitch", "ai_core", False, message_id)
                    )

                response_record = cursor.fetchone()

                if not response_record:
                    if message_id is not None and not periodic_scan:
                        print(f"Attempt {ai_response_loops}/4: No matching AI response yet for response_to_msg_id={message_id}")
                    else:
                        print(f"Attempt {ai_response_loops}/4: No pending AI response yet for Twitch")
                    continue

                ai_message = response_record["message"]
                ai_msg_id = response_record["msg_id"]

                # Pull origin info (and optionally create chatlog threading id)
                info = message_info(
                    cursor,
                    response_record,
                    chat_history=chat_history,
                    bot_info=bot_info,
                    fallback_response_to_id=response_to_id,
                    connection=connection,
                )

                # Send to twitch
                await target_channel.send(ai_message)
                ai_response = True

                print(f"Response from AI Core (Loop {ai_response_loops}): {ai_message[:30]}...")
                term_print("Response from AI Core received and sent.")

                # If chat_history is on, message_info may have built a better thread id
                final_response_to_id = info.get("chatlog_response_to_id", response_to_id)

                if chat_history == "true":
                    chatbot_id, chatbot_nick = bot_info
                    try:
                        cursor.execute(
                            """
                            INSERT INTO flowmu_chatlog (userid, username, message, is_response, platform, response_to)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (chatbot_id, chatbot_nick, ai_message, True, "twitch", final_response_to_id)
                        )
                        connection.commit()
                    except Error as e:
                        print(f"Error writing AI message to chatlog: {e}")

                # --- Cleanup ---
                try:
                    # delete the AI reply row we used
                    cursor.execute("DELETE FROM flowmu_messages WHERE msg_id = %s", (ai_msg_id,))
                    connection.commit()

                    # delete origin row if we can identify it
                    origin_msg_id = info.get("origin_msg_id")
                    if origin_msg_id is not None:
                        cursor.execute("DELETE FROM flowmu_messages WHERE msg_id = %s", (origin_msg_id,))
                        connection.commit()
                        print(f"Deleted origin msg_id={origin_msg_id} and AI reply msg_id={ai_msg_id}")
                    else:
                        print(f"Deleted AI reply msg_id={ai_msg_id} (no origin msg_id found)")

                except Error as e:
                    print(f"Error cleaning up messages: {e}")

                break  # done

            except Error as e:
                print(f"Error retrieving response from database: {e}")

            finally:
                if cursor:
                    cursor.close()

        if not ai_response:
            if message_id is not None and not periodic_scan:
                print(f"No response from AI Core after {ai_response_loops} attempts ({ai_response_loops*5} seconds total) for response_to_msg_id={message_id}.")
            else:
                print(f"No response from AI Core after {ai_response_loops} attempts ({ai_response_loops*5} seconds total) for Twitch.")
            term_print("No response from AI Core after waiting.")

    except Exception as e:
        print(f"Critical error in response function: {e}")

    finally:
        if connection.is_connected():
            connection.close()

def message_info(
    cursor,
    response_record,
    *,
    chat_history="false",
    bot_info=None,
    fallback_response_to_id=0,
    connection=None,
):
    """
    Builds the context for an AI reply row.

    - Finds the origin message via response_to_msg_id (if present)
    - If chat_history is enabled and origin isn't from twitch, logs origin into flowmu_chatlog first
      and returns the new chatlog id to thread the AI response.
    """
    origin_msg_id = response_record.get("response_to_msg_id")
    origin_row = None
    chatlog_response_to_id = fallback_response_to_id

    if origin_msg_id is not None:
        cursor.execute(
            """
            SELECT msg_id, msg_from, msg_to, message, user, responded
            FROM flowmu_messages
            WHERE msg_id = %s
            LIMIT 1
            """,
            (origin_msg_id,)
        )
        origin_row = cursor.fetchone()

    # If we have an origin row from another app (ex: STT_Voice_App),
    # and chat_history is enabled, log it so the AI response can thread to it.
    if chat_history == "true" and origin_row and origin_row.get("msg_from") != "flowmu_twitch":
        try:
            # Use msg_from as the "username" since we don't have a real user id here
            cursor.execute(
                """
                INSERT INTO flowmu_chatlog (userid, username, message, is_response, platform, response_to)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (0, origin_row["msg_from"], origin_row["message"], False, origin_row["msg_from"], None)
            )
            connection.commit()

            cursor.execute("SELECT LAST_INSERT_ID() AS id")
            row = cursor.fetchone()
            if row and row.get("id") is not None:
                chatlog_response_to_id = int(row["id"])

        except Error as e:
            print(f"Error archiving origin message to chatlog: {e}")

    return {
        "origin_msg_id": origin_msg_id,
        "origin_row": origin_row,
        "chatlog_response_to_id": chatlog_response_to_id,
    }

async def periodic_check(interval):
    while True:
        old_settings = settings.copy()
        check_settings()  # This will call your existing check_settings function
        send_status() # send status update
        await response(None, 1, 0)

        # Check if channels have changed
        if old_settings.get('chat_channel') != settings.get('chat_channel'):
            await bot.update_channels()  # Update channels if there was a change
            await asyncio.sleep(3)
            await bot.connected_channels[0].send("*Flow-Mu shyly steps into the chat, looking around with a soft smile.*")
            await bot.connected_channels[0].send(
                "H-Hi, everyone! *blushes* I’m Flow-Mu! If you want to chat, just mention my name. "
                "I’ll be here to keep everyone company and share some smiles! *giggles*"
            )


        # Add other periodic checks here if needed

        await asyncio.sleep(interval)  # Wait for the specified interval (in seconds)


#   User welcome - Welcome new users and say hello to returning ones
async def user_welcome(user, user_id, message):
    # Connect to the database
    connection = connect_to_db()

    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return

    try:
        cursor = connection.cursor(dictionary=True)

        # 1. Check if user exists and get current stats
        cursor.execute(
            'SELECT msg_today, msg_total, username FROM user_mapping WHERE platform_id = %s AND platform = %s',
            (user_id, 'twitch')
        )
        user_db = cursor.fetchone()
        print(user_db)

        if user_db:
            # --- EXISTING USER ---
            
            # Check if they have NOT messaged today (0 is False)
            if user_db['msg_today'] == 0:
                #await message.channel.send(f"Welcome back {user_db['username']}!")
                await message.channel.send(f"Welcome back, {user_db['username']}! 🌸 It's always a delight to have you here again! Whether we're playing games or just sharing giggles over silly stories, your presence truly lights up our space. Pull up a comfy seat and let's create more fun memories together! 💖✨")

            # Increment Total
            new_total = user_db['msg_total'] + 1
            
            # 2. UPDATE: Set msg_today to 1 (True) and save new total
            cursor.execute(
                "UPDATE user_mapping SET msg_total = %s, msg_today = 1 WHERE platform_id = %s",
                (new_total, user_id)
            )

        else:
            # --- NEW USER ---
            
            # Send welcome
            #await message.channel.send(f"Welcome to the stream, {user}!")
            await message.channel.send(f"Hey there, {user}! 🌸 Welcome to the chat! Grab a cozy seat and let's make sweet, clumsy memories together! 💖")

            # Try to convert user_id to int for ffid (Twitch IDs are numbers)
            try:
                ffid = int(user_id)
            except ValueError:
                ffid = 0 # Fallback just in case

            # 3. INSERT: Add new user with msg_today = 1 (True) and msg_total = 1
            cursor.execute(
                "INSERT INTO user_mapping (ffid, platform, username, platform_id, user_auth, msg_today, msg_total) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (ffid, 'twitch', user, user_id, 0, 1, 1)
            )

        # 4. Commit changes to save them
        connection.commit()

    except Exception as e:
        print(f"Critical error in User function: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

#   clear users welcome
def clear_user_welcome():
    # Connect to the database
    connection = connect_to_db()

    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return

    try:
        cursor = connection.cursor()

        # Update ALL users to set msg_today to 0 (False)
        # No WHERE clause means it updates every row
        cursor.execute("UPDATE user_mapping SET msg_today = 0")

        # Commit is mandatory to save the change
        connection.commit()
        print("Reset: All user 'msg_today' flags set to False.")

    except Exception as e:
        print(f"Critical error clearing user welcome status: {e}")

    finally:
        # Ensure the connection is closed
        if connection.is_connected():
            cursor.close()
            connection.close()
# Startup functions
db_check = connect_to_db()
if db_check is not None:
    settings = get_settings(check=False)
else:
    settings = config.fallback_settings

testing_mode= settings.get('testing_mode') == 'true'  # Ensure boolean conversion
debug_mode = settings.get('debug_mode') == 'true'
clear_user_welcome()

#   |================================================================|
#   |##################   Bot code below  ###########################|
#   |================================================================|

if testing_mode:
    chat_channel = ['flowmubot']
    oauth_token = config.twitch_testing_oauth
else:
    chat_channel = settings.get('chat_channel', 'flowmubot')
    if isinstance(chat_channel, str):
        chat_channel = [chat_channel]  # Ensure it's a list
    oauth_token = config.twitch_oauth

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=chat_channel)
        self.current_channels = chat_channel

    async def event_ready(self):
        global bot_info  # Declare as global to use in other functions
        print(f'\nLogged in as | {self.nick}')
        print(f'User id is | {self.user_id}')
        print(f"listening on: {self.current_channels}")  # Ensure this reflects the current channels
        print(f"Testing mod: {testing_mode}")
        print(f"Debug mode: {debug_mode}")
        print(f"Bot vertion: {bot_ver}")
        print("The Bot is up and running.\n")

        # Save bot information globally
        bot_info = [self.user_id, self.nick]
        
        # Start the periodic settings check task
        self.loop.create_task(periodic_check(30))  # Check every 30 seconds

    async def update_channels(self):
        new_channels = settings.get('chat_channel', self.current_channels)
        connection = connect_to_db()
        cursor = connection.cursor(dictionary=True)
        
        # Ensure `new_channels` is treated as a list containing a single channel name, if it is a string
        if isinstance(new_channels, str):
            new_channels = [new_channels]  # Convert the string to a list containing one element

        # debug_modeging point to check what is being passed
        print(f"Updating channels: {new_channels} (type: {type(new_channels)})")

        if new_channels != self.current_channels:
            # Leave the current channels
            for channel in self.current_channels:
                print(f"Leaving channel: {channel}")  # debug_mode print for leaving
                await self.part_channels([f"#{channel.lstrip('#')}"])  # Ensure part works with proper format            # Join the new channels, ensure the channel has a '#' prefix

            for channel in new_channels:
                channel_with_hash = f"#{channel.lstrip('#')}"  # Ensure it starts with a #
                print(f"Attempting to join channel: {channel_with_hash} (type: {type(channel_with_hash)})")
                await self.join_channels([channel_with_hash])  # Pass the single channel as a list
            self.current_channels = new_channels  # Update the current channels list
            print(f"Updated channels: Now listening on: {self.current_channels}")
            term_print(f"Channel chaneged to: {self.current_channels}")

            # change settings enable/disable when chanel is changed
            try:
                change_settings = ['chat_history', 'random_reply', 'use_tos']
                favoured_channel ='the_insane_lord'
                term_print(f"Turning off settings due to channel change: {', '.join(change_settings)}")

                if channel == favoured_channel:
                    for setting in change_settings:
                        cursor.execute(
                            "UPDATE flowmu_settings SET value = %s WHERE setting = %s",
                            ('true', setting)
                        )
                    connection.commit()

                else:
                    for setting in change_settings:
                        cursor.execute(
                            "UPDATE flowmu_settings SET value = %s WHERE setting = %s",
                            ('false', setting)
                        )
                    connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")
            
    async def event_message(self, message):
        bot_running = settings.get('twitch_bot')
        
        tsp = time_stamp()
        
        if bot_running == 'true':
            if message.echo or message.author.name in ignore_users:
                return

            if not message.content.startswith('?'):
                if message.author.name != message.channel.name:
                    await user_welcome(message.author.name, message.author.id, message)

                user_message = str(message.content)
                term_msg = f"{tsp} | {message.author.name}: {message.content}"
                print(term_msg)

                
                # Await the send_message function to ensure it runs properly
                await send_message(term_msg, message, user_message)

            await self.handle_commands(message)
        
        else:
            if message.content.startswith('?'):
                print("Bot is turned off. Commands and AI are disabled.")
                term_print("Bot is turned off. Commands and AI are disabled.")
   
#   |================================================================|
#   |##################   Commands go below  ########################|
#   |================================================================|

#   bot introduction/testing command
    @commands.command()
    async def hello(self, ctx: commands.Context):
        await ctx.send(f'Hello {ctx.author.name}! I am Flow-Mu. It is great to be here. When my brain is working I only respond to my name')

#   info command
    @commands.command()
    async def info(self, ctx: commands.Context):
         await ctx.send(f'My name is Flow-Mu. I am an AI bot that is a friend for the chat. If you want to see how I work, use ?code. I am currently in Version: {bot_ver}')

#    DnD dice roll
    @commands.command()
    async def roll(self, ctx: commands.Context, dice: str = 'x'):
        dice_list = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20']
        dice = dice.lower()

        if dice == 'x':
            await ctx.send("Hey!! you have to pick a dice. What am I meant to roll?")
        elif dice in dice_list:
            num = int(dice.strip('d'))
            if debug_mode == True:
                print(f"Dice picked: {dice}, number set: {num}")
            result = random.randint(1, num)
            await ctx.send(f"Hey, here is what you got: {result}")
        else:
            await ctx.send(f"Sorry, I don't have that dice. I do have these: {', '.join(dice_list)}")

    @commands.command()
    async def code(self, ctx: commands.Context):
        await ctx.send("oh! you want to see my code *blushes with a smile* ok here it is: https://github.com/TheInsaneLord/Flow-Mu")

    @commands.command()
    async def boop(self, ctx, user: str="x"):
        boop_chance = 65  # success chance
        roll = random.randint(0, 100)
        global bot_accept_names

        if debug_mode == True:
            print(f"Detected user: {user}\n roll result: {roll}")

        # Check for user
        if user == "x":
            await ctx.send("You have to give me a name to boop.")

        # when flow-mu has to boop self
        if user in bot_accept_names:
            if debug_mode == True:
                print("flow-mu boops self")
            await ctx.send(f"Oh no!! I have to boop my own nose.")

            if roll < boop_chance: # bad boop
                await ctx.send("Flow-mu failed at booping her own nose and has ended up slaping her face instead.")
            else: # good boop
                await ctx.send("Oh good, nothing bad happened.")

        # Failed other users
        else:
            if debug_mode == True:
                    print("flow-mu boops other")

            if roll < boop_chance: # bad boop
                await ctx.send(f"Flow-mu tries to boop {user} on the nose but fails the stealth check and then trips up and falls on her face.")
                await ctx.send(f"Ouch!... You saw nothing {user}.")

            else: # good boop
                await ctx.send(f"Flow-mu succeeded in sneaking up and booping {user} on their nose.")
                await ctx.send(f"Ha ha ha I booped you {user}.")
    
    @commands.command()
    async def goto(self, ctx, goto_channel="x"):
        connection = connect_to_db()
        cursor = connection.cursor(dictionary=True)
        
        if goto_channel != 'X':
            # turn off setting when changing channel
            try:
                cursor.execute(
                    "UPDATE flowmu_settings SET value = %s WHERE setting = %s",
                    (goto_channel, 'chat_channel',
                    
                    )
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")


            cursor.close()
            connection.close()

            # let user know bot is moving to new channel
            term_print(f"Going to {goto_channel}")
            await ctx.send(f"Ok I will head over to {goto_channel}. Hope they are playing some thing fun.")
        else:
            term_print(f"Failed to go to: {goto_channel}")
            await ctx.send("Hmm... did you for get to say what channel I should go to")

    @commands.command()
    async def tos(self, ctx, status=('x')):
        connection = connect_to_db()
        cursor = connection.cursor(dictionary=True)
        user_id = str(ctx.author.id)
        platform = 'Twitch'  # Adjust this if you're using another platform
        username = str(ctx.author.name)
        status = status.lower()

        if status == 'agree':
            try:
                # Check if user is already in the tos_users table
                cursor.execute('SELECT * FROM tos_users WHERE user_id = %s AND platform = %s', (user_id, platform))
                result = cursor.fetchone()

                from datetime import datetime
                re_agree_note = f"Re-agreed on {datetime.utcnow().isoformat()} UTC"

                if not result:
                    # 🟢 New agreement
                    cursor.execute(
                        'INSERT INTO tos_users (user_id, platform, username, agreed_at, agreed_version, status, notes) VALUES (%s, %s, %s, NOW(), %s, %s, %s)',
                        (user_id, platform, username, '1.0', True, "Initial agreement")
                    )
                    connection.commit()
                    await ctx.send(f"Thank you {username} for agreeing to my ToS.")

                elif result['status'] == 0:
                    # 🔄 Re-agreeing after opt-out
                    existing_notes = result['notes'] or ""
                    updated_notes = (existing_notes + "\n" + re_agree_note).strip()

                    cursor.execute(
                        '''
                        UPDATE tos_users
                        SET status = 1, agreed_at = NOW(), agreed_version = %s, notes = %s
                        WHERE user_id = %s AND platform = %s
                        ''',
                        ('1.0', updated_notes, user_id, platform)
                    )
                    connection.commit()
                    await ctx.send(f"Welcome back {username}! Your agreement to the ToS has been re-activated.")

                else:
                    # ✅ Already agreed
                    await ctx.send(f"{username}, you have already agreed to my ToS — no need to do it again.")

            except Error as e:
                print(f"Error sending message to database: {e}")
                await ctx.send("Oh no, I'm having some issues — don't worry, @the_insane_lord will fix it.")
            finally:
                cursor.close()
                connection.close()


        elif status == 'disagree':
            try:
                # Fetch existing notes
                cursor.execute('SELECT notes FROM tos_users WHERE user_id = %s AND platform = %s', (user_id, platform))
                result = cursor.fetchone()
                existing_notes = result['notes'] if result and result['notes'] else ""

                # Build new opt-out note with timestamp
                from datetime import datetime
                optout_note = f"Opted out on {datetime.utcnow().isoformat()} UTC"
                updated_notes = (existing_notes + "\n" + optout_note).strip()

                # Soft delete: set status = 0 and update notes
                cursor.execute('''
                    UPDATE tos_users
                    SET status = 0, notes = %s
                    WHERE user_id = %s AND platform = %s AND status = 1
                ''', (updated_notes, user_id, platform))

                connection.commit()

                await ctx.send("You’ve opted out of Flow-Mu’s ToS. Please contact contact@insane-servers.co.uk to request data removal under GDPR.")

            except Error as e:
                print(f"Error processing opt-out: {e}")
                await ctx.send("Something went wrong while processing your opt-out. Please contact @the_insane_lord.")
            finally:
                cursor.close()
                connection.close()
       
        else:
            await ctx.send("You can find the ToS here: https://insane-servers.co.uk/flow-mu_tos. if you agree just do ?tos agree")

#   Change Reply chans

    @commands.command()
    async def rc(self, ctx, chance="-1"):
        connection = connect_to_db()
        cursor = connection.cursor(dictionary=True)
        
        if chance != -1 or chance != "-1":
            chance = chance.strip("%")
            chance = int(chance)
            
            print(f"Changeing Reply chance to: {chance}")
            
           # check the perms
            if (ctx.author.is_mod or ctx.author.name.lower() == ctx.channel.name.lower()):
                # chaneg chance
                print("User is authorised.")
                cursor.execute(
                    "UPDATE flowmu_settings SET value = %s WHERE setting = %s",
                    (chance, 'random_reply_chance')
                )
                connection.commit()
                await ctx.send(f"Reply chance updated to {chance}%.")

            else:
                await ctx.send(f"Sorry {ctx.author.name}, this command is for the streamer or mods only.")

        else:
            await ctx.send("Please provide a number between 0 and 100 (e.g. ?rc 25)")

# run section
if db_check is not None:
    print("Database connected.")

bot = Bot()
bot.run()
