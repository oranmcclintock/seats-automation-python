import requests
import json
import base64
import time
import os
from datetime import datetime
from datetime import timedelta, timezone 

# ENV VARS (With defaults)
API_HOST = os.getenv("API_HOST", "01v2mobileapi.seats.cloud")

def _extract_raw_token(token: str) -> str:
    t = (token or "").strip()
    return t[7:] if t.startswith("Bearer ") else t

def decodeJwt(token):
    try:
        payloadPart = _extract_raw_token(token).split(".")[1]
        padding = "=" * ((4 - len(payloadPart) % 4) % 4)
        decodedBytes = base64.urlsafe_b64decode(payloadPart + padding)
        return json.loads(decodedBytes)
    except Exception:
        return {}

def getHeaders(token: str):
    tokenData = decodeJwt(token)
    tenant_id = tokenData.get("TenantId", "126") # Fallback to 126

    cleanToken = token.strip()
    if not cleanToken.startswith("Bearer "):
        cleanToken = f"Bearer {cleanToken}"
        
    return {
        "Authorization": cleanToken,
        "Abp.TenantId": tenant_id,  
        "Host": API_HOST,
        "User-Agent": "SeatsMobile/1728493384 CFNetwork/1568.100.1.2.1 Darwin/24.0.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
    }

def fetchProfile(token: str):
    url = f"https://{API_HOST}/api/v1/students/myself/profile"
    try:
        response = requests.get(url, headers=getHeaders(token))
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
        response = requests.get(url, headers=getHeaders(token), params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR: fetchTimetable failed with status {response.status_code}")
    except Exception as e:
        print(f"ERROR: fetchTimetable failed due to network/request issue: {e}")
        pass
    return []

def fetchUserData(token: str):
    tokenData = decodeJwt(token)
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
        response = requests.get(url, headers=getHeaders(token))
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