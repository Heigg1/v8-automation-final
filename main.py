import csv
import smtplib
import requests
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime
import os

# ====================== 配置 ======================
SENDER_EMAIL = "150102030@qq.com"
SENDER_PASSWORD = "czlspwmcdqqnbjii"
RECEIVER_EMAIL = "150102030@qq.com"
DB_FILE = "v8_database.csv"
# 免费API，无需注册
API_URL = "https://www.thesportsdb.com/api/v1/json/3/"
# ===================================================

def send_email(content):
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = Header("V8.0自进化破庄神器", 'utf-8')
    msg['To'] = Header("用户", 'utf-8')
    msg['Subject'] = Header("【V8.0全自动分析+复盘报告】", 'utf-8')
    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 发邮件失败: {e}")

def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except:
        return []

def save_db(rows):
    headers = [
        "match_id","league","home","away","match_time",
        "jc_win","jc_draw","jc_lose",
        "handicap","hcp_win","hcp_draw","hcp_lose",
        "over_under","over","under","is_single",
        "basic_analysis","handicap_analysis","human_analysis",
        "pattern_type","draw_prob","final_result","review","hit_status"
    ]
    with open(DB_FILE, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)

def fetch_live_match(home, away):
    """从免费API抓取比赛数据"""
    try:
        res = requests.get(f"{API_URL}searchteams.php?t={home}").json()
        if res['teams']:
            team_id = res['teams'][0]['idTeam']
            matches = requests.get(f"{API_URL}eventslast.php?id={team_id}").json()
            return matches['events']
    except:
        return None

def analyze(match):
    win = float(match['jc_win'])
    draw = float(match['jc_draw'])
    lose = float(match['jc_lose'])
    is_single = match['is_single']

    wp = 1/win
    dp = 1/draw
    lp = 1/lose
    total = wp+dp+lp
    wp = round(wp/total*100,1)
    dp = round(dp/total*100,1)
    lp = round(lp/total*100,1)

    pattern = "自然盘"
    if win < 1.6: pattern = "热门诱盘"
    if is_single == "是": pattern += "(单关风控)"

    suggestion = "平" if dp >= 30 else ("胜" if win < 1.8 else "负")

    return (f"""
【场次】{match['match_id']} {match['home']} vs {match['away']}
【时间】{match['match_time']}
【赔率】胜{win} 平{draw} 负{lose}
【单关】{is_single}
【概率】胜{wp}% 平{dp}% 负{lp}%
【形态】{pattern}
【结论】{suggestion}
""", suggestion, dp, pattern)

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = load_db()
    if not rows:
        send_email(f"【V8.0 全自动分析+复盘报告】{now}\n暂无比赛数据，请通过指令添加比赛。")
        return

    full_report = f"【V8.0 全自动分析+复盘报告】{now}\n\n"
    updated = False

    for match in rows:
        report, sug, dp, pattern = analyze(match)
        match['basic_analysis'] = report
        match['draw_prob'] = str(dp)
        match['pattern_type'] = pattern
        full_report += report + "\n" + "-"*30 + "\n"

        # 自动抓取赛果并复盘
        if not match.get('final_result'):
            events = fetch_live_match(match['home'], match['away'])
            if events:
                for event in events:
                    if event['strHomeTeam'] == match['home'] and event['strAwayTeam'] == match['away']:
                        home_goals = event['intHomeScore']
                        away_goals = event['intAwayScore']
                        if home_goals is not None and away_goals is not None:
                            if home_goals > away_goals:
                                result = "胜"
                            elif home_goals < away_goals:
                                result = "负"
                            else:
                                result = "平"
                            match['final_result'] = result
                            match['hit_status'] = "命中" if sug == result else "未命中"
                            match['review'] = "自动复盘完成"
                            updated = True
                        break

    if updated:
        save_db(rows)
    send_email(full_report)
    print("✅ 全自动分析+复盘完成")

if __name__ == "__main__":
    main()
