import requests
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os

# --------------------------
# 配置信息（从GitHub Secrets读取）
# --------------------------
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# Football-Data.org API（免费无密钥）
BASE_URL = "https://api.football-data.org/v4"
# 主流联赛代码：PL=英超，BL1=德甲，SA=意甲，PD=西甲，FL1=法甲，AUS=澳超
LEAGUES = ["PL", "BL1", "SA", "PD", "FL1", "AUS"]

# --------------------------
# 1. 拉取当日赛程
# --------------------------
def fetch_matches():
    headers = {"X-Auth-Token": ""}  # 免费版留空即可
    matches = []
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    for league in LEAGUES:
        url = f"{BASE_URL}/competitions/{league}/matches?dateFrom={today}&dateTo={tomorrow}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            for match in data.get("matches", []):
                matches.append({
                    "id": match["id"],
                    "league": league,
                    "home_team": match["homeTeam"]["name"],
                    "away_team": match["awayTeam"]["name"],
                    "kickoff": match["utcDate"],
                    "status": match["status"]
                })
        except Exception as e:
            print(f"拉取{league}赛程失败: {str(e)}")
    return matches

# --------------------------
# 2. V8.0精简分析逻辑（胜平负+亚盘/大小球建议）
# --------------------------
def analyze_match(match):
    # 这里是V8.0的基础分析框架，你可以后续自行扩展赔率、伤停等逻辑
    analysis = {
        "match_id": match["id"],
        "home": match["home_team"],
        "away": match["away_team"],
        "kickoff": match["kickoff"],
        "prediction": None,
        "confidence": 0,
        "tips": []
    }

    # 示例：简单的基本面分析（后续可替换为你的自进化逻辑）
    analysis["prediction"] = "暂未获取完整数据，建议赛前45分钟再看分析"
    analysis["tips"].append("⚠️  免费API无实时赔率，建议结合竞彩网数据交叉验证")
    return analysis

# --------------------------
# 3. 发送邮件报告
# --------------------------
def send_email(analyses):
    if not analyses:
        return

    html = """
    <h2>⚽ 今日足球分析报告（V8.0精简版）</h2>
    <hr>
    """
    for a in analyses:
        html += f"""
        <h3>{a['home']} vs {a['away']}</h3>
        <p>开球时间: {a['kickoff']}</p>
        <p>预测结果: {a['prediction']}</p>
        <p>置信度: {a['confidence']}%</p>
        <ul>
        """
        for tip in a["tips"]:
            html += f"<li>{tip}</li>"
        html += "</ul><hr>"

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = "今日足球分析报告"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {str(e)}")

# --------------------------
# 主流程
# --------------------------
if __name__ == "__main__":
    print("=== 开始拉取赛程 ===")
    matches = fetch_matches()
    print(f"共拉取到{len(matches)}场比赛")

    print("=== 开始V8.0分析 ===")
    analyses = [analyze_match(m) for m in matches]

    print("=== 发送分析报告 ===")
    send_email(analyses)

    print("=== 流程结束 ===")
