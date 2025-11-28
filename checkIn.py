import json
import os
import requests
import time
import random # ADDED: needed for random.choice
from datetime import datetime
from encryption import Encryption

TENANT_ID = "126"
API_HOST = "01v2mobileapi.seats.cloud"
DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE"

def getHeaders(token):
    cleanToken = token.strip()
    if not cleanToken.startswith("Bearer "):
        cleanToken = f"Bearer {cleanToken}"

    return {
        "Authorization": cleanToken,
        "Abp.TenantId": TENANT_ID,
        "Host": API_HOST,
        "User-Agent": "SeatsMobile/1728493384 CFNetwork/1568.100.1.2.1 Darwin/24.0.0",
        "Accept": "*/*",
        "Content-Type": "application/json"
    }

def log_response(user_id, endpoint, response_text):
    """Saves raw API responses to disk for debugging."""

    filename = f"request-logs/{user_id}/{endpoint}-{int(time.time())}.json"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:

        f.write(response_text)

def send_discord_webhook(success, lesson_title, user_id, error_msg=None):
    if not DISCORD_WEBHOOK_URL or "YOUR_DISCORD_WEBHOOK" in DISCORD_WEBHOOK_URL:
        return

    embed = {
        "title": "Check-In Successful" if success else "Check-In Failed",
        "color": 3066993 if success else 15158332,  # Green or Red
        "description": f"**Lesson:** {lesson_title}",
        "fields": [{"name": "Student ID", "value": user_id, "inline": True}],
        "timestamp": datetime.now().isoformat()
    }

    if error_msg:
        embed["fields"].append({"name": "Error", "value": str(error_msg), "inline": False})

    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"Discord Error: {e}")


# noinspection PyBroadException
def load_mobile_phone_setting():
    """Loads the signing key from config.json (now saved by main.py)"""
    try:
        with open("config.json", "r") as f:
            return json.load(f).get("mobile_phone_setting")
    except:
        return None

def performCheckIn(token, lesson, user_id="Unknown", mobile_phone_val=None):

    if not mobile_phone_val:
        error_msg = "Missing 'mobile_phone_setting'. Token configuration may be incomplete."
        print(f"Error: {error_msg}")
        return {"success": False, "code": 0, "error": error_msg}

    timestamp = datetime.now().isoformat().split('.')[0]
    timetable_id = str(lesson["ids"]["timetableId"])
    student_schedule_id = str(lesson["ids"]["studentScheduleId"])
    check_in_reason = "Ibeacon"
    check_in_input = None

    beacon_data = lesson["auth"].get("beaconData")
    if not beacon_data:
        error_msg = "No iBeacon data available for this lesson."
        print(f"Error: {error_msg}")
        return {"success": False, "code": 0, "error": error_msg}

    uuid = random.choice(beacon_data).get("uuid")

    if not uuid:
        error_msg = "Selected iBeacon data is missing a UUID."
        print(f"Error: {error_msg}")
        return {"success": False, "code": 0, "error": error_msg}

    fp_input = f"{timestamp}{timetable_id}{student_schedule_id}{check_in_reason}{check_in_input or ''}"
    fingerprint = Encryption.compute_fingerprint(fp_input, mobile_phone_val)

    url = f"https://{API_HOST}/api/v2/students/myself/checkin?fp={fingerprint}"

    payload = {
        "Timestamp": timestamp,
        "TimetableId": int(timetable_id),
        "StudentScheduleId": int(student_schedule_id),
        "CheckInReason": check_in_reason,
        "Uuid": uuid,
        "Longitude": "", "Latitude": "", "LocationName": "", "CheckInInput": check_in_input
    }

    try:

        response = requests.post(url, headers=getHeaders(token), json=payload)
        log_response(user_id, "CheckIn", response.text)

        success = response.status_code in [200, 201]
        error_msg = None if success else response.text

        send_discord_webhook(success, lesson["title"], user_id, error_msg)

        if success:
            return {"success": True, "code": response.status_code}
        else:
            return {"success": False, "code": response.status_code, "error": response.text}

    except Exception as e:
        send_discord_webhook(False, lesson["title"], user_id, str(e))
        return {"success": False, "code": 0, "error": str(e)}