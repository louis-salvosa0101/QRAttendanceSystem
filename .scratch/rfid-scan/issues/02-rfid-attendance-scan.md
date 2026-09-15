# 02: RFID Attendance Scan

**What to build:** On the existing scanner page, a hidden input always listens for RFID card taps (USB HID reader or NFC HID app) at the same time the QR camera is running — whichever fires first is processed. When a student taps their registered card during an active session, the system records Time In (first scan) or Time Out (second scan) exactly as a QR scan would. Every scan — QR and RFID — now records its Scan Method. Tapping an unregistered card shows a clear on-screen error.

**Blocked by:** 01 — RFID Registration (the `rfid_uid` column and at least one registered student must exist before this can be verified end-to-end)

**Status:** ready-for-agent

## Acceptance criteria

- [ ] Scan records (session_scans / attendance_records) have a new `scan_method` field storing `'qr'` or `'rfid'`
- [ ] The existing `POST /api/scan` endpoint records `scan_method: 'qr'` on every QR Attendance scan
- [ ] `POST /api/scan/rfid` accepts `{ rfid_uid, session_id }`, looks up the Student by RFID UID, and records Time In or Time Out using the same session filter rules as the QR scan endpoint
- [ ] A student who has already scanned via QR (Time In) can scan via RFID (Time Out) in the same session, and vice versa — Scan Method does not affect whether it is Time In or Time Out; only scan count within the session does
- [ ] Tapping an unregistered RFID UID returns an error JSON and displays an on-screen message: "Card not recognized. Please register your RFID card with an officer."
- [ ] The scanner page has a hidden auto-focused input that captures RFID UID keystrokes from the USB HID reader / NFC HID app; it stays focused whenever the user is not interacting with another element
- [ ] QR camera scanning and RFID input listening are active simultaneously on the scanner page — no toggle required
- [ ] All new endpoints return 401 JSON for unauthenticated requests
- [ ] Endpoint tests cover: valid UID first scan → Time In, valid UID second scan → Time Out, unregistered UID → error JSON, session not active → error JSON, student fails session filter → error JSON, unauthenticated → 401
