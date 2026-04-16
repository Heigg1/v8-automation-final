import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import json

# ====================== 邮箱配置 ======================
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# ====================== 联赛配置 ======================
LEAGUE_CODES = [
    "soccer_epl",
    "soccer_bundesliga",
    "soccer_serie_a",
    "soccer_laliga",
    "soccer_ligue_1",
    "soccer_china_super"
]

# ====================== 进化数据库 ======================
DB_FILE = "v8_evolution_db.json"

def init_db():
    if not os.path.exists(DB_FILE):
        data = {
            "total": 0,
            "correct": 0,
            "draw_correct": 0,
            "predictions": [],
            "sent_live": {}
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def load_db():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

# ====================== 邮件发送 ======================
def send_email(subject, body):
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=20) as server:
            server.login(SENDER_EMAIL, SENDER_PWD)
            server.send_message(msg)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 发邮件失败: {e}")

# ====================== 获取今日比赛 ======================
def get_today_matches():
    matches = []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for league in LEAGUE_CODES:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {
                "apiKey": "39b9c560a6910a1a22b756357dd12776",
                "regions": "eu",
                "markets": "h2h,spreads",
                "dateFormat": "iso"
            }
            res = requests.get(url, params=params, timeout=10)
            if res.status_code != 200:
                continue
            for game in res.json():
                if game["commence_time"].startswith(today):
                    bm = game.get("bookmakers", [])
                    if not bm:
                        continue
                    mk = bm[0].get("markets", [])
                    h2h = next((m for m in mk if m["key"] == "h2h"), None)
                    if not h2h:
                        continue
                    outs = h2h["outcomes"]
                    h = next((x["price"] for x in outs if x["name"] == game["home_team"]), None)
                    d = next((x["price"] for x in outs if x["name"] == "Draw"), None)
                    a = next((x["price"] for x in outs if x["name"] == game["away_team"]), None)
                    if not h or not d or not a:
                        continue
                    matches.append({
                        "id": game["id"],
                        "home": game["home_team"],
                        "away": game["away_team"],
                        "kickoff": game["commence_time"],
                        "h": h,
                        "d": d,
                        "a": a,
                        "league": league,
                        "is_single": "【单关】" if league in ["soccer_epl", "soccer_china_super"] else ""
                    })
        except Exception:
            continue
    return matches

# ====================== 11:10 发送今日赛程 ======================
def send_schedule_1110():
    now = datetime.now()
    if not (now.hour == 11 and 9 <= now.minute <= 11):
        return
    matches = get_today_matches()
    if not matches:
        send_email("V8.0 今日赛程", "<h3>今日无赛事</h3>")
        return
    html = "<h2>📅 今日全部赛程</h2>"
    for m in matches:
        html += f"<p>{m['is_single']} {m['home']} vs {m['away']}　开球：{m['kickoff']}</p>"
    send_email("V8.0 今日赛程", html)

# ====================== 赛前45分钟 临场分析 ======================
def send_live_analysis():
    db = load_db()
    matches = get_today_matches()
    now_utc = datetime.utcnow()
    for m in matches:
        try:
            kickoff = datetime.fromisoformat(m["kickoff"].replace("Z", ""))
        except:
            continue
        diff = kickoff - now_utc
        if not (timedelta(minutes=40) < diff < timedelta(minutes=50)):
            continue
        if db["sent_live"].get(m["id"]):
            continue

        h, d, a = m["h"], m["d"], m["a"]
        imp = 1/h + 1/d + 1/a
        ph = round(1/h/imp*100)
        pd = round(1/d/imp*100)
        pa = round(1/a/imp*100)

        trap = ""
        if h > 2.0 and d < 3.3:
            trap = "诱主盘，重点防平"
            pred = "平局"
            conf = 78
        elif abs(h - a) < 0.3 and d < 3.2:
            trap = "胶着盘，机构藏平局"
            pred = "平局"
            conf = 82
        elif h < 1.85:
            trap = "正路主胜"
            pred = "主胜"
            conf = 70
        elif a < 1.85:
            trap = "正路客胜"
            pred = "客胜"
            conf = 70
        else:
            pred = "平局" if pd > 35 else ("主胜" if h < a else "客胜")
            conf = 68

        html = f"""
        <h3>⚽ 临场分析 {m['is_single']}</h3>
        <p>{m['home']} vs {m['away']}</p>
        <p>赔率：{h:.2f} / {d:.2f} / {a:.2f}</p>
        <p>概率：胜{ph}% 平{pd}% 负{pa}%</p>
        <p><b>推荐：{pred}（置信度 {conf}%）</b></p>
        <p>庄路提示：{trap}</p>
        """
        send_email(f"V8.0 临场推荐 {m['home']}vs{m['away']}", html)

        db["predictions"].append({
            "match_id": m["id"],
            "match": f"{m['home']}vs{m['away']}",
            "predict": pred,
            "result": None
        })
        db["sent_live"][m["id"]] = True
    save_db(db)

# ====================== 全部比赛结束后统一复盘 ======================
def full_review_at_night():
    now = datetime.now()
    if now.hour < 23:
        return
    db = load_db()
    try:
        date_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        url = "https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": "fe3a02e0f72a47479a18732b6d784c21"}
        params = {"date": date_str}
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code != 200:
            return
        games = res.json().get("matches", [])
        for g in games:
            if g.get("status") != "FINISHED":
                continue
            hg = g["score"]["fullTime"].get("homeTeam")
            ag = g["score"]["fullTime"].get("awayTeam")
            if hg is None or ag is None:
                continue
            actual = "主胜" if hg > ag else "客胜" if hg < ag else "平局"
            for pred in db["predictions"]:
                if pred["match_id"] == g["id"] and pred["result"] is None:
                    pred["result"] = actual
                    db["total"] += 1
                    if pred["predict"] == actual:
                        db["correct"] += 1
                        if actual == "平局":
                            db["draw_correct"] += 1
        save_db(db)
        total = db["total"]
        correct = db["correct"]
        draw_ok = db["draw_correct"]
        acc = round(correct / max(total, 1) * 100, 2)
        d_acc = round(draw_ok / max(total, 1) * 100, 2)
        report = f"""
        <h2>✅ 今日全部比赛复盘完成</h2>
        <p>总场次：{total}</p>
        <p>正确：{correct}</p>
        <p>整体命中率：{acc}%</p>
        <p>平局专项命中：{d_acc}%</p>
        """
        send_email("V8.0 每日复盘报告", report)
    except Exception as e:
        print(f"复盘异常: {e}")

# ====================== 主程序 ======================
if __name__ == "__main__":
    init_db()
    send_schedule_1110()
    send_live_analysis()
    full_review_at_night()
