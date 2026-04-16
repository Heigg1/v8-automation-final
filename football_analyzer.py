import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os

# ====================== 配置区 ======================
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# 联赛列表
LEAGUES = [
    "soccer_epl",           # 英超
    "soccer_bundesliga",    # 德甲
    "soccer_serie_a",       # 意甲
    "soccer_laliga",        # 西甲
    "soccer_ligue_1",       # 法甲
    "soccer_china_super"    # 中超
]

# ====================== 拉取比赛 + 赔率 ======================
def get_today_matches_with_odds():
    matches = []
    today = datetime.utcnow().strftime("%Y-%m-%d")

    for league in LEAGUES:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {
                "apiKey": "",
                "regions": "eu",
                "markets": "h2h,spreads,totals",
                "dateFormat": "iso"
            }
            resp = requests.get(url, params=params, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()

            for game in data:
                game_date = game["commence_time"].split("T")[0]
                if game_date != today:
                    continue

                # 欧赔
                h2h = next((m for m in game["bookmakers"][0]["markets"] if m["key"] == "h2h"), None)
                if not h2h:
                    continue
                outcomes = h2h["outcomes"]
                home_odds = next((o["price"] for o in outcomes if o["name"] == game["home_team"]), None)
                draw_odds = next((o["price"] for o in outcomes if o["name"] == "Draw"), None)
                away_odds = next((o["price"] for o in outcomes if o["name"] == game["away_team"]), None)

                if not home_odds or not draw_odds or not away_odds:
                    continue

                matches.append({
                    "home": game["home_team"],
                    "away": game["away_team"],
                    "kickoff": game["commence_time"],
                    "league": league,
                    "home_odds": home_odds,
                    "draw_odds": draw_odds,
                    "away_odds": away_odds,
                    "is_single": "【单关】" if league in ["soccer_epl", "soccer_china_super"] else ""
                })
        except Exception as e:
            continue

    return matches

# ====================== V8.0 核心分析 ======================
def v8_analysis(match):
    h = match["home_odds"]
    d = match["draw_odds"]
    a = match["away_odds"]

    # 平局概率（简化量化）
    draw_pct = round((1/d) / ((1/h)+(1/d)+(1/a)) * 100)

    # 庄套路识别
    trap = ""
    if h > 2.0 and d < 3.3 and a > 3.2:
        trap = "疑似诱主，防平局"
    elif h < 1.85 and a > 4.2:
        trap = "主胜格局，机构一致"
    elif abs(h - a) < 0.3 and d < 3.2:
        trap = "平局韬光，重点防平"

    # 预测方向
    if min(h, d, a) == h:
        pred = "主胜"
        conf = 68
    elif min(h, d, a) == a:
        pred = "客胜"
        conf = 66
    else:
        pred = "平局"
        conf = 75

    return {
        "match": f"{match['is_single']} {match['home']} vs {match['away']}",
        "time": match["kickoff"],
        "odds": f"{h:.2f} / {d:.2f} / {a:.2f}",
        "draw_rate": f"{draw_pct}%",
        "predict": pred,
        "conf": conf,
        "trap": trap
    }

# ====================== 发送邮件 ======================
def send_report(analysis_list):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not analysis_list:
        body = f"""
        <h2>✅ V8.0 系统正常运行</h2>
        <p>时间：{now}</p>
        <p>今日无主流联赛赛事</p>
        """
    else:
        body = f"<h2>⚽ V8.0 今日赛事分析报告 {now}</h2><hr>"
        for item in analysis_list:
            body += f"""
            <p><b>{item['match']}</b></p>
            <p>开球：{item['time']}</p>
            <p>赔率：{item['odds']}</p>
            <p>平局概率：{item['draw_rate']}</p>
            <p>预测：{item['predict']}（置信度 {item['conf']}%）</p>
            <p>庄路提示：{item['trap']}</p>
            <hr>
            """

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = "V8.0 足球分析报告"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PWD)
            smtp.send_message(msg)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 发邮件失败：{str(e)}")

# ====================== 主程序 ======================
if __name__ == "__main__":
    print("=== V8.0 开始运行 ===")
    matches = get_today_matches_with_odds()
    results = [v8_analysis(m) for m in matches]
    send_report(results)
    print("=== 全部完成 ===")
