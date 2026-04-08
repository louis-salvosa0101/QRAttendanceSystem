# Deployment Guide: Supabase + Render

Complete step-by-step instructions to deploy the QR Attendance System to the web using Supabase (database) and Render (hosting).

---

## Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up (or log in).
2. Click **"New Project"**.
3. Choose your organization, give your project a name (e.g. `qr-attendance`).
4. **Set a strong database password** — save this somewhere safe, you'll need it.
5. Choose a region close to you (e.g. `Southeast Asia (Singapore)` if you're in the Philippines).
6. Click **"Create new project"** and wait for it to finish provisioning (~2 minutes).

---

## Step 2: Get Your Supabase Connection String

1. In your Supabase project dashboard, go to **Project Settings** (gear icon in the left sidebar).
2. Click **Database** in the settings menu.
3. Scroll down to **Connection string** and select the **URI** tab.
4. Copy the connection string. It looks like this:

```
postgresql://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
```

5. Replace `[YOUR-PASSWORD]` with the database password you set in Step 1.

---

## Step 3: Update Your `.env` File Locally

Open your `.env` file and add the `DATABASE_URL` line with the connection string from Step 2. Your `.env` should now look something like:

```
SECRET_KEY=your-existing-secret-key
AES_KEY=your-existing-aes-key
AES_IV=your-existing-aes-iv
DATABASE_URL=postgresql://postgres.abcdefg:MyPassword123@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

---

## Step 4: Test Locally (Optional but Recommended)

Run the app locally to verify it connects to Supabase and creates the tables:

```powershell
python app.py
```

You should see:

- The table creation happening (no errors)
- The **"DEFAULT ADMIN ACCOUNT CREATED"** message (first run only)
- The server starting on `http://127.0.0.1:5000`

Open the browser and you should see the login page. Log in with `admin` / `admin123`.

If you get connection errors, double-check your `DATABASE_URL` — especially the password and that you're using port `6543` (the pooler port).

---

## Step 5: Push Your Code to GitHub

1. Create a GitHub repository:
   - Go to [github.com](https://github.com) and click **"New repository"**.
   - Name it (e.g. `QRAttendanceSys`), set it to **Private** or **Public**.
   - Don't initialize with README (you already have one).

2. Make sure `.env` is listed in your `.gitignore` so your secrets are never pushed.

3. Commit and push:

```powershell
git add .
git commit -m "Add Supabase, auth, student detail, deployment"
git remote add origin https://github.com/YOUR_USERNAME/QRAttendanceSys.git
git push -u origin main
```

If you already have a remote set up, just run `git push`.

---

## Step 6: Create a Render Account

1. Go to [render.com](https://render.com) and sign up (you can sign in with GitHub for convenience).
2. Connect your GitHub account if prompted.

---

## Step 7: Create a Web Service on Render

1. From the Render dashboard, click **"New +"** > **"Web Service"**.
2. Connect your GitHub repository (`QRAttendanceSys`).
3. Configure the service:

| Setting           | Value                             |
|-------------------|-----------------------------------|
| **Name**          | `qr-attendance` (or your choice)  |
| **Region**        | Choose closest to you             |
| **Branch**        | `main`                            |
| **Runtime**       | `Python 3`                        |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app`                |
| **Instance Type** | **Free** (for testing)            |

---

## Step 8: Set Environment Variables on Render

In the service creation page (or under the **Environment** tab after creation), click **"Add Environment Variable"** for each:

| Key            | Value                                                  |
|----------------|--------------------------------------------------------|
| `SECRET_KEY`   | Your secret key (same as in your `.env`)               |
| `AES_KEY`      | Your base64-encoded AES key (same as in your `.env`)   |
| `AES_IV`       | Your base64-encoded AES IV (same as in your `.env`)    |
| `DATABASE_URL` | Your Supabase connection string from Step 2            |

**Important**: Use the exact same `AES_KEY` and `AES_IV` values from your local `.env`. If you use different ones, all existing QR codes will become unreadable.

---

## Step 9: Deploy

1. Click **"Create Web Service"** (or **"Deploy"** if the service already exists).
2. Render will:
   - Clone your repo
   - Run `pip install -r requirements.txt`
   - Start the app with `gunicorn app:app`
3. Watch the deploy logs for any errors. A successful deploy shows something like:
   ```
   [INFO] Starting gunicorn
   [INFO] Listening at: http://0.0.0.0:10000
   ```
4. The first time it starts, it will create all database tables in Supabase and seed the default admin account.

---

## Step 10: Access Your Live Site

1. Render gives you a URL like: `https://qr-attendance.onrender.com`
2. Open it in your browser.
3. You'll see the **Officer Login** page.
4. Log in with:
   - **Username**: `admin`
   - **Password**: `admin123`
5. **Change this password** as soon as possible after first login.

---

## Verifying Everything Works

After deployment, check these:

1. **Login** — `admin` / `admin123` should work.
2. **Students page** — Register a student manually, then click their name to see the detail dashboard.
3. **Generate QR** — Generate a QR code for a student.
4. **Scanner** — Create a session and test scanning.
5. **Supabase dashboard** — Go to your Supabase project > **Table Editor** and you should see data in the `students`, `sessions`, `officers`, etc. tables.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **"Connection refused" errors** | Make sure your `DATABASE_URL` uses port `6543` (pooler), not `5432`. |
| **"Password authentication failed"** | Double-check the password in your connection string matches what you set when creating the Supabase project. |
| **App crashes on Render** | Check the Render logs (under the **Logs** tab). Common issues are missing environment variables. |
| **Free tier cold starts** | Render's free tier spins down after 15 minutes of inactivity. The first request after that takes ~30-60 seconds to wake up. |
| **QR codes disappear after redeploy** | On the free tier, Render uses ephemeral storage. QR code PNGs saved on the server filesystem are lost on each deploy. Consider regenerating them as needed. |
