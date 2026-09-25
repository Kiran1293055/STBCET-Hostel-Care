# STBCET HostelCare — Updated Flask + MySQL

## New feature
Maintenance staff must upload a work-completion photo when changing a complaint to **Work Completed**.

Workflow:
Student submits -> Admin assigns -> Staff updates -> Staff uploads completion photo -> Admin verifies -> Closed -> Student sees photo.

## Requirements
- Python 3.10+
- MySQL Server 8.x
- VS Code (recommended)

## 1. Create database
Open MySQL Workbench and run `database.sql`.

## 2. Install packages
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configure database
Set environment variables, or edit the defaults in `app.py`.

Windows CMD example:
```cmd
set DB_HOST=localhost
set DB_PORT=3306
set DB_USER=root
set DB_PASSWORD=YOUR_MYSQL_PASSWORD
set DB_NAME=stbcet_hostel
set SECRET_KEY=stbcet-secret-key
```

PowerShell:
```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="YOUR_MYSQL_PASSWORD"
$env:DB_NAME="stbcet_hostel"
$env:SECRET_KEY="stbcet-secret-key"
```

## 4. Run
```bash
python app.py
```

Open:
`http://127.0.0.1:5000`

## Default admin
Email: `admin@stbcet.edu.in`
Password: `Admin@STBCET2026`

Change this password for any real deployment.

## Important
Do not use MySQL Router ports 6446/6447 for this application. A normal local MySQL Server connection is normally `localhost:3306`, unless your MySQL Server was configured differently.

## Image uploads
- Student issue photos: `static/uploads/complaints`
- Maintenance completion photos: `static/uploads/maintenance`
- Maximum image size: 5 MB
- Allowed: JPG, JPEG, PNG, WEBP

## Admin graphical reports

The Admin Dashboard now includes live graphical reports based on the MySQL data:
- Student registrations by month
- Complaint status distribution
- Complaints by category
- Monthly complaint trend

The charts update automatically when the admin dashboard is refreshed. The dashboard still includes student approval, staff management, complaint assignment, maintenance proof-photo verification, and complaint closure.


## Existing database compatibility
If you previously created the `users` table with an older version of the project, the application automatically migrates the old `name` column to the current `full_name` field and preserves the existing data. No need to delete the database.
