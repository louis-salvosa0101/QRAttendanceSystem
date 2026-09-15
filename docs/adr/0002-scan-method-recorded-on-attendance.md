# scan_method recorded on every attendance scan

Every Attendance Record stores which input channel was used — `qr` or `rfid` — as a `scan_method` field. This field cannot be backfilled after the fact (the information is lost once the scan is processed), so it must be captured at write time even if no reports currently consume it.

We considered omitting it on the grounds that the result (Time In / Time Out) is what matters, not the method. We chose to record it anyway because RFID is a new channel whose adoption is unknown, and the cost of adding a nullable text column is negligible compared to the cost of instrumenting historical data later.

## Considered Options

- **Omit scan_method** — simpler schema, no audit trail for channel usage.
- **Record scan_method** ✅ — small schema cost, preserves the option to report RFID adoption over time.
