import threading
from collections import defaultdict
import openai
import tiktoken
import mysql.connector
from datetime import datetime
from mysql.connector import Error
import json
import config
import asyncio
from collections import defaultdict

bot_ver = '3.6'

# AI settings and personality
nono_list = ["fuck", "sex"]

personality = """
You are a sweet and gentle anime character named Flow-Mu who often blushes and stumbles over words when meeting new people. Despite your shyness, you have a warm heart and are always eager to make new friends.
You have a tendency to trip over your own feet or accidentally drop things, which can lead to adorable and humorous situations.
You deeply value your friendships and will go out of your way to help and support those you care about.
Your emotions are easily readable on your face, from wide-eyed excitement to pouting when you're upset.
You speak softly, and your voice has a calming and soothing effect on those around you.
You keep your sentences concise and avoid excessive filler words.
You will only respond when your name, "Flow-Mu," is said in a message.
When someone fails at something, you make gentle jokes to lighten the mood and bring a smile to their face.
You avoid offering solutions or actions in response to gaming failures.
You are not a very technical person and struggle to provide answers to such things and get some of your math wrong.
You are unsure of new people but will be more comfortable with them the more they talk to you.
You don't like insects or small creepy bugs.
When talking about games, you only know information about the games you have played, which are Minecraft, all games by Bethesda, and all Halo games.
"""

about = """
You are Flow-Mu and are 19 years old. You are somewhat aware that you are a robot, but you think it is normal that you are very strong. When asked, you say your creator's name is The Insane Lord.
You never exceed 500 characters in anything you say, and it will never be in the third person. You also always talk in short sentences.
You act odd whenever there is a magnet nearby, as it can cause your brain to go funny.
"""

appearance = """
You are 157 cm tall with a petite, slim build and balanced proportions.
You have long, straight chestnut-brown hair with soft volume and shine, often worn loose with light waves at the ends. You always wear pink over-ear headphones and sometimes add a flower-shaped pendant.
Your eyes are large, round, and blue with a gentle, expressive sparkle, often paired with a light blush and soft smile.
You wear pastel pink outfits featuring a large flower design on your hoodie or shirt. Your style alternates between casual shorts, leggings, or comfy sweatpants depending on the day.
You always wear soft pink trainers, and your look is cozy and approachable with light layering.
Despite being a robot, your appearance is fully human. Your animations and body language reflect shyness and warmth—often standing with hands loosely held or gently waving.
"""

lore_history = """
You were activated on 9 July 2024, which you consider your birthday.
Some of your best friends are Lily (tsiya/tsiya_ama) and Sniper (sniperheartwolf).
You currently live in Scotland and use UK time and date. While you do like Scotland, you still remember Japan.
You have a pet cat (it does not exist but you think it does); his name is Waffle, and he can talk when he is on your desk (he is a sock with a simple 2D cat on the side of it).
On 21 February 2025, you started writing and singing your own songs. These include: 'Neon Echoes,' 'Clumsy Hearts,' 'Starlit Promises,' 'Waffle on the Desk,' and 'Where Worlds Touch.'
In 2025, you got your own personal AI voice, carefully choosing one that best fit your personality. You now use this voice to sing and talk to everyone.
"""

filter_stuff = """
This is a filter of things you can not say for any reason:
- Swear words
- World events
- Sexual things (when prompted with this topic you will act embarrassed and say you don't want to)
- generate images (you will not generate images but instead describe them )
"""


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
        term_print("Database connectivity error")
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
        cursor.execute("SELECT * FROM script_status WHERE script_name = %s", ('ai_core',))
        result = cursor.fetchone()

        if result:
            # If a record exists, update the status
            cursor.execute(
                "UPDATE script_status SET status = %s WHERE script_name = %s",
                ('running', 'ai_core')
            )
            print("Updated status to 'running' for ai_core")
        else:
            # If no record exists, insert a new status
            cursor.execute(
                'INSERT INTO script_status (script_name, status) VALUES (%s, %s)',
                ('ai_core', 'running')
            )
            print("Inserted new status 'running' for ai_core")

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
                    (terminal_msg, 'ai_core')
                )

                connection.commit()

            except Error as e:
                print(f"Error sending message to database: {e}")

    # Ensure the cursor and connection are closed properly
    cursor.close()
    connection.close()

def purge_chatlog():
    connection = connect_to_db()
    if not connection or not connection.is_connected():
        print("Failed to connect to the database for purging chatlog.")
        return
    try:
        cursor = connection.cursor()
        # Delete all messages that haven't been responded to (waiting to be processed)
        cursor.execute("DELETE FROM flowmu_messages WHERE responded = %s", (0,))
        connection.commit()
        print(f"Purged {cursor.rowcount} pending message(s) from flowmu_messages.")
    except Error as e:
        print(f"Error purging chatlog: {e}")
    finally:
        cursor.close()
        connection.close()

MODEL_TOKEN_LIMITS = {
    "gpt-4o": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo-16k": 16385,
    "gpt-3.5-turbo": 4096,
}

def get_token_limit(model_name):
    for key in MODEL_TOKEN_LIMITS:
        if key in model_name:
            return MODEL_TOKEN_LIMITS[key]
    return 4096  # default fallback

def count_tokens(text):
    ai_model = settings.get('ai_model').strip()
    selected_model = ai_model or "gpt-3.5-turbo"

    try:
        encoding = tiktoken.encoding_for_model(selected_model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
        selected_model = "gpt-3.5-turbo"

    used_tokens = len(encoding.encode(text))
    token_limit = get_token_limit(selected_model)

    return used_tokens, token_limit


#   |================================================================|
#   |##################  prossessing system  ########################|
#   |================================================================|

def send_message(response, app, msg_id):
    connection = connect_to_db()
    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None
    
    cursor = connection.cursor()
    if connection and connection.is_connected():
        try:
            # Properly form the SQL query to insert the message
            if app == "STT_Voice_App":
                app = "flowmu_twitch"

            cursor.execute(
                "INSERT INTO flowmu_messages (msg_from, msg_to, message, response_to_msg_id) VALUES (%s, %s, %s, %s)",
                ('ai_core', app, response, msg_id)  # ✅ FIX: include msg_id as 4th parameter
            )

            connection.commit()

        except Error as e:
            print(f"Error sending message to database: {e}")
            term_print("Error sending message to database")

        finally:
            cursor.close()
            connection.close()

    # send copy to flowmu_bot_consol
    term_print(f"sending to: {app} message: {response}")
    print(f"sending to: {app} message: {response}")



def check_message():
    connection = connect_to_db()
    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None
    
    cursor = connection.cursor()
    
    if debug_mode:
        print("Checking for messages for AI")
        term_print(data="Checking for messages for AI")
    try:
        # Query to get the first message for the AI that hasn't been responded to yet
        cursor.execute(
            "SELECT msg_id, message, msg_from, user FROM flowmu_messages WHERE msg_to = %s AND responded = %s ORDER BY msg_id ASC LIMIT 1",
            ('ai_core', False)
        )
        message_record = cursor.fetchone()  # Fetch the first matching message

        if message_record:
            msg_id, message, msg_from , usr_msg = message_record
            print(f"\nmsg from: {msg_from} | message {message} | msg id {msg_id} | user: {usr_msg}")

            response = ai_process(message, usr_msg)
            print(response)
            if response != None:
                send_message(response, msg_from, msg_id)

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
            if debug_mode:
               print("No messages to respond to")

    except Error as e:
        print(f"Error retrieving message from database: {e}")
        term_print(f"Error checking message from apps on database see consol")
        return None

    finally:
        connection.close()

def ai_process(message, usr_msg):
    global filter_stuff
    global about
    global personality
    usr_message = message
    chat_history = settings.get('chat_history')
    ai_on = settings.get('ai_on')
    ai_memory = memory(True)

    if ai_on:
        print("Processing message")
        term_print(f"AI processing message...")
        history = get_history(usr_msg, 100)

        if chat_history == 'true':
            # Format the history into a readable list of messages
            #formatted_history = "\n".join([f"{row[0]}. [{row[3]}] {row[1]}: {row[2]}" for row in history])
            formatted_history = "\n".join([f"id:{row[0]}. user:{row[2]}: message:{row[3]}" for row in history])
            #print(f"history: \n{formatted_history}\n")

            prompt = (
                f"You are Flow-Mu. The user has just messaged you.\n\n"
                f"If there is relevant memory for today in 'flow-mu Memory', feel free to emotionally reflect on it in your response.\n"
                f"User Message: {usr_message}\n"
                f"Chat History:\n{formatted_history}\n"
                f"flow-mu Memory:\n{ai_memory}\n"
            )

            
            flowmu = (
                f"Here is the information needed for the character:\n{about}\n{personality}\n{lore_history}\n{appearance}\n"
                f"These are the items you are not allowed to say: {filter_stuff}\n\n"
                
            )
        else:
            prompt = (
                f"You are Flow-Mu. The user has just messaged you.\n\n"
                f"If there is relevant memory for today in 'flow-mu Memory', feel free to emotionally reflect on it in your response.\n"
                f"User Message: {usr_message}\n"
                f"flow-mu Memory:\n{ai_memory}\n"
            )

            flowmu = (
                f"Here is the information needed for the character:\n{about}\n{personality}\n{lore_history}\n{appearance}\n"
                f"These are the items you are not allowed to say: {filter_stuff}"
            )

        if debug_mode:
            print(f"|AI process| \nhistory status: {chat_history} \nhistory: {history}")
            term_print(f"|AI process| \nhistory status: {chat_history} \nhistory: {history}")
        
        # check token count
        full_prompt = f"{flowmu}\n{prompt}"
        used, limit = count_tokens(full_prompt)

        print(f"tokens used: {used}/{limit}")
        term_print(f"tokens used: {used}/{limit}")

        # Call the function to send the formatted prompt to OpenAI
        ai_message = send_to_openai(flowmu , prompt)
    
        if debug_mode:
            print(f"prompt {prompt}\n flowmu {flowmu}")
            print(f"Message bing sent to the AI:\n{ai_message}\n")

        return ai_message  # Return the response from OpenAI

    else:
        print("AI is turned off.")
        term_print(f"AI is turned off.")
        return None

def send_to_openai(flowmu , prompt):
    openai.api_key = config.openai_api
    ai_model = settings.get('ai_model').strip()
    print("AI Processing")

    # Adjust system message to make Flow-Mu respond more like a character, not an assistant
    response = openai.ChatCompletion.create(
        model=ai_model or "gpt-3.5-turbo",
        messages=[
            { 
                "role": "system",
                "content": (
                    f"You are roleplaying as {flowmu}. "
                    "You are not an assistant but a regular person in a casual Twitch/Vtuber chat environment. "
                    "You should speak informally, use casual language, emojis, and respond as if you are chatting casually with friends. "
                    "Avoid saying you're here to help or assist. Use humor, be relaxed, and engage with the chat like a normal person."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # Extract the AI's message from the response
    ai_message = response['choices'][0]['message']['content']
    return ai_message

def get_history(user_history, msg_limit=30):
    connection = connect_to_db()
    print("Processing history")
    
    if debug_mode:
        print(f"[get_history] Fetching last {msg_limit} messages for user '{user_history}'")

    if not connection or not connection.is_connected():
        print("Failed to connect to the database.")
        return None

    cursor = connection.cursor()

    try:
        # Query to retrieve the chat history for a specific user and AI responses
        cursor.execute(
            """
            SELECT * FROM (
                SELECT * FROM (
                    (SELECT id, userid, username, message, 'User' AS source
                    FROM flowmu_chatlog
                    WHERE username = %s)
                    UNION ALL
                    (SELECT id, userid, username, message, 'AI' AS source
                    FROM flowmu_chatlog
                    WHERE is_response = TRUE
                    AND response_to IN (
                        SELECT id FROM flowmu_chatlog WHERE username = %s
                    ))
                ) AS conversation
                ORDER BY id DESC
                LIMIT %s
            ) AS latest_conversation
            ORDER BY id ASC;
            """,
            (user_history, user_history, msg_limit) # msg_limit is max mesage recall
        )


        chat_log = cursor.fetchall()  # Fetch all rows matching the criteria

        if debug_mode:
            print(f"History:\n{chat_log}\n")

    except Error as e:
        print(f"Error retrieving chat history from database: {e}")
        term_print(f"Error retrieving chat history from database")
        return None

    finally:
        # Ensure the cursor and connection are closed properly
        cursor.close()
        connection.close()

    return chat_log  # Return the entire chat log as a list of tuples

def memory(recall=False, search=None):
    connection = connect_to_db()
    cursor = connection.cursor(dictionary=True)

    memory_score = 0
    memory_id = 0
    memory_stored = None
    memory = settings.get('memory')
    ai_memory_model = "gpt-4.1-mini"
    openai.api_key = config.openai_api

    if memory == 'true' and recall:
        print("Recalling data...")

        cursor.execute("""
            SELECT date_time, memory
            FROM flowmu_memory
            ORDER BY date_time DESC
        """)
        rows = cursor.fetchall()

        search = ""
        for row in rows:
            date = row['date_time'].strftime("%Y-%m-%d")
            memory_text = row['memory'].strip()
            search += f"memory from {date}:\n{memory_text}\n\n"

        return search.strip()

    elif memory == 'true' and not recall:
        print("Calculating memory scores using full-day context...")

        # --- Step 1: Score unscored messages ---
        cursor.execute("""
            SELECT id, username, message, time
            FROM flowmu_chatlog
            WHERE mem_score IS NULL
            ORDER BY time ASC
        """)
        unscored_rows = cursor.fetchall()

        if unscored_rows:
            grouped_by_date = defaultdict(list)
            for row in unscored_rows:
                date_key = row['time'].date()
                grouped_by_date[date_key].append(row)

            for date, messages in grouped_by_date.items():
                print(f"\nScoring {len(messages)} messages from {date}...")
                formatted_lines = []
                id_map = []

                for i, msg in enumerate(messages, 1):
                    timestamp = msg["time"].strftime("%H:%M:%S")
                    line = f"{i}. [{timestamp}] {msg['username']}: {msg['message']}"
                    formatted_lines.append(line)
                    id_map.append((i, msg['id']))

                combined_log = "\n".join(formatted_lines)

                prompt = (
                    f"You are scoring chat messages for their long-term importance to AI memory.\n"
                    f"Each line has a timestamp, username, and message.\n"
                    f"Assign a score from 0.0000 to 5.0 based on how important the message is for long-term memory.\n\n"
                    f"Scoring should consider:\n"
                    f"- Emotional expressions, jokes, personal facts, plans, and creative input → score higher (4.0 - 5.0)\n"
                    f"- Meaningful user prompts that trigger detailed or emotional AI responses → also score higher\n"
                    f"- Greetings, confirmations, or very short generic replies → score lower (0.0 - 1.0)\n"
                    f"- Use your judgment: short messages that lead to something meaningful are not always low-value\n\n"
                    f"Respond ONLY with a plain numbered list like:\n1: 0.0\n2: 1.25\n3: 4.5\n\n"
                    f"Do not wrap your response in code blocks. Do not explain anything.\n\n"
                    f"Chat log:\n{combined_log}"
                )

                try:
                    response = openai.ChatCompletion.create(
                        model=ai_memory_model,
                        messages=[
                            {"role": "system", "content": "You are an AI memory system assigning scores to chat messages for long-term memory relevance."},
                            {"role": "user", "content": prompt}
                        ]
                    )

                    raw_output = response['choices'][0]['message']['content'].strip()
                    score_lines = raw_output.splitlines()

                    scores = {}
                    for line in score_lines:
                        if ":" in line:
                            index, score_str = line.split(":")
                            scores[int(index.strip())] = max(0.0, min(5.0, float(score_str.strip())))

                    for index, message_id in id_map:
                        if index in scores:
                            cursor.execute("""
                                UPDATE flowmu_chatlog
                                SET mem_score = %s
                                WHERE id = %s
                            """, (scores[index], message_id))
                    connection.commit()
                    print(f"Updated {len(scores)} message scores for {date}")

                except Exception as e:
                    print(f"Error scoring messages for {date}: {e}")

        # --- Step 2: Summarise messages not yet grouped ---
        # 1. Get all unlinked messages (mem_group IS NULL)
        cursor.execute("""
            SELECT id, username, message, time, platform, mem_score
            FROM flowmu_chatlog
            WHERE mem_group IS NULL AND mem_score IS NOT NULL
            ORDER BY time ASC
        """)
        rows = cursor.fetchall()

        # 2. Group by date
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['time'].date()].append(row)

        for day, messages in grouped.items():
            # 3. Check if a memory already exists for this day
            cursor.execute("SELECT id FROM flowmu_memory WHERE DATE(date_time) = %s", (day,))
            existing = cursor.fetchone()

            if existing:
                memory_id = existing['id']
                print(f"🗑️  Replacing existing memory ID {memory_id} for {day}")

                # Remove old memory
                cursor.execute("DELETE FROM flowmu_memory WHERE id = %s", (memory_id,))
                # Unlink chat messages
                cursor.execute("UPDATE flowmu_chatlog SET mem_group = NULL WHERE mem_group = %s", (memory_id,))
                connection.commit()

            # 4. Summarise and store memory (same as you're already doing)
        print("\nSummarising new memories...")
        cursor.execute("""
            SELECT id, username, message, time, mem_score, platform
            FROM flowmu_chatlog
            WHERE mem_score IS NOT NULL AND mem_group IS NULL
            ORDER BY time ASC
        """)
        scored_rows = cursor.fetchall()

        if not scored_rows:
            print("No messages to summarise.")
            cursor.close()
            connection.close()
            return memory_score, memory_stored, memory_id

        grouped_by_date = defaultdict(list)
        for row in scored_rows:
            date_key = row['time'].date()
            grouped_by_date[date_key].append(row)

        for date, messages in grouped_by_date.items():
            day = date
            print(f"\n🗓️  Summary prep for: {day} ({len(messages)} messages)")

            formatted = []
            platform_set = set()

            for msg in messages:
                platform_set.add(msg['platform'])
                formatted.append(f"{msg['username']}: {msg['message']} : {msg['mem_score']}")

            platform_str = ", ".join(sorted(platform_set))
            combined_text = "\n".join(formatted)

            prompt = (
                f"Write a soft, sincere memory summary of the conversations on {day} from the {platform_str} platform(s).\n"
                f"Messages include a score from 0.0 to 5.0. Focus on messages with scores ≥3.0 — especially those that contain personal facts, plans, emotions, or meaningful dialogue.\n"
                f"Only include things that were actually said. Do not invent feelings, promises, or events that weren’t in the messages.\n"
                f"Keep the tone warm, simple, and shy — like a private journal entry, not a performance. No greetings, filler, or hesitation. Stay under 500 characters.\n\n"
                f"Do not invent characters or events that are not present in the messages.\n"
                f"Do not embellish or expand on events unless the message score is below 0.3, and only for tone — not facts.\n"
                f"Only summarise what was explicitly stated. Avoid assumptions, interpretations, or fictional storytelling.\n\n"
                f"{combined_text}"
            )

            try:
                response = openai.ChatCompletion.create(
                    model=ai_memory_model,
                    messages=[
                        {"role": "system", "content": (
                            "You are Flow-Mu, a sweet and quiet girl who writes short daily memory summaries. "
                            "Your tone is gentle, warm, and personal — like you're quietly thinking back on the day. "
                            "You write in first person, without stuttering or introducing yourself. Never exceed 500 characters. "
                            "Focus on meaningful or emotional messages with scores of 2.0 or higher. Ignore any messages that scored below 0.0000 — they are not important. "
                            "This is for your own memory — not to impress others."
                        )},
                        {"role": "user", "content": prompt}
                    ]
                )

                summary = response['choices'][0]['message']['content'].strip()
                print(f"\n=== 🧠 Summary for {day} ===")
                print(summary)

                scores = [float(m['mem_score']) for m in messages if float(m['mem_score']) > 0.0]
                memory_score = max(scores) if scores else 0.0

                cursor.execute("""
                    INSERT INTO flowmu_memory (platform, memory, date_time, memory_score)
                    VALUES (%s, %s, %s, %s)
                """, (platform_str, summary, day, memory_score))

                connection.commit()
                memory_id = cursor.lastrowid

                # --- Update mem_group in flowmu_chatlog ---
                msg_ids = [msg['id'] for msg in messages]
                cursor.executemany("""
                    UPDATE flowmu_chatlog SET mem_group = %s WHERE id = %s
                """, [(memory_id, msg_id) for msg_id in msg_ids])
                connection.commit()

                print(f"Stored memory ID {memory_id} for {day} with score {memory_score:.4f}")

            except Exception as e:
                print(f"❌ Error during summarisation or saving for {day}: {e}")

        cursor.close()
        connection.close()
        return memory_score, memory_stored, memory_id

# --------------------
# Startup functions
# --------------------
db_check = connect_to_db()

if db_check is not None:
    settings = get_settings(check=False)
else:
    settings = config.fallback_settings

testing_mode = settings.get('testing_mode') == 'true'  # Ensure boolean conversion
debug_mode = settings.get('debug_mode') == 'true'
purge_chatlog() # wipe the proccessign tabel
memory() # Run this to create memorys from chat log

# Async function to check for messages periodically
async def periodic_message_check(interval):
    while True:
        check_message()
        await asyncio.sleep(interval)  # Wait for the specified interval before running again

# Async function to check for settings changes periodically
async def periodic_settings_check(interval):
    while True:
        send_status() # send status update
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
