# RFID UID stored as a separate nullable column on students

The school's RFID cards expose only a raw hardware UID (not the student number) when read by a USB HID or NFC HID reader. We store this UID as a separate `rfid_uid TEXT UNIQUE NULL` column on the `students` table and require an explicit RFID Registration step — performed by an officer — to bind a card to a student. A student without an RFID Registration has `rfid_uid = NULL` and can only use QR scanning.

We considered encoding the student number into the card's chip memory (which would let us skip the registration step), but this requires a card-writing device and school-level re-issuance of all cards — not feasible since the cards are already issued.

## Consequences

- A migration is required to add `rfid_uid` to the `students` table.
- The attendance scan endpoint must support two lookup paths: by decrypted QR payload (existing) and by raw RFID UID (new).
- Students who have never had RFID Registration simply have `NULL` and are unaffected by the feature.
