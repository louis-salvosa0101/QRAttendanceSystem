#!/usr/bin/env python3
"""
Automated database verification script for the QR Attendance System.
Runs against a temporary database (data/attendance_check.db) so production data is not modified.

Usage: python check_db.py
"""
import os
import sys

# Use a separate test database so we don't modify production
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
config.DATABASE_PATH = os.path.join(config.EXCEL_DIR, "attendance_check.db")

from db import init_db, get_db
from student_registry import (
    register_student,
    get_all_students,
    get_student,
    get_students_by_filter,
    delete_student,
    clear_registry,
    get_registry_stats,
    register_students_bulk,
)
from session_manager import (
    create_session,
    get_session,
    get_active_sessions,
    get_all_sessions,
    validate_session,
    record_student_scan,
    get_student_scan_info,
    close_session,
    clear_all_sessions,
)
from excel_logger import (
    log_attendance,
    log_absent_students,
    get_attendance_records,
    get_session_stats,
    generate_summary_sheet,
    clear_attendance_records,
)

# Remove test DB from previous run so we start fresh
if os.path.exists(config.DATABASE_PATH):
    try:
        os.remove(config.DATABASE_PATH)
    except OSError:
        pass

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  [PASS] {msg}")


def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  [FAIL] {msg}")
    if detail:
        print(f"         {detail}")


def section(name):
    print(f"\n--- {name} ---")


# ---------------------------------------------------------------------------
# 1. Database init
# ---------------------------------------------------------------------------
section("1. Database & init")
try:
    init_db()
    ok("init_db() runs without error")
except Exception as e:
    fail("init_db()", str(e))

with get_db() as conn:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = [r[0] for r in cursor.fetchall()]
expected = ["attendance_records", "session_scans", "sessions", "students"]
if set(expected) <= set(tables):
    ok("All 4 tables exist")
else:
    fail("Tables", f"Got {tables}, expected {expected}")

# ---------------------------------------------------------------------------
# 2. Student registry
# ---------------------------------------------------------------------------
section("2. Student registry")
r1 = register_student({
    "name": "Alice",
    "student_number": "S001",
    "course": "BSCS",
    "year": "1",
    "section": "A",
})
if r1 is True:
    ok("Register new student returns True")
else:
    fail("Register new student", f"Expected True, got {r1}")

r2 = register_student({
    "name": "Alice Updated",
    "student_number": "S001",
    "course": "BSCS",
    "year": "2",
    "section": "A",
})
if r2 is False:
    ok("Register existing student (update) returns False")
else:
    fail("Register update", f"Expected False, got {r2}")

s = get_student("S001")
if s and s.get("name") == "Alice Updated" and s.get("year") == "2":
    ok("get_student returns updated data")
else:
    fail("get_student after update", str(s))

if register_student({"name": "X", "student_number": "", "course": "Y", "year": "1", "section": "Z"}) is False:
    ok("Empty student_number returns False")
else:
    fail("Empty student_number should return False")

register_student({"name": "Bob", "student_number": "S002", "course": "BSIT", "year": "1", "section": "B"})
all_students = get_all_students()
if len(all_students) >= 2 and any(x["student_number"] == "S001" for x in all_students):
    ok("get_all_students returns list of dicts")
else:
    fail("get_all_students", f"len={len(all_students)}")

filtered = get_students_by_filter(course="BSCS")
if len(filtered) >= 1 and all(x.get("course") == "BSCS" for x in filtered):
    ok("get_students_by_filter(course=...)")
else:
    fail("get_students_by_filter", str(filtered))

stats = get_registry_stats()
if isinstance(stats, dict) and "total" in stats and "by_course" in stats:
    ok("get_registry_stats structure")
else:
    fail("get_registry_stats", str(stats))

missing = get_student("NONEXISTENT")
if missing is None or missing == {}:
    ok("get_student(non-existing) returns None or empty")
else:
    fail("get_student(non-existing)", str(missing))

# ---------------------------------------------------------------------------
# 3. Sessions
# ---------------------------------------------------------------------------
section("3. Sessions")
sess = create_session(subject="Math", teacher="Dr. X", required_year=["1", "2"])
if not sess or "session_id" not in sess or "scanned_students" not in sess:
    fail("create_session", str(sess))
else:
    ok("create_session returns full dict with session_id, scanned_students")

sid = sess["session_id"]
if get_session(sid) and get_session(sid)["subject"] == "Math":
    ok("get_session(valid_id)")
else:
    fail("get_session(valid_id)")

if get_session("INVALID_ID_XYZ") is None:
    ok("get_session(invalid_id) returns None")
else:
    fail("get_session(invalid_id)")

valid, msg = validate_session(sid)
if valid and "active" in msg.lower():
    ok("validate_session(active)")
else:
    fail("validate_session(active)", msg)

active_list = get_active_sessions()
if any(s["session_id"] == sid for s in active_list):
    ok("get_active_sessions includes new session")
else:
    fail("get_active_sessions", str(active_list))

# ---------------------------------------------------------------------------
# 4. Session scans (Time In / Time Out)
# ---------------------------------------------------------------------------
section("4. Session scans")
succ, msg, scan_type, fine, reason = record_student_scan(sid, "S001")
if succ and scan_type == "time_in":
    ok("First scan -> Time In")
else:
    fail("First scan", f"succ={succ}, scan_type={scan_type}")

succ2, msg2, scan_type2, _, _ = record_student_scan(sid, "S001")
if succ2 and scan_type2 == "time_out":
    ok("Second scan -> Time Out")
else:
    fail("Second scan", f"succ={succ2}, scan_type={scan_type2}")

succ3, msg3, scan_type3, _, _ = record_student_scan(sid, "S001")
if not succ3 and scan_type3 is None and "already" in msg3.lower():
    ok("Third scan rejected (duplicate)")
else:
    fail("Third scan (duplicate)", f"succ={succ3}, msg={msg3}")

info = get_student_scan_info(sid, "S001")
if info and info.get("status") == "out" and "time_in" in info and "time_out" in info:
    ok("get_student_scan_info")
else:
    fail("get_student_scan_info", str(info))

if record_student_scan("FAKE_SID", "S001")[0] is False:
    ok("Scan for non-existing session returns False")
else:
    fail("Scan invalid session")

# ---------------------------------------------------------------------------
# 5. Attendance records
# ---------------------------------------------------------------------------
section("5. Attendance records")
student_data = {"name": "Alice Updated", "student_number": "S001", "course": "BSCS", "year": "2", "section": "A"}
if log_attendance(student_data, sid, "Time In", 0, ""):
    ok("log_attendance")
else:
    fail("log_attendance")

records = get_attendance_records(session_id=sid)
if records and len(records) >= 1 and records[0].get("datetime") and records[0].get("session_id") == sid:
    ok("get_attendance_records(session_id=...) and record has datetime")
else:
    fail("get_attendance_records", str(records)[:200])

records_all = get_attendance_records()
if len(records_all) >= 1:
    ok("get_attendance_records() no filters")
else:
    fail("get_attendance_records() empty")

stats_sess = get_session_stats(sid)
if "total_present" in stats_sess and "total_fines" in stats_sess and "records" in stats_sess:
    ok("get_session_stats structure")
else:
    fail("get_session_stats", str(stats_sess)[:150])

try:
    out_path = os.path.join(config.EXCEL_DIR, "summary_check.xlsx")
    generate_summary_sheet(out_path)
    if os.path.exists(out_path):
        ok("generate_summary_sheet creates file")
        try:
            os.remove(out_path)
        except OSError:
            pass
    else:
        fail("generate_summary_sheet", "File not created")
except Exception as e:
    fail("generate_summary_sheet", str(e))

# ---------------------------------------------------------------------------
# 6. Close session & absent/partial
# ---------------------------------------------------------------------------
section("6. Close session & absent/partial")
# S002 never scanned → should be marked absent when we log_absent_students
required = get_all_students()
close_ok, close_msg = close_session(sid)
if close_ok:
    ok("close_session")
else:
    fail("close_session", close_msg)

session_after = get_session(sid)
if session_after and session_after.get("is_active") in (0, False):
    ok("Session is_active false after close")
else:
    fail("Session still active after close", str(session_after))

absent_result = log_absent_students(sid, session_after, required)
if isinstance(absent_result, dict) and "absent_logged" in absent_result and "partial_updated" in absent_result:
    ok("log_absent_students returns counts")
else:
    fail("log_absent_students", str(absent_result))

# S002 was required but never scanned → should have one Absent record
records_after = get_attendance_records(session_id=sid)
absent_records = [r for r in records_after if r.get("status") == "Absent"]
if any(r.get("student_number") == "S002" for r in absent_records):
    ok("Absent student has Absent record")
else:
    fail("Absent record for S002", f"Records: {[r.get('student_number') for r in records_after]}")

# ---------------------------------------------------------------------------
# 7. Clear / reset
# ---------------------------------------------------------------------------
section("7. Clear & reset")
n = clear_attendance_records()
if isinstance(n, int) and n >= 0:
    ok("clear_attendance_records returns int")
else:
    fail("clear_attendance_records", str(n))

if len(get_attendance_records()) == 0:
    ok("Attendance records empty after clear")
else:
    fail("Attendance records not empty after clear")

n_sess = clear_all_sessions()
if isinstance(n_sess, int) and n_sess >= 0:
    ok("clear_all_sessions returns int")
else:
    fail("clear_all_sessions", str(n_sess))

if len(get_all_sessions()) == 0:
    ok("Sessions empty after clear_all_sessions")
else:
    fail("Sessions not empty after clear")

# Clean up test DB
try:
    os.remove(config.DATABASE_PATH)
except OSError:
    pass

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print(f"Result: {passed} passed, {failed} failed")
if failed == 0:
    print("Database check: ALL PASSED")
    sys.exit(0)
else:
    print("Database check: SOME FAILED — fix failures and re-run.")
    sys.exit(1)
