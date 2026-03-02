# QR Attendance System Setup Guide

Follow these steps to set up and run the **Advanced QR-Based Attendance System** on a new computer.

## Prerequisites

Before you begin, ensure the following are installed:

1. **Python 3.8 or higher**: [Download from python.org](https://www.python.org/downloads/)
   - **Important**: During installation, check the box that says **"Add Python to PATH"**.

---

## Installation Steps

### 1. Get the Files

Copy the project folder (`QRAttendanceSys`) to the new computer, or clone it if using Git.

### 2. Open Terminal

1. Open the project folder.
2. Click on the address bar at the top of the folder window, type `cmd` or `powershell`, and press **Enter**.

### 3. Create a Virtual Environment (Recommended)

This keeps the system dependencies separate from your global Python installation.

```bash
python -m venv venv
```

### 4. Activate the Virtual Environment

- **Windows (PowerShell):**
  ```bash
  .\venv\Scripts\activate
  ```
- **Windows (Command Prompt):**
  ```bash
  .\venv\Scripts\activate.bat
  ```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Application

### 1. Start the Server

With the virtual environment activated, run:

```bash
python app.py
```

### 2. Access the System

Open your web browser and go to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Restarting the System

If you need to restart the application:

1.  **Stop the Server**: In the terminal where the app is running, press **Ctrl + C**.
2.  **Start Again**: Run the command:
    ```bash
    python app.py
    ```

---

## Full System Reset (Factory Reset)

If you want to clear all data and start completely fresh:

### via the Web Interface (Recommended)

1.  **Generated QR Codes**: Go to `Generate QR` and click **Clear All**.
2.  **Session History**: Go to `Sessions` and click **Clear History**.
3.  **Attendance Records**: Go to `Records` and click **Reset Records**.

### Manually (Hard Reset)

Delete the following files/folders while the app is closed:

- Clear the `static/qrcodes/` folder.
- Delete `data/attendance_log.xlsx`.
- Delete `data/sessions.json`.

---

## Accessing from Other Devices (Optional)

If you want to use a phone as a scanner while the server runs on your PC:

1. **Find your Local IP Address**:
   - Open CMD and type `ipconfig`.
   - Look for **IPv4 Address** (e.g., `192.168.1.10`).
2. **Update `app.py`**:
   Change `app.run(debug=True, host='127.0.0.1', port=5000)` to:
   `app.run(debug=True, host='0.0.0.0', port=5000)`
3. **Firewall**: Ensure your Windows Firewall allows incoming connections on port `5000`.
4. **Access**: On your phone browser, go to `http://192.168.1.10:5000`.

---

## Troubleshooting

| Issue                      | Solution                                                                                                                                                                     |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `python` command not found | Ensure Python is installed and added to PATH.                                                                                                                                |
| `pip` install errors       | Ensure you have an active internet connection for the first-time setup.                                                                                                      |
| Camera doesn't start       | Ensure the browser has permission. **On mobile**, you MUST use HTTPS (using a tool like ngrok) or `localhost`. Browsers block cameras on insecure `http://IP-ADDRESS` links. |
| Port 5000 already in use   | Change the port in `app.py` (e.g., `port=5001`).                                                                                                                             |

### Fixing Mobile Camera Issues (HTTPS)

Since browsers block camera access on insecure IP links, use **ngrok** to get a free secure URL:

1. Download ngrok from [ngrok.com](https://ngrok.com/).
2. Run `ngrok http 5000` in a new terminal.
3. Access the system via the `https://...` link provided on your phone.

---

## Important Data Folders

- **`data/`**: Contains the `attendance_log.xlsx` and session data.
- **`static/qrcodes/`**: Where generated student QR codes are stored.
- **`uploads/`**: Where your uploaded Excel student lists are saved.

**Always back up the `data/` folder to prevent losing attendance records.**

Solution 2: Browser "Flag" Workaround (Android Only)
If you are using Chrome on Android, you can force it to treat your PC's IP as secure:

1. Open Chrome on your phone.
2. Type chrome://flags in the address bar.
3. Search for: "Insecure origins treated as secure".
4. Type your PC's IP and port (e.g., http://192.168.1.10:5000).
5. Change the setting to Enabled and restart Chrome.


## Mobile Setup
1. brave://flags/
2. Search "Insecure origins treated as secure"
3. Add ip address of the server "http://192.168.1.10:5000"