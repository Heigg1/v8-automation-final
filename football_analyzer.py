# -*- coding: utf-8 -*-
import sys
import os
import requests
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
EMAIL_AUTH_CODE = os.getenv("EMAIL_AUTH_CODE")

TARGET_LEAGUES = {
    "england-premier-league": "英超",
    "germany-bundesliga": "德甲",
    "italy-serie-a": "意甲",
    "france-ligue-1": "法甲",
    "spain-la-liga": "西甲",
    "australia-a-league": "澳超",
    "japan-j1-league": "日职联",
    "korea-k-league-1": "韩K联"
}

DATA_FILE = "match_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_email(subject, html_content):
    try:
        msg = MIMEText(html_content, "html", "utf-8")
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def fetch_schedule():
    matches = []
    url = f"https://api.odds-api.io/v3/events?apiKey={ODDS_API_KEY}&sport=football&status=pending"
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        events = res.json()
    except:
        return 0

    for ev in events:
        slug = ev["league"]["slug"]
        if slug not in TARGET_LEAGUES:
            continue
        lg = TARGET_LEAGUES[slug]
        mid = ev["id"]
        home = ev["home"]
        away = ev["away"]
        ko = ev["date"].replace("T", " ").split(".")[0]
        single = lg in ["英超", "德甲", "澳超", "日职联", "韩K联"]

        ou = f"https://api.odds-api.io/v3/odds?apiKey={ODDS_API_KEY}&eventId={mid}&bookmakers=Bet365&markets=h2h,spreads,totals"
        try:
            o = requests.get(ou, timeout=15).json()
            h2h = next((x for x in o.get("markets", []) if x["key"]=="h2h"), None)
            sp = next((x for x in o.get("markets", []) if x["key"]=="spreads"), None)
            to = next((x for x in o.get("markets", []) if x["key"]=="totals"), None)
            h = h2h["outcomes"][0]["price"] if h2h else None
            d = h2h["outcomes"][1]["price"] if h2h else None
            a = h2h["outcomes"][2]["price"] if h2h else None
            ah = sp["name"] if sp else None
            tl = to["name"] if to else None
        except:
            h=d=a=ah=tl=None

        matches.append({
            "match_id": mid, "联赛": lg, "主队": home, "客队": away, "开赛时间": ko, "单关": single,
            "初盘主胜": h, "初盘平": d, "初盘客胜": a, "初盘亚盘": ah, "初盘大小球": tl,
            "临盘主胜": None, "临盘平": None, "临盘客胜": None, "临盘亚盘": None, "临盘大小球": None,
            "抓取初盘时间": now(), "抓取临盘时间": None, "赛果": None, "比分": None, "大小球结果": None
        })

    save_data(matches)
    html = "<h3>今日赛程</h3><table border=1><tr><th>联赛</th><th>对阵</th><th>时间</th><th>单关</th></tr>"
    for m in matches:
        html += f"<tr><td>{m['联赛']}</td><td>{m['主队']} vs {m['客队']}</td><td>{m['开赛时间']}</td><td>{'✅' if m['单关'] else ''}</td></tr>"
    html += "</table>"
    send_email("今日赛程已抓取", html)
    return len(matches)

def fetch_live_odds():
    data = load_data()
    cnt = 0
    for m in data:
        if m["抓取临盘时间"]: continue
        try:
            ko = datetime.strptime(m["开赛时间"], "%Y-%m-%d %H:%M:%S")
        except: continue
        if datetime.now() >= ko - timedelta(minutes=45):
            try:
                ou = f"https://api.odds-api.io/v3/odds?apiKey={ODDS_API_KEY}&eventId={m['match_id']}&bookmakers=Bet365&markets=h2h,spreads,totals"
                o = requests.get(ou, timeout=15).json()
                h2h = next((x for x in o.get("markets", []) if x["key"]=="h2h"), None)
                sp = next((x for x in o.get("markets", []) if x["key"]=="spreads"), None)
                to = next((x for x in o.get("markets", []) if x["key"]=="totals"), None)
                m["临盘主胜"] = h2h["outcomes"][0]["price"] if h2h else None
                m["临盘平"] = h2h["outcomes"][1]["price"] if h2h else None
                m["临盘客胜"] = h2h["outcomes"][2]["price"] if h2h else None
                m["临盘亚盘"] = sp["name"] if sp else None
                m["临盘大小球"] = to["name"] if to else None
                m["抓取临盘时间"] = now()
                cnt +=1
            except: continue
    save_data(data)
    send_email("临盘已更新", f"更新{cnt}场")
    return cnt

def fetch_result():
    data = load_data()
    cnt =0
    url = f"https://api.odds-api.io/v3/events?apiKey={ODDS_API_KEY}&sport=football&status=completed"
    try:
        events = requests.get(url, timeout=15).json()
    except:
        return 0
    for ev in events:
        mid = ev["id"]
        for m in data:
            if m["match_id"]==mid and not m["赛果"]:
                hs = ev.get("homeScore",0)
                as_ = ev.get("awayScore",0)
                m["比分"]=f"{hs}-{as_}"
                if hs>as_: m["赛果"]="主胜"
                elif hs<as_: m["赛果"]="客胜"
                else: m["赛果"]="平局"
                if m["初盘大小球"]:
                    try:
                        line = float(m["初盘大小球"].split()[-1])
                        m["大小球结果"]="大" if hs+as_>line else "小"
                    except: pass
                cnt +=1
    save_data(data)
    send_email("赛果已更新", f"更新{cnt}场")
    return cnt

def generate_review():
    data = load_data()
    rows=[]
    total=0
    i_ok=l_ok=0
    for m in data:
        if not m["赛果"]: continue
        total +=1
        ip = [m["初盘主胜"],m["初盘平"],m["初盘客胜"]]
        ipd = ["主胜","平局","客胜"][ip.index(min(ip))] if all(ip) else "无"
        lp = [m["临盘主胜"],m["临盘平"],m["临盘客胜"]]
        lpd = ["主胜","平局","客胜"][lp.index(min(lp))] if all(lp) else ipd
        if ipd==m["赛果"]:i_ok +=1
        if lpd==m["赛果"]:l_ok +=1
        rows.append(f"<tr><td>{m['联赛']}</td><td>{m['主队']}vs{m['客队']}</td><td>{ipd}</td><td>{lpd}</td><td>{m['赛果']}({m['比分']})</td><td>{'✅'if ipd==m['赛果']else'❌'}</td><td>{'✅'if lpd==m['赛果']else'❌'}</td></tr>")
    html = f"<h3>复盘</h3><table border=1><tr><th>联赛</th><th>对阵</th><th>初盘</th><th>临盘</th><th>赛果</th><th>初盘</th><th>临盘</th></tr>{''.join(rows)}</table><br><p>总{total} 初盘{i_ok}/{total} 临盘{l_ok}/{total}</p>"
    send_email("复盘报告", html)
    return html

if __name__ == "__main__":
    if len(sys.argv)<2:
        print("schedule live result review")
        sys.exit()
    c = sys.argv[1]
    if c=="schedule":fetch_schedule()
    elif c=="live":fetch_live_odds()
    elif c=="result":fetch_result()
    elif c=="review":generate_review()
