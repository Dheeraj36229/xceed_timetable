import json
import os
import time
import base64
import threading
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from instagrapi import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

FILE_NAME = "user_settings.txt"
USERNAME = "xceed_timetable"  
PASSWORD = "88475vansh@62390"
def get_insta_client():
    cl = Client()
    # Update user-agent to avoid gql errors
    cl.set_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")
    session_file = f"{USERNAME}_session.json"
    try:
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            cl.login(USERNAME, PASSWORD)
        else:
            cl.login(USERNAME, PASSWORD)
            cl.dump_settings(session_file)
    except Exception as e:
        print(f"[Insta] Login Failed: {e}")
        if os.path.exists(session_file): os.remove(session_file)
        return None
    return cl


def safe_select(wait, xpath, text, retries=5):
    for i in range(retries):
        try:
            element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            dropdown = Select(element)
            if text in [o.text.strip() for o in dropdown.options]:
                dropdown.select_by_visible_text(text)
                time.sleep(2)
                return True
        except: pass
        time.sleep(2)
    raise Exception(f"Failed to find option '{text}'")

def upload_to_gofile(path):
    for attempt in range(3):
        try:
            # 1. Get Best Server
            resp = requests.get("https://api.gofile.io/servers", timeout=15)
            
            # Check if status code is 200 and content exists
            if resp.status_code != 200 or not resp.text.strip():
                raise Exception(f"Server API returned status {resp.status_code}")

            res = resp.json()
            if res.get("status") != "ok":
                raise Exception("Server status not OK")

            srv = res["data"]["servers"][0]["name"]

            # 2. Upload File
            with open(path, 'rb') as f:
                up_resp = requests.post(
                    f"https://{srv}.gofile.io/contents/uploadfile", 
                    files={'file': f}, 
                    timeout=60
                )
                
                if not up_resp.text.strip():
                    raise Exception("Upload API returned empty response")
                
                up = up_resp.json()

            if up.get("status") == "ok":
                return up['data']['downloadPage']
            else:
                raise Exception(f"Upload failed: {up.get('status')}")

        except Exception as e:
            print(f"[GoFile] Attempt {attempt+1} failed: {e}")
            time.sleep(5)

def run_timetable_selection(driver, wait, settings):
    driver.get("https://xceed.nitj.ac.in/timetable")
    safe_select(wait, "//select[contains(@class, 'chakra-select')]", settings["session"])
    safe_select(wait, "//*[@id='root']/div/div[3]/select", settings["department"])
    safe_select(wait, "/html/body/div[1]/div/div[4]/div[2]/div[1]/select", settings["section"])

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-gpu")
    chrome_options.binary_location = "/opt/render/project/src/.render/chrome/opt/google/chrome/google-chrome"
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)


def process_timetables():
    if not os.path.exists(FILE_NAME):
        return

    # 1. Read the current dictionary
    with open(FILE_NAME, "r") as f:
        data = json.load(f)

    for username, settings in data.items():
        if settings["status"] == "pending":
            
        # Check if we already processed this user (optional logic)
            print(f"Generating timetable for {username}...")
            print(f"Session: {settings['session']}, Dept: {settings['department']}")
            driver = get_driver()
            wait = WebDriverWait(driver, 30)
            driver = get_driver()
            wait = WebDriverWait(driver, 30)
            try:
                run_timetable_selection(driver, wait, settings)
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[4]/div[2]/div[2]/div/div[2]/div[2]/button")))
                driver.execute_script("arguments[0].click();", btn)
                wait.until(lambda d: len(d.window_handles) > 1)
                driver.switch_to.window(driver.window_handles[1])
                js = "var cb=arguments[arguments.length-1];fetch(window.location.href).then(r=>r.blob()).then(b=>{var rd=new FileReader();rd.onloadend=()=>cb(rd.result);rd.readAsDataURL(b);});"
                base64_data = driver.execute_async_script(js)
                if "base64," in base64_data:
                    with open(f"{username}_tb.pdf", "wb") as f: f.write(base64.b64decode(base64_data.split("base64,")[1]))
                    download_link = upload_to_gofile(f"{username}_tb.pdf")
                    if download_link:
                        cl = get_insta_client()
                        if cl: cl.direct_send(f"Updated PDF ({settings['section']}): {download_link}", [cl.user_id_from_username(username)])
                        print(f"Sent timetable to {username} via Instagram.")
            except Exception as e: print(f"PDF Error: {e}")
            finally: driver.quit()
            settings["status"] = "completed"
            # --- YOUR AUTOMATION CODE GOES HERE ---
            # 1. Open Selenium/Playwright
            # 2. Scrape the data
            # 3. Generate PDF
            # 4. Send via Instagram/Email
            # ---------------------------------------
    with open("user_settings.txt", "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    while True:
        print("Checking for new requests...")
        process_timetables()

        # Wait 60 seconds before checking the file again
        time.sleep(60)
