from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests
import base64
from processtimetable import process_timetables
from botworker import reminderstart
import threading
from botworker import  start_keep_alive

app = Flask(__name__)
CORS(app)

FILE_NAME = "user_settings.txt"

def load_data():
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

@app.route('/process-all', methods=['POST'])
def process_all():
    new_data = request.json
    # Use .get() with an empty string default to avoid errors if key is missing
    username = new_data.get('instagram', '')

    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400
    
    # 1. Load and Update Data
    data_dict = load_data()

    # Define the payload we want to save/update
    user_payload = {
        "session": new_data.get('session'),
        "department": new_data.get('department'),
        "section": new_data.get('section'),
        "status": "pending"
    }

    # Logic: If user is brand new OR doesn't have a reminder_status, overwrite/create
    # Otherwise, update the existing entry without losing 'reminder_status'
    user_info = data_dict.get(username)
    
    if not user_info or "reminder_status" not in user_info:
        data_dict[username] = user_payload
    else:
        # This keeps 'reminder_status' intact while updating the other fields
        data_dict[username].update(user_payload)

    # Save to file
    try:
        with open(FILE_NAME, "w") as f:
            json.dump(data_dict, f, indent=4)
    except Exception as e:
        return jsonify({"status": "error", "message": f"File save failed: {str(e)}"}), 500

    # 2. Trigger bot
    try:
        process_timetables()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Bot error: {str(e)}"}), 500


reminder_started = False
@app.route('/set-reminder', methods=['POST'])
def set_reminder():
    global reminder_started
    new_data = request.json
    username = new_data.get('instagram')
    
    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    data_dict = load_data()

    # Check if user exists, otherwise create an empty entry
    if username not in data_dict:
        data_dict[username] = {
            "session": None, 
            "department": None, 
            "section": None, 
            "reminder_status": "no", 
            "status": "pending"
        }

    # UPDATE only the keys that are actually provided in the request
    # This prevents overwriting existing data with 'null'
    for key in ['session', 'department', 'section']:
        if key in new_data:
            data_dict[username][key] = new_data[key]

    # Force these specific values
    data_dict[username]["reminder_status"] = "yes"
    data_dict[username]["status"] = "completed"

    # Save to file
    with open(FILE_NAME, "w") as f:
        json.dump(data_dict, f, indent=4)

    # 2. Trigger bot
    if not reminder_started:
        thread = threading.Thread(target=reminderstart, daemon=True)
        thread.start()
        reminder_started = True
        print("Reminder thread spawned.")

    return jsonify({"status": "success", "message": "Reminder set!"})



GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
FILE_PATH = "user_settings.json"

def save_to_github(data):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # 1. Get the current file (we need the 'sha' tag to overwrite it)
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    # 2. Encode the new data to Base64
    content = base64.b64encode(json.dumps(data, indent=4).encode()).decode()

    # 3. Push the update
    payload = {
       "message": "Update user settings [skip ci] [skip render]",
        "content": content,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    requests.put(url, headers=headers, json=payload)
    print("Settings synced to GitHub!")

def load_from_github():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    
    if r.status_code == 200:
        content = base64.b64decode(r.json()['content']).decode()
        return json.loads(content)
    return {}

def boot_system():
    print("Initializing System...")
    # Load the latest user data from GitHub into a global variable or file
    global_user_data = load_from_github()
    
    # Save it locally so the existing bot logic can read it
    with open("user_settings.json", "w") as f:
        json.dump(global_user_data, f)
    
    # Now start the background thread
    t = threading.Thread(target=reminderstart, daemon=True)
    t.start()
    print("Background reminder service is live!")

# Run boot logic
boot_system()

if __name__ == '__main__':
    start_keep_alive("https://xceed-timetable.onrender.com")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
