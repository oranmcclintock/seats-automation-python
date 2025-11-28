import time
import random
import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from database import engine, Base, get_db
import models
import schemas

# Import your existing logic files
# Ensure getUserData.py and checkIn.py are in the same folder
from getUserData import fetchUserData, fetchMobilePhoneSetting
from checkIn import performCheckIn

# --- REQUIRED LINES IN YOUR NEW main.py ---
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
# ... other imports

app = FastAPI(title="SEAtS Automation Web App") # <--- THIS LINE IS CRITICAL
# ... rest of the code for startup, scheduler, and routes

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SeatsApp")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SEAtS Automation Web App")
templates = Jinja2Templates(directory="templates")

# Scheduler setup
scheduler = BackgroundScheduler()

# In-memory set to track scheduled lesson IDs to prevent duplicates
scheduled_lessons_cache = set()

# --- Scheduler Logic ---

def automated_check_in_task(token: str, lesson: dict, user_id: str, mobile_key: str, webhook_url: str):
    """The actual function called when the timer hits."""
    logger.info(f"Executing Check-in for {user_id} - {lesson.get('title')}")
    try:
        performCheckIn(token, lesson, user_id, mobile_key, webhook_url)
    except Exception as e:
        logger.error(f"Check-in failed: {e}")

def schedule_refresh_job():
    """Runs every 30 mins to fetch schedules and queue check-ins."""
    logger.info("Running Schedule Refresh...")
    db = next(get_db())
    users = db.query(models.User).filter(models.User.is_active == True).all()
    
    now = datetime.now()

    for user in users:
        try:
            data = fetchUserData(user.token)
            if not data or "schedule" not in data:
                continue

            student_id = data["user"].get("studentId")
            schedule = data.get("schedule", [])

            for lesson in schedule:
                # Unique ID for this specific lesson instance
                lid = f"{student_id}-{lesson['ids']['timetableId']}"
                
                # Skip if already handled/passed
                if lid in scheduled_lessons_cache:
                    continue

                # Parse start time
                try:
                    start_dt = datetime.strptime(lesson['startTime'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue

                # Calculate Check-in Time (1 min before +/- random seconds)
                random_offset = random.randint(-60, 60)
                target_time = start_dt - timedelta(minutes=1) + timedelta(seconds=random_offset)

                # Only schedule if it's in the future (and within next 24 hours to be safe)
                if now < target_time < now + timedelta(hours=24):
                    logger.info(f"Scheduling {user.alias}: {lesson['title']} at {target_time}")
                    
                    scheduler.add_job(
                        automated_check_in_task,
                        'date',
                        run_date=target_time,
                        args=[user.token, lesson, student_id, user.mobile_key, user.webhook_url],
                        id=lid,
                        replace_existing=True
                    )
                    scheduled_lessons_cache.add(lid)

        except Exception as e:
            logger.error(f"Error processing user {user.alias}: {e}")

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(schedule_refresh_job, 'interval', minutes=30)
    scheduler.start()
    # Run once immediately on startup
    scheduler.add_job(schedule_refresh_job, 'date', run_date=datetime.now() + timedelta(seconds=5))

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

# --- API Routes ---

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return templates.TemplateResponse("index.html", {"request": request, "users": users})

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. Fetch mobile signing key
    mobile_key = fetchMobilePhoneSetting(user.token)
    if not mobile_key:
        raise HTTPException(status_code=400, detail="Could not fetch Mobile Signing Key from token.")

    # 2. Save to DB
    db_user = models.User(
        alias=user.alias,
        token=user.token,
        mobile_key=mobile_key,
        webhook_url=user.webhook_url
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Trigger a refresh so this user gets scheduled immediately
    scheduler.add_job(schedule_refresh_job, 'date', run_date=datetime.now() + timedelta(seconds=2))
    
    return db_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"ok": True}

@app.get("/schedule/{user_id}")
def get_user_schedule(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    data = fetchUserData(user.token)
    return data