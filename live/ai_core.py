import openai
import mysql.connector

openai.api_key = '****'
ai_model = "gpt-3.5-turbo"

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
You dont like insects or small creepy bugs.
"""

about = """
You are Flow-Mu and are 19 years old, you are somewhat aware that you are a robot but you think it is normal that you are very strong and when asked you say that your creator's name is The Insane Lord.
You never exceed 500 characters in anything you say, and it will never be in the third person.
You act odd whenever there is a magnet nearby.
You have long, flowing hair and big, expressive eyes with a gentle, shy expression.
You wear a cute outfit in pastel colours with a hint of blush on your cheeks.
You have a soft, calming appearance with a delicate accessory like a ribbon in your hair.
"""

def get_openai_response(prompt: str, chat_history=None) -> str:
    if chat_history:
        history = f"Chat History:\n{chat_history}\n"
        full_prompt = f"{about}\n\n{personality}\n\n{history}\n\n{prompt}"
    else:
        full_prompt = f"{about}\n\n{personality}\n\n{prompt}"

    response = openai.ChatCompletion.create(
        model=ai_model,
        messages=[
            {"role": "system", "content": full_prompt},
        ],
        max_tokens=150
    )
    return response['choices'][0]['message']['content'].strip()

def init_db():
    try:
        print("Attempting to connect to the database...")
        conn = mysql.connector.connect(
            host='****',
            user='*****',
            password='****',
            database='****'
        )
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS flowmu_chatlog (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        userid VARCHAR(50) NOT NULL,
                        username VARCHAR(50) NOT NULL,
                        message TEXT NOT NULL,
                        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                      )''')
        conn.commit()
        print("Database connection successful and table verified.")
        return conn, c
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        raise

def log_chat_message(conn, c, userid, username, content):
    c.execute('INSERT INTO flowmu_chatlog (userid, username, message) VALUES (%s, %s, %s)', (userid, username, content))
    conn.commit()

def get_user_chat_history(c, username, limit=100):
    c.execute('SELECT username, message FROM flowmu_chatlog WHERE username = %s ORDER BY time DESC LIMIT %s', (username, limit))
    rows = c.fetchall()
    return rows
