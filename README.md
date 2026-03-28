# Advanced QR-Based Attendance System

A modern, secure, and fully offline QR code attendance tracking system built with Flask and Python.

> **First time?** See the [Setup Guide](SETUP_GUIDE.md) for complete installation and usage instructions.

## Features

- **AES-256 Encrypted QR Codes** — Student data is encrypted to prevent tampering
- **Browser-Based QR Scanning** — Uses your webcam directly in the browser
- **SQLite Database** — ACID-compliant local storage for students, sessions, and attendance
- **Session Management** — Time-limited sessions with auto-expiry and course/year/section filtering
- **Duplicate Detection** — Prevents double-scanning within the same session
- **Batch QR Generation** — Generate QR codes for all students from an Excel master list
- **Summary Reports** — Auto-generated attendance summaries with Excel export
- **Fine Tracking** — Automatic fines for late, absent, and partial attendance
- **Mobile Access** — Built-in ngrok tunnel for HTTPS access on phones/tablets
- **Fully Offline** — No external database or internet required (after initial setup)

## Security

| Feature                | Description                                         |
| ---------------------- | --------------------------------------------------- |
| AES-256-CBC Encryption | QR data is encrypted and cannot be manually created |
| SHA-256 Hash           | Data integrity verification                         |
| Session Tokens         | Each session has a unique ID                        |
| Duplicate Detection    | One scan per student per session                    |
| Session Expiry         | Sessions auto-close after configured duration       |

## Tech Stack

- **Backend:** Python 3, Flask
- **QR Generation:** qrcode, Pillow
- **QR Scanning:** html5-qrcode (browser-based)
- **Encryption:** PyCryptodome (AES-256-CBC)
- **Data Storage:** SQLite (primary), openpyxl (Excel export)
- **Mobile Tunneling:** pyngrok (ngrok)
- **UI:** Custom CSS with glassmorphism design
- **Icons:** Lucide Icons

## Project Structure

```
QRAttendanceSys/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── crypto_utils.py        # AES encryption/decryption
├── qr_generator.py        # QR code generation
├── session_manager.py     # Session management
├── student_registry.py    # Student registry
├── db.py                  # SQLite database module
├── excel_logger.py        # Attendance logging & Excel export
├── migrate_to_sqlite.py   # Legacy data migration
├── check_db.py            # Database verification script
├── requirements.txt       # Python dependencies
├── SETUP_GUIDE.md         # Full setup & usage guide
├── DATABASE_CHECKLIST.md  # Database verification checklist
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── scanner.html
│   ├── sessions.html
│   ├── generate.html
│   ├── students.html
│   ├── records.html
│   └── 404.html
├── static/qrcodes/        # Generated QR code images
├── data/                  # SQLite DB, Excel exports
└── uploads/               # Uploaded master lists
```

## License

