import csv
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

# ============ 配置 ============
SENDER_EMAIL = "150102030@qq.com"
SENDER_PASSWORD = "czlspwmcdqqnbjii"
RECEIVER_EMAIL = "150102030@qq.com"
DB_FILE = "v8_database.csv"

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

def analyze(match):
    win = float(match['jc_win'])
    draw = float(match['jc_draw'])
    lose = float(match['jc_lose'])
    is_single = match['is_single']

    wp = 1 / win
    dp = 1 / draw
    lp = 1 / lose
    total = wp + dp + lp
    wp = round(wp / total * 100, 1)
    dp = round(dp / total * 100, 1)
    lp = round(lp / total * 100, 1)

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
开赛时间: {match['match_time']}
竞彩胜平负: 胜{win} | 平{draw} | 负{lose}
单关标识: {is_single}
概率分布: 胜{wp}% | 平{dp}% | 负{lp}%
盘口形态: {pattern}
最终结论: {suggestion}
"""
    return report

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    matches = load_db()
    if not matches:
        send_email(f"【V8.0全自动分析+复盘报告】{now}\n暂无比赛数据，请上传竞彩截图，由豆包录入。")
        return

    full_report = f"【V8.0全自动分析+复盘报告】{now}\n\n"
    for match in matches:
        full_report += analyze(match) + "\n" + "-"*30 + "\n"

    send_email(full_report)
    print("✅ 分析完成，邮件已发送")

if __name__ == "__main__":
    main()
