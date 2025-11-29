<img width="1882" height="965" alt="2025-11-29_23-10-41" src="https://github.com/user-attachments/assets/7d7f8aa3-24ae-45b2-85e6-1dbb3f1cc648" />
<img width="1893" height="963" alt="2025-11-29_23-14-55" src="https://github.com/user-attachments/assets/0be0841b-bae5-49c7-88e8-f3a9e14678e1" />

# SEAtS Attendance Automation (Web Platform)

[Dashboard View]: https://github.com/user-attachments/assets/7d7f8aa3-24ae-45b2-85e6-1dbb3f1cc648
[Mobile View]: https://github.com/user-attachments/assets/0be0841b-bae5-49c7-88e8-f3a9e14678e1

> DISCLAIMER: EDUCATIONAL & SECURITY RESEARCH ONLY
> This project is a Proof-of-Concept (PoC) designed to highlight security flaws in the SEAtS attendance system. It is not intended for violating university policies or misrepresenting attendance. This repository does not provide tools to steal authentication tokens.

---

## 1. Project Overview

This is a fully automated, web-based dashboard built to handle SEAtS attendance. The goal is to demonstrate how easily the current Bluetooth-based verification can be bypassed using standard API automation, primarily due to weak authentication protocols and excessive client-side trust.

This is a persistent FastAPI web service capable of:
- Managing multiple student accounts simultaneously.
- Synchronising timetable data automatically.
- Handling attendance check-ins in the background.

## 2. Key Features

### Web Dashboard
A clean, responsive interface built with Bootstrap 5 to manage accounts and view upcoming schedules.

### Multi-Tenant Architecture
Backed by SQLite and SQLAlchemy, allowing persistent storage for multiple student profiles and scheduled tasks.

### Smart Scheduling
- **Auto-Poll:** Checks the SEAtS API every 30 minutes for updates.
- **Data Extraction:** Extracts event details and the specific Beacon UUIDs required for check-in.
- **Precision:** Schedules the check-in request for the exact class start time with a randomized delay to appear human.

### Discord Webhook Notifications
Sends real-time alerts for:
- Successful check-ins.
- API errors or failures.
- Token expiration warnings.

### Fingerprint Generation
Implements the cryptographic logic required to generate valid `fp` (fingerprint) values, ensuring the API accepts requests as if they originated from the official mobile app.

## 3. Technical Architecture

- **Backend:** FastAPI (Async Python)
- **Database:** SQLite + SQLAlchemy ORM
- **Scheduling:** APScheduler (BackgroundScheduler)
- **Frontend:** Jinja2 Templates + Mobile Optimized CSS

### Automation Workflow

1. **Sync:** Polls `/api/v2/students/myself/events` every 30 minutes.
2. **Parse:** Scrapes class metadata and the leaked Bluetooth Beacon UUID.
3. **Schedule:** Queues a background job to fire 0–60 seconds after class start.
4. **Execute:** Sends a crafted POST request to `/checkin`, mimicking the mobile client.

## 4. Security Vulnerabilities Exposed

### Critical: Excessive Token Longevity
The access tokens SEAtS issues are valid for 10 years (expiry set to 2035). If a token is intercepted once, an attacker has persistent access indefinitely without re-authentication.

### High: Information Leakage (Beacon UUIDs)
The API response for student timetables contains the valid Bluetooth Beacon UUIDs used for physical presence verification. This allows for remote "replay" attacks to spoof attendance.

### Medium: Lack of Client Integrity
There are no checks for device attestation, IP reputation, or anti-automation. The API accepts generic HTTP requests provided the headers mimic the standard client.

## 5. Installation and Usage

### Requirements
- Python 3.10+
- A valid SEAtS Bearer Token.

### Installation

Clone the repository and create a virtual environment:

```
git clone https://github.com/oranmcclintock/seats-automation-python.git
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

Install dependencies:

```
pip install -r requirements.txt
```

### Running the Server

Start the FastAPI application:

```
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access the dashboard at `http://localhost:8000`.

### Operation

1. Open the dashboard and click **Add User**.
2. Paste your SEAtS Bearer Token.
3. The system will retrieve your profile and display the token expiry date.
4. Toggle the **Automation** switch.

The system will now schedule and submit all future check-ins automatically.

## 6. Mitigation Recommendations

To address these vulnerabilities:

- **Reduce Token Lifetime:** Expire access tokens in under one hour and enforce refresh token rotation.
- **Remove Beacon Data:** Stop sending Beacon UUIDs in client-visible API responses.
- **Device Verification:** Implement Android Play Integrity or iOS DeviceCheck.
- **Server-Side Validation:** Validate attendance based on trusted network signals rather than trusting client-submitted beacon data.
