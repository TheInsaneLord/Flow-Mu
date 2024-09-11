from twitchio.ext import commands
import mysql.connector
from mysql.connector import Error
import random
import config
import json
from threading import Thread
from datetime import datetime
import asyncio

# global varebals
bot_accept_names = ["flow-mu", "@flow-mu", "@flowmubot", "@FlowMuBot","@Flow-Mu Bot#7224", "@Flow-Mu Bot"] # Names AI will respond to
ignore_users = []
raw_tps = datetime.now().timestamp()
tsp = datetime.fromtimestamp(raw_tps).strftime("%H:%M")

#   |================================================================|
#   |##################   Configuration Below  ######################|
#   |================================================================|

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

    # If no change then say no change
    print("No settings have changed.")

def send_status():
    # Send status every 30 seconds
    connection = connect_to_db()
    cursor = connection.cursor()

    cursor.execute(
        'INSERT INTO script_status (script_name, status) VALUES (%s, %s)',
        ('twitch_bot', 'running')
    )

    connection.commit()
    # Ensure the cursor and connection are closed properly
    cursor.close()
    connection.close()

def term_print(data):
    global tsp
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
    global debug
    ai_on = settings.get('ai_on')
    chat_history = settings.get('chat_history')
    random_reply_chance = settings.get('random_reply_chance')
    random_reply = settings.get('random_reply')
    cursor = connection.cursor()

    if random_reply == 'true':
        chance = random.randint(0, 100)
        print(f"random_reply_chance: {random_reply_chance} chance gen {chance}")
    else:
        chance = 101

    if debug:
        print(f"change to msg: {chance}")
        print(f"random_reply_chance: {random_reply_chance}")

    # Send to message database
    if ai_on and (any(name in user_message.lower() for name in bot_accept_names) or chance <= int(random_reply_chance)):
        print("Sending message to AI Core.")
        
        print(f"AI ON: {ai_on}")
        print(f"Random Reply Chance: {random_reply_chance}, Chance: {chance}")
        print(f"Message: {user_message}, Bot Accept Names: {bot_accept_names}")


        if connection and connection.is_connected():
            try:
                # Properly form the SQL query to insert the message
                cursor.execute(
                    "INSERT INTO flowmu_messages (msg_from, msg_to, message) VALUES (%s, %s, %s)",
                    ('flowmu_twitch', 'ai_core', user_message)
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

            # log message to chat hostory for user
            if chat_history == 'true':
                if connection and connection.is_connected():
                    try:
                        cursor.execute(
                            'INSERT INTO flowmu_chatlog (userid, username, message, is_response, platform) VALUES (%s, %s, %s, %s, %s)',
                            (message.author.id, message.author.name, user_message, False, 'twitch')
                        )

                        connection.commit()

                    except Error as e:
                        print(f"Error sending message to database: {e}")

            # After sending the message, check for AI response
            await response(message)

    # Send consol to web rermeinal
    print("sending message to consol history panel")
    
    cursor.close()
    connection.close()
    term_print(term_msg)

    
async def response(message):
    global bot_info  # Make sure we can access bot_info here
    await asyncio.sleep(4)  # Simulate processing time
    chat_history = settings.get('chat_history')
    print("Checking for response from AI Core")
    term_print("Checking for response from AI Core")

    # Connect to the database
    connection = connect_to_db()

    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return  # Exit if the database connection fails

    try:
        cursor = connection.cursor(dictionary=True)

        # Query to find the first message where msg_to is 'flowmu_twitch' and msg_from is 'ai_core'
        cursor.execute(
            "SELECT msg_id, message FROM flowmu_messages WHERE msg_to = %s AND msg_from = %s AND responded = %s ORDER BY msg_id ASC LIMIT 1",
            ('flowmu_twitch', 'ai_core', False)
        )

        # Fetch the first matching message
        response_record = cursor.fetchone()

        if response_record:
            ai_message = response_record['message']
            print(f"Response from AI Core: {ai_message}")

            # Send the AI's response back to the Twitch chat
            await message.channel.send(ai_message)

            # Add response to chat history
            if chat_history == 'true':
                chatbot_id, chatbot_nick = bot_info  # Get bot info

                if connection and connection.is_connected():
                    try:
                        cursor.execute(
                            'INSERT INTO flowmu_chatlog (userid, username, message, is_response, platform) VALUES (%s, %s, %s, %s, %s)',
                            (chatbot_id, chatbot_nick, ai_message, False, 'twitch')
                        )

                        connection.commit()

                    except Error as e:
                        print(f"Error sending message to database: {e}")
            
            # clean the dtatbase of read messages
            try:
                # Delete the AI response after sending
                cursor.execute(
                    "DELETE FROM flowmu_messages WHERE msg_id = %s",
                    (response_record['msg_id'],)
                )
                connection.commit()

                # Delete the original message from flowmu_twitch
                cursor.execute(
                    "DELETE FROM flowmu_messages WHERE msg_from = %s AND msg_to = %s AND responded = %s",
                    ('flowmu_twitch', 'ai_core', True)
                )
                connection.commit()

                print(f"Deleted original and response messages for msg_id {response_record['msg_id']}")
            except Error as e:
                print(f"Error cleaning up messages: {e}")

        else:
            print("No response found from AI Core.")

    except Error as e:
        print(f"Error retrieving response from database: {e}")
        term_print("Error retrieving response from database")

    finally:
        # Ensure the cursor and connection are closed properly
        cursor.close()
        connection.close()


async def periodic_check(interval):
    while True:
        old_settings = settings.copy()
        check_settings()  # This will call your existing check_settings function

        # Check if channels have changed
        if old_settings.get('chat_channel') != settings.get('chat_channel'):
            await bot.update_channels()  # Update channels if there was a change

        # Add other periodic checks here if needed

        await asyncio.sleep(interval)  # Wait for the specified interval (in seconds)

# Startup functions
db_check = connect_to_db()
if db_check is not None:
    settings = get_settings(check=False)
else:
    settings = config.fallback_settings

istesting = settings.get('istesting') == 'true'  # Ensure boolean conversion
debug = istesting

#   |================================================================|
#   |##################   Bot code below  ###########################|
#   |================================================================|

if istesting:
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
        print(f"Testing mod: {istesting}")
        print("The Bot is up and running.\n")

        # Save bot information globally
        bot_info = [self.user_id, self.nick]
        
        # Start the periodic settings check task
        self.loop.create_task(periodic_check(30))  # Check every 30 seconds

    async def update_channels(self):
        new_channels = settings.get('chat_channel', self.current_channels)
        
        # Ensure `new_channels` is treated as a list containing a single channel name, if it is a string
        if isinstance(new_channels, str):
            new_channels = [new_channels]  # Convert the string to a list containing one element

        # Debugging point to check what is being passed
        print(f"Updating channels: {new_channels} (type: {type(new_channels)})")

        if new_channels != self.current_channels:
            # Leave the current channels
            for channel in self.current_channels:
                print(f"Leaving channel: {channel}")  # Debug print for leaving
                await self.part_channels([f"#{channel.lstrip('#')}"])  # Ensure part works with proper format
            # Join the new channels, ensure the channel has a '#' prefix
            for channel in new_channels:
                channel_with_hash = f"#{channel.lstrip('#')}"  # Ensure it starts with a #
                print(f"Attempting to join channel: {channel_with_hash} (type: {type(channel_with_hash)})")
                await self.join_channels([channel_with_hash])  # Pass the single channel as a list
            self.current_channels = new_channels  # Update the current channels list
            print(f"Updated channels: Now listening on: {self.current_channels}")


            
    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users:
            return
        
        if not message.content.startswith('?'):
            user_message = str(message.content)
            term_msg = f"{tsp} | {message.author.name}: {message.content}"
            print(term_msg)

            # Await the send_message function to ensure it runs properly
            await send_message(term_msg, message, user_message)

        await self.handle_commands(message)


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
        await ctx.send(f'My name is Flow-Mu I am a AI bot that is a friend for the chat if you want to see how I work then use ?code I am currently in Version 3.0')

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

    @commands.command()
    async def boop(self, ctx, user: str="x"):
        chance = 65  # success chance
        roll = random.randint(0, 100)
        global bot_accept_names

        if debug == True:
            print(f"Detected user: {user}\n roll result: {roll}")

        # Check for user
        if user == "x":
            await ctx.send("You have to give me a name to boop.")

        # when flow-mu has to boop self
        if user in bot_accept_names:
            if debug == True:
                print("flow-mu boops self")
            await ctx.send(f"Oh no!! I have to boop my own nose.")

            if roll < chance: # bad boop
                await ctx.send("Flow-mu failed at booping her own nose and has ended up slaping her face instead.")
            else: # good boop
                await ctx.send("Oh good, nothing bad happened.")

            return

        # Failed other users
        if debug == True:
                print("flow-mu boops other")

        if roll < chance: # bad boop
            await ctx.send(f"Flow-mu tries to boop {user} on the nose but fails the stealth check and then trips up and falls on her face.")
            await ctx.send(f"Ouch!... You saw nothing {user}.")

        else: # good boop
            await ctx.send(f"Flow-mu succeeded in sneaking up and booping {user} on their nose.")
            await ctx.send(f"Ha ha ha I booped you {user}.")
    
    @commands.command()
    async def st(self, ctx: commands.Context):
        check_settings()
        term_print(settings)
        #settings = get_settings(check=True)
        #await ctx.send(settings)
        #print(settings)

# run section
if db_check is not None:
    print("Database connected.")

bot = Bot()
bot.run()