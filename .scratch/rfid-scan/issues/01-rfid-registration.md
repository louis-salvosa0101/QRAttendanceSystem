# 01: RFID Registration

**What to build:** An officer can open any student's record — from the student list or the student detail page — scan that student's school ID card with a USB HID reader or NFC HID app, and register the card's RFID UID to that student. The student detail page shows an RFID status badge (✅ Registered / ⬜ Not registered). If the student already has a card registered, a confirmation prompt appears before overwriting. The officer can also unlink a card entirely from a student's record.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

## Acceptance criteria

- [ ] The `students` table has a new `rfid_uid TEXT UNIQUE NULL` column; existing rows are unaffected
- [ ] `POST /api/students/register-rfid` accepts `{ student_number, rfid_uid }` and links the RFID UID to that Student
- [ ] When the student already has an RFID UID, the endpoint returns 409 with the existing UID in the response body — unless `{ confirm: true }` is also sent, in which case it overwrites
- [ ] `DELETE /api/students/<student_number>/rfid` unlinks the RFID UID; returns 404 if the student has no UID registered
- [ ] The student list page has a "Register RFID" button per row; clicking opens a modal with a "Scan card now…" prompt that listens for RFID UID input (USB HID keystroke / NFC HID app)
- [ ] The student detail page shows an RFID status badge and Register / Unlink RFID buttons
- [ ] The Unlink action shows a confirmation prompt ("Unlink RFID from [Student Name]?") before calling the delete endpoint
- [ ] All new endpoints return 401 JSON for unauthenticated requests
- [ ] Endpoint tests cover: register new UID (success), register when UID exists without `confirm` (409), register when UID exists with `confirm: true` (overwrite success), unlink success, unlink when student has no UID (404), unauthenticated (401)
