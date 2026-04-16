import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os

# 从 GitHub 密钥读取
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

BASE_URL = "https://api.football-data.org/v4"
LEAGUES = ["PL", "BL1", "SA", "PD", "FL1", "AUS"]

def fetch_today_matches():
    matches = []
    today = datetime.now().strftime("%Y-%m-%d")
    headers = {"X-Auth-Token": ""}

    for league in LEAGUES:
        try:
            url = f"{BASE_URL}/competitions/{league}/matches?dateFrom={today}&dateTo={today}"
            res = requests.get(url, headers=headers, timeout=10)
            data = res.json()
            for match in data.get("matches", []):
                matches.append({
                    "home": match["homeTeam"]["name"],
                    "away": match["awayTeam"]["name"],
                    "time": match["utcDate"],
                    "status": match["status"]
                })
        except:
            continue
    return matches

def send_mail(matches):
    if not matches:
        return

    body = "<h2>今日足球赛程（V8.0自动报告）</h2>"
    for m in matches:
        body += f"<p>{m['home']} vs {m['away']} | {m['time']}</p>"

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = "今日足球赛程"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    matches = fetch_today_matches()
    send_mail(matches)
