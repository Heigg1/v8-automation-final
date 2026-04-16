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

# 历史盘路平局率
league_draw_rate = {
    "欧罗巴": 28.5,
    "澳超": 26.0,
    "英超": 25.2,
    "西甲": 24.8,
    "意甲": 26.1,
    "德甲": 23.5,
    "法甲": 27.3,
    "默认": 25.0
}

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

def fetch_match_result(home, away, match_time_str):
    try:
        match_time = datetime.strptime(match_time_str, "%Y-%m-%d %H:%M")
        now = datetime.now()
        if match_time >= now:
            return None
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
        return "【数据错误】", "未知", "低", "", ""

    is_single = match.get("is_single", "否")
    league = match.get("league", "默认")

    # 基础概率计算
    wp = 1/win
    dp = 1/draw
    lp = 1/lose
    total = wp + dp + lp
    wp = round(wp/total*100,1)
    dp = round(dp/total*100,1)
    lp = round(lp/total*100,1)

    # 人性盘识别
    pattern = "自然盘"
    human_analysis = "无明显人性诱盘痕迹"
    risk_level = "低"

    if win < 1.6:
        pattern = "热门诱盘"
        dp += 5.0
        human_analysis = "⚠️ 热门低赔诱盘：主胜赔率过低，易吸引散户无脑投注，庄家控盘风险高，平局概率显著提升"
        risk_level = "高"
        if is_single == "是":
            pattern += "(单关风控)"
            dp += 3.0
            human_analysis = "🚨 单关热门诱盘：单关赛事投注量大，庄家有极强动机做局，平局是平衡投注量的最优结果，需重点防平"
            risk_level = "极高"

    league_draw = league_draw_rate.get(league, league_draw_rate["默认"])
    if dp >= league_draw + 3:
        pattern = "平局倾向盘"
        human_analysis = f"📊 历史盘路匹配：该联赛平局打出率约为{league_draw}%，本场平局赔率下的隐含概率({dp}%)显著高于联赛平均水平，平局打出概率偏高"
        risk_level = "中"

    # 推荐逻辑
    if dp >= 30:
        suggestion = "平"
    elif win < 1.8 and risk_level != "极高":
        suggestion = "胜"
    else:
        suggestion = "平/胜"

    report = f"""
【场次】{match['match_id']} {match['home']} vs {match['away']}
时间：{match['match_time']}
联赛：{league}
赔率：胜{win} 平{draw} 负{lose}
单关：{is_single}
基础概率：胜{wp}% 平{dp}% 负{lp}%
盘口形态：{pattern}
人性盘分析：{human_analysis}
风险等级：{risk_level}
推荐方向：{suggestion}
"""
    return report, suggestion, risk_level, pattern, human_analysis, dp

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    matches = load_db()
    if not matches:
        send_email(f"【V8.0全自动分析+复盘报告】{now}\n暂无比赛数据，请上传竞彩截图")
        return

    full_report = f"【V8.0全自动分析+复盘报告】{now}\n\n"
    updated = False

    for m in matches:
        report, suggestion, risk_level, pattern, human_analysis, dp = analyze(m)
        full_report += report

        # 只对已结束的比赛复盘
        if not m.get("final_result"):
            res = fetch_match_result(m["home"], m["away"], m["match_time"])
            if res:
                m["final_result"] = res
                m["hit_status"] = "命中" if suggestion == res else "未命中"
                m["review"] = "自动复盘完成"
                m["pattern_type"] = pattern
                m["human_analysis"] = human_analysis
                m["draw_prob"] = dp
                updated = True
                full_report += f"【赛果更新】实际结果：{res} | 本次预测：{m['hit_status']}\n"

        full_report += "-" * 50 + "\n"

    if updated:
        save_db(matches)

    send_email(full_report)
    print("✅ V8.0 稳定版分析+复盘完成，邮件已发送")

if __name__ == "__main__":
    main()
