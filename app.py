from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from processtimetable import process_timetables
from botworker import reminderstart

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
        success = process_timetables()
        if success:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Bot failed to process"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Bot error: {str(e)}"}), 500


@app.route('/set-reminder', methods=['POST'])
def set_reminder():
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
    try:
        success = reminderstart()
        if success:
            return jsonify({"status": "success", "message": "Settings saved and reminder active"})
        else:
            return jsonify({"status": "error", "message": "Bot failed to process"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)