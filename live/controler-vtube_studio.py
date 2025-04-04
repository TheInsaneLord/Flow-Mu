import mysql.connector
from mysql.connector import Error
import openai
import asyncio
import pyvts
import config
import time
import json

# --------------------
# Global Configuration
# --------------------
vtube_enabled = True
testing_mode = False 
msgid_list = []
sleep_time = 2
auth_client = None

#emotions = ['happy', 'sad', 'angry','sarcastic', 'neutral','anxious', 'excited']
emotions = ['happy', 'excited'] # this is temp 

# --------------------
# Database Functions
# --------------------
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

def get_message():
    connection = connect_to_db()
    platforms = ["discord", "twitch"]

    if connection and connection.is_connected():
        message = None
        msgid = None
        
        for plat in platforms:
            cursor = connection.cursor(dictionary=True)
            query = (
                "SELECT msg_id, message FROM flowmu_messages "
                "WHERE msg_to = %s AND msg_from = %s ORDER BY msg_id ASC"
            )
            cursor.execute(query, (f'flowmu_{plat}', 'ai_core'))
            row = cursor.fetchone()
            cursor.close()

            # If a message is found, exit the loop.
            if row is not None:
                msgid = row['msg_id']
                message = row['message']
                break

        connection.close()

        # Check if the message has been processed repeatedly;
        # mark_msg() will remove it if seen 5 or more times.
        if message is not None:
            mark_msg(msgid)

        return message
    else:
        print("Database connection/retrieval issue")
    return None

def mark_msg(msgid):
    connection = connect_to_db()
    global msgid_list

    if connection is None or not connection.is_connected():
        print("Unable to connect to database for message check.")
        return

    cursor = connection.cursor(dictionary=True)
    # Check if the message still exists in the database.
    cursor.execute("SELECT msg_id FROM flowmu_messages WHERE msg_id = %s", (msgid,))
    result = cursor.fetchone()
    if result is None:
        # If the message no longer exists in the DB, remove all its occurrences from msgid_list.
        while msgid in msgid_list:
            msgid_list.remove(msgid)
        print(f"Message {msgid} no longer exists in DB; removed from tracker.")
        cursor.close()
        connection.close()
        return

    # Add the current msgid to the tracking list.
    msgid_list.append(msgid)
    count = msgid_list.count(msgid)
    
    # If the same message has been processed 5 or more times, delete it from the database.
    if count >= 5:
        try:
            delete_query = "DELETE FROM flowmu_messages WHERE msg_id = %s"
            cursor.execute(delete_query, (msgid,))
            connection.commit()
            print(f"Message {msgid} deleted from database after {count} checks.")
            # Remove all occurrences of this msgid from the tracking list.
            while msgid in msgid_list:
                msgid_list.remove(msgid)
        except Exception as e:
            print(f"Error deleting message {msgid}: {e}")

    cursor.close()
    connection.close()

    print(f"\n\ncount: {count} | message id list: {msgid_list}")

# --------------------
# Emotion Calculation
# --------------------
def get_emotion(message):
    openai.api_key = config.openai_api

    prompt =  f"You are a sentiment analysis tool. Classify the emotional tone of the given message into one of these categories: {emotions} respond with just one word representing the emotion."
    messages = [
        {
            "role": "system",
            "content": (prompt
               )
        },
        {
            "role": "user",
            "content": f"Message: \"{message}\""
        }
    ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=5,
        temperature=0.0,
    )
    
    emotion = response.choices[0].message['content'].strip().lower()
    return emotion

# --------------------
# Character Control
# --------------------
# Helper Function to Trigger a Hotkey
async def trigger_hotkey(client, hotkey_id):
    print(f"Triggering hotkey with ID: {hotkey_id}")
    payload = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "hotkey_request",
        "messageType": "HotkeyTriggerRequest",
        "data": {
            "hotkeyID": hotkey_id
        }
    }
    try:
        await client.websocket.send(json.dumps(payload))
        print("Sent hotkey trigger payload:", payload)
        response = await client.websocket.recv()
        print("Hotkey trigger response:", response)
    except Exception as e:
        print(f"Error sending hotkey trigger payload via websocket: {e}")

async def control_character(emotion):
    print("Inside control_character() with emotion:", emotion)
    global auth_client
    available_hotkeys = await get_expressionids(auth_client)
    if available_hotkeys is None:
        print("Error getting hotkey IDs.")
        return

    print("Available hotkeys mapping:", available_hotkeys)
    # Look up the hotkeyID for the detected emotion; default to 'neutral' if not found.
    hotkey_id = available_hotkeys.get(emotion, available_hotkeys.get('neutral'))
    print("Setting character animation using hotkeyID:", hotkey_id)

    if auth_client is None:
        print("No authenticated client available.")
        return

    try:
        await trigger_hotkey(auth_client, hotkey_id)
    except Exception as e:
        print(f"Error triggering animation with hotkeyID '{hotkey_id}': {e}")
    
    await asyncio.sleep(sleep_time)

# --------------------
# Functions
# --------------------
def monitor_messages():
    print("Starting to monitor messages from the database...")
    while True:
        msg = get_message()

        if msg:
            print(f"New message received: {msg}")
            emotion = get_emotion(msg)
            print(f"Detected emotion: {emotion}")
            asyncio.run(control_character(emotion))

        # Poll frequently to catch messages within the available window.
        time.sleep(sleep_time)

async def get_expressionids(client):
    print("Inside get_expressionids()")
    print("Global emotions:", emotions)
    # Build desired mapping from the global 'emotions' list.
    desired_mapping = {emotion: f"{emotion}_expression" for emotion in emotions}
    print("Desired mapping:", desired_mapping)
    
    payload = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "getHotkeysRequest",
        "messageType": "HotkeysInCurrentModelRequest",
        "data": {}
    }
    try:
        await client.websocket.send(json.dumps(payload))
        print("Sent payload:", payload)
        response = await client.websocket.recv()
        print("Received response:", response)
        data = json.loads(response)
        available = data.get("data", {}).get("availableHotkeys", [])
        hotkeys_dict = {}
        for hk in available:
            name = hk.get("name", "").strip()
            # Remove extra quotes if present.
            if name.startswith("'") and name.endswith("'"):
                name = name[1:-1]
            print("Processing hotkey:", name)
            # Compare available hotkeys with our desired mapping.
            for emotion, desired_name in desired_mapping.items():
                if name.lower() == desired_name.lower():
                    hotkeys_dict[emotion] = hk.get("hotkeyID")
                    print(f"Match found: {emotion} -> {hk.get('hotkeyID')}")
                    break
        print("Final hotkeys_dict:", hotkeys_dict)
        return hotkeys_dict
    except Exception as e:
        print(f"Error querying available hotkeys: {e}")
        return None


async def authenticate_plugin():
    client = pyvts.vts(host="127.0.0.1", port=8001)
    await client.connect()

    # Hard-coded token (replace with your stored token as needed)
    token = '****' # you have to replace the token yourself when it changes
    auth_payload = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "authRequest",
        "messageType": "AuthenticationRequest",
        "data": {
            "pluginName": "FlowMuBot",
            "pluginDeveloper": "The_Insane_Lord",
            "authenticationToken": token
        }
    }

    await client.websocket.send(json.dumps(auth_payload))
    auth_response = await client.websocket.recv()
    print("Authentication response:", auth_response)
    auth_data = json.loads(auth_response)
    global auth_client
    if auth_data.get("data", {}).get("authenticated", False):
        print("Authenticated successfully with stored token!")
        auth_client = client
        return client
    else:
        print("Stored token is invalid. Requesting new token...")
        auth_token_request_payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "authTokenRequest",
            "messageType": "AuthenticationTokenRequest",
            "data": {
                "pluginName": "FlowMuBot",
                "pluginDeveloper": "The_Insane_Lord",
                "pluginIcon": "",
                "pluginIconColor": "#ffffff"
            }
        }
        await client.websocket.send(json.dumps(auth_token_request_payload))
        token_response = await client.websocket.recv()
        print("Token request response:", token_response)
        token_data = json.loads(token_response)
        new_token = token_data.get("data", {}).get("authenticationToken")
        if not new_token:
            print("Failed to retrieve new token.")
            await client.close()
            return None
        print("Received new token:", new_token)
        new_auth_payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "authRequest",
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": "FlowMuBot",
                "pluginDeveloper": "The_Insane_Lord",
                "authenticationToken": new_token
            }
        }
        await client.websocket.send(json.dumps(new_auth_payload))
        final_response = await client.websocket.recv()
        print("Final authentication response:", final_response)
        final_data = json.loads(final_response)
        if final_data.get("data", {}).get("authenticated", False):
            print("Authenticated successfully with new token!")
            auth_client = client
            return client
        else:
            print("Authentication failed with new token.")
            await client.close()
            return None

# --------------------
# Main Script Execution
# --------------------
if __name__ == "__main__":
    async def main():
        global auth_client
        db = connect_to_db()
        auth_client = await authenticate_plugin()
        if auth_client is None:
            print("Could not authenticate client. Exiting.")
            return
        
        if db is None:
            print("Failed to connect to database.")
            exit()
        else:
            print("Connected to database proceeding.")
        
        if testing_mode:
            while True:
                # Use asyncio.to_thread() to avoid blocking the event loop
                test_text = await asyncio.to_thread(input, "Provide example message: ")
                emotion = get_emotion(test_text)
                print("Detected emotion:", emotion)
                await control_character(emotion)
        else:
            while True:
                # Poll for a message from the database without blocking the event loop.
                message = await asyncio.to_thread(get_message)
                if message:
                    emotion = get_emotion(message)
                    print("Detected emotion:", emotion)
                    await control_character(emotion)
                await asyncio.sleep(sleep_time)
    
    asyncio.run(main())

