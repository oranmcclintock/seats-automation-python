import time
import random
import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from database import engine, Base, get_db
import models
import schemas

# Import your existing logic files
from getUserData import fetchUserData, fetchMobilePhoneSetting
from checkIn import performCheckIn

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SeatsApp")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SEAtS Automation Web App")
templates = Jinja2Templates(directory="templates")

scheduler = BackgroundScheduler()
scheduled_lessons_cache = set()

# --- Scheduler Logic ---

def automated_check_in_task(token: str, lesson: dict, user_id: str, mobile_key: str, webhook_url: str):
    logger.info(f"Executing Check-in for {user_id} - {lesson.get('title')}")
    try:
        performCheckIn(token, lesson, user_id, mobile_key, webhook_url)
    except Exception as e:
        logger.error(f"Check-in failed: {e}")

def schedule_refresh_job():
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
                lid = f"{student_id}-{lesson['ids']['timetableId']}"
                
                if lid in scheduled_lessons_cache:
                    continue

                try:
                    start_dt = datetime.strptime(lesson['startTime'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue

                # Schedule check-in: 1 min before start +/- random offset
                random_offset = random.randint(-60, 60)
                target_time = start_dt - timedelta(minutes=1) + timedelta(seconds=random_offset)

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
    if not scheduler.running:
        scheduler.add_job(schedule_refresh_job, 'interval', minutes=30)
        scheduler.start()
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
    mobile_key = fetchMobilePhoneSetting(user.token)
    if not mobile_key:
        raise HTTPException(status_code=400, detail="Could not fetch Mobile Signing Key from token.")

    db_user = models.User(
        alias=user.alias,
        token=user.token,
        mobile_key=mobile_key,
        webhook_url=user.webhook_url
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
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

# NEW: Toggle Active Status
@app.patch("/users/{user_id}/toggle")
def toggle_user_active(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    db.commit()
    return {"id": user.id, "is_active": user.is_active}

@app.get("/schedule/{user_id}")
def get_user_schedule(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    data = fetchUserData(user.token)
    return data

# NEW: Manual Check-In
@app.post("/checkin/{user_id}")
def manual_checkin(user_id: int, req: schemas.CheckInRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 1. Fetch fresh schedule to get beacon data
    data = fetchUserData(user.token)
    if not data or "schedule" not in data:
        raise HTTPException(status_code=500, detail="Failed to fetch schedule from SEAtS")

    student_id = data["user"].get("studentId")
    
    # 2. Find the specific lesson
    target_lesson = None
    for lesson in data["schedule"]:
        # Compare IDs
        if (lesson["ids"]["timetableId"] == req.timetable_id and 
            lesson["ids"]["studentScheduleId"] == req.student_schedule_id):
            target_lesson = lesson
            break
    
    if not target_lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in current schedule")

    # 3. Perform Check-in
    result = performCheckIn(user.token, target_lesson, student_id, user.mobile_key, user.webhook_url)
    
    return result