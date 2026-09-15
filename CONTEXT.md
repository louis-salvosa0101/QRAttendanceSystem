# QR Attendance System

A web-based QR code attendance tracking and financial fine management system for school sessions and student registries.

## Language

**Student**:
A registered individual identified by a unique student number whose attendance and fine balances are tracked.
_Avoid_: User, member, attendee

**Session**:
A scheduled or open event timeframe against which student attendance is recorded and evaluated.
_Avoid_: Class, meeting, event

**Attendance Record**:
A log capturing a student's status (Time In, Time Out, Absent, Late) and any automated fine incurred during a session.
_Avoid_: Log entry, check-in record

**Fine**:
A monetary penalty recorded against a student, generated automatically from session rules or assessed manually.
_Avoid_: Fee, charge, penalty

**Manual Fine**:
An ad-hoc fine issued directly to a student by an officer for non-session-specific reasons.
_Avoid_: Custom fine, extra penalty

**Fine Payment**:
A recorded monetary credit applied to reduce a student's total outstanding fine balance.
_Avoid_: Transaction, receipt, settlement

**RFID UID**:
The raw hardware identifier read from the RFID/NFC chip embedded in a student's school ID card, stored as a unique text string and used to identify the student at scan time.
_Avoid_: Card number, card ID, NFC ID, RFID code

**RFID Registration**:
The officer-performed act of linking an RFID UID to an existing Student record, binding a physical card to a known student identity.
_Avoid_: Card enrollment, card binding, NFC setup

**Scan Method**:
The input channel used to record an Attendance Record — either `qr` (camera-read encrypted QR code) or `rfid` (card tap via USB HID reader or NFC HID app).
_Avoid_: Scan type, input type, scan mode
