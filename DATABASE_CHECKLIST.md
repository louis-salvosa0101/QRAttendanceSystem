# Database Verification Checklist

Use this checklist to verify the SQLite database and related modules have no errors or bugs. Run the automated script first, then confirm critical flows in the app.

---

## Quick run (automated)

```bash
python check_db.py
```

Resolve any failed items, then optionally run the manual checks below.

---

## 1. Database & initialization

| # | Check | How to verify |
|---|--------|----------------|
| 1.1 | Database file path is valid | `config.DATABASE_PATH` points to `data/attendance.db` |
| 1.2 | `init_db()` runs without error | App starts without traceback; `data/attendance.db` exists after first run |
| 1.3 | All tables exist | Run `check_db.py` or: `sqlite3 data/attendance.db ".tables"` → `attendance_records  session_scans  sessions  students` |
| 1.4 | Foreign keys enabled | No orphan rows; deleting a session does not leave invalid `session_scans` (handled by app logic) |

---

## 2. Student registry (`student_registry.py`)

| # | Check | Expected |
|---|--------|----------|
| 2.1 | Register new student | `register_student({...})` returns `True`; student appears in `get_all_students()` |
| 2.2 | Register same student again (update) | Returns `False`; student data is updated (e.g. name/course) |
| 2.3 | Empty or missing `student_number` | Returns `False`; no row inserted |
| 2.4 | `get_student(sn)` for existing student | Returns dict with `name`, `student_number`, `course`, `year`, `section` |
| 2.5 | `get_student(sn)` for non-existing | Returns `None` or `{}` |
| 2.6 | `get_students_by_filter(course=..., year=[...], section=...)` | Returns only students matching all provided filters |
| 2.7 | `delete_student(sn)` | Returns `True`; student no longer in `get_all_students()` |
| 2.8 | `clear_registry()` | Returns count; `get_all_students()` is empty |
| 2.9 | `get_registry_stats()` | Returns `{ total: int, by_course: {...} }` |

---

## 3. Sessions (`session_manager.py`)

| # | Check | Expected |
|---|--------|----------|
| 3.1 | `create_session(...)` | Returns dict with `session_id`, `subject`, `created_at`, `expires_at`, `is_active: True`, `scanned_students: {}`, `attendance_count: 0` |
| 3.2 | `get_session(session_id)` | Returns full session dict including `scanned_students` |
| 3.3 | `get_session(invalid_id)` | Returns `None` |
| 3.4 | `get_active_sessions()` | Only sessions with `is_active` and not expired; expired sessions auto-set to inactive |
| 3.5 | `get_all_sessions()` | All sessions, newest first |
| 3.6 | `required_year` filter | Stored and returned as list (e.g. `['1','2']`), not broken JSON |
| 3.7 | `validate_session(valid_id)` | `(True, "Session is active.")` |
| 3.8 | `validate_session(closed_id)` | `(False, "Session has been closed.")` |
| 3.9 | `validate_session(invalid_id)` | `(False, "Session not found.")` |
| 3.10 | `clear_all_sessions()` | All sessions and session_scans removed; returns count |

---

## 4. Session scans (Time In / Time Out)

| # | Check | Expected |
|---|--------|----------|
| 4.1 | First scan → Time In | `record_student_scan(sid, sn)` returns `(True, "Time In recorded.", 'time_in', fine, reason)`; session `scanned_students[sn].status == 'in'` |
| 4.2 | Second scan → Time Out | Returns `(True, "Time Out recorded.", 'time_out', ...)`; `scanned_students[sn].status == 'out'`, `time_out` set |
| 4.3 | Third scan (duplicate) | Returns `(False, "Student already timed in and timed out...", None, 0, '')` |
| 4.4 | Scan for non-existing session | Returns `(False, "Session not found.", None, 0, '')` |
| 4.5 | Late fine | If scan is > LATE_THRESHOLD_MINUTES after session start, `fine == FINE_LATE` and reason mentions late |
| 4.6 | `get_student_scan_info(sid, sn)` | Returns `{ status, time_in, time_out, fine, fine_reason }` or `{}` if not scanned |

---

## 5. Close session & absent/partial

| # | Check | Expected |
|---|--------|----------|
| 5.1 | `close_session(session_id)` | Returns `(True, "Session closed successfully.")`; session `is_active` false |
| 5.2 | Partial scan (Time In only) | After close, that student's scan has FINE_PARTIAL added and reason includes "No Time Out" |
| 5.3 | `log_absent_students(sid, session_data, required_students)` | Students in `required_students` who never scanned get one Absent record each; count in `absent_logged` |
| 5.4 | Partial update in DB | Student who only had Time In has their attendance record updated to "Partial (No Time Out)" with correct fine |

---

## 6. Attendance records (`excel_logger.py`)

| # | Check | Expected |
|---|--------|----------|
| 6.1 | `log_attendance(student_data, session_id, status, fine, reason)` | Returns `True`; one row in `attendance_records` |
| 6.2 | `get_attendance_records()` no filters | Returns all records, each with `datetime`, `name`, `student_number`, `course`, `year`, `section`, `session_id`, `status`, `fine`, `fine_reason` |
| 6.3 | `get_attendance_records(session_id=...)` | Only records for that session |
| 6.4 | `get_attendance_records(student_number=...)` | Only records for that student |
| 6.5 | `get_attendance_records(date_from=..., date_to=...)` | Only records in that date range (inclusive) |
| 6.6 | `get_session_stats(session_id)` | Returns `total_present`, `time_in_count`, `time_out_count`, `absent_count`, `total_fines`, `by_course`, `records` |
| 6.7 | `generate_summary_sheet(filepath)` | Creates Excel file with Summary sheet; no exception |
| 6.8 | `clear_attendance_records()` | All rows in `attendance_records` deleted; returns count |

---

## 7. App / API behavior

| # | Check | How to verify |
|---|--------|----------------|
| 7.1 | App starts | `python app.py` → no import or init_db error |
| 7.2 | Create session (API) | POST `/api/session/create` → 200, `session_id` in response |
| 7.3 | Scan QR (API) | POST `/api/scan` with valid session + QR payload → Time In then Time Out success |
| 7.4 | Close session (API) | POST `/api/session/<id>/close` → absent/partial counts in response |
| 7.5 | Records page | `/records` loads; filters work; no 500 |
| 7.6 | Download records | `/api/records/download` returns Excel (or empty workbook if no records) |
| 7.7 | Reset records (API) | DELETE `/api/records/reset` → success; `get_attendance_records()` empty |
| 7.8 | Clear session history (API) | DELETE `/api/session/clear-history` → success; `get_all_sessions()` empty |

---

## 8. Edge cases & data integrity

| # | Check | Expected |
|---|--------|----------|
| 8.1 | Session with `required_year` list | Session created and returned with list; filter in close uses it correctly |
| 8.2 | Empty required_students on close | `log_absent_students` returns `absent_logged: 0`, no error |
| 8.3 | Update partial fine reason | Existing Time In row updated to Partial; no duplicate row |
| 8.4 | Record keys for UI | Every record has `datetime` (from `recorded_at`) for templates |
| 8.5 | SQL injection / quoting | Use only parameterized queries (no string formatting for SQL) |

---

## 9. Migration

| # | Check | Expected |
|---|--------|----------|
| 9.1 | `migrate_to_sqlite.py` with no legacy files | Completes; "Imported 0" where no files |
| 9.2 | Migration with existing `student_registry.json` | Students imported; no duplicate key error (INSERT OR REPLACE) |
| 9.3 | Migration with existing `sessions.json` | Sessions and session_scans imported |
| 9.4 | Migration with existing `attendance_log.xlsx` | Rows from non-Summary sheets in `attendance_records` |

---

## Sign-off

- [ ] `python check_db.py` — all checks passed  
- [ ] Manual: create session → scan (Time In/Out) → close → view records  
- [ ] Manual: filters and download work on Records page  
- [ ] No errors in console when using Scanner and Sessions  

*Last updated: SQLite implementation*
