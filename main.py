import csv
import smtplib
import requests
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

# ============ 配置 ============
SENDER_EMAIL = "150102030@qq.com"
SENDER_PASSWORD = "czlspwmcdqqnbjii"
RECEIVER_EMAIL = "150102030@qq.com"
DB_FILE = "v8_database.csv"
API_URL = "https://www.thesportsdb.com/api/v1/json/3/"

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

def fetch_match_result(home, away):
    try:
        res = requests.get(f"{API_URL}searchteams.php?t={home}").json()
        if not res.get("teams"):
            return None
        team_id = res["teams"][0]["idTeam"]
        events = requests.get(f"{API_URL}eventslast.php?id={team_id}").json()
        for ev in events.get("events", []):
            if ev.get("strHomeTeam") == home and ev.get("strAwayTeam") == away:
                hg = ev.get("intHomeScore")
                ag = ev.get("intAwayScore")
                if hg is not None and ag is not None:
                    if hg > ag:
                        return "胜"
                    elif hg < ag:
                        return "负"
                    else:
                        return "平"
        return None
    except:
        return None

def analyze(match):
    try:
        win = float(match["jc_win"])
        draw = float(match["jc_draw"])
        lose = float(match["jc_lose"])
    except:
        return "【数据错误】", "未知"

    is_single = match.get("is_single", "否")
    wp = 1/win
    dp = 1/draw
    lp = 1/lose
    total = wp + dp + lp
    wp = round(wp/total*100,1)
    dp = round(dp/total*100,1)
    lp = round(lp/total*100,1)

    pattern = "自然盘"
    if win < 1.6:
        pattern = "热门诱盘"
    if is_single == "是":
        pattern += "(单关风控)"

    if dp >= 30:
        suggestion = "平"
    elif win < 1.8:
        suggestion = "胜"
    else:
        suggestion = "负"

    report = f"""
【场次】{match['match_id']} {match['home']} vs {match['away']}
时间：{match['match_time']}
赔率：胜{win} 平{draw} 负{lose}
单关：{is_single}
概率：胜{wp}% 平{dp}% 负{lp}%
形态：{pattern}
推荐：{suggestion}
"""
    return report, suggestion

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    matches = load_db()
    if not matches:
        send_email(f"【V8.0全自动分析+复盘报告】{now}\n暂无比赛数据")
        return

    full_report = f"【V8.0全自动分析+复盘报告】{now}\n\n"
    updated = False

    for m in matches:
        report, suggestion = analyze(m)
        full_report += report

        # 自动复盘
        if not m.get("final_result"):
            res = fetch_match_result(m["home"], m["away"])
            if res:
                m["final_result"] = res
                m["hit_status"] = "命中" if suggestion == res else "未命中"
                m["review"] = "自动复盘完成"
                updated = True
                full_report += f"【赛果】{res} | {m['hit_status']}\n"

        full_report += "-" * 40 + "\n"

    if updated:
        save_db(matches)

    send_email(full_report)

if __name__ == "__main__":
    main()
