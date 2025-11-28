import json
import os
import sys
import time
import random
import argparse
from datetime import datetime, timedelta
from getUserData import fetchUserData, fetchMobilePhoneSetting  # Now fetches the key
from checkIn import performCheckIn  # Must be updated to accept key and webhook URL

CONFIG_FILE = "config.json"


def loadConfig():
    if not os.path.exists(CONFIG_FILE):
        return {"tokens": {}, "active": None, "DISCORD_WEBHOOK_URL": "YOUR_DISCORD_WEBHOOK_URL_HERE"}
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

            # Ensure multi-user structure is enforced (handles older single-token format)
            if "token" in config and "tokens" not in config:
                config["tokens"] = {"Default": {"token": config.pop("token"),
                                                "mobile_phone_setting": config.pop("mobile_phone_setting", None)}}
                config["active"] = "Default"

            # Ensure keys exist for the CLI
            if "DISCORD_WEBHOOK_URL" not in config:
                config["DISCORD_WEBHOOK_URL"] = "YOUR_DISCORD_WEBHOOK_URL_HERE"

            # Normalize token storage (critical for handling the backup's global key flaw)
            normalized_tokens = {}
            for alias, token_data in config.get("tokens", {}).items():
                if isinstance(token_data, str):
                    # Convert old string token format to modern dict format
                    normalized_tokens[alias] = {"token": token_data,
                                                "mobile_phone_setting": config.get("mobile_phone_setting")}
                elif isinstance(token_data, dict):
                    normalized_tokens[alias] = token_data

            return {"tokens": normalized_tokens, "active": config.get("active"),
                    "DISCORD_WEBHOOK_URL": config.get("DISCORD_WEBHOOK_URL")}

    except json.JSONDecodeError:
        return {"tokens": {}, "active": None, "DISCORD_WEBHOOK_URL": "YOUR_DISCORD_WEBHOOK_URL_HERE"}


def saveConfig(config):
    try:
        # Save tokens using the modern structure
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

    # Store the new token and initialize settings structure
    config["tokens"][alias] = {
        "token": token,
        "mobile_phone_setting": None
    }
    if not config.get("active"): config["active"] = alias

    print(f"Fetching required signing key for '{alias}'...")
    mobile_setting = fetchMobilePhoneSetting(token)

    if mobile_setting:
        # Save the key per-user
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

    token = token_data.get("token")

    if not token:
        print(f"ERROR: No token found for active user '{active_alias}'.")
        return

    data = fetchUserData(token)

    if not data or "user" not in data:
        print("Failed to fetch data. Check the Bearer Token or API status.")
        return

    u = data["user"]

    # FIX: Print user info, including email
    print(f"\nUser: {u.get('name')} ({u.get('studentId')})")
    print(f"Email: {u.get('email', 'N/A')}")  # Email displayed
    print("-" * 30)

    # FIX: Safely retrieve schedule, defaulting to an empty list
    schedule = data.get("schedule", [])

    if schedule:
        for l in schedule:
            # Safely retrieve title and time from the lesson object
            print(f"{l.get('startTime', 'N/A')} - {l.get('title', 'N/A')}")
    else:
        print("No upcoming lessons found or failed to fetch schedule data.")

    print("")


def checkInMenu():
    config = loadConfig()
    active_alias = config.get("active")
    token_data = config.get("tokens", {}).get(active_alias)
    webhook_url = config.get("DISCORD_WEBHOOK_URL")

    if not token_data:
        print("ERROR: No active token selected.")
        return

    token = token_data.get("token")
    # FIX: Get mobile key from per-user storage
    mobile_phone_setting = token_data.get("mobile_phone_setting")

    if not token or not mobile_phone_setting:
        print("ERROR: Active token is missing the Bearer token or Signing Key.")
        return

    data = fetchUserData(token)

    if not data:
        print("\nERROR: Failed to fetch user data. Check the Bearer Token validity or API endpoint.")
        return

    # FIX: Safely retrieve schedule, defaulting to an empty list
    schedule = data.get("schedule", [])

    if not schedule:
        print("\n--- Manual Check-In ---")
        print("No upcoming lessons found. Check time range in getUserData.py.")
        return

    print("\n--- Manual Check-In ---")
    for i, l in enumerate(schedule, 1):
        print(f"{i}. {l.get('title', 'N/A')} ({l.get('startTime', 'N/A')})")

    try:
        idx = int(input("Select class: ")) - 1

        if 0 <= idx < len(schedule):
            print("Checking in...")
            user_id = data.get("user", {}).get("studentId", "Unknown")

            # Pass all required parameters for the check-in request
            res = performCheckIn(token, schedule[idx], user_id, mobile_phone_setting, webhook_url)

            if res.get('success'):
                print(f"Check-In SUCCESSFUL! Code: {res.get('checkinCode', 'N/A')}")
            else:
                print(f"Check-In FAILED: {res.get('error', 'Unknown error')}")
        else:
            print("Invalid selection.")

    except ValueError:
        print("Invalid input (must be a number).")
    except Exception as e:
        print(f"An unexpected error occurred during check-in: {e}")


def startScheduler():
    config = loadConfig()
    all_tokens_data = config.get("tokens", {})
    webhook_url = config.get("DISCORD_WEBHOOK_URL")

    if not all_tokens_data:
        print("No tokens found.")
        return

    # 1. Feature: Account Selection (remains the same)
    print("\n--- SELECT ACCOUNTS FOR AUTO-SCHEDULER ---")
    token_keys = list(all_tokens_data.keys())
    for i, name in enumerate(token_keys, 1):
        print(f"{i}. {name}")

    choice = input("\nEnter numbers separated by comma (e.g. '1,2') or press Enter for ALL: ").strip()

    active_tokens = {}
    if not choice:
        active_tokens = all_tokens_data
    else:
        try:
            idxs = [int(x) - 1 for x in choice.split(",") if x.strip()]
            for i in idxs:
                if 0 <= i < len(token_keys):
                    key = token_keys[i]
                    active_tokens[key] = all_tokens_data[key]
        except:
            print("Invalid selection. Defaulting to ALL.")
            active_tokens = all_tokens_data

    print(f"\nRunning Scheduler for: {', '.join(active_tokens.keys())}")
    print("Press Ctrl+C to stop.\n")

    # State tracking
    processed_lessons = set()
    lesson_targets = {}

    last_fetch_time = 0
    FETCH_INTERVAL = 1800

    try:
        while True:
            now = datetime.now()

            # --- A. Fetch Data (Every 30 mins or on start) ---
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
                        schedule = data.get("schedule", [])

                        if not schedule: continue

                        user_id = data["user"]["studentId"]

                        for lesson in schedule:
                            lesson_id = f"{user_id}-{lesson['ids']['timetableId']}"

                            if lesson_id not in processed_lessons and lesson_id not in lesson_targets:
                                # FIX: Use reliable datetime parsing
                                start_dt = datetime.strptime(lesson['startTime'], '%Y-%m-%d %H:%M:%S')

                                # FIX: Correct check-in logic (1 minute before +/- 60 seconds)
                                random_offset = random.randint(-60, 60)
                                check_in_offset = timedelta(minutes=1) - timedelta(seconds=random_offset)
                                target_time = start_dt - check_in_offset

                                if target_time > now - timedelta(minutes=10):
                                    lesson_targets[lesson_id] = {
                                        "time": target_time,
                                        "lesson": lesson,
                                        "token": token,
                                        "name": name,
                                        "uid": user_id,
                                        "key": mobile_phone_setting,
                                        "webhook_url": webhook_url
                                    }
                                    print(
                                        f"\n[SCHEDULED] '{name}' for {lesson['title']} at {target_time.strftime('%Y-%m-%d %H:%M:%S')}")

                    except Exception as e:
                        print(f"\nError fetching {name}: {e}")

                last_fetch_time = time.time()
                sys.stdout.write("\r" + " " * 50 + "\r")

            # --- B. Check Triggers (remains the same) ---
            to_remove = []
            for lid, info in lesson_targets.items():
                if now >= info["time"]:
                    print(f"\n[CHECK-IN] {info['name']} -> {info['lesson']['title']} (SENDING REQUEST)")

                    # Use mobile_phone_setting from info dict
                    res = performCheckIn(
                        info["token"],
                        info["lesson"],
                        info["uid"],
                        info["key"],
                        info["webhook_url"]
                    )

                    if res.get('success'):
                        print(
                            f"[CHECK-IN] {info['name']} -> {info['lesson']['title']} SUCCESS! Code: {res.get('checkinCode', 'N/A')}")
                    else:
                        print(f"[ERROR] {info['name']} -> {info['lesson']['title']} FAILED: {res.get('error')}")

                    processed_lessons.add(lid)
                    to_remove.append(lid)

            for lid in to_remove:
                del lesson_targets[lid]

            # --- C. Feature: Detailed Display (Grouped Users) (remains the same) ---
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

# --- This executes first, determines run mode ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEAtS Automation CLI.")
    parser.add_argument('run_mode', nargs='?', default=None, help='Set to "scheduler" to run scheduler directly.')
    args = parser.parse_args()

    try:
        if args.run_mode == 'scheduler':
            # 1. Run in headless mode
            print("Starting SEAtS Scheduler in Headless Mode...")
            startScheduler()
        else:
            # 2. Run in interactive CLI mode
            main()
    except KeyboardInterrupt:
        sys.exit(0)