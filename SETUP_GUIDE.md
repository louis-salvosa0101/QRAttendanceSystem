# QR Attendance System Setup Guide

Follow these steps to set up and run the **Advanced QR-Based Attendance System** on a new computer.

---

## Prerequisites

Before you begin, ensure the following are installed:

1. **Python 3.8 or higher** — [Download from python.org](https://www.python.org/downloads/)
   - **Important**: During installation, check **"Add Python to PATH"**.

---

## Installation Steps

### 1. Get the Files

Copy the project folder (`QRAttendanceSys`) to the new computer, or clone it if using Git.

### 2. Open Terminal

1. Open the project folder.
2. Click the address bar at the top of the folder window, type `cmd` or `powershell`, and press **Enter**.

### 3. Create a Virtual Environment (Recommended)

Keeps dependencies separate from your global Python installation.

```bash
python -m venv .venv
```

### 4. Activate the Virtual Environment

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

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Application

### 1. Start the Server

With the virtual environment activated:

```bash
python app.py
```

### 2. Access the System

Open your browser and go to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

The app runs on `0.0.0.0` by default, so it is also reachable from other devices on your network at `http://YOUR_IP:5000` (e.g. `http://192.168.1.10:5000`).

---

## First-Time Setup Workflow

### 1. Register Students

- Go to **Students**.
- Add students manually or import from an Excel file.
- Use **Generate QR** to create QR codes for each student.

### 2. Create a Session

- Go to **Sessions**.
- Enter subject, teacher, and optional notes.
- **Required Attendees Filter** (optional):
  - **Course** — Limit to a specific course (e.g. BSCS).
  - **Year Level** — Select 1st–4th year (leave all unchecked for all years).
  - **Section** — Limit to a section (e.g. A).
- Click **Create Session**.

### 3. Scan Attendance

- Go to **Scanner**.
- Select the active session.
- Click **Start Camera** and scan student QR codes.
- Students not matching the session filter (course/year/section) will be rejected with a notification.

### 4. Close Session & View Records

- Close the session from **Sessions** when done.
- Absent students (who did not scan) are marked with a fine.
- View and filter records on the **Records** page.
- Use **Generate Summary** and **Download Excel** to export data.

---

## Database & Data Storage

The system uses **SQLite** for storage. The database file is created automatically on first run.

| Location        | Contents                                                                 |
|----------------|--------------------------------------------------------------------------|
| `data/attendance.db` | SQLite database (students, sessions, attendance records)                 |
| `data/attendance_log.xlsx` | Generated when you click **Generate Summary** (Excel export)   |
| `static/qrcodes/`    | Generated student QR code images                                       |
| `uploads/`           | Uploaded Excel master lists                                            |

**Back up the `data/` folder regularly**, especially `attendance.db`.

---

## Migrating Legacy Data

If you have data from an older version (JSON/Excel files):

1. Place these files in the `data/` folder:
   - `sessions.json`
   - `student_registry.json`
   - `attendance_log.xlsx`
2. Run the migration script:

   ```bash
   python migrate_to_sqlite.py
   ```

3. Answer `y` when prompted to merge with existing data (if any).
4. After migration, you can archive or delete the old JSON/Excel files.

---

## Verifying the Database

To check that the database and modules work correctly:

```bash
python check_db.py
```

All checks should pass. See `DATABASE_CHECKLIST.md` for a full verification checklist.

---

## Restarting the System

1. **Stop the server**: In the terminal, press **Ctrl + C**.
2. **Start again**:
   ```bash
   python app.py
   ```

---

## Full System Reset (Factory Reset)

### Via the Web Interface (Recommended)

1. **QR Codes**: Go to **Generate QR** → **Clear All**.
2. **Sessions**: Go to **Sessions** → **Clear History**.
3. **Students**: Go to **Students** → **Clear Registry**.
4. **Attendance Records**: Go to **Records** → **Reset Records**.

### Manually (Hard Reset)

With the app **closed**, delete:

- `data/attendance.db` — Resets students, sessions, and attendance.
- Contents of `static/qrcodes/` — Removes generated QR codes.
- Contents of `uploads/` — Removes uploaded files.

---

## Accessing from Other Devices (Mobile / Tablet)

The app binds to `0.0.0.0` by default, so it is reachable from other devices on your network.

### 1. Find Your Local IP Address

- **Windows**: Open CMD and run `ipconfig`. Look for **IPv4 Address** (e.g. `192.168.1.10`).
- **Linux / macOS**: Run `ip addr` or `ifconfig`.

### 2. Firewall

Ensure your firewall allows incoming connections on port **5000**.

### 3. Access from Phone/Tablet

Open the browser and go to `http://YOUR_IP:5000` (e.g. `http://192.168.1.10:5000`).

### 4. Camera on Mobile (HTTPS Required)

Browsers block camera access on insecure `http://` links from non-localhost origins. Use one of these options:

**Option A: ngrok (Recommended)**

1. Download ngrok from [ngrok.com](https://ngrok.com/).
2. Run `ngrok http 5000` in a new terminal.
3. Use the `https://...` URL shown by ngrok on your phone.

**Option B: Chrome Flag (Android Only)**

1. Open Chrome on your phone.
2. Go to `chrome://flags`.
3. Search for **"Insecure origins treated as secure"**.
4. Add your server URL (e.g. `http://192.168.1.10:5000`).
5. Enable the setting and restart Chrome.

**Option B (Brave):** Use `brave://flags` and the same steps.

---

## Configuration

Edit `config.py` to customize:

| Setting                  | Description                                      | Default              |
|--------------------------|--------------------------------------------------|----------------------|
| `AES_KEY` / `AES_IV`     | Encryption keys (change in production)           | —                    |
| `SESSION_DURATION_HOURS` | How long sessions stay active                    | 4                    |
| `DATABASE_PATH`          | SQLite database file path                        | `data/attendance.db` |
| `FINE_LATE`              | Fine for scanning late (PHP)                     | 25                   |
| `FINE_ABSENT`            | Fine for not scanning (PHP)                      | 50                   |
| `FINE_PARTIAL`           | Fine for partial scan, Time In only (PHP)        | 25                   |
| `LATE_THRESHOLD_MINUTES` | Minutes after session start before considered late | 15                |

---

## Troubleshooting

| Issue                      | Solution                                                                 |
|----------------------------|--------------------------------------------------------------------------|
| `python` command not found | Install Python and add it to PATH.                                      |
| `pip` install errors       | Check internet connection; try `pip install --upgrade pip`.             |
| Camera doesn't start       | Grant browser permission; on mobile use HTTPS (e.g. ngrok).            |
| Port 5000 already in use  | Change the port in `app.py` (e.g. `port=5001`).                          |
| Database errors            | Run `python check_db.py`; ensure `data/` folder exists and is writable.  |
| Student scan rejected      | Check session filter (course/year/section); student must match.         |

---

## Project Structure

```
QRAttendanceSys/
├── app.py              # Main Flask application
├── config.py           # Configuration
├── db.py               # SQLite database module
├── crypto_utils.py      # AES encryption/decryption
├── qr_generator.py     # QR code generation
├── session_manager.py  # Session management
├── student_registry.py # Student registry
├── excel_logger.py     # Attendance logging & Excel export
├── migrate_to_sqlite.py # Legacy data migration
├── check_db.py        # Database verification script
├── requirements.txt   # Python dependencies
├── data/              # attendance.db, exports
├── static/qrcodes/    # Generated QR images
├── uploads/           # Uploaded Excel files
└── templates/         # HTML templates
```

---

## Excel Master List Format

For bulk student import and QR generation:

| Name           | Student Number | Course | Year | Section |
|----------------|----------------|--------|------|---------|
| Juan Dela Cruz | 2024-00001     | BSCS   | 3    | A       |
| Maria Santos   | 2024-00002     | BSIT   | 2    | B       |

---

## Cloud Deployment (Supabase + Render)

### 1. Set Up Supabase Database

1. Go to [supabase.com](https://supabase.com) and create a free account.
2. Create a new project. Note your **database password**.
3. Go to **Project Settings > Database > Connection string** and copy the **URI** format.
4. It will look like: `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`

### 2. Deploy to Render

1. Push your code to a GitHub repository.
2. Go to [render.com](https://render.com) and create a free account.
3. Click **New > Web Service** and connect your GitHub repo.
4. Set the following:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add these **Environment Variables** in Render's dashboard:
   - `SECRET_KEY` — a random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `AES_KEY` — your base64-encoded AES key (from `.env`)
   - `AES_IV` — your base64-encoded AES IV (from `.env`)
   - `DATABASE_URL` — your Supabase connection string from step 1
6. Click **Deploy**. The app will be live at `https://your-app.onrender.com`.

### 3. Default Login

After first deployment, log in with:
- **Username**: `admin`
- **Password**: `admin123`

Change this password immediately after first login.

---

## Quick Reference

| Action              | Location / Command                          |
|---------------------|---------------------------------------------|
| Start app (local)   | `python app.py`                             |
| Start app (prod)    | `gunicorn app:app`                          |
| Default login       | admin / admin123                            |
| Local URL           | http://127.0.0.1:5000                       |
| Network URL         | http://YOUR_IP:5000                         |
