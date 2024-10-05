import discord
from discord.ext import commands
import mysql.connector
from mysql.connector import Error
import config
import random
from datetime import datetime
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="?", case_insensitive=True, intents=intents)


bot_accept_names = ["flow-mu", "@flow-mu", "@flowmubot", "@FlowMuBot","@Flow-Mu Bot#7224", "@Flow-Mu Bot"] # Names AI will respond to
ignore_users = [""]

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
        # Check if a status already exists for the discord bot
        cursor.execute("SELECT * FROM script_status WHERE script_name = %s", ('discord_bot',))
        result = cursor.fetchone()

        if result:
            # If a record exists, update the status
            cursor.execute(
                "UPDATE script_status SET status = %s WHERE script_name = %s",
                ('running', 'discord_bot')
            )
            print("Updated status to 'running' for discord_bot")
        else:
            # If no record exists, insert a new status
            cursor.execute(
                'INSERT INTO script_status (script_name, status) VALUES (%s, %s)',
                ('discord_bot', 'running')
            )
            print("Inserted new status 'running' for discord_bot")

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
                    (terminal_msg, 'flowmu_discord')
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
        # Check if user is already in the tos_users table
        cursor.execute('SELECT * FROM tos_users WHERE user_id = %s AND platform = %s'
                        , (message.author.id, 'discord'))
        tos = cursor.fetchone()
        print(tos)
        if tos:
            print("Sending message to AI Core.")
            
            print(f"AI ON: {ai_on}")
            print(f"Random Reply Chance: {random_reply_chance}, Chance: {chance}")
            print(f"Message: {user_message}, Bot Accept Names: {bot_accept_names}")

            if connection and connection.is_connected():
                # log message to chat hostory for user
                print(f"chat_history: {chat_history}")
                if chat_history == 'true':
                    if connection and connection.is_connected():
                        try:
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
                        
                        except Error as e:
                            print(f"Error sending message to database: {e}")             
                
                # Send to AI                            
                try:
                    cursor.execute(
                        "INSERT INTO flowmu_messages (msg_from, msg_to, message) VALUES (%s, %s, %s)",
                        ('flowmu_discord', 'ai_core', user_message)
                    )

                    connection.commit()

                except Error as e:
                    print(f"Error sending message to database: {e}")

                
                # After sending the message, check for AI response
                await response(message, response_to_id)
        
        else:
            print("User did not agree to ToS")
            await message.channel.send("I can't speak to peole who haven't agree to my ToS use ?tos .")

    # Send consol to web rermeinal
    print("sending message to consol history panel")
    
    cursor.close()
    connection.close()
    term_print(term_msg)

    
async def response(message, response_to_id):
    global bot_info
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

        # Query to find the first message where msg_to is 'flowmu_discord' and msg_from is 'ai_core'
        cursor.execute(
            "SELECT msg_id, message FROM flowmu_messages WHERE msg_to = %s AND msg_from = %s AND responded = %s ORDER BY msg_id ASC LIMIT 1",
            ('flowmu_discord', 'ai_core', False)
        )

        # Fetch the first matching message
        response_record = cursor.fetchone()

        if response_record:
            ai_message = response_record['message']
            print(f"Response from AI Core: {ai_message}")

            # Send the AI's response back to the discord chat
            await message.channel.send(ai_message)

            # Add response to chat history
            if chat_history == 'true':
                chatbot_id, chatbot_nick = bot_info  # Get bot info

                if connection and connection.is_connected():
                    try:
                        cursor.execute(
                            'INSERT INTO flowmu_chatlog (userid, username, message, is_response, platform, response_to) VALUES (%s, %s, %s, %s, %s, %s)',
                            (chatbot_id, chatbot_nick, ai_message, True, 'discord', response_to_id)
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

                # Delete the original message from flowmu_discord
                cursor.execute(
                    "DELETE FROM flowmu_messages WHERE msg_from = %s AND msg_to = %s AND responded = %s",
                    ('flowmu_discord', 'ai_core', True)
                )
                connection.commit()

                print(f"Deleted original and response messages for msg_id {response_record['msg_id']}")
            except Error as e:
                print(f"Error cleaning up messages: {e}")

        else:
            print("No response found from AI Core.")
            term_print("No response found from AI Core")

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
        send_status() # send status update

        # Add other periodic checks here if needed

        await asyncio.sleep(interval)  # Wait for the specified interval (in seconds)



#   |================================================================|
#   |##################   Bot code below  ###########################|
#   |================================================================|

# Removing help
bot.remove_command('help')
print("Bot is loading...\nConnecting to Discord...")

@bot.event
async def on_ready():
    global bot_info
    await bot.change_presence(activity=discord.Game(name='I am Flow-Mu a AI pal'))
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)
    print(f"Bot running as: {bot.user.name}")
    print(f"Testing mode: {istesting}")    
    print("Loading Done")
    print(" ")
    print("The bot is up and running")
    print(" ")
    bot_info = [bot.user.id, bot.user.name]

    # Start the periodic settings check task
    bot.loop.create_task(periodic_check(30))  # Check every 30 seconds

@bot.event
async def on_message(message):
    bot_running = settings.get('discord_bot')
    tsp = time_stamp()

    if bot_running != 'false':
        if message.author == bot.user or message.author.name in ignore_users:
            return

        if not message.content.startswith('?'):
            user_message = str(message.content)
            term_msg = f"{tsp} | {message.author.name}: {message.content}"
            print(term_msg)
            await send_message(term_msg, message, user_message)
            
        await bot.process_commands(message)
    
    else:
        if message.content.startswith('?'):
            print("Bot is turned off.")
            term_print("Bot is turned off. Commands and AI are disabled.")
            await message.channel.send("Sorry, the bot is currently disabled.")
        else:
            print("Bot is turned off. Ignoring non-command message.")
            term_print("Bot is turned off. Ignoring non-command message.")

#   |================================================================|
#   |##################  Commands go below  ########################|
#   |================================================================|

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.hybrid_command(name="info", help="Gives you information on the bot", with_app_command=True)
async def info(ctx):
    embed = discord.Embed(title="Insane_L Bot", description="to help make things easier on the server.", color=0x98B1B7)

    embed.add_field(name="owner:", value="The insane lord")
    embed.add_field(name="Coder:", value="The insane lord")
    embed.add_field(name="Version:", value="3.1")

    await ctx.send(embed=embed)

@bot.hybrid_command(name="roll", pass_context=True)
async def roll(ctx, dice: str = 'x'):
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

#   show the code on GitHub
@bot.hybrid_command(name="code", pass_context=True)
async def code(ctx):
    await ctx.send("oh! you want to see my code *blushes with a smile* ok here it is: https://github.com/TheInsaneLord/Flow-Mu")

@bot.command()
async def boop(ctx, user: str="x"):
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

    # Failed other users
    else:
        if debug == True:
                print("flow-mu boops other")

        if roll < chance: # bad boop
            await ctx.send(f"Flow-mu tries to boop {user} on the nose but fails the stealth check and then trips up and falls on her face.")
            await ctx.send(f"Ouch!... You saw nothing {user}.")

        else: # good boop
            await ctx.send(f"Flow-mu succeeded in sneaking up and booping {user} on their nose.")
            await ctx.send(f"Ha ha ha I booped you {user}.")

@bot.command()
async def tos(ctx, status=('x')):
    connection = connect_to_db()
    cursor = connection.cursor(dictionary=True)
    user_id = str(ctx.author.id)
    platform = 'Discord'  # Adjust this if you're using another platform
    username = str(ctx.author.name)
    status = status.lower()

    if status == 'agree':
        try:
            # Check if user is already in the tos_users table
            cursor.execute('SELECT * FROM tos_users WHERE user_id = %s AND platform = %s', (user_id, platform))
            result = cursor.fetchone()

            if not result:
                    # Insert new user agreement into tos_users table
                cursor.execute(
                    'INSERT INTO tos_users (user_id, platform, username, agreed_at, agreed_version, status) VALUES (%s, %s, %s, NOW(), %s, %s)',
                    (user_id, platform, username, '1.0', True)
                )
                connection.commit()
                await ctx.send(f"Thank you {username} for agreeing to my ToS.")
            else:
                await ctx.send(f"{username}, you have already agreed to my ToS you don't need to do it agin.")

        except Error as e:
            print(f"Error sending message to database: {e}")
            await ctx.send("Oh no, I am having some issues don't worry @the_insane_lord will look at it.")
        finally:
            cursor.close()
            connection.close()
    else:
        await ctx.send("You can find the ToS here: https://insane-servers.co.uk/flow-mu_tos. if you agree just do ?tos agree")

# Startup functions
db_check = connect_to_db()
if db_check is not None:
    settings = get_settings(check=False)
else:
    settings = config.fallback_settings

istesting = settings.get('istesting') == 'true'  # Ensure boolean conversion
debug = istesting
key = config.discord_key

# run section
if db_check is not None:
    print("Database connected.")

bot.run(key)

