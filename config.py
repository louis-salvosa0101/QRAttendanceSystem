"""
Configuration settings for the QR Attendance System.
"""
import os
import sys
import base64

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


def _require_env(name):
    value = os.environ.get(name)
    if not value or value == 'change-me':
        sys.exit(
            f"[ERROR] {name} is not set. "
            f"Copy .env.example to .env and fill in your values."
        )
    return value


# Flask
SECRET_KEY = _require_env('SECRET_KEY')

# AES Encryption (base64-encoded in .env, decoded to raw bytes here)
AES_KEY = base64.b64decode(_require_env('AES_KEY'))   # Must be 32 bytes
AES_IV = base64.b64decode(_require_env('AES_IV'))     # Must be 16 bytes

if len(AES_KEY) != 32:
    sys.exit(f"[ERROR] AES_KEY must decode to exactly 32 bytes, got {len(AES_KEY)}")
if len(AES_IV) != 16:
    sys.exit(f"[ERROR] AES_IV must decode to exactly 16 bytes, got {len(AES_IV)}")

# Directories
QR_CODES_DIR = os.path.join(BASE_DIR, 'static', 'qrcodes')
EXCEL_DIR = os.path.join(BASE_DIR, 'data')
MASTER_LIST_DIR = os.path.join(BASE_DIR, 'uploads')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# Excel files (legacy / export only)
ATTENDANCE_LOG_FILE = os.path.join(EXCEL_DIR, 'attendance_log.xlsx')
SESSIONS_FILE = os.path.join(EXCEL_DIR, 'sessions.json')
STUDENT_REGISTRY_FILE = os.path.join(EXCEL_DIR, 'student_registry.json')

# SQLite database (primary storage)
DATABASE_PATH = os.path.join(EXCEL_DIR, 'attendance.db')

# Session settings
SESSION_DURATION_HOURS = 4  # How long a session remains valid

# Fine settings (in PHP Pesos)
FINE_LATE = 25        # Fine for scanning 15+ minutes after session start
FINE_ABSENT = 50      # Fine for not scanning at all
FINE_PARTIAL = 25     # Fine for only Time In or only Time Out
LATE_THRESHOLD_MINUTES = 15  # Minutes after session start before considered late

# Ensure directories exist
for d in [QR_CODES_DIR, EXCEL_DIR, MASTER_LIST_DIR]:
    os.makedirs(d, exist_ok=True)
