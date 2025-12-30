from processtimetable import *
weekday = datetime.now().weekday()
class_slots = [
        (8, 0), (9, 0), (10, 0), (11, 0), 
        (12, 0), (13, 0), (14, 0), (15, 0), (16, 0)
    ]

import time
from datetime import datetime

def reminderstart():
    print("Reminder service started...")
    
    while True:
        now = datetime.now()
        weekday = now.weekday()
        current_time = (now.hour, now.minute)

        # Only check if the current minute matches one of our slots
        for idx, slot in enumerate(class_slots):
            # Check if we are in the first 15 minutes of a slot
            if now.hour == slot[0] and 0 <= now.minute < 15:
                
                if not os.path.exists(FILE_NAME):
                    continue

                with open(FILE_NAME, "r") as f:
                    data = json.load(f)

                for username, settings in data.items():
                    if settings.get("reminder_status") == "yes":
                        process_single_reminder(username, settings, weekday, idx, slot)
                
                # Sleep longer after a successful trigger to avoid double-sending
                time.sleep(900) # Sleep 15 mins
        
        time.sleep(30) # Check every 30 seconds

def process_single_reminder(username, settings, weekday, slot_idx, slot_time):
    driver = None
    try:
        print(f"Processing {username} for {slot_time[0]}:{slot_time[1]+25} reminder...")
        driver = get_driver()
        wait = WebDriverWait(driver, 30)
        
        run_timetable_selection(driver, wait, settings)
        
        # Using slot_idx + 2 for the column
        xpath = f"/html/body/div[1]/div/div[4]/div[2]/div[2]/div/div[1]/div/div/table/tbody/tr[{weekday+1}]/td[{slot_idx+2}]/div"
        which_class = driver.find_element(By.XPATH, xpath).text
        
        cl = get_insta_client() # Ensure this is a function call ()
        cl.direct_send(f"Next class at {slot_time[0]}:{slot_time[1]+25}: \n{which_class}", [cl.user_id_from_username(username)])
        print(f"Sent reminder to {username} for class: \n{which_class}")
    except Exception as e:
        print(f"Error for {username}: {e}")
    finally:
        if driver:
            driver.quit()

