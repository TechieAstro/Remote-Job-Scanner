import os
import sys
import json
import urllib.request
import urllib.parse
import ssl
import smtplib
import re
import string
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# Path constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file not found at {CONFIG_FILE}. Exiting.")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_db(db_path):
    if not os.path.exists(db_path):
        return [], set(), set()
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        seen_guids = set()
        seen_keys = set()
        db_records = []
        
        for item in data:
            if isinstance(item, str):
                seen_guids.add(item)
                db_records.append({"guid": item, "clean_key": "", "timestamp": 0})
            elif isinstance(item, dict):
                guid = item.get("guid")
                clean_key = item.get("clean_key")
                if guid:
                    seen_guids.add(guid)
                if clean_key:
                    seen_keys.add(clean_key)
                db_records.append(item)
        return db_records, seen_guids, seen_keys
    except Exception as e:
        print(f"Error reading database file: {e}. Starting fresh.")
        return [], set(), set()

def save_db(db_path, db_records):
    # Keep only the last 2000 records to prevent DB file from growing indefinitely
    trimmed_records = db_records[-2000:]
    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(trimmed_records, f, indent=2)
    except Exception as e:
        print(f"Error saving database file: {e}")

def get_clean_key(title, company):
    def clean(s):
        if not s:
            return ""
        s = s.lower()
        # Remove suffixes like inc, llc, ltd, corp, group, etc.
        s = re.sub(r'\b(inc|llc|ltd|corp|co|group|plc|corporation|limitada|solutions)\b', '', s)
        # Remove punctuation and whitespace
        s = "".join(c for c in s if c not in string.punctuation)
        return " ".join(s.split())
    
    return f"{clean(company)}||{clean(title)}"

# ==========================================
# DATE POSTED SCRAPER (JSON-LD)
# ==========================================
def scrape_date_posted(url):
    """Scrapes the exact posting date from a job's JSON-LD script tags."""
    if not url:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=4) as response:
            html = response.read().decode('utf-8', errors='ignore')
            json_ld_pattern = re.compile(r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>', re.DOTALL | re.IGNORECASE)
            
            for match in json_ld_pattern.finditer(html):
                try:
                    js_data = json.loads(match.group(1).strip())
                    dicts_to_check = []
                    if isinstance(js_data, dict):
                        dicts_to_check.append(js_data)
                    elif isinstance(js_data, list):
                        dicts_to_check.extend(js_data)
                    
                    # Traverse @graph schemas if present
                    for d in dicts_to_check:
                        if "@graph" in d and isinstance(d["@graph"], list):
                            dicts_to_check.extend(d["@graph"])

                    for d in dicts_to_check:
                        if isinstance(d, dict) and d.get("@type") == "JobPosting":
                            date_posted = d.get("datePosted")
                            if date_posted:
                                # Normalise ISO date string
                                return date_posted
                except Exception:
                    continue
    except Exception:
        # Fail silently to avoid stopping the entire scan
        pass
    return None

def normalize_date_to_timestamp(date_str):
    if not date_str:
        return 0
    try:
        # Standardize strings like "2026-08-17T12:00:00Z" or "2026-08-17"
        clean_date = date_str.split("T")[0]
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        return dt.timestamp() * 1000
    except Exception:
        return 0

# ==========================================
# SOURCE INTEGRATIONS
# ==========================================

# 1. HIMALAYAS API
def fetch_himalayas(query):
    url = f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote(query)}&limit=20"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            data = json.loads(response.read().decode())
            raw_jobs = data.get("jobs", [])
            normalized = []
            for r in raw_jobs:
                min_sal = r.get("minSalary")
                max_sal = r.get("maxSalary")
                cur = r.get("currency", "USD")
                per = r.get("salaryPeriod", "annual")
                salary_str = ""
                if min_sal is not None and max_sal is not None:
                    salary_str = f"{cur} {min_sal:,.0f} - {max_sal:,.0f} ({per})"
                elif min_sal is not None:
                    salary_str = f"From {cur} {min_sal:,.0f} ({per})"
                elif max_sal is not None:
                    salary_str = f"Up to {cur} {max_sal:,.0f} ({per})"

                loc = r.get("locationRestrictions") or "Worldwide"
                if isinstance(loc, list):
                    loc = ", ".join(loc)
                
                normalized.append({
                    "title": r.get("title", "").strip(),
                    "companyName": r.get("companyName", "").strip(),
                    "applicationLink": r.get("applicationLink"),
                    "excerpt": r.get("excerpt", "")[:280] + "...",
                    "source": "Himalayas",
                    "seniority": r.get("seniority", []),
                    "locationRestrictions": loc,
                    "salary": salary_str,
                    "pubDate": r.get("pubDate", 0),
                    "guid": f"himalayas-{r.get('guid')}"
                })
            return normalized
    except Exception as e:
        print(f"Himalayas fetch failed: {e}", file=sys.stderr)
        return []

# 2. REMOTIVE API
def fetch_remotive(query):
    url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(query)}&limit=20"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            data = json.loads(response.read().decode())
            raw_jobs = data.get("jobs", [])
            normalized = []
            for r in raw_jobs:
                pub_date_str = r.get("publication_date", "")
                pub_timestamp = 0
                if pub_date_str:
                    try:
                        dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                        pub_timestamp = dt.timestamp() * 1000
                    except Exception:
                        pass
                
                desc = re.sub('<[^<]+?>', '', r.get("description", ""))
                
                normalized.append({
                    "title": r.get("title", "").strip(),
                    "companyName": r.get("company_name", "").strip(),
                    "applicationLink": r.get("url"),
                    "excerpt": desc[:280] + "..." if desc else "",
                    "source": "Remotive",
                    "seniority": [],
                    "locationRestrictions": r.get("candidate_required_location") or "Worldwide",
                    "salary": r.get("salary", ""),
                    "pubDate": pub_timestamp,
                    "guid": f"remotive-{r.get('id')}"
                })
            return normalized
    except Exception as e:
        print(f"Remotive fetch failed: {e}", file=sys.stderr)
        return []

# 3. WE WORK REMOTELY (RSS Feed Cache)
_wwr_cache = None
def fetch_wwr_rss():
    global _wwr_cache
    if _wwr_cache is not None:
        return _wwr_cache
    
    url = "https://weworkremotely.com/remote-jobs.rss"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            _wwr_cache = items
            return items
    except Exception as e:
        print(f"We Work Remotely RSS fetch failed: {e}", file=sys.stderr)
        _wwr_cache = []
        return []

def search_wwr(query):
    items = fetch_wwr_rss()
    normalized = []
    query_clean = query.lower()
    
    for item in items:
        raw_title = item.find('title').text if item.find('title') is not None else ""
        desc_html = item.find('description').text if item.find('description') is not None else ""
        desc_clean = re.sub('<[^<]+?>', '', desc_html)
        
        # Local keyword match
        if query_clean in raw_title.lower() or query_clean in desc_clean.lower():
            if ":" in raw_title:
                parts = raw_title.split(":", 1)
                company = parts[0].strip()
                title = parts[1].strip()
            else:
                company = "Unknown"
                title = raw_title.strip()
                
            link = item.find('link').text if item.find('link') is not None else ""
            guid_el = item.find('guid')
            guid_val = guid_el.text if guid_el is not None else link
            
            pub_date_str = item.find('pubDate').text if item.find('pubDate') is not None else ""
            pub_timestamp = 0
            if pub_date_str:
                try:
                    dt = datetime.strptime(pub_date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    pub_timestamp = dt.timestamp() * 1000
                except Exception:
                    pass
            
            normalized.append({
                "title": title,
                "companyName": company,
                "applicationLink": link,
                "excerpt": desc_clean[:280] + "..." if desc_clean else "",
                "source": "We Work Remotely",
                "seniority": [],
                "locationRestrictions": "Worldwide",
                "salary": "",
                "pubDate": pub_timestamp,
                "guid": f"wwr-{guid_val}"
            })
    return normalized

# 4. ARBEITNOW (API Cache)
_arbeitnow_cache = None
def fetch_arbeitnow_api():
    global _arbeitnow_cache
    if _arbeitnow_cache is not None:
        return _arbeitnow_cache
    
    url = "https://www.arbeitnow.com/api/job-board-api"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            data = json.loads(response.read().decode())
            jobs = data.get("data", [])
            _arbeitnow_cache = jobs
            return jobs
    except Exception as e:
        print(f"Arbeitnow API fetch failed: {e}", file=sys.stderr)
        _arbeitnow_cache = []
        return []

def search_arbeitnow(query):
    jobs = fetch_arbeitnow_api()
    normalized = []
    query_clean = query.lower()
    
    for r in jobs:
        # Ensure the job is remote
        is_remote = r.get("remote", False)
        tags = [t.lower() for t in r.get("tags", [])]
        
        # Check if remote in tags too
        if not is_remote and "remote" in tags:
            is_remote = True
            
        if not is_remote:
            continue
            
        title = r.get("title", "")
        desc = re.sub('<[^<]+?>', '', r.get("description", ""))
        
        # Local keyword match
        if query_clean in title.lower() or query_clean in desc.lower() or any(query_clean in t for t in tags):
            created_at = r.get("created_at")
            pub_timestamp = 0
            if isinstance(created_at, (int, float)):
                pub_timestamp = created_at * 1000
            elif isinstance(created_at, str):
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    pub_timestamp = dt.timestamp() * 1000
                except Exception:
                    pass
                    
            normalized.append({
                "title": title.strip(),
                "companyName": r.get("company_name", "").strip(),
                "applicationLink": r.get("url"),
                "excerpt": desc[:280] + "..." if desc else "",
                "source": "Arbeitnow",
                "seniority": [],
                "locationRestrictions": "Remote",
                "salary": "",
                "pubDate": pub_timestamp,
                "guid": f"arbeitnow-{r.get('slug')}"
            })
    return normalized

# ==========================================
# ALTERNATIVE NOTIFICATION WEBHOOKS
# ==========================================
def send_discord_notification(webhook_url, category_title, jobs):
    if not webhook_url or not jobs:
        return
    print(f"Sending Discord webhook notification for {category_title}...")
    
    embed = {
        "title": f"🔔 {category_title} remote jobs",
        "description": f"Found {len(jobs)} new remote job listings!",
        "color": 5814783, # Purple
        "fields": [],
        "footer": {
            "text": "Remote Job Scanner"
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    for job in jobs[:10]:
        salary_info = f" | 💵 {job.get('salary')}" if job.get('salary') else ""
        location_info = f"📍 {job.get('locationRestrictions')}"
        source_info = f"Source: {job.get('source')}"
        
        embed["fields"].append({
            "name": f"{job.get('title')} @ {job.get('companyName')}",
            "value": f"[Apply Here]({job.get('applicationLink')})\n{location_info}{salary_info} | {source_info}",
            "inline": False
        })
        
    payload = {"embeds": [embed]}
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
            pass
    except Exception as e:
        print(f"Failed to send Discord webhook: {e}", file=sys.stderr)

def send_telegram_notification(bot_token, chat_id, category_title, jobs):
    if not bot_token or not chat_id or not jobs:
        return
    print(f"Sending Telegram bot notification for {category_title}...")
    
    message = f"<b>🔔 New {category_title} Jobs</b>\n\n"
    for job in jobs[:10]:
        title_esc = job.get('title', '').replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        comp_esc = job.get('companyName', '').replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        link = job.get('applicationLink')
        source = job.get('source')
        loc = job.get('locationRestrictions', 'Worldwide')
        sal = f" (💵 {job.get('salary')})" if job.get('salary') else ""
        
        message += f"• <a href='{link}'>{title_esc}</a> @ <b>{comp_esc}</b>\n"
        message += f"  📍 {loc}{sal} | <i>{source}</i>\n\n"
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
            pass
    except Exception as e:
        print(f"Failed to send Telegram message: {e}", file=sys.stderr)

# ==========================================
# REPORT FORMATTING & EMAIL
# ==========================================
def format_salary(job):
    # Already formatted in normalize
    return job.get("salary", "")

def build_html_report(grouped_jobs, total_new_jobs, report_time):
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
    .badge-source {
        background-color: rgba(71, 85, 105, 0.15);
        color: #94a3b8;
        border: 1px solid rgba(71, 85, 105, 0.3);
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
                seniority_str = ", ".join(job.get("seniority", []))
                location_str = job.get("locationRestrictions") or "Worldwide"
                salary_str = job.get("salary", "")
                
                html += f"""
                <div class="job-card">
                    <h3 class="job-title"><a href="{job.get('applicationLink')}" target="_blank">{job.get('title')}</a></h3>
                    <div class="company-name">{job.get('companyName')}</div>
                    
                    <div class="meta-badges">
                """
                if seniority_str:
                    html += f'<span class="badge badge-seniority">Seniority: {seniority_str}</span>'
                html += f'<span class="badge badge-location">📍 {location_str}</span>'
                if salary_str:
                    html += f'<span class="badge badge-salary">💵 {salary_str}</span>'
                html += f'<span class="badge badge-source">🔍 {job.get("source")}</span>'
                
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

    html += """
            <div class="footer">
                <p>This report was generated automatically by the Multi-Source Remote Job Scanner.</p>
                <p>Data aggregated from Himalayas, Remotive, We Work Remotely, and Arbeitnow.</p>
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
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 Multi-Source Remote Job Scan: {total_new_jobs} New Jobs ({report_time})"
    msg["From"] = sender_email or smtp_username
    msg["To"] = recipient_email
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

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print(f"--- Remote Job Scan Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Load configuration and database
    config = load_config()
    db_path = os.path.join(BASE_DIR, config.get("db_file", "jobs_db.json"))
    db_records, seen_guids, seen_keys = load_db(db_path)

    # 2. Fetch and aggregate
    new_jobs_by_category = {}
    total_new_jobs = 0
    queries = config.get("queries", {})

    # Pre-cache RSS / JSON data feeds to avoid downloading them multiple times
    fetch_wwr_rss()
    fetch_arbeitnow_api()

    for cat_key, query_str in queries.items():
        print(f"\n[Category: {cat_key.upper()}] Querying all sources for '{query_str}'...")
        
        # Fetch from all 4 sites
        all_candidate_jobs = []
        all_candidate_jobs.extend(fetch_himalayas(query_str))
        all_candidate_jobs.extend(fetch_remotive(query_str))
        all_candidate_jobs.extend(search_wwr(query_str))
        all_candidate_jobs.extend(search_arbeitnow(query_str))
        
        # Deduplicate and filter new entries
        new_jobs = []
        for job in all_candidate_jobs:
            guid = job.get("guid")
            clean_key = get_clean_key(job.get("title"), job.get("companyName"))
            
            # Cross-site deduplication
            is_new = (guid not in seen_guids) and (clean_key not in seen_keys)
            
            if is_new:
                # Scrape accurate datePosted for new jobs (HTML JSON-LD check)
                link = job.get("applicationLink")
                scraped_date = scrape_date_posted(link)
                if scraped_date:
                    ts = normalize_date_to_timestamp(scraped_date)
                    if ts > 0:
                        job["pubDate"] = ts
                
                # Update trackers
                job["clean_key"] = clean_key
                new_jobs.append(job)
                
                # Temporarily add to tracking sets for duplicate safety inside the same hourly batch
                seen_guids.add(guid)
                seen_keys.add(clean_key)
                
                # Append record
                db_records.append({
                    "guid": guid,
                    "clean_key": clean_key,
                    "timestamp": datetime.now().timestamp()
                })
        
        new_jobs_by_category[cat_key] = new_jobs
        total_new_jobs += len(new_jobs)
        print(f"Finished query. Found {len(new_jobs)} new remote jobs.")

    # 3. Report generation and dispatch
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

        # Send notifications
        # A. Email (SMTP)
        send_email(config.get("email", {}), html_report, total_new_jobs, report_time)
        
        # B. Slack/Discord / Telegram Notifications
        discord_config = config.get("discord", {})
        telegram_config = config.get("telegram", {})
        
        for cat_key, jobs in new_jobs_by_category.items():
            if jobs:
                # Discord webhook
                if discord_config.get("webhook_url"):
                    send_discord_notification(discord_config.get("webhook_url"), f"{cat_key.capitalize().replace('_', ' ')}", jobs)
                
                # Telegram notification
                if telegram_config.get("bot_token") and telegram_config.get("chat_id"):
                    send_telegram_notification(telegram_config.get("bot_token"), telegram_config.get("chat_id"), f"{cat_key.capitalize().replace('_', ' ')}", jobs)

        # Save database
        save_db(db_path, db_records)
    else:
        print("\nNo new jobs found and send_empty_reports is disabled. Skipping report generation.")

    print(f"\n--- Remote Job Scan Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

if __name__ == "__main__":
    main()
