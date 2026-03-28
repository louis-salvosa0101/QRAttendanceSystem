"""
Configuration settings for the QR Attendance System.
"""
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask
SECRET_KEY = secrets.token_hex(32)

# AES Encryption Key (32 bytes for AES-256) - Change this in production!
AES_KEY = b'QRAttendSys2024!SecureKey32Bytes'  # Exactly 32 bytes
AES_IV = b'InitVector16Byte'  # Exactly 16 bytes

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
