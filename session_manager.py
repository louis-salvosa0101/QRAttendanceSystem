"""
Session management for class attendance sessions.
Each session has a unique ID, creation time, and expiration.
Sessions are stored in a JSON file for simplicity (offline-first).
"""
import json
import os
import secrets
import string
from datetime import datetime, timedelta
from config import SESSIONS_FILE, SESSION_DURATION_HOURS


def _load_sessions() -> dict:
    """Load sessions from JSON file."""
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_sessions(sessions: dict):
    """Save sessions to JSON file."""
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2, default=str)


def create_session(subject: str = "", teacher: str = "", notes: str = "", duration_hours: float = None) -> dict:
    """
    Create a new attendance session.
    Returns the session data including the unique session ID.
    """
    if duration_hours is None:
        duration_hours = SESSION_DURATION_HOURS

    # Generate a unique, readable session token
    token_chars = string.ascii_uppercase + string.digits
    session_id = ''.join(secrets.choice(token_chars) for _ in range(8))

    now = datetime.now()
    session = {
        'session_id': session_id,
        'subject': subject,
        'teacher': teacher,
        'notes': notes,
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(hours=float(duration_hours))).isoformat(),
        'is_active': True,
        'scanned_students': {},  # Dict: {student_number: 'in' or 'out'}
        'attendance_count': 0
    }

    sessions = _load_sessions()
    sessions[session_id] = session
    _save_sessions(sessions)

    return session


def get_session(session_id: str) -> dict:
    """Get a session by its ID."""
    sessions = _load_sessions()
    return sessions.get(session_id)


def get_active_sessions() -> list:
    """Get all currently active sessions."""
    sessions = _load_sessions()
    now = datetime.now()
    active = []
    for sid, session in sessions.items():
        expires_at = datetime.fromisoformat(session['expires_at'])
        if session['is_active'] and now < expires_at:
            active.append(session)
        elif session['is_active'] and now >= expires_at:
            # Auto-expire
            session['is_active'] = False
            sessions[sid] = session
    _save_sessions(sessions)
    return active


def get_all_sessions() -> list:
    """Get all sessions (active and expired)."""
    sessions = _load_sessions()
    return list(sessions.values())


def validate_session(session_id: str) -> tuple:
    """
    Validate if a session is still active.
    Returns (is_valid, message).
    """
    session = get_session(session_id)
    if not session:
        return False, "Session not found."

    if not session['is_active']:
        return False, "Session has been closed."

    now = datetime.now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    if now >= expires_at:
        session['is_active'] = False
        sessions = _load_sessions()
        sessions[session_id] = session
        _save_sessions(sessions)
        return False, "Session has expired."

    return True, "Session is active."


def record_student_scan(session_id: str, student_number: str) -> tuple:
    """
    Record a student scan in the session with Time In / Time Out logic.
    - 1st scan = Time In
    - 2nd scan = Time Out
    - 3rd+ scan = Rejected (already completed)
    Returns (success, message, scan_type).
    scan_type is 'time_in', 'time_out', or None on failure.
    """
    sessions = _load_sessions()
    session = sessions.get(session_id)

    if not session:
        return False, "Session not found.", None

    scanned = session['scanned_students']

    # Backward compatibility: convert old list format to dict
    if isinstance(scanned, list):
        scanned = {s: 'in' for s in scanned}
        session['scanned_students'] = scanned

    if student_number not in scanned:
        # First scan → Time In
        scanned[student_number] = 'in'
        session['scanned_students'] = scanned
        session['attendance_count'] = len(scanned)
        sessions[session_id] = session
        _save_sessions(sessions)
        return True, "Time In recorded.", 'time_in'

    elif scanned[student_number] == 'in':
        # Second scan → Time Out
        scanned[student_number] = 'out'
        session['scanned_students'] = scanned
        sessions[session_id] = session
        _save_sessions(sessions)
        return True, "Time Out recorded.", 'time_out'

    else:
        # Already timed out
        return False, "Student already timed in and timed out for this session.", None


def close_session(session_id: str) -> tuple:
    """
    Manually close a session.
    Returns (success, message).
    """
    sessions = _load_sessions()
    session = sessions.get(session_id)

    if not session:
        return False, "Session not found."

    session['is_active'] = False
    sessions[session_id] = session
    _save_sessions(sessions)

    return True, "Session closed successfully."
