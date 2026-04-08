"""
Session management for class attendance sessions.
Each session has a unique ID, creation time, and expiration.
Sessions are stored in PostgreSQL (Supabase) for ACID compliance and durability.
"""
import json
import secrets
import string
from datetime import datetime, timedelta

from config import (SESSION_DURATION_HOURS, FINE_LATE, FINE_ABSENT,
                    FINE_PARTIAL, LATE_THRESHOLD_MINUTES)
from db import get_db, _cur


def _session_row_to_dict(row, scanned_students: dict = None) -> dict:
    """Convert session row to full session dict with scanned_students."""
    if not row:
        return None
    d = dict(row)
    required_year = d.get('required_year')
    if isinstance(required_year, str) and required_year:
        try:
            d['required_year'] = json.loads(required_year)
        except json.JSONDecodeError:
            d['required_year'] = []
    else:
        d['required_year'] = required_year or []

    d['scanned_students'] = scanned_students if scanned_students is not None else {}
    d['attendance_count'] = len(d['scanned_students'])
    return d


def _load_scanned_students(conn, session_id: str) -> dict:
    """Load scanned students for a session as {student_number: {status, time_in, time_out, fine, fine_reason}}."""
    cur = _cur(conn)
    cur.execute(
        """SELECT student_number, status, time_in, time_out, fine, fine_reason
           FROM session_scans WHERE session_id = %s""",
        (session_id,)
    )
    rows = cur.fetchall()
    result = {}
    for r in rows:
        result[r['student_number']] = {
            'status': r['status'],
            'time_in': r['time_in'],
            'time_out': r['time_out'],
            'fine': r['fine'] or 0,
            'fine_reason': r['fine_reason'] or '',
        }
    return result


def create_session(subject: str = "", teacher: str = "", notes: str = "",
                   duration_hours: float = None,
                   required_course: str = "",
                   required_year: list = None,
                   required_section: str = "") -> dict:
    """
    Create a new attendance session.
    Returns the session data including the unique session ID.
    """
    if duration_hours is None:
        duration_hours = SESSION_DURATION_HOURS

    token_chars = string.ascii_uppercase + string.digits
    session_id = ''.join(secrets.choice(token_chars) for _ in range(8))

    now = datetime.now()
    expires_at = now + timedelta(hours=float(duration_hours))
    required_year_json = json.dumps(required_year or [])

    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            """INSERT INTO sessions (session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section)
               VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s)""",
            (session_id, subject, teacher, notes, now.isoformat(), expires_at.isoformat(),
             required_course, required_year_json, required_section)
        )

    session = get_session(session_id)
    return session


def get_session(session_id: str) -> dict | None:
    """Get a session by its ID."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            """SELECT session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section
               FROM sessions WHERE session_id = %s""",
            (session_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        scanned = _load_scanned_students(conn, session_id)
        return _session_row_to_dict(row, scanned)


def get_active_sessions() -> list:
    """Get all currently active sessions."""
    now = datetime.now()
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            """UPDATE sessions SET is_active = 0
               WHERE is_active = 1 AND expires_at <= %s""",
            (now.isoformat(),)
        )

        cur.execute(
            """SELECT session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section
               FROM sessions WHERE is_active = 1 AND expires_at > %s""",
            (now.isoformat(),)
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        session = get_session(row['session_id'])
        if session:
            result.append(session)
    return result


def get_all_sessions() -> list:
    """Get all sessions (active and expired)."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            """SELECT session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section
               FROM sessions ORDER BY created_at DESC"""
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        session = get_session(row['session_id'])
        if session:
            result.append(session)
    return result


def validate_session(session_id: str) -> tuple:
    """
    Validate if a session is still active.
    Returns (is_valid, message).
    """
    session = get_session(session_id)
    if not session:
        return False, "Session not found."

    if not session.get('is_active'):
        return False, "Session has been closed."

    now = datetime.now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    if now >= expires_at:
        with get_db() as conn:
            cur = _cur(conn)
            cur.execute(
                "UPDATE sessions SET is_active = 0 WHERE session_id = %s",
                (session_id,)
            )
        return False, "Session has expired."

    return True, "Session is active."


def record_student_scan(session_id: str, student_number: str) -> tuple:
    """
    Record a student scan in the session with Time In / Time Out logic.
    Returns (success, message, scan_type, fine_amount, fine_reason).
    """
    session = get_session(session_id)
    if not session:
        return False, "Session not found.", None, 0, ''

    scanned = session.get('scanned_students', {})
    now = datetime.now()
    now_iso = now.isoformat()

    if student_number not in scanned:
        # First scan -> Time In
        session_start = datetime.fromisoformat(session['created_at'])
        minutes_late = (now - session_start).total_seconds() / 60
        fine = FINE_LATE if minutes_late > LATE_THRESHOLD_MINUTES else 0
        fine_reason = f'Late by {int(minutes_late)} min (>{LATE_THRESHOLD_MINUTES} min threshold)' if fine else ''

        with get_db() as conn:
            cur = _cur(conn)
            cur.execute(
                """INSERT INTO session_scans (session_id, student_number, status, time_in, time_out, fine, fine_reason)
                   VALUES (%s, %s, 'in', %s, NULL, %s, %s)""",
                (session_id, student_number, now_iso, fine, fine_reason)
            )
        return True, "Time In recorded.", 'time_in', fine, fine_reason

    elif scanned[student_number]['status'] == 'in':
        # Second scan -> Time Out (fine was already applied at Time In, don't charge again)
        with get_db() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE session_scans SET status = 'out', time_out = %s
                   WHERE session_id = %s AND student_number = %s""",
                (now_iso, session_id, student_number)
            )
        return True, "Time Out recorded.", 'time_out', 0, ''

    else:
        return False, "Student already timed in and timed out for this session.", None, 0, ''


def process_scan(conn, session_id: str, student_number: str) -> tuple:
    """
    Validate the session and record a student scan in one connection.
    Only queries the single student's row instead of loading all scanned
    students.  Designed to be called inside an outer ``get_db()`` block so
    the caller can share the same connection for registration and logging.

    Returns (success, message, scan_type, fine_amount, fine_reason, attendance_count).
    """
    cur = _cur(conn)

    # 1. Fetch session row
    cur.execute(
        """SELECT session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section
           FROM sessions WHERE session_id = %s""",
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
        return False, "Session not found.", None, 0, '', 0

    session = _session_row_to_dict(row)

    if not session.get('is_active'):
        return False, "Session has been closed.", None, 0, '', 0

    now = datetime.now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    if now >= expires_at:
        cur.execute(
            "UPDATE sessions SET is_active = 0 WHERE session_id = %s",
            (session_id,),
        )
        return False, "Session has expired.", None, 0, '', 0

    # 2. Check course / year / section requirements (returned to caller)
    #    We expose the session dict so the caller can do the filter check
    #    before we touch session_scans.  Store it on the tuple via a helper.
    #    -- actually, let the caller handle that before calling us.

    # 3. Look up only THIS student's existing scan
    cur.execute(
        """SELECT status, fine, fine_reason
           FROM session_scans WHERE session_id = %s AND student_number = %s""",
        (session_id, student_number),
    )
    existing = cur.fetchone()
    now_iso = now.isoformat()

    if existing is None:
        # First scan -> Time In
        session_start = datetime.fromisoformat(session['created_at'])
        minutes_late = (now - session_start).total_seconds() / 60
        fine = FINE_LATE if minutes_late > LATE_THRESHOLD_MINUTES else 0
        fine_reason = (
            f'Late by {int(minutes_late)} min (>{LATE_THRESHOLD_MINUTES} min threshold)'
            if fine else ''
        )
        cur.execute(
            """INSERT INTO session_scans
               (session_id, student_number, status, time_in, time_out, fine, fine_reason)
               VALUES (%s, %s, 'in', %s, NULL, %s, %s)""",
            (session_id, student_number, now_iso, fine, fine_reason),
        )
        scan_type = 'time_in'

    elif existing['status'] == 'in':
        # Second scan -> Time Out (fine already applied at Time In)
        cur.execute(
            """UPDATE session_scans SET status = 'out', time_out = %s
               WHERE session_id = %s AND student_number = %s""",
            (now_iso, session_id, student_number),
        )
        fine, fine_reason, scan_type = 0, '', 'time_out'

    else:
        return (False, "Student already timed in and timed out for this session.",
                None, 0, '', 0)

    # 4. Cheap count instead of loading every row
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM session_scans WHERE session_id = %s",
        (session_id,),
    )
    attendance_count = cur.fetchone()['cnt']

    return True, ("Time In recorded." if scan_type == 'time_in' else "Time Out recorded."),\
        scan_type, fine, fine_reason, attendance_count


def get_session_row(conn, session_id: str) -> dict | None:
    """Lightweight session fetch on an existing connection (no scanned-students load)."""
    cur = _cur(conn)
    cur.execute(
        """SELECT session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section
           FROM sessions WHERE session_id = %s""",
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return _session_row_to_dict(row)


def get_student_scan_info(session_id: str, student_number: str) -> dict:
    """Get the scan info for a student in a session."""
    session = get_session(session_id)
    if not session:
        return {}
    return session.get('scanned_students', {}).get(student_number, {})


def close_session(session_id: str) -> tuple:
    """
    Manually close a session.
    Also marks students who only Time In (no Time Out) with FINE_PARTIAL.
    """
    session = get_session(session_id)
    if not session:
        return False, "Session not found."

    with get_db() as conn:
        cur = _cur(conn)
        scanned = session.get('scanned_students', {})
        for student_number, info in scanned.items():
            if info.get('status') == 'in':
                current_fine = FINE_PARTIAL
                partial_reason = 'No Time Out recorded (partial scan) - considered late'
                cur.execute(
                    """UPDATE session_scans SET fine = %s, fine_reason = %s
                       WHERE session_id = %s AND student_number = %s""",
                    (current_fine, partial_reason, session_id, student_number)
                )
        cur.execute("UPDATE sessions SET is_active = 0 WHERE session_id = %s", (session_id,))

    return True, "Session closed successfully."


def clear_all_sessions() -> int:
    """Clear all sessions from the database. Returns count deleted."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("DELETE FROM session_scans")
        cur.execute("DELETE FROM sessions")
        return cur.rowcount
