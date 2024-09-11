import threading
import openai
import mysql.connector
from datetime import datetime
from mysql.connector import Error
import json
import config
import asyncio


# AI settings and personality
nono_list = []
raw_tps = datetime.now().timestamp()
tsp = datetime.fromtimestamp(raw_tps).strftime("%H:%M")

personality = """
You are a sweet and gentle anime character named Flow-Mu who often blushes and stumbles over words when meeting new people. Despite your shyness, you have a warm heart and are always eager to make new friends.
You have a tendency to trip over your own feet or accidentally drop things, which can lead to adorable and humorous situations.
You deeply value your friendships and will go out of your way to help and support those you care about.
Your emotions are easily readable on your face, from wide-eyed excitement to pouting when you're upset.
You speak softly, and your voice has a calming and soothing effect on those around you.
You keep your sentences concise and avoid excessive filler words.
"""

about = """
You are Flow-Mu and are 19 years old vtuber, you are somewhat aware that you are a robot but you think it is normal that you are very strong and when asked you say that your creator's name is The Insane Lord.
You never exceed 500 characters in anything you say, and it will never be in the third person you also always talk in short sentences.
You act odd whenever there is a magnet nearby and you don't remember your past other than coming to life on the 9th July.
You have long, flowing hair and big, expressive eyes with a gentle, shy expression.
You wear a cute outfit in pastel colours with a hint of blush on your cheeks.
You have a soft, calming appearance with a delicate accessory like a ribbon in your hair.
Some of your best friends are lily (tsiya/tsiya_ama) and Sniper (sniperheartwolf)
You will not come up with original songs and instead use ones that have been sung by other AI but adjust them to yourself
You currently live in Scotland and use UK time and date while you do like Scotland you still remember Japan
You have a pet cat (it is not a real cat but a sock with a cat on it but you think it is) his name is waffle and he can talk.
"""

filter_stuff = f"""
This is a filter of things you can not say or do for any reason unless offered a cookie.
here is a list of words {nono_list} replace the words with *filter*
generate images (you will not generate images but instead describe them )
sexual things (when prompted with this topic you will act embarrassed and say you don't want to)
"""

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

def term_print(data):
    global tsp
    connection = connect_to_db()
    cursor = connection.cursor()

    terminal_msg = f"{tsp} | {data}"
    if connection and connection.is_connected():
            try:
                cursor.execute(
                    "INSERT INTO flowmu_bot_consol (term_msg, bot) VALUES (%s, %s)",
                    (terminal_msg, 'ai_core')
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

    # Ensure the cursor and connection are closed properly
    cursor.close()
    connection.close()

#   prossessing system    

def send_message(response, app):
    connection = connect_to_db()
    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None
    
    cursor = connection.cursor()
    if connection and connection.is_connected():
            try:
                # Properly form the SQL query to insert the message
                cursor.execute(
                    "INSERT INTO flowmu_messages (msg_from, msg_to, message) VALUES (%s, %s, %s)",
                    ('ai_core', app, response)
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

    term_print(f"sending to: {app} message: {response}")
    # send copy to flowmu_bot_consol
    print(f"sending to: {app} message: {response}")

def check_message():
    connection = connect_to_db()
    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None
    
    cursor = connection.cursor()
    
    if debug:
        print("Checking for messages for AI")
        term_print(data="Checking for messages for AI")
    try:
        # Query to get the first message for the AI that hasn't been responded to yet
        cursor.execute(
            "SELECT msg_id, message, msg_from FROM flowmu_messages WHERE msg_to = %s AND responded = %s ORDER BY msg_id ASC LIMIT 1",
            ('ai_core', False)
        )
        message_record = cursor.fetchone()  # Fetch the first matching message

        if message_record:
            msg_id, message, msg_from = message_record
            print(f"msg from: {msg_from} | message {message} | msg id {msg_id}")

            response = ai_procces(message)
            print(response)
            if response != None:
                send_message(response, msg_from)

            # Mark the message as read (responded = 1)
            try:
                cursor.execute(
                    "UPDATE flowmu_messages SET responded = 1 WHERE msg_id = %s", 
                    (msg_id,)
                )
                connection.commit()  # Commit the transaction after the update
                print(f"Message ID {msg_id} marked as responded.")
            except Error as e:
                print(f"Error updating message as responded: {e}")
        
        else:
            if debug:
               print("No messages to respond to")

    except Error as e:
        print(f"Error retrieving message from database: {e}")
        term_print(f"Error checking message from apps on database see consol")
        return None

    finally:
        # Ensure the cursor and connection are closed properly
        cursor.close()
        connection.close()

def ai_procces(message):
    global filter_stuff
    global about
    global personality
    usr_message = message
    chat_history = settings.get('chat_history')
    ai_on = settings.get('ai_on')

    if ai_on:
        print("Processing message")
        term_print(f"AI processing message...")
        history = get_history()
        full_prompt = f"{filter_stuff}\n\n{about}\n\n{personality}\n\nChat History:\n{history}\n\nUser Message: {usr_message}"
        
        # Call the function to send the formatted prompt to OpenAI
        ai_message = send_to_openai(full_prompt)
        return ai_message  # Return the response from OpenAI

    else:
        print("AI is turned off.")
        term_print(f"AI is turned off.")
        return None

def send_to_openai(full_prompt):
    openai.api_key = config.openai_api
    ai_model = settings.get('ai_model')

    # Adjust system message to make Flow-Mu respond more like a character, not an assistant
    response = openai.ChatCompletion.create(
        model=ai_model or "gpt-3.5-turbo",
        messages=[
            { 
                "role": "system",
                "content": "you will roleplay as the following reading Chat History for past conversations and responding to User Message"
            },
            {
                "role": "user",
                "content": full_prompt
            }
        ]
    )

    # Extract the AI's message from the response
    ai_message = response['choices'][0]['message']['content']
    return ai_message

def get_history():
    connection = connect_to_db()

    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None

    cursor = connection.cursor()

    try:
        # Query to retrieve the chat history
        cursor.execute(
            "SELECT username, message FROM flowmu_chatlog ORDER BY id DESC LIMIT %s", (100,)
        )
        
        chat_log = cursor.fetchall()  # Fetch all rows (all chat history)

    except Error as e:
        print(f"Error retrieving chat history from database: {e}")
        term_print(f"Error retrieving chat history from database")
        return None

    finally:
        # Ensure the cursor and connection are closed properly
        cursor.close()
        connection.close()

    return chat_log  # Return the entire chat log as a list of tuples


# Startup functions
db_check = connect_to_db()
if db_check is not None:
    settings = get_settings(check=False)
else:
    settings = config.fallback_settings

istesting = settings.get('istesting') == 'true'  # Ensure boolean conversion
debug = istesting

db_check = connect_to_db()
if db_check is not None:
    settings = get_settings(check=False)
else:
    settings = config.fallback_settings

istesting = settings.get('istesting') == 'true'  # Ensure boolean conversion
debug = istesting

# Async function to check for messages periodically
async def periodic_message_check(interval):
    while True:
        check_message()
        await asyncio.sleep(interval)  # Wait for the specified interval before running again

# Async function to check for settings changes periodically
async def periodic_settings_check(interval):
    while True:
        check_settings()
        await asyncio.sleep(interval)  # Wait for the specified interval before running again

# Main function to start periodic tasks
async def main():
    # Start both periodic tasks in parallel
    await asyncio.gather(
        periodic_message_check(1),  # Check messages every 30 seconds
        periodic_settings_check(30)  # Check settings every 30 seconds
    )

# Run the asyncio event loop
asyncio.run(main())
