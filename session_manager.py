"""
Session management for class attendance sessions.
Each session has a unique ID, creation time, and expiration.
Sessions are stored in PostgreSQL (Supabase) for ACID compliance and durability.
"""
import json
import math
import secrets
import string
from datetime import datetime, timedelta

from config import (SESSION_DURATION_HOURS, FINE_LATE, FINE_ABSENT,
                    FINE_PARTIAL, LATE_THRESHOLD_MINUTES, ph_now,
                    TIME_OUT_COOLDOWN_AFTER_TIME_IN_SECONDS,
                    session_fine_value)
from db import get_db, _cur

_SESSION_COLS = """session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section,
               scheduled_start, fine_late, fine_absent, fine_partial,
               late_threshold_minutes"""


def _cooldown_retry_after_seconds(now: datetime, time_in_iso, cooldown_sec: int) -> int | None:
    """If Time Out is blocked by cooldown, return seconds to wait (>=1); else None."""
    if cooldown_sec <= 0:
        return None
    if not time_in_iso:
        return None
    s = str(time_in_iso).strip()
    if not s:
        return None
    try:
        t_in = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if t_in.tzinfo is not None:
            t_in = t_in.replace(tzinfo=None)
    except ValueError:
        return None
    elapsed = (now - t_in).total_seconds()
    if elapsed >= cooldown_sec:
        return None
    return max(1, int(math.ceil(cooldown_sec - elapsed)))


def _cooldown_blocked_message(retry_after: int) -> str:
    return (
        f'Time Out is not available yet. Wait {retry_after} more second(s) after Time In '
        'before scanning again.'
    )


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


def _batch_load_scans(cur, session_ids: list) -> dict:
    """Batch-load scanned students for multiple sessions in a single query.
    Returns {session_id: {student_number: {status, time_in, ...}}}."""
    if not session_ids:
        return {}
    cur.execute(
        """SELECT session_id, student_number, status, time_in, time_out, fine, fine_reason
           FROM session_scans WHERE session_id = ANY(%s)""",
        (session_ids,)
    )
    scans_map = {}
    for r in cur.fetchall():
        sid = r['session_id']
        if sid not in scans_map:
            scans_map[sid] = {}
        scans_map[sid][r['student_number']] = {
            'status': r['status'],
            'time_in': r['time_in'],
            'time_out': r['time_out'],
            'fine': r['fine'] or 0,
            'fine_reason': r['fine_reason'] or '',
        }
    return scans_map


def create_session(subject: str = "", teacher: str = "", notes: str = "",
                   duration_hours: float = None,
                   required_course: str = "",
                   required_year: list = None,
                   required_section: str = "",
                   scheduled_start: str = "",
                   fine_late: int = None,
                   fine_absent: int = None,
                   fine_partial: int = None,
                   late_threshold_minutes: int = None) -> dict:
    """
    Create a new attendance session.
    Returns the session data including the unique session ID.
    """
    if duration_hours is None:
        duration_hours = SESSION_DURATION_HOURS
    if fine_late is None:
        fine_late = FINE_LATE
    if fine_absent is None:
        fine_absent = FINE_ABSENT
    if fine_partial is None:
        fine_partial = FINE_PARTIAL
    if late_threshold_minutes is None:
        late_threshold_minutes = LATE_THRESHOLD_MINUTES

    token_chars = string.ascii_uppercase + string.digits
    session_id = ''.join(secrets.choice(token_chars) for _ in range(8))

    now = ph_now()
    if scheduled_start:
        try:
            start_dt = datetime.fromisoformat(
                scheduled_start.replace('Z', '+00:00'))
            if start_dt.tzinfo is not None:
                from config import PH_TZ
                start_dt = start_dt.astimezone(PH_TZ).replace(tzinfo=None)
        except (ValueError, TypeError):
            start_dt = now
    else:
        start_dt = now
    expires_at = start_dt + timedelta(hours=float(duration_hours))
    required_year_json = json.dumps(required_year or [])

    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            """INSERT INTO sessions (session_id, subject, teacher, notes, created_at, expires_at,
               is_active, required_course, required_year, required_section,
               scheduled_start, fine_late, fine_absent, fine_partial, late_threshold_minutes)
               VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (session_id, subject, teacher, notes, now.isoformat(), expires_at.isoformat(),
             required_course, required_year_json, required_section,
             scheduled_start or None, fine_late, fine_absent, fine_partial,
             late_threshold_minutes)
        )

    session = get_session(session_id)
    return session


def get_session(session_id: str) -> dict | None:
    """Get a session by its ID."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = %s",
            (session_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        scanned = _load_scanned_students(conn, session_id)
        return _session_row_to_dict(row, scanned)


def get_active_sessions() -> list:
    """Get all currently active sessions, auto-expiring any that are past due."""
    now = ph_now()

    with get_db() as conn:
        cur = _cur(conn)

        cur.execute(
            """UPDATE sessions SET is_active = 0
               WHERE is_active = 1 AND expires_at <= %s
               RETURNING session_id""",
            (now.isoformat(),)
        )
        expired_ids = [r['session_id'] for r in cur.fetchall()]

        cur.execute(
            f"""SELECT {_SESSION_COLS}
                FROM sessions WHERE is_active = 1 AND expires_at > %s""",
            (now.isoformat(),)
        )
        rows = cur.fetchall()

        sids = [r['session_id'] for r in rows]
        scans_map = _batch_load_scans(cur, sids)

    if expired_ids:
        _handle_auto_expired(expired_ids)

    return [_session_row_to_dict(r, scans_map.get(r['session_id'], {})) for r in rows]


def _handle_auto_expired(session_ids: list):
    """Process absent/partial logging for sessions that auto-expired.

    Mirrors the logic in api_close_session: mark partial scans with fines
    in session_scans, then log absent/partial students to attendance_records.
    """
    from excel_logger import log_absent_students
    from student_registry import get_students_by_filter

    for sid in session_ids:
        session = get_session(sid)
        if not session:
            continue

        s_fine_partial = session_fine_value(session, 'fine_partial', FINE_PARTIAL)
        scanned = session.get('scanned_students', {})

        with get_db() as conn:
            cur = _cur(conn)
            for student_number, info in scanned.items():
                if info.get('status') == 'in':
                    cur.execute(
                        """UPDATE session_scans SET fine = %s, fine_reason = %s
                           WHERE session_id = %s AND student_number = %s""",
                        (s_fine_partial,
                         'No Time Out recorded (partial scan) - considered late',
                         sid, student_number)
                    )

        session = get_session(sid)
        required_students = get_students_by_filter(
            course=session.get('required_course') or None,
            year=session.get('required_year') or None,
            section=session.get('required_section') or None,
        )
        if required_students:
            log_absent_students(sid, session, required_students)


def get_all_sessions() -> list:
    """Get all sessions (active and expired)."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            f"SELECT {_SESSION_COLS} FROM sessions ORDER BY created_at DESC"
        )
        rows = cur.fetchall()

        sids = [r['session_id'] for r in rows]
        scans_map = _batch_load_scans(cur, sids)

    return [_session_row_to_dict(r, scans_map.get(r['session_id'], {})) for r in rows]


def get_session_count() -> int:
    """Return total number of sessions (lightweight count)."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT COUNT(*) AS cnt FROM sessions")
        return cur.fetchone()['cnt']


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

    now = ph_now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    if now >= expires_at:
        with get_db() as conn:
            cur = _cur(conn)
            cur.execute(
                "UPDATE sessions SET is_active = 0 WHERE session_id = %s",
                (session_id,)
            )
        _handle_auto_expired([session_id])
        return False, "Session has expired."

    return True, "Session is active."


def record_student_scan(session_id: str, student_number: str) -> tuple:
    """
    Record a student scan in the session with Time In / Time Out logic.
    Returns (success, message, scan_type, fine_amount, fine_reason, retry_after_seconds).
    On cooldown rejection, retry_after_seconds is the wait time; otherwise None.
    """
    session = get_session(session_id)
    if not session:
        return False, "Session not found.", None, 0, '', None

    scanned = session.get('scanned_students', {})
    now = ph_now()
    now_iso = now.isoformat()

    if student_number not in scanned:
        # First scan -> Time In
        s_fine_late = session_fine_value(session, 'fine_late', FINE_LATE)
        s_threshold = session_fine_value(session, 'late_threshold_minutes',
                                         LATE_THRESHOLD_MINUTES)
        session_start = datetime.fromisoformat(
            session.get('scheduled_start') or session['created_at']
        )
        minutes_late = (now - session_start).total_seconds() / 60
        fine = s_fine_late if minutes_late > s_threshold else 0
        fine_reason = f'Late by {int(minutes_late)} min (>{s_threshold} min threshold)' if fine else ''

        with get_db() as conn:
            cur = _cur(conn)
            cur.execute(
                """INSERT INTO session_scans (session_id, student_number, status, time_in, time_out, fine, fine_reason)
                   VALUES (%s, %s, 'in', %s, NULL, %s, %s)""",
                (session_id, student_number, now_iso, fine, fine_reason)
            )
        return True, "Time In recorded.", 'time_in', fine, fine_reason, None

    elif scanned[student_number]['status'] == 'in':
        retry = _cooldown_retry_after_seconds(
            now,
            scanned[student_number].get('time_in'),
            TIME_OUT_COOLDOWN_AFTER_TIME_IN_SECONDS,
        )
        if retry is not None:
            return False, _cooldown_blocked_message(retry), None, 0, '', retry
        # Second scan -> Time Out (fine was already applied at Time In, don't charge again)
        with get_db() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE session_scans SET status = 'out', time_out = %s
                   WHERE session_id = %s AND student_number = %s""",
                (now_iso, session_id, student_number)
            )
        return True, "Time Out recorded.", 'time_out', 0, '', None

    else:
        return False, "Student already timed in and timed out for this session.", None, 0, '', None


def process_scan(conn, session_id: str, student_number: str) -> tuple:
    """
    Validate the session and record a student scan in one connection.
    Only queries the single student's row instead of loading all scanned
    students.  Designed to be called inside an outer ``get_db()`` block so
    the caller can share the same connection for registration and logging.

    Returns (success, message, scan_type, fine_amount, fine_reason, attendance_count,
             retry_after_seconds). On cooldown rejection, retry_after_seconds is set; else None.
    """
    cur = _cur(conn)

    # 1. Fetch session row
    cur.execute(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
        return False, "Session not found.", None, 0, '', 0, None

    session = _session_row_to_dict(row)

    if not session.get('is_active'):
        return False, "Session has been closed.", None, 0, '', 0, None

    now = ph_now()
    expires_at = datetime.fromisoformat(session['expires_at'])
    if now >= expires_at:
        cur.execute(
            "UPDATE sessions SET is_active = 0 WHERE session_id = %s",
            (session_id,),
        )
        _handle_auto_expired([session_id])
        return False, "Session has expired.", None, 0, '', 0, None

    # 2. Check course / year / section requirements (returned to caller)
    #    We expose the session dict so the caller can do the filter check
    #    before we touch session_scans.  Store it on the tuple via a helper.
    #    -- actually, let the caller handle that before calling us.

    # 3. Look up only THIS student's existing scan
    cur.execute(
        """SELECT status, fine, fine_reason, time_in
           FROM session_scans WHERE session_id = %s AND student_number = %s""",
        (session_id, student_number),
    )
    existing = cur.fetchone()
    now_iso = now.isoformat()

    if existing is None:
        # First scan -> Time In
        s_fine_late = session_fine_value(session, 'fine_late', FINE_LATE)
        s_threshold = session_fine_value(session, 'late_threshold_minutes',
                                         LATE_THRESHOLD_MINUTES)
        session_start = datetime.fromisoformat(
            session.get('scheduled_start') or session['created_at']
        )
        minutes_late = (now - session_start).total_seconds() / 60
        fine = s_fine_late if minutes_late > s_threshold else 0
        fine_reason = (
            f'Late by {int(minutes_late)} min (>{s_threshold} min threshold)'
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
        retry = _cooldown_retry_after_seconds(
            now,
            existing.get('time_in'),
            TIME_OUT_COOLDOWN_AFTER_TIME_IN_SECONDS,
        )
        if retry is not None:
            return False, _cooldown_blocked_message(retry), None, 0, '', 0, retry
        # Second scan -> Time Out (fine already applied at Time In)
        cur.execute(
            """UPDATE session_scans SET status = 'out', time_out = %s
               WHERE session_id = %s AND student_number = %s""",
            (now_iso, session_id, student_number),
        )
        fine, fine_reason, scan_type = 0, '', 'time_out'

    else:
        return (False, "Student already timed in and timed out for this session.",
                None, 0, '', 0, None)

    # 4. Cheap count instead of loading every row
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM session_scans WHERE session_id = %s",
        (session_id,),
    )
    attendance_count = cur.fetchone()['cnt']

    return True, ("Time In recorded." if scan_type == 'time_in' else "Time Out recorded."),\
        scan_type, fine, fine_reason, attendance_count, None


def get_session_row(conn, session_id: str) -> dict | None:
    """Lightweight session fetch on an existing connection (no scanned-students load)."""
    cur = _cur(conn)
    cur.execute(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = %s",
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

    s_fine_partial = session_fine_value(session, 'fine_partial', FINE_PARTIAL)

    with get_db() as conn:
        cur = _cur(conn)
        scanned = session.get('scanned_students', {})
        for student_number, info in scanned.items():
            if info.get('status') == 'in':
                partial_reason = 'No Time Out recorded (partial scan) - considered late'
                cur.execute(
                    """UPDATE session_scans SET fine = %s, fine_reason = %s
                       WHERE session_id = %s AND student_number = %s""",
                    (s_fine_partial, partial_reason, session_id, student_number)
                )
        cur.execute("UPDATE sessions SET is_active = 0 WHERE session_id = %s", (session_id,))

    return True, "Session closed successfully."


def sync_scan_row_from_attendance(
    session_id: str,
    student_number: str,
    status: str,
    time_in,
    time_out,
    fine: int = 0,
    fine_reason: str = '',
) -> None:
    """
    Align session_scans with attendance_records after manual post-close edits.
    Absent -> delete scan row; Time Out -> upsert status out; Time In / Partial -> upsert status in.
    """
    sn = str(student_number).strip()
    fine_i = int(fine or 0)
    fr = (fine_reason or '') if fine_reason is not None else ''
    ti = None if time_in is None or (isinstance(time_in, str) and not str(time_in).strip()) else str(time_in).strip()
    to = None if time_out is None or (isinstance(time_out, str) and not str(time_out).strip()) else str(time_out).strip()

    with get_db() as conn:
        cur = _cur(conn)
        if status == 'Absent':
            cur.execute(
                "DELETE FROM session_scans WHERE session_id = %s AND student_number = %s",
                (session_id, sn),
            )
            return

        if status == 'Time Out' and ti and to:
            cur.execute(
                """INSERT INTO session_scans (session_id, student_number, status, time_in, time_out, fine, fine_reason)
                   VALUES (%s, %s, 'out', %s, %s, %s, %s)
                   ON CONFLICT (session_id, student_number) DO UPDATE SET
                     status = 'out',
                     time_in = EXCLUDED.time_in,
                     time_out = EXCLUDED.time_out,
                     fine = EXCLUDED.fine,
                     fine_reason = EXCLUDED.fine_reason""",
                (session_id, sn, ti, to, fine_i, fr),
            )
            return

        if not ti:
            ti = ph_now().isoformat()
        cur.execute(
            """INSERT INTO session_scans (session_id, student_number, status, time_in, time_out, fine, fine_reason)
               VALUES (%s, %s, 'in', %s, NULL, %s, %s)
               ON CONFLICT (session_id, student_number) DO UPDATE SET
                 status = 'in',
                 time_in = EXCLUDED.time_in,
                 time_out = NULL,
                 fine = EXCLUDED.fine,
                 fine_reason = EXCLUDED.fine_reason""",
            (session_id, sn, ti, fine_i, fr),
        )


def delete_session(session_id: str) -> bool:
    """Delete a single session, its scans, and attendance records."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("DELETE FROM attendance_records WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM session_scans WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
        return cur.rowcount > 0


def clear_all_sessions() -> int:
    """Clear all sessions from the database. Returns count deleted."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("DELETE FROM session_scans")
        cur.execute("DELETE FROM sessions")
        return cur.rowcount
