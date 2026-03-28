# QR Attendance System — Setup Guide

Complete guide to install, configure, and use the QR Attendance System.

---

## 1. Prerequisites

- **Python 3.8 or higher** — [Download from python.org](https://www.python.org/downloads/)
  - During installation, check **"Add Python to PATH"**.

---

## 2. Installation

### 2.1 Get the Files

Copy the project folder (`QRAttendanceSys`) to your computer, or clone it with Git.

### 2.2 Open Terminal

1. Open the project folder in File Explorer.
2. Click the address bar, type `cmd` or `powershell`, and press **Enter**.

### 2.3 Create a Virtual Environment (Recommended)

```bash
python -m venv .venv
```

### 2.4 Activate the Virtual Environment

- **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\activate
  ```
- **Windows (Command Prompt):**
  ```cmd
  .\.venv\Scripts\activate.bat
  ```
- **Linux / macOS:**
  ```bash
  source .venv/bin/activate
  ```

### 2.5 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.6 Configure Environment Variables

The app reads secrets from a `.env` file (never hardcoded, never committed to Git).

1. Copy the example file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and fill in the values. To generate secure keys, run:

   ```bash
   python -c "import secrets, os, base64; print(f'SECRET_KEY={secrets.token_hex(32)}'); print(f'AES_KEY={base64.b64encode(os.urandom(32)).decode()}'); print(f'AES_IV={base64.b64encode(os.urandom(16)).decode()}')"
   ```

3. Paste the output into your `.env` file.

| Variable     | Purpose                                    | Format         |
|--------------|--------------------------------------------|----------------|
| `SECRET_KEY` | Flask session/cookie signing               | Hex string     |
| `AES_KEY`    | AES-256 encryption key for QR codes        | Base64 (32 B)  |
| `AES_IV`     | AES initialization vector                  | Base64 (16 B)  |

> **Warning:** Changing `AES_KEY` or `AES_IV` will make all existing QR codes unreadable. Regenerate all QR codes after changing these values.

---

## 3. Running the Application

With the virtual environment activated:

```bash
python app.py
```

Open your browser and go to: **http://127.0.0.1:5000**

The app also binds to `0.0.0.0`, so other devices on your local network can reach it at `http://YOUR_IP:5000` (e.g. `http://192.168.1.10:5000`).

To stop the server, press **Ctrl + C** in the terminal. To restart, run `python app.py` again.

---

## 4. Mobile Access (ngrok)

Browsers block camera access over plain `http://` from non-localhost origins, so using the QR scanner on a phone requires HTTPS. The app has **built-in ngrok support** that creates a secure tunnel automatically.

### 4.1 One-Time Setup

1. **Sign up** for a free account at [ngrok.com](https://dashboard.ngrok.com/signup).
2. **Copy your authtoken** from the [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).
3. **Set the token** (with your venv activated):

   ```bash
   python -c "from pyngrok import ngrok; ngrok.set_auth_token('YOUR_TOKEN_HERE')"
   ```

### 4.2 Usage

When you run `python app.py`, ngrok starts automatically and prints a public HTTPS URL:

```
************************************************************
  NGROK TUNNEL ACTIVE
  Public URL: https://xxxx-xxx-xxx.ngrok-free.app
  Use this URL on your phone to access the system
************************************************************
```

Open that URL on your phone — the camera and QR scanner will work over HTTPS.

### 4.3 Disabling ngrok

To run without ngrok (local-only mode), set the environment variable before starting:

- **PowerShell:** `$env:USE_NGROK="0"; python app.py`
- **CMD:** `set USE_NGROK=0 && python app.py`
- **Linux / macOS:** `USE_NGROK=0 python app.py`

### 4.4 Alternative: Chrome/Brave Flag (Android Only)

If you prefer not to use ngrok:

1. Open Chrome on your phone and go to `chrome://flags` (or `brave://flags` for Brave).
2. Search for **"Insecure origins treated as secure"**.
3. Add your server URL (e.g. `http://192.168.1.10:5000`).
4. Enable the setting and restart the browser.

---

## 5. First-Time Usage Workflow

### 5.1 Register Students

- Go to **Students**.
- Add students manually or import from an Excel master list.
- Use **Generate QR** to create QR codes for each student.

### 5.2 Create a Session

- Go to **Sessions**.
- Enter subject, teacher, and optional notes.
- **Required Attendees Filter** (optional):
  - **Course** — Limit to a specific course (e.g. BSCS).
  - **Year Level** — Select 1st–4th year (leave all unchecked for all years).
  - **Section** — Limit to a section (e.g. A).
- Click **Create Session**.

### 5.3 Scan Attendance

- Go to **Scanner**.
- Select the active session.
- Click **Start Camera** and scan student QR codes.
- Students not matching the session filter (course/year/section) will be rejected.

### 5.4 Close Session & View Records

- Close the session from **Sessions** when done.
- Absent students (who did not scan) are marked with a fine.
- View and filter records on the **Records** page.
- Use **Generate Summary** and **Download Excel** to export data.

---

## 6. Excel Master List Format

For bulk student import and QR generation, use this column layout:

| Name           | Student Number | Course | Year | Section |
|----------------|----------------|--------|------|---------|
| Juan Dela Cruz | 2024-00001     | BSCS   | 3    | A       |
| Maria Santos   | 2024-00002     | BSIT   | 2    | B       |

You can download a sample template from the **Generate QR** page.

---

## 7. Configuration

Secrets (`SECRET_KEY`, `AES_KEY`, `AES_IV`) are stored in `.env` — see Section 2.6.

Other settings in `config.py`:

| Setting                  | Description                                       | Default              |
|--------------------------|---------------------------------------------------|----------------------|
| `SESSION_DURATION_HOURS` | How long sessions stay active                     | 4                    |
| `DATABASE_PATH`          | SQLite database file path                         | `data/attendance.db` |
| `FINE_LATE`              | Fine for scanning late (PHP)                      | 25                   |
| `FINE_ABSENT`            | Fine for not scanning (PHP)                       | 50                   |
| `FINE_PARTIAL`           | Fine for partial scan, Time In only (PHP)         | 25                   |
| `LATE_THRESHOLD_MINUTES` | Minutes after session start before considered late | 15                  |

---

## 8. Database & Data Storage

The system uses **SQLite**. The database file is created automatically on first run.

| Location                   | Contents                                              |
|----------------------------|-------------------------------------------------------|
| `data/attendance.db`       | SQLite database (students, sessions, attendance)      |
| `data/attendance_log.xlsx` | Generated when you click **Generate Summary**         |
| `static/qrcodes/`         | Generated student QR code images                      |
| `uploads/`                 | Uploaded Excel master lists                           |

**Back up the `data/` folder regularly**, especially `attendance.db`.

### Verifying the Database

```bash
python check_db.py
```

All checks should pass. See `DATABASE_CHECKLIST.md` for a full verification checklist.

---

## 9. Migrating Legacy Data

If you have data from an older version (JSON/Excel files):

1. Place these files in the `data/` folder:
   - `sessions.json`
   - `student_registry.json`
   - `attendance_log.xlsx`
2. Run the migration script:

   ```bash
   python migrate_to_sqlite.py
   ```

3. Answer `y` when prompted to merge with existing data.
4. After migration, you can archive or delete the old JSON/Excel files.

---

## 10. Full System Reset

### Via the Web Interface (Recommended)

1. **QR Codes** — Go to **Generate QR** → **Clear All**.
2. **Sessions** — Go to **Sessions** → **Clear History**.
3. **Students** — Go to **Students** → **Clear Registry**.
4. **Attendance Records** — Go to **Records** → **Reset Records**.

### Manual Reset

With the app stopped, delete:

- `data/attendance.db` — Resets students, sessions, and attendance.
- Contents of `static/qrcodes/` — Removes generated QR codes.
- Contents of `uploads/` — Removes uploaded files.

---

## 11. Troubleshooting

| Issue                      | Solution                                                                |
|----------------------------|-------------------------------------------------------------------------|
| `python` command not found | Install Python and add it to PATH.                                     |
| `pip` install errors       | Check internet connection; try `pip install --upgrade pip`.            |
| Camera doesn't start       | Grant browser permission; on mobile use HTTPS via ngrok (Section 4).  |
| Port 5000 already in use   | Change the port in `app.py` (e.g. `port=5001`).                       |
| Database errors            | Run `python check_db.py`; ensure `data/` folder exists and is writable.|
| Student scan rejected      | Check session filter (course/year/section); student must match.        |
| ngrok fails to start       | Make sure you've set your authtoken (Section 4.1).                     |

---

## Quick Reference

| Action              | Command / Location              |
|---------------------|---------------------------------|
| Start app           | `python app.py`                 |
| Stop app            | `Ctrl + C`                      |
| Migrate legacy data | `python migrate_to_sqlite.py`   |
| Verify database     | `python check_db.py`            |
| Local URL           | http://127.0.0.1:5000           |
| Network URL         | http://YOUR_IP:5000             |
| Mobile URL          | Printed by ngrok on startup     |
| Disable ngrok       | `$env:USE_NGROK="0"` (PowerShell) |
