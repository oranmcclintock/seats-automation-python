<img width="1882" height="965" alt="2025-11-29_23-10-41" src="https://github.com/user-attachments/assets/7d7f8aa3-24ae-45b2-85e6-1dbb3f1cc648" />
<img width="1893" height="963" alt="2025-11-29_23-14-55" src="https://github.com/user-attachments/assets/0be0841b-bae5-49c7-88e8-f3a9e14678e1" />

# SEAtS Attendance Automation (Web Platform)

**DISCLAIMER: EDUCATIONAL & SECURITY RESEARCH ONLY**  
This project is a proof-of-concept created to demonstrate security weaknesses within the SEAtS attendance system.  
It must not be used to violate university policies or misrepresent attendance.  
This repository does not provide tools, instructions, or guidance for acquiring authentication tokens.

---

## 1. Project Overview

This application is a fully automated, web-based dashboard for managing SEAtS attendance. It demonstrates how the current Bluetooth-based presence verification system can be bypassed through standard API automation due to weaknesses in SEAtS authentication and client-side trust.

Unlike earlier CLI versions, this release operates as a persistent FastAPI web service capable of:

- Managing multiple student accounts  
- Synchronising timetable data  
- Automatically performing attendance check-ins at scheduled times  

This project is intended solely for security research and responsible disclosure.

---

## 2. Key Features

### Web Dashboard
A modern, responsive Bootstrap 5 interface for managing accounts and viewing schedules.

### Multi-Tenant Architecture
SQLite and SQLAlchemy provide durable storage for multiple student profiles and scheduled tasks.

### Smart Scheduling
- Polls the SEAtS API every 30 minutes  
- Extracts event details and beacon UUIDs  
- Schedules attendance submissions at the exact class start time with optional randomised delays  

### Discord Webhook Notifications
Provides real-time alerts for:
- Successful check-ins  
- Errors or API failures  
- Token expiration or invalidation  

### Fingerprint Generation
Implements the cryptographic logic required to produce valid `fp` fingerprint values accepted by the official SEAtS mobile API.

---

## 3. Technical Architecture

Backend: FastAPI (asynchronous Python server)  
Database: SQLite + SQLAlchemy ORM  
Scheduling: APScheduler (BackgroundScheduler)  
Frontend: Jinja2 templates with mobile optimisation  

### Automation Workflow

1. **Sync:** Poll the `/api/v2/students/myself/events` endpoint every 30 minutes.  
2. **Parse:** Extract class metadata and the leaked Bluetooth Beacon UUID.  
3. **Schedule:** Queue background jobs 0–60 seconds after class start time.  
4. **Execute:** Perform a crafted POST to the SEAtS `/checkin` endpoint, imitating official mobile client behaviour.

---

## 4. Security Vulnerabilities Demonstrated

### Critical: Excessive Token Longevity
SEAtS access tokens have a 10-year expiration (valid until 2035).  
Once intercepted, long-term persistent access is possible without reauthentication.

### High: Information Leakage (Beacon UUIDs)
Timetable responses contain valid Bluetooth Beacon UUIDs used for physical presence verification.  
These can be replayed remotely to spoof attendance.

### Medium: Lack of Client Integrity Checks
No device attestation, IP reputation filtering, or anti-automation checks are enforced.  
The API accepts generic HTTP requests that mimic the mobile app.

---

## 5. Installation and Usage

### Requirements
- Python 3.10+
- A valid SEAtS Bearer Token (not provided)

---

### Installation

Create a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Running the Server

Start the FastAPI application with Uvicorn:

```bash

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access the web dashboard:

```bash
http://localhost:8000
```

### Operation

1. Open the dashboard and click Add User.
2. Paste your SEAtS Bearer Token.
3. The system retrieves your profile and token expiry.
4. Toggle the automation switch to enable automatic attendance handling.

The system will now schedule and submit all future check-ins automatically.

## 6. Mitigation Recommendations

To address the vulnerabilities demonstrated:

- Reduce Access Token lifetime to under one hour and enforce refresh-token rotation.

- Remove Beacon UUIDs from client-visible API fields.

- Implement mobile device integrity checks (Android Play Integrity, iOS DeviceCheck).

- Perform server-side validation of attendance submissions rather than trusting client beacon data.
