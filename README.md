# Advanced QR-Based Attendance System

A modern, secure, and fully offline QR code attendance tracking system built with Flask and Python.

## Features

- **AES-256 Encrypted QR Codes** — Student data is encrypted to prevent tampering
- **Browser-Based QR Scanning** — Uses your webcam directly in the browser
- **SQLite Database** — ACID-compliant local storage for students, sessions, and attendance
- **Session Management** — Time-limited sessions with auto-expiry
- **Duplicate Detection** — Prevents double-scanning within the same session
- **Batch QR Generation** — Generate QR codes for all students from an Excel master list
- **Summary Reports** — Auto-generated attendance summaries per student
- **Fully Offline** — No external database or internet required (after initial setup)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```

### 3. Open in Browser

Navigate to: **http://127.0.0.1:5000**

## Usage Guide

### Step 1: Generate QR Codes

1. Go to **Generate QR** page
2. Either create QR codes individually or upload an Excel file with student data
3. **Excel Format:** Columns should be: `Name | Student Number | Course | Year | Section`
4. You can download a sample template from the page

### Step 2: Create a Session

1. Go to **Sessions** page
2. Fill in the subject, teacher name, and optional notes
3. Click **Create Session** — a unique session ID will be generated
4. Sessions automatically expire after 4 hours (configurable)

### Step 3: Scan Attendance

1. Go to **Scanner** page
2. Select the active session from the dropdown
3. Click **Start Camera** to begin scanning
4. Point the camera at a student's QR code
5. The system will:
   - Decrypt and validate the QR data
   - Check for duplicate scans
   - Log the attendance to Excel
   - Show confirmation with student info

### Step 4: View & Export Records

1. Go to **Records** page
2. Filter by session, student number, or date range
3. Click **Generate Summary** for per-student attendance totals
4. Click **Download Excel** to get the full attendance file

## Security Features

| Feature                | Description                                         |
| ---------------------- | --------------------------------------------------- |
| AES-256-CBC Encryption | QR data is encrypted and cannot be manually created |
| SHA-256 Hash           | Data integrity verification                         |
| Session Tokens         | Each session has a unique ID                        |
| Duplicate Detection    | One scan per student per session                    |
| Session Expiry         | Sessions auto-close after configured duration       |

## Project Structure

```
QRAttendanceSys/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── crypto_utils.py        # AES encryption/decryption
├── qr_generator.py        # QR code generation
├── session_manager.py     # Session management
├── db.py                  # SQLite database module
├── excel_logger.py        # Attendance logging (SQLite) & Excel export
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
│   ├── base.html          # Base layout
│   ├── index.html         # Dashboard
│   ├── scanner.html       # QR Scanner
│   ├── sessions.html      # Session management
│   ├── generate.html      # QR generation
│   ├── records.html       # Attendance records
│   └── 404.html           # Error page
├── static/qrcodes/        # Generated QR code images
├── data/                  # SQLite DB (attendance.db), Excel exports
└── uploads/               # Uploaded master lists
```

## Configuration

Edit `config.py` to customize:

- `AES_KEY` / `AES_IV` — Encryption keys (change for production!)
- `SESSION_DURATION_HOURS` — How long sessions remain active (default: 4 hours)
- `DATABASE_PATH` — SQLite database file (default: `data/attendance.db`)
- File paths for data storage

### Migrating from JSON/Excel (Legacy)

If you have existing data in `sessions.json`, `student_registry.json`, or `attendance_log.xlsx`, run:

```bash
python migrate_to_sqlite.py
```

This imports all legacy data into SQLite. Back up your data folder before running.

## Excel Master List Format

| Name           | Student Number | Course | Year | Section |
| -------------- | -------------- | ------ | ---- | ------- |
| Juan Dela Cruz | 2024-00001     | BSCS   | 3    | A       |
| Maria Santos   | 2024-00002     | BSIT   | 2    | B       |

## Tech Stack

- **Backend:** Python 3, Flask
- **QR Generation:** qrcode, Pillow
- **QR Scanning:** html5-qrcode (browser-based)
- **Encryption:** PyCryptodome (AES-256-CBC)
- **Data Storage:** SQLite (primary), openpyxl (Excel export)
- **UI:** Custom CSS with glassmorphism design
- **Icons:** Lucide Icons

## License

