import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import os

# ====================== 配置 ======================
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

LEAGUES = [
    "soccer_epl",
    "soccer_bundesliga",
    "soccer_serie_a",
    "soccer_laliga",
    "soccer_ligue_1",
    "soccer_china_super"
]

# ====================== 抓取赛事与赔率 ======================
def get_matches():
    matches = []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for league in LEAGUES:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": "", "regions": "eu", "markets": "h2h", "dateFormat": "iso"}
            res = requests.get(url, params=params, timeout=10)
            if res.status_code != 200:
                continue
            for g in res.json():
                if g["commence_time"].startswith(today):
                    h = next((o["price"] for o in g["bookmakers"][0]["markets"][0]["outcomes"] if o["name"] == g["home_team"]), None)
                    d = next((o["price"] for o in g["bookmakers"][0]["markets"][0]["outcomes"] if o["name"] == "Draw"), None)
                    a = next((o["price"] for o in g["bookmakers"][0]["markets"][0]["outcomes"] if o["name"] == g["away_team"]), None)
                    if h and d and a:
                        matches.append({
                            "home": g["home_team"], "away": g["away_team"], "time": g["commence_time"],
                            "h": h, "d": d, "a": a, "league": league
                        })
        except:
            continue
    return matches

# ====================== V8.0 人性化盘 + 庄思维核心 ======================
def v8_human_logic(m):
    h, d, a = m["h"], m["d"], m["a"]
    implied = (1/h + 1/d + 1/a)
    p_h = round((1/h)/implied * 100)
    p_d = round((1/d)/implied * 100)
    p_a = round((1/a)/implied * 100)

    # -------- 人性化盘核心：庄意图 + 大众心理 --------
    trap = ""
    confidence = 60

    # 1. 热门诱盘（庄利用大众心理）
    if h > 2.0 and d < 3.3 and a > 3.2:
        trap = "诱主，大众偏爱主胜，庄故意送舒服盘 → 防平"
        final = "平局"
        confidence = 78
    # 2. 实力均衡，庄藏平局
    elif abs(h - a) < 0.3 and d < 3.2:
        trap = "人气均衡，庄刻意韬光养晦 → 平局首选"
        final = "平局"
        confidence = 82
    # 3. 强队浅盘，不支持赢球
    elif h < 1.85 and d < 3.4 and (h - a) > 1.2:
        trap = "强队盘口过浅，不符合大众预期 → 防冷平"
        final = "平局"
        confidence = 75
    # 4. 自然盘，无明显做局
    elif min(h, a) < 1.95:
        final = "主胜" if h < a else "客胜"
        trap = "自然盘，庄无明显做局"
        confidence = 70
    # 5. 默认高概率平局
    else:
        final = "平局"
        trap = "盘口结构偏胶着，人性化判断走平"
        confidence = 72

    return {
        "match": f"{m['home']} vs {m['away']}",
        "time": m["time"],
        "odds": f"{h:.2f} | {d:.2f} | {a:.2f}",
        "prob": f"胜{p_h}% / 平{p_d}% / 负{p_a}%",
        "result": final,
        "conf": f"{confidence}%",
        "trap": trap
    }

# ====================== 邮件发送 ======================
def send_email(rows):
    now = datetime.now().strftime("%m-%d %H:%M")
    if not rows:
        html = f"<h3>✅ V8.0 人性化盘系统正常运行 {now}</h3><p>今日无赛事</p>"
    else:
        html = f"<h2>⚽ V8.0 人性化盘分析报告 {now}</h2><hr>"
        for r in rows:
            html += f"<p><b>{r['match']}</b></p><p>赔率：{r['odds']}</p><p>概率：{r['prob']}</p><p>推荐：<b>{r['result']}</b> {r['conf']}</p><p>庄意图：{r['trap']}</p><hr>"
    
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = "V8.0 人性化盘分析报告"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=10) as s:
            s.login(SENDER_EMAIL, SENDER_PWD)
            s.send_message(msg)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 发邮件失败：{e}")

# ====================== 主程序 ======================
if __name__ == "__main__":
    matches = get_matches()
    analysis = [v8_human_logic(m) for m in matches]
    send_email(analysis)
