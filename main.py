import json
import os
import sys
import time
import random
import argparse
from datetime import datetime, timedelta
from getUserData import fetchUserData, fetchMobilePhoneSetting
from checkIn import performCheckIn

CONFIG_FILE = "config.json"

def loadConfig():
    if not os.path.exists(CONFIG_FILE):
        return {"tokens": {}, "active": None}
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

            if "token" in config and "tokens" not in config:
                config["tokens"] = {"Default": {"token": config.pop("token"), "mobile_phone_setting": None}}
                config["active"] = "Default"

            if "mobile_phone_setting" in config:
                config.pop("mobile_phone_setting")

            return {"tokens": config.get("tokens", {}), "active": config.get("active")}

    except json.JSONDecodeError:
        return {"tokens": {}, "active": None}

def saveConfig(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print("\nConfiguration saved successfully")
    except Exception as e:
        print(f"\nError saving configuration: {e}")


def _validate_token(token: str) -> bool:
    t = (token or "").strip()
    if t.startswith("Bearer "):
        t = t[7:]

    return len(t) > 50


def addToken():
    print("\n--- Add New Token ---")
    token = input("Paste Bearer Token: ").strip()
    if not _validate_token(token):
        print("Invalid token format.")
        return

    config = loadConfig()
    alias = input("Enter name (e.g. 'Personal'): ").strip()
    if not alias: alias = f"User_{len(config.get('tokens', {})) + 1}"

    config["tokens"][alias] = {
        "token": token,
        "mobile_phone_setting": None
    }

    if not config.get("active"): config["active"] = alias

    print(f"Fetching required signing key for '{alias}'...")
    mobile_setting = fetchMobilePhoneSetting(token)

    if mobile_setting:

        config["tokens"][alias]["mobile_phone_setting"] = mobile_setting
        print("Successfully fetched signing key (MobilePhone setting).")
    else:
        print("Warning: Failed to fetch signing key. Check-in functionality may fail.")

    saveConfig(config)
    print(f"Added '{alias}'.")


def selectToken():
    config = loadConfig()
    tokens = config.get("tokens", {})
    if not tokens: return

    print("\n--- Select Active Token ---")
    keys = list(tokens.keys())
    for i, k in enumerate(keys, 1):
        print(f"{i}. {k} {'*' if k == config.get('active') else ''}")

    try:
        idx = int(input("Select: ")) - 1
        if 0 <= idx < len(keys):
            config["active"] = keys[idx]
            saveConfig(config)
            print(f"Active: {keys[idx]}")
    except:
        pass


def deleteToken():
    config = loadConfig()
    tokens = config.get("tokens", {})
    if not tokens: return

    print("\n--- Delete Token ---")
    keys = list(tokens.keys())
    for i, k in enumerate(keys, 1):
        print(f"{i}. {k}")

    try:
        idx = int(input("Delete: ")) - 1
        if 0 <= idx < len(keys):
            toDelete = keys[idx]
            del config["tokens"][toDelete]


            if config.get("active") == toDelete:
                config["active"] = None

            saveConfig(config)
            print("Deleted.")
    except:
        pass


def viewData():
    config = loadConfig()
    active_alias = config.get("active")
    token_data = config.get("tokens", {}).get(active_alias)

    if not token_data:
        print("ERROR: No active token selected.")
        return

    # Explicitly extract the token string
    token = token_data.get("token")

    if not token:
        print(f"ERROR: No token found for active user '{active_alias}'.")
        return

    data = fetchUserData(token)

    if not data or "user" not in data:
        print("Failed to fetch data. Check the Bearer Token or API status.")
        return

    u = data["user"]

    print(f"\nUser: {u.get('name')} ({u.get('studentId')})")
    print(f"Email: {u.get('email', 'N/A')}")
    print("-" * 30)
    for l in data["schedule"]:
        print(f"{l['startTime']} - {l['title']}")
    print("")

def checkInMenu():
    config = loadConfig()
    active_alias = config.get("active")
    token_data = config.get("tokens", {}).get(active_alias)

    if not token_data:
        print("No active token selected.")
        return

    token = token_data.get("token")
    mobile_phone_setting = token_data.get("mobile_phone_setting")

    if not token or not mobile_phone_setting:
        print("Active token is missing the Bearer token or Signing Key.")
        return

    data = fetchUserData(token)
    schedule = data.get("schedule", [])

    print("\n--- Manual Check-In ---")
    for i, l in enumerate(schedule, 1):
        print(f"{i}. {l['title']} ({l['startTime']})")

    try:
        idx = int(input("Select class: ")) - 1
        if 0 <= idx < len(schedule):
            print("Checking in...")
            user_id = data.get("user", {}).get("studentId", "Unknown")
            # PASS THE MOBILE_PHONE_SETTING
            res = performCheckIn(token, schedule[idx], user_id, mobile_phone_setting)
            print(res)
    except:
        pass

def startScheduler():
    config = loadConfig()
    all_token_data = config.get("tokens", {})

    if not all_token_data:
        print("No tokens found.")
        return

    print("\n--- SELECT ACCOUNTS FOR AUTO-SCHEDULER ---")
    token_keys = list(all_token_data.keys())
    for i, name in enumerate(token_keys, 1):
        print(f"{i}. {name}")

    choice = input("\nEnter numbers separated by comma (e.g. '1,2') or press Enter for ALL: ").strip()

    active_tokens = {}
    if not choice:
        active_tokens = all_token_data
    else:
        try:
            idxs = [int(x) - 1 for x in choice.split(",")]
            for i in idxs:
                if 0 <= i < len(token_keys):
                    key = token_keys[i]
                    active_tokens[key] = all_token_data[key]
        except:
            print("Invalid selection. Defaulting to ALL.")
            active_tokens = all_token_data

    print(f"\nRunning Scheduler for: {', '.join(active_tokens.keys())}")
    print("Press Ctrl+C to stop.\n")

    processed_lessons = set()
    lesson_targets = {}

    last_fetch_time = 0
    FETCH_INTERVAL = 1800

    try:
        while True:
            now = datetime.now()

            if time.time() - last_fetch_time > FETCH_INTERVAL:
                sys.stdout.write("\r[System] Refreshing schedules...                     ")
                sys.stdout.flush()

                current_config_tokens = loadConfig().get("tokens", {})

                for name, token_data in active_tokens.items():
                    if name in current_config_tokens:
                        token_data = current_config_tokens[name]

                    token = token_data.get("token")
                    mobile_phone_setting = token_data.get("mobile_phone_setting")

                    if not token or not mobile_phone_setting:
                        print(f"\nSkipping '{name}': Token or Signing Key missing.")
                        continue

                    try:
                        data = fetchUserData(token)
                        if not data or "schedule" not in data: continue

                        user_id = data["user"]["studentId"]

                        for lesson in data["schedule"]:
                            lesson_id = f"{user_id}-{lesson['ids']['timetableId']}"

                            if lesson_id not in processed_lessons and lesson_id not in lesson_targets:
                                start_dt = datetime.strptime(lesson['startTime'], '%Y-%m-%d %H:%M:%S')

                                # Check-in 1 minute before lesson start time, with a random offset of +/- 60 seconds
                                random_offset_seconds = random.randint(-60, 60)
                                check_in_offset = timedelta(minutes=1) - timedelta(seconds=random_offset_seconds)
                                target_time = start_dt - check_in_offset

                                if target_time > now - timedelta(minutes=10):
                                    lesson_targets[lesson_id] = {
                                        "time": target_time,
                                        "lesson": lesson,
                                        "token": token,
                                        "name": name,
                                        "uid": user_id,
                                        "key": mobile_phone_setting
                                    }
                    except Exception as e:
                        print(f"\nError fetching {name}: {e}")

                last_fetch_time = time.time()
                sys.stdout.write("\r" + " " * 50 + "\r")

            to_remove = []
            for lid, info in lesson_targets.items():
                if now >= info["time"]:
                    print(f"\n[CHECK-IN] {info['name']} -> {info['lesson']['title']}")
                    # Pass the key to performCheckIn
                    performCheckIn(info["token"], info["lesson"], info["uid"], info["key"])

                    processed_lessons.add(lid)
                    to_remove.append(lid)

            for lid in to_remove:
                del lesson_targets[lid]

            closest_time = None
            closest_info = None

            for lid, info in lesson_targets.items():
                if info["time"] > now:
                    if closest_time is None or info["time"] < closest_time:
                        closest_time = info["time"]
                        closest_info = info

            if closest_info:
                users_with_class = []
                target_title = closest_info['lesson']['title']
                target_start = closest_info['lesson']['startTime']

                for lid, info in lesson_targets.items():
                    if (info['lesson']['title'] == target_title and
                            info['lesson']['startTime'] == target_start and
                            info['time'] > now):
                        users_with_class.append(info['name'])

                users_with_class = sorted(list(set(users_with_class)))
                names_str = ", ".join(users_with_class)

                wait_sec = int((closest_time - now).total_seconds())
                d = wait_sec // 86400
                h = (wait_sec % 86400) // 3600
                m = (wait_sec % 3600) // 60
                s = wait_sec % 60

                status = f"Next: [{names_str}] {target_title} in {d}d {h}h {m}m {s}s"
            else:
                status = "No upcoming classes found."

            sys.stdout.write(f"\r{status.ljust(80)}")
            sys.stdout.flush()

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped.")

def main():
    while True:

        config = loadConfig()
        tokenCount = len(config.get("tokens", {}))
        activeStatus = config.get("active", "None")

        print("\nSEAtS Automation CLI")
        print(f"Status: {tokenCount} tokens stored | Active: {activeStatus}")
        print("--------------------")
        print("1. Add Token (Fetches Signing Key)")
        print("2. Select Active")
        print("3. View Data")
        print("4. Manual Check-In")
        print("5. Start Scheduler")
        print("6. Delete Token")
        print("7. Exit")

        c = input("Choice: ")
        if c == "1":
            addToken()
        elif c == "2":
            selectToken()
        elif c == "3":
            viewData()
        elif c == "4":
            checkInMenu()
        elif c == "5":
            startScheduler()
        elif c == "6":
            deleteToken()
        elif c == "7":
            sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEAtS Automation CLI and Scheduler.")
    parser.add_argument(
        '--start-scheduler',
        action='store_true',
        help='Start the scheduler immediately without the interactive menu.'
    )
    args = parser.parse_args()

    if args.start_scheduler:
        # Executes the scheduler function directly
        startScheduler()
    else:
        try:
            # Runs the interactive CLI menu
            main()
        except KeyboardInterrupt:
            sys.exit(0)