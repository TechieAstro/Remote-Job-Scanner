import os
import sys
import json
import urllib.request
import urllib.parse
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# Path constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file not found at {CONFIG_FILE}. Creating default...")
        default_config = {
            "email": {
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_username": "",
                "smtp_password": "",
                "sender_email": "",
                "recipient_email": "",
                "use_tls": True
            },
            "queries": {
                "cybersecurity": "cybersecurity",
                "virtual_assistant": "virtual assistant",
                "it_support": "it support"
            },
            "send_empty_reports": False,
            "save_local_reports": True,
            "reports_dir": "reports",
            "db_file": "jobs_db.json"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_db(db_path):
    if not os.path.exists(db_path):
        return []
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading database file: {e}. Starting fresh.")
        return []

def save_db(db_path, seen_guids):
    # Keep only the last 2000 job IDs to prevent the DB file from growing indefinitely
    trimmed_guids = list(seen_guids)[-2000:]
    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(trimmed_guids, f, indent=2)
    except Exception as e:
        print(f"Error saving database file: {e}")

def fetch_jobs_from_api(query):
    url = f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote(query)}&limit=20"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    
    # Disable SSL verification to prevent local environment issues
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                return data.get("jobs", [])
    except Exception as e:
        print(f"API Error fetching '{query}': {e}", file=sys.stderr)
    return []

def format_salary(job):
    min_sal = job.get("minSalary")
    max_sal = job.get("maxSalary")
    currency = job.get("currency", "USD")
    period = job.get("salaryPeriod", "annual")
    
    if min_sal is not None and max_sal is not None:
        return f"{currency} {min_sal:,.0f} - {max_sal:,.0f} ({period})"
    elif min_sal is not None:
        return f"From {currency} {min_sal:,.0f} ({period})"
    elif max_sal is not None:
        return f"Up to {currency} {max_sal:,.0f} ({period})"
    return ""

def build_html_report(grouped_jobs, total_new_jobs, report_time):
    # CSS design styles
    css_styles = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #0f172a;
        color: #e2e8f0;
        margin: 0;
        padding: 0;
    }
    .container {
        max-width: 700px;
        margin: 20px auto;
        padding: 20px;
        background-color: #0f172a;
    }
    .header {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(79, 70, 229, 0.2);
    }
    .header h1 {
        margin: 0 0 10px 0;
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
    }
    .header p {
        margin: 0;
        color: #e2e8f0;
        font-size: 14px;
        opacity: 0.9;
    }
    .stats-badge {
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.2);
        color: #ffffff;
        padding: 4px 12px;
        border-radius: 50px;
        font-size: 12px;
        font-weight: 600;
        margin-top: 10px;
    }
    .category-section {
        margin-bottom: 30px;
    }
    .category-title {
        font-size: 18px;
        font-weight: 700;
        color: #f8fafc;
        border-left: 4px solid #6366f1;
        padding-left: 10px;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .job-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
        transition: transform 0.2s, border-color 0.2s;
    }
    .job-card:hover {
        border-color: #4f46e5;
    }
    .job-title {
        font-size: 16px;
        font-weight: 600;
        margin: 0 0 5px 0;
    }
    .job-title a {
        color: #38bdf8;
        text-decoration: none;
    }
    .job-title a:hover {
        text-decoration: underline;
    }
    .company-name {
        font-size: 14px;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 12px;
    }
    .meta-badges {
        margin-bottom: 12px;
    }
    .badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 6px;
        margin-bottom: 6px;
        text-transform: capitalize;
    }
    .badge-seniority {
        background-color: rgba(124, 58, 237, 0.15);
        color: #c084fc;
        border: 1px solid rgba(124, 58, 237, 0.3);
    }
    .badge-location {
        background-color: rgba(13, 148, 136, 0.15);
        color: #2dd4bf;
        border: 1px solid rgba(13, 148, 136, 0.3);
    }
    .badge-salary {
        background-color: rgba(22, 163, 74, 0.15);
        color: #4ade80;
        border: 1px solid rgba(22, 163, 74, 0.3);
    }
    .job-excerpt {
        font-size: 13px;
        color: #cbd5e1;
        line-height: 1.5;
        margin: 8px 0 0 0;
    }
    .job-date {
        font-size: 11px;
        color: #64748b;
        margin-top: 10px;
        text-align: right;
    }
    .no-jobs {
        text-align: center;
        padding: 40px;
        background-color: #1e293b;
        border: 1px dashed #334155;
        border-radius: 10px;
        color: #94a3b8;
    }
    .footer {
        text-align: center;
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #334155;
        font-size: 12px;
        color: #64748b;
        line-height: 1.6;
    }
    .footer a {
        color: #94a3b8;
        text-decoration: underline;
    }
    """

    # Start HTML
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Remote Job Scan Alert</title>
        <style>{css_styles}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Hourly Remote Job Scan</h1>
                <p>Generated on {report_time}</p>
                <div class="stats-badge">{total_new_jobs} New Job(s) Found</div>
            </div>
    """

    # Grouped Jobs
    categories_metadata = [
        ("Cybersecurity", "cybersecurity"),
        ("Virtual Assistant", "virtual_assistant"),
        ("IT Support", "it_support")
    ]

    for title, key in categories_metadata:
        jobs = grouped_jobs.get(key, [])
        html += f"""
        <div class="category-section">
            <div class="category-title">{title} ({len(jobs)})</div>
        """
        
        if not jobs:
            html += """
            <div class="no-jobs">
                No new job openings found in this category since the last scan.
            </div>
            """
        else:
            for job in jobs:
                # Format tags and components
                seniority_str = ", ".join(job.get("seniority", [])) or "Not Specified"
                location_str = job.get("locationRestrictions") or "Worldwide"
                if isinstance(location_str, list):
                    location_str = ", ".join(location_str)
                
                salary_str = format_salary(job)
                
                # HTML template card
                html += f"""
                <div class="job-card">
                    <h3 class="job-title"><a href="{job.get('applicationLink')}" target="_blank">{job.get('title')}</a></h3>
                    <div class="company-name">{job.get('companyName')}</div>
                    
                    <div class="meta-badges">
                        <span class="badge badge-seniority">Seniority: {seniority_str}</span>
                        <span class="badge badge-location">📍 {location_str}</span>
                """
                if salary_str:
                    html += f'<span class="badge badge-salary">💵 {salary_str}</span>'
                
                # Format publish date
                pub_date_raw = job.get("pubDate", 0)
                try:
                    pub_date = datetime.fromtimestamp(pub_date_raw / 1000).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pub_date = "Recently"

                html += f"""
                    </div>
                    <p class="job-excerpt">{job.get('excerpt')}</p>
                    <div class="job-date">Published: {pub_date}</div>
                </div>
                """
        
        html += "</div>"

    # Footer with Himalayas attribution
    html += """
            <div class="footer">
                <p>This report was generated automatically by the Remote Job Scanner.</p>
                <p>Job data provided by <a href="https://himalayas.app" target="_blank">Himalayas Remote Job Board</a>. Powered by their free Remote Jobs API.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(config_email, html_content, total_new_jobs, report_time):
    smtp_host = config_email.get("smtp_host")
    smtp_port = config_email.get("smtp_port")
    smtp_username = config_email.get("smtp_username")
    smtp_password = config_email.get("smtp_password")
    sender_email = config_email.get("sender_email")
    recipient_email = config_email.get("recipient_email")
    use_tls = config_email.get("use_tls", True)

    if not smtp_host or not smtp_username or not smtp_password or not recipient_email:
        print("SMTP credentials not fully configured. Skipping email delivery.")
        return False

    print(f"Sending email report to {recipient_email}...")
    
    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 Remote Job Scan: {total_new_jobs} New Jobs ({report_time})"
    msg["From"] = sender_email or smtp_username
    msg["To"] = recipient_email

    # Add HTML body
    msg.attach(MIMEText(html_content, "html"))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        
        server.login(smtp_username, smtp_password)
        server.sendmail(msg["From"], msg["To"], msg.as_string())
        server.close()
        print("Email report sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        return False

def main():
    print(f"--- Remote Job Scan Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Load configuration and database
    config = load_config()
    db_path = os.path.join(BASE_DIR, config.get("db_file", "jobs_db.json"))
    seen_guids = set(load_db(db_path))

    # 2. Fetch jobs
    new_jobs_by_category = {}
    total_new_jobs = 0

    queries = config.get("queries", {})
    for cat_key, query_str in queries.items():
        print(f"Fetching listings for query: '{query_str}'...")
        jobs = fetch_jobs_from_api(query_str)
        
        # Filter duplicates using unique GUID
        new_jobs = []
        for job in jobs:
            guid = job.get("guid")
            if guid and guid not in seen_guids:
                new_jobs.append(job)
                seen_guids.add(guid)
        
        new_jobs_by_category[cat_key] = new_jobs
        total_new_jobs += len(new_jobs)
        print(f"Found {len(jobs)} active jobs, {len(new_jobs)} are new.")

    # 3. Report generation and dispatch
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if we should execute actions
    should_report = total_new_jobs > 0 or config.get("send_empty_reports", False)
    
    if should_report:
        html_report = build_html_report(new_jobs_by_category, total_new_jobs, report_time)
        
        # Save HTML report locally if configured
        if config.get("save_local_reports", True):
            reports_dir = os.path.join(BASE_DIR, config.get("reports_dir", "reports"))
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
            
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            file_path = os.path.join(reports_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_report)
            print(f"Report saved locally to: {file_path}")

        # Send email if credentials exist
        send_email(config.get("email", {}), html_report, total_new_jobs, report_time)
        
        # Save seen GUIDs back to database
        save_db(db_path, seen_guids)
    else:
        print("No new jobs found and send_empty_reports is disabled. Skipping report generation.")

    print(f"--- Remote Job Scan Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

if __name__ == "__main__":
    main()
