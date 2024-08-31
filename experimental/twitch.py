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
settings = config.fallback_settings
bot_accept_names = ["flow-mu", "@flow-mu", "@flowmubot", "@FlowMuBot","@Flow-Mu Bot#7224", "@Flow-Mu Bot"] # Names AI will respond to
istesting = False
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

#   bot functions
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

    except Error as e:  # If error happens it will use fallback settings from config.py
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
    old_settings = settings.copy
    new_settings = get_settings(check=True)

    # compair changes from old_settings to new one
    if old_settings != new_settings:  
        # If there's a difference, update the global settings
        print("Settings have changed, updating global settings.")
        settings = get_settings(check=False)  # This will update the global settings
        print("Updated settings:", settings)

    # If no change then say no change
    print("No settings have changed.")

def send_status():
    while True:
        try:
            print(f"Status update sent: {response.status_code}")
        except Exception as e:
            print(f"Error sending status update: {e}")
        # Send status every 30 seconds


def send_message(term_msg, message):
    # databse tabel layout msg_id msg_from msg_to message tabel name 'flowmu_messages'
    # Establish connection to the database
    connection = connect_to_db()
    global bot_accept_names
    ai_on = True
    random_reply_chance = 5
    cursor = connection.cursor()

    # Send to message database
    if ai_on and any(name in message.lower() for name in bot_accept_names):
        print("Sending message to AI Core.")
        
        if connection and connection.is_connected():
            try:
                # Properly form the SQL query to insert the message
                cursor.execute(
                    "INSERT INTO flowmu_messages (msg_from, msg_to, message) VALUES (%s, %s, %s)",
                    ('flowmu_twitch', 'ai_core', message)
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

    # Send consol to web rermeinal
    print("sending message to chat history panel")
    # tabel name: 'flowmu_bot_consol' coloms: 'msg_id term_msg bot'
    if connection and connection.is_connected():
            try:
                cursor.execute(
                    "INSERT INTO flowmu_bot_consol (term_msg, bot) VALUES (%s, %s)",
                    (term_msg, 'flowmu_twitch')
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

    # Ensure the cursor and connection are closed properly
    cursor.close()
    connection.close()

def response():
    asyncio.sleep(3) 
    print("response from AI Core")
    # Connect to the database
    connection = connect_to_db()
    
    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None  # Return None if the connection fails

    try:
        cursor = connection.cursor(dictionary=True)
        
        # Query to find a message where msg_to is 'flowmu_twitch' and msg_from is 'ai_core'
        cursor.execute(
            "SELECT * FROM flowmu_messages WHERE msg_to = %s AND msg_from = %s ORDER BY msg_id ASC LIMIT 1",
            ('flowmu_twitch', 'ai_core')
        )
        
        # Fetch the first matching message
        response_message = cursor.fetchone()
        
        if response_message:
            # If a message is found, return it or process it further
            print("Response found from AI Core.")
            return response_message
        else:
            # If no message is found, return None
            print("No response found from AI Core.")
            return None
    
    except Error as e:
        print(f"Error retrieving response from database: {e}")
        return None

    finally:
        # Ensure the cursor and connection are closed properly
        cursor.close()
        connection.close()

# strart up functions
connect_to_db()

#   |================================================================|
#   |##################   Bot code below  ###########################|
#   |================================================================|

if istesting:
    chat_channel = ['flowmubot']
    oauth_token = config.twitch_testing_oauth
else:
    chat_channel = ["the_insane_lord"] # get from settings
    oauth_token = config.twitch_oauth # get from settings

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=oauth_token, prefix='?', initial_channels=chat_channel)

    async def event_ready(self):
        print(f'\nLogged in as | {self.nick}')
        print(f'User id is | {self.user_id}')
        print(f"listining on: {chat_channel}")
        print(f"Testing mod: {istesting}")
        print("The Bot is up and running.\n")


    async def event_message(self, message):
        if message.echo or message.author.name in ignore_users:
            return
        
        user_message = str(message.content)
        term_msg = f"{tsp} | {message.author.name}: {message.content}"
        print(term_msg)

        send_message(term_msg, user_message)

        await self.handle_commands(message)


#   |================================================================|
#   |##################   Commands go below  ########################|
#   |================================================================|

bot = Bot()
bot.run()
