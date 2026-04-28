#!/usr/bin/env python3
"""
Integration check for post-close attendance editing (PATCH + session_scans sync).
Requires DATABASE_URL in environment (e.g. from .env).

Usage: python verify_post_close_attendance.py
Exit 0 on success, 1 on failure, 0 with message if skipped (no DATABASE_URL).
"""
import os
import sys
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, '.env'))

if not os.environ.get('DATABASE_URL', '').strip():
    print('SKIP: DATABASE_URL not set — skipping post-close attendance integration check.')
    sys.exit(0)

from db import init_db, get_db, _cur
from student_registry import register_student, delete_student, get_student, get_students_by_filter
from session_manager import (
    create_session,
    get_session,
    close_session,
    sync_scan_row_from_attendance,
    delete_session,
)
from excel_logger import (
    get_attendance_records,
    log_absent_students,
    update_session_attendance_record,
    add_manual_attendance_record,
)


def main():
    init_db()
    suffix = uuid.uuid4().hex[:8]
    tid = f'TEST_PC_{suffix}'
    sn = f'TESTPC_{suffix}'

    register_student({
        'name': 'PostClose Verify',
        'student_number': sn,
        'course': 'TESTPC_CRS',
        'year': '1',
        'section': 'A',
    })

    sess = create_session(
        subject='Post-close verify',
        teacher='',
        notes='',
        duration_hours=0.1,
        required_course='TESTPC_CRS',
        required_year=['1'],
        required_section='A',
    )
    sid = sess['session_id']

    close_session(sid)
    session_row = get_session(sid)
    required = get_students_by_filter(
        course='TESTPC_CRS',
        year=['1'],
        section='A',
    )
    log_absent_students(sid, session_row, required)

    rows = [r for r in get_attendance_records(session_id=sid) if r.get('student_number') == sn]
    if not rows:
        print('FAIL: expected absent attendance row for test student')
        delete_session(sid)
        delete_student(sn)
        return 1
    rid = rows[0]['id']
    if rows[0].get('status') != 'Absent':
        print('FAIL: expected Absent before edit, got', rows[0].get('status'))
        delete_session(sid)
        delete_student(sn)
        return 1

    ti = '2026-04-28 08:00:00'
    to = '2026-04-28 09:00:00'
    ok, msg, record = update_session_attendance_record(
        rid, sid,
        {'status': 'Time Out', 'time_in': ti, 'time_out': to, 'fine': 0, 'fine_reason': 'Manual credit — verify script'},
    )
    if not ok or not record:
        print('FAIL: update_session_attendance_record:', msg)
        delete_session(sid)
        delete_student(sn)
        return 1

    sync_scan_row_from_attendance(
        sid, sn, record['status'], record.get('time_in'), record.get('time_out'),
        int(record.get('fine') or 0), record.get('fine_reason') or '',
    )

    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            """SELECT status, time_in, time_out FROM session_scans
               WHERE session_id = %s AND student_number = %s""",
            (sid, sn),
        )
        scan = cur.fetchone()

    if not scan or scan.get('status') != 'out':
        print('FAIL: session_scans should have status out after Time Out sync, got', scan)
        delete_session(sid)
        delete_student(sn)
        return 1

    st = get_student(sn)
    ok2, msg2, rec2 = add_manual_attendance_record(
        sid, st, 'Absent', None, None, 0, 'duplicate test should fail',
    )
    if ok2:
        print('FAIL: add_manual_attendance_record should reject duplicate student')
        delete_session(sid)
        delete_student(sn)
        return 1

    ok3, msg3, _ = update_session_attendance_record(rid, tid, {'fine': 0})
    if ok3:
        print('FAIL: update for wrong session_id should fail')
        delete_session(sid)
        delete_student(sn)
        return 1

    delete_session(sid)
    delete_student(sn)
    print('OK: post-close attendance update + session_scans sync')
    return 0


if __name__ == '__main__':
    sys.exit(main())
