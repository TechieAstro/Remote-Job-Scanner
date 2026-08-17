# Remote Job Scanner Daemon

A fully autonomous remote job scanner that polls for new opportunities in **Cybersecurity**, **Virtual Assistant**, and **IT Support** categories. The scanner runs hourly in the background using PM2 and saves reports locally. Once SMTP is configured, it will email reports to you.

## System Architecture

- **`config.json`**: Contains search keywords, local reports directory, and email/SMTP credentials.
- **`jobs_db.json`**: A JSON database tracking all processed job GUIDs to prevent duplicate alerts.
- **`scanner.py`**: The core logic script. It fetches job listings, filters duplicates, renders the email HTML, saves local copies, and sends the emails.
- **`daemon.py`**: Python looping daemon that executes the scanner every 3600 seconds (1 hour).
- **`launcher.js`**: Node.js launcher that PM2 uses to manage and persist the daemon.
- **`run_scanner.bat`**: A convenience batch file to run the scanner instantly and append console logs to `execution_log.txt`.

---

## Configuration (`config.json`)

To enable email notifications, edit [config.json](file:///C:/Users/Administrator/remote-job-scanner/config.json) with your credentials:

```json
{
  "email": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-google-app-password",
    "sender_email": "your-email@gmail.com",
    "recipient_email": "destination-email@gmail.com",
    "use_tls": true
  },
  "queries": {
    "cybersecurity": "cybersecurity",
    "virtual_assistant": "virtual assistant",
    "it_support": "it support"
  },
  "send_empty_reports": false,
  "save_local_reports": true,
  "reports_dir": "reports",
  "db_file": "jobs_db.json"
}
```

*Note: For Gmail, you will need to generate an **App Password** from your Google account settings under 2-Step Verification.*

---

## Operating Instructions

### 1. View Process Status
Use PM2 to check if the scanner daemon is active and healthy:
```bash
pm2 status
```

### 2. Monitor Logs
Check stdout and error logs in real-time:
```bash
pm2 logs remote-job-scanner
```

### 3. Restart / Stop
To restart or stop the scanner:
```bash
pm2 restart remote-job-scanner
pm2 stop remote-job-scanner
```

### 4. Manually Run a Scan
To trigger a manual scan immediately outside the hourly schedule, double-click [run_scanner.bat](file:///C:/Users/Administrator/remote-job-scanner/run_scanner.bat) or execute it from the terminal:
```cmd
C:\Users\Administrator\remote-job-scanner\run_scanner.bat
```
Logs for manual runs are written to `execution_log.txt`.

---

## Attribution & Data Source
Job listings are retrieved from the free, public [Himalayas API](https://himalayas.app/docs/remote-jobs-api). As per the Himalayas API licensing terms, please include appropriate attribution back to Himalayas if you share this data.
