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

# Excel files
ATTENDANCE_LOG_FILE = os.path.join(EXCEL_DIR, 'attendance_log.xlsx')
SESSIONS_FILE = os.path.join(EXCEL_DIR, 'sessions.json')

# Session settings
SESSION_DURATION_HOURS = 4  # How long a session remains valid

# Ensure directories exist
for d in [QR_CODES_DIR, EXCEL_DIR, MASTER_LIST_DIR]:
    os.makedirs(d, exist_ok=True)
