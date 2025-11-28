import requests
import json
import base64
import time
from datetime import datetime

TENANT_ID = "126"
API_HOST = "01v2mobileapi.seats.cloud"


def _extract_raw_token(token: str) -> str:
    t = (token or "").strip()
    return t[7:] if t.startswith("Bearer ") else t


def getHeaders(token: str):
    cleanToken = token.strip()
    if not cleanToken.startswith("Bearer "):
        cleanToken = f"Bearer {cleanToken}"
    return {
        "Authorization": cleanToken,
        "Abp.TenantId": TENANT_ID,
        "Host": API_HOST,
        "User-Agent": "SeatsMobile/1728493384 CFNetwork/1568.100.1.2.1 Darwin/24.0.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
    }


def decodeJwt(token):
    try:
        payloadPart = _extract_raw_token(token).split(".")[1]
        padding = "=" * ((4 - len(payloadPart) % 4) % 4)
        decodedBytes = base64.urlsafe_b64decode(payloadPart + padding)
        return json.loads(decodedBytes)
    except Exception:
        return {}


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
    except Exception:
        pass
    return []

def fetchUserData(token: str):
    tokenData = decodeJwt(token)
    profileData = fetchProfile(token)
    timetableData = fetchTimetable(token)

    userName = "Unknown"
    userEmail = "Unknown"

    if "name" in tokenData and isinstance(tokenData["name"], list) and len(tokenData["name"]) >= 2:
        userName = tokenData["name"][0]
        userEmail = tokenData["name"][1]

    def fmt_ts(ts):
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "Unknown"

    cleanTimetable = []
    for lesson in timetableData or []:

        beacon_data = lesson.get("iBeaconData", [])

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
                # Storing the full beacon data array
                "auth": {"beaconData": beacon_data},
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