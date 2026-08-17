# Remote Job Scanner Daemon

A fully autonomous, multi-source remote job scanner that polls for new opportunities in **Cybersecurity**, **Virtual Assistant**, and **IT Support** categories. The scanner runs hourly in the background using PM2, saves reports locally, and sends digests via **Email**, **Discord Webhooks**, and **Telegram Bots**.

## Key Features

- **Multi-Source Aggregation**: Fetches listings from 4 remote job sources:
  - **Himalayas API** (Tech and startup-focused remote listings)
  - **Remotive API** (Global remote developer, sales, and support roles)
  - **We Work Remotely RSS** (Established remote-first jobs catalog)
  - **Arbeitnow API** (Remote-friendly direct employer listings)
- **JSON-LD Schema Scraping**: Automatically crawls the landing pages of new job listings to locate schema metadata (`datePosted`) for 100% accurate job creation dates.
- **Fuzzy Semantic Deduplication**: Normalizes titles and company names to prevent the same job from being emailed multiple times if it is aggregated from multiple sources.
- **Multi-Channel Notifications**:
  - Email (via SMTP / Gmail)
  - Discord Webhook Integrations (Embed format)
  - Telegram Bots (HTML message format)

---

## Configuration (`config.json`)

To configure notifications and query filters, edit [config.json](file:///C:/Users/Administrator/remote-job-scanner/config.json):

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
  "discord": {
    "webhook_url": "https://discord.com/api/webhooks/... (Leave empty to disable)"
  },
  "telegram": {
    "bot_token": "BOT_TOKEN (Leave empty to disable)",
    "chat_id": "CHAT_ID (Leave empty to disable)"
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

*Note: For Gmail SMTP, generate an **App Password** from your Google account settings under 2-Step Verification.*

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
To trigger a manual scan immediately outside the hourly schedule, execute:
```cmd
C:\Users\Administrator\remote-job-scanner\run_scanner.bat
```
Logs for manual runs are written to `execution_log.txt`.

---

## Attribution & Licensing
Job listings are retrieved using free and public APIs. Please include appropriate attribution back to **Himalayas**, **Remotive**, **We Work Remotely**, and **Arbeitnow** if you redistribute or republish this data.
