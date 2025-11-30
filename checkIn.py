import json
import os
import requests
import time
import random
from datetime import datetime
from encryption import Encryption
from utils import get_headers, get_session, API_HOST

def log_response(user_id, endpoint, response_text):
    """Saves raw API responses to disk for debugging."""
    filename = f"request-logs/{user_id}/{endpoint}-{int(time.time())}.json"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        f.write(response_text)

def send_discord_webhook(success, lesson_title, user_id, error_msg=None, checkin_code=None, webhook_url=None):
    if not webhook_url or "YOUR_DISCORD_WEBHOOK" in webhook_url:
        return

    embed = {
        "title": "Check-In Successful" if success else "Check-In Failed",
        "color": 3066993 if success else 15158332,
        "description": f"**Lesson:** {lesson_title}",
        "fields": [{"name": "Student ID", "value": user_id, "inline": True}],
        "timestamp": datetime.now().isoformat()
    }

    if success and checkin_code:
        embed["fields"].append({"name": "Check-In Code", "value": checkin_code, "inline": False})

    if error_msg:
        embed["fields"].append({"name": "Error", "value": str(error_msg), "inline": False})

    try:
        requests.post(webhook_url, json={"embeds": [embed]})
    except Exception as e:
        print(f"Discord Error: {e}")

def performCheckIn(token, lesson, user_id="Unknown", mobile_phone_val=None, webhook_url=None):
    if not mobile_phone_val:
        error_msg = "Missing 'mobile_phone_setting'. Token configuration may be incomplete."
        print(f"Error: {error_msg}")
        return {"success": False, "code": 0, "error": error_msg}

    # Prepare Payload
    timestamp = datetime.now().isoformat().split('.')[0]
    timetable_id = str(lesson["ids"]["timetableId"])
    student_schedule_id = str(lesson["ids"]["studentScheduleId"])
    check_in_reason = "Ibeacon"
    check_in_input = None

    beacon_data = lesson["auth"].get("beaconData")
    if not beacon_data or not isinstance(beacon_data, list) or len(beacon_data) == 0:
        error_msg = "No iBeacon data available for this lesson."
        print(f"Error: {error_msg}")
        return {"success": False, "code": 0, "error": error_msg}

    uuid = random.choice(beacon_data).get("uuid")

    if not uuid:
        error_msg = "Selected iBeacon data is missing a UUID."
        print(f"Error: {error_msg}")
        return {"success": False, "code": 0, "error": error_msg}

    # Calculate Fingerprint
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
        response = get_session().post(url, headers=get_headers(token), json=payload)

        log_response(user_id, "CheckIn", response.text)

        success = response.status_code in [200, 201]
        error_msg = None
        checkin_code = None

        if success:
            try:
                data = response.json()
                checkin_code = data.get("checkinCode")
            except json.JSONDecodeError:
                pass

            if not checkin_code:
                checkin_code = lesson.get("checkinCode")

        else:
            error_msg = response.text

        send_discord_webhook(success, lesson["title"], user_id, error_msg, checkin_code, webhook_url)

        if success:
            return {"success": True, "code": response.status_code, "checkinCode": checkin_code}
        else:
            return {"success": False, "code": response.status_code, "error": response.text}

    except Exception as e:
        send_discord_webhook(False, lesson["title"], user_id, str(e), checkin_code=None, webhook_url=webhook_url)
        return {"success": False, "code": 0, "error": str(e)}