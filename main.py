import time
from datetime import datetime
from utils import get_headers, get_session, decode_jwt, API_HOST

def fetchProfile(token: str):
    url = f"https://{API_HOST}/api/v1/students/myself/profile"
    try:
        # RELIABILITY FIX: Use session with retry
        response = get_session().get(url, headers=get_headers(token))
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def fetchTimetable(token: str):
    startDate = int(time.time())
    endDate = startDate + (7 * 24 * 60 * 60)

    url = f"https://{API_HOST}/api/v2/students/myself/events"
    params = {"startDate": startDate, "endDate": endDate}

    try:
        response = get_session().get(url, headers=get_headers(token), params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR: fetchTimetable failed with status {response.status_code}")
    except Exception as e:
        print(f"ERROR: fetchTimetable failed due to network/request issue: {e}")
        pass
    return []

def fetchUserData(token: str):
    tokenData = decode_jwt(token)
    profileData = fetchProfile(token)
    timetableData = fetchTimetable(token)

    userName = tokenData.get("name") if isinstance(tokenData.get("name"), str) else "Unknown"
    userEmail = "N/A"

    name_field = tokenData.get("name")
    if isinstance(name_field, list) and len(name_field) >= 2:
        userName = name_field[0]
        userEmail = name_field[1]

    if profileData and profileData.get('email'):
        userEmail = profileData.get('email')

    def fmt_ts(ts):
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "Unknown"

    cleanTimetable = []
    for lesson in timetableData or []:
        beaconData = lesson.get("iBeaconData", [])
        beacon_data_list = beaconData if isinstance(beaconData, list) else []

        start_ts = lesson.get("start")
        cleanTimetable.append(
            {
                "title": lesson.get("title"),
                "room": lesson.get("roomName"),
                "startTime": fmt_ts(start_ts),
                "ids": {
                    "timetableId": lesson.get("timeTableId"),
                    "studentScheduleId": lesson.get("studentScheduleId"),
                },
                "auth": {"beaconData": beacon_data_list},
            }
        )

    exp_ts = tokenData.get("exp")
    finalData = {
        "user": {
            "name": userName,
            "email": userEmail,
            "studentId": tokenData.get("studentId"),
            "tenantId": tokenData.get("TenantId"),
            "tokenExpiration": fmt_ts(exp_ts),
        },
        "profileDetails": profileData,
        "schedule": cleanTimetable,
    }

    return finalData

def fetchMobilePhoneSetting(token: str):
    url = f"https://{API_HOST}/api/v1/app/settingsextended"
    try:
        response = get_session().get(url, headers=get_headers(token))
        if response.status_code == 200:
            data = response.json()
            for setting in data:
                if setting.get("key") == "MobilePhone":
                    return setting.get("value")
    except Exception as e:
        print(f"Error fetching mobile setting: {e}")
    return None

if __name__ == "__main__":
    print("This module is intended to be used by the CLI. Provide a token to fetchUserData(token).")