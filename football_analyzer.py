import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os

# --------------------------
# 1. 基础配置
# --------------------------
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# 免费赛事+赔率API（和竞彩数据同源）
BASE_URL = "https://api.the-odds-api.com/v4/sports"
API_KEY = ""  # 留空，用公共接口即可
LEAGUES = ["soccer_epl", "soccer_bundesliga", "soccer_serie_a", "soccer_la_liga", "soccer_ligue1", "soccer_a_league"]

# --------------------------
# 2. 拉取当日赛事+赔率
# --------------------------
def fetch_matches_with_odds():
    matches = []
    today = datetime.now().strftime("%Y-%m-%d")
    for league in LEAGUES:
        try:
            url = f"{BASE_URL}/{league}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,spreads,totals"
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            for game in data:
                match_date = game["commence_time"].split("T")[0]
                if match_date == today:
                    # 提取欧赔、亚盘、大小球数据
                    h2h = game["bookmakers"][0]["markets"][0]["outcomes"]
                    spreads = game["bookmakers"][0]["markets"][1]["outcomes"]
                    totals = game["bookmakers"][0]["markets"][2]["outcomes"]
                    
                    matches.append({
                        "home": game["home_team"],
                        "away": game["away_team"],
                        "kickoff": game["commence_time"],
                        "win_odds": next(o["price"] for o in h2h if o["name"] == game["home_team"]),
                        "draw_odds": next(o["price"] for o in h2h if o["name"] == "Draw"),
                        "lose_odds": next(o["price"] for o in h2h if o["name"] == game["away_team"]),
                        "handicap": spreads[0]["point"],
                        "handicap_odds": spreads[0]["price"],
                        "over_under": totals[0]["point"],
                        "over_odds": totals[0]["price"],
                        "under_odds": totals[1]["price"]
                    })
        except Exception as e:
            print(f"拉取{league}数据失败: {str(e)}")
    return matches

# --------------------------
# 3. V8.0核心分析逻辑（适配真实赔率）
# --------------------------
def v8_analyze(match):
    analysis = {
        "match": f"{match['home']} vs {match['away']}",
        "kickoff": match["kickoff"],
        "prediction": None,
        "confidence": 0,
        "handicap_tip": "",
        "ou_tip": "",
        "tips": []
    }

    # 欧赔分析
    w, d, l = match["win_odds"], match["draw_odds"], match["lose_odds"]
    if w < d and w < l:
        analysis["prediction"] = "主胜"
        analysis["confidence"] = 70
    elif l < w and l < d:
        analysis["prediction"] = "客胜"
        analysis["confidence"] = 70
    else:
        analysis["prediction"] = "平局"
        analysis["confidence"] = 75
        analysis["tips"].append("⚠️ 平局概率偏高，需重点关注")

    # 亚盘/大小球建议
    analysis["handicap_tip"] = f"{match['home']} {match['handicap']}，倾向{'上盘' if match['handicap'] < 0 else '下盘'}"
    analysis["ou_tip"] = f"大小球{match['over_under']}，倾向{'大球' if match['over_odds'] < match['under_odds'] else '小球'}"

    # 庄套路识别
    if w > 2.0 and d < 3.3 and l > 3.0:
        analysis["tips"].append("⚠️ 疑似诱主，警惕平局或客胜")
    if w < 1.8 and l > 4.0:
        analysis["tips"].append("✅ 主胜基本面与机构态度一致，稳定性高")

    return analysis

# --------------------------
# 4. 发送邮件报告
# --------------------------
def send_email(analyses):
    if not analyses:
        return

    html = """
    <h1>⚽ V8.0 全自动足球分析报告（竞彩同源数据）</h1>
    <p>生成时间: {}</p>
    <hr>
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    for a in analyses:
        html += f"""
        <h2>{a['match']}</h2>
        <p>开球时间: {a['kickoff']}</p>
        <h3>📊 核心预测</h3>
        <p>结果: <strong>{a['prediction']}</strong></p>
        <p>置信度: {a['confidence']}%</p>
        
        <h3>📈 盘口建议</h3>
        <p>亚盘: {a['handicap_tip']}</p>
        <p>大小球: {a['ou_tip']}</p>
        
        <h3>⚠️ 风险提示</h3>
        <ul>
        """
        for tip in a["tips"]:
            html += f"<li>{tip}</li>"
        html += "</ul><hr>"

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = "V8.0 今日足球分析报告（竞彩同源数据）"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("✅ V8.0分析报告发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)}")

# --------------------------
# 主流程
# --------------------------
if __name__ == "__main__":
    print("=== 1. 拉取当日赛事+竞彩同源赔率 ===")
    matches = fetch_matches_with_odds()
    print(f"共拉取到{len(matches)}场比赛")

    print("=== 2. V8.0核心分析 ===")
    analyses = [v8_analyze(match) for match in matches]

    print("=== 3. 发送分析报告 ===")
    send_email(analyses)

    print("=== 流程结束，V8.0闭环运行完成 ===")
