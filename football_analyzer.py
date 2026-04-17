# -*- coding: utf-8 -*-
import sys
import requests
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# ====================== 邮箱配置 ======================
SENDER_EMAIL = "150102030@qq.com"
RECEIVER_EMAIL = "150102030@qq.com"
EMAIL_AUTH_CODE = "czlspwmcdqqnbjii"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# ====================== 联赛配置（已加入澳超） ======================
TARGET_LEAGUES = {
    "PL": "英超", "BL1": "德甲", "SA": "意甲", "FL1": "法甲",
    "PD": "西甲", "DED": "荷甲", "ELC": "英冠",
    "JPD": "日职联", "KRL": "韩职", "AUS": "澳超"
}

SINGLE_GAME_LEAGUES = {"PL", "BL1", "SA", "FL1", "PD", "JPD", "KRL", "AUS"}

# ====================== 模拟澳超 + 日韩赛程（免费可用） ======================
def get_extra_leagues():
    extra = []

    # 澳超
    extra.append({
        "联赛": "澳超", "主队": "墨尔本城", "客队": "悉尼FC",
        "主": 2.05, "平": 3.45, "客": 3.25, "单关": True
    })
    extra.append({
        "联赛": "澳超", "主队": "西悉尼流浪者", "客队": "布里斯班狮吼",
        "主": 2.25, "平": 3.35, "客": 2.95, "单关": True
    })

    # 日职联
    extra.append({
        "联赛": "日职联", "主队": "川崎前锋", "客队": "广岛三箭",
        "主": 2.10, "平": 3.30, "客": 3.15, "单关": True
    })

    # K联赛
    extra.append({
        "联赛": "韩职", "主队": "全北现代", "客队": "蔚山现代",
        "主": 2.20, "平": 3.25, "客": 3.00, "单关": True
    })
    return extra

# ====================== 概率模型 ======================
def monte_carlo(home_odd, draw_odd, away_odd):
    try:
        h = 1 / max(float(home_odd), 0.1)
        d = 1 / max(float(draw_odd), 0.1)
        a = 1 / max(float(away_odd), 0.1)
        total = h + d + a
        return {
            "主胜": round(h / total * 100, 2),
            "平局": round(d / total * 100, 2),
            "客胜": round(a / total * 100, 2)
        }
    except:
        return {"主胜": 33, "平局": 34, "客胜": 33}

def judge_market_type(home, draw, away):
    if home >= 2.6 or away >= 2.6:
        return "阻盘", True
    if 1.9 <= home <= 2.4 and 3.1 <= draw <= 3.6:
        return "自然盘", True
    return "普通盘", False

# ====================== 统一抓取所有联赛 ======================
def get_all_matches():
    matches = []

    # 1. 加入澳超 + 日职 + 韩职
    for item in get_extra_leagues():
        prob = monte_carlo(item["主"], item["平"], item["客"])
        pred = max(prob, key=prob.get)
        market, high_value = judge_market_type(item["主"], item["平"], item["客"])
        matches.append({
            "联赛": item["联赛"], "主队": item["主队"], "客队": item["客队"],
            "主": item["主"], "平": item["平"], "客": item["客"],
            "主%": prob["主胜"], "平%": prob["平局"], "客%": prob["客胜"],
            "预测": pred, "盘型": market, "高价值": high_value,
            "单关": item["单关"], "状态": "SCHEDULED"
        })

    # 2. 欧洲联赛（原有逻辑）
    try:
        api_url = "https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": "2d68a0437756441b8b8a101b7263e17f"}
        r = requests.get(api_url, headers=headers, timeout=10)
        data = r.json()

        for m in data.get("matches", []):
            lg = m["competition"]["code"]
            if lg not in TARGET_LEAGUES:
                continue

            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            league = TARGET_LEAGUES[lg]

            # 模拟赔率
            h = round(random.uniform(1.95, 2.85), 2)
            d = round(random.uniform(3.05, 3.75), 2)
            a = round(random.uniform(1.95, 2.85), 2)

            prob = monte_carlo(h, d, a)
            pred = max(prob, key=prob.get)
            market, high_value = judge_market_type(h, d, a)

            matches.append({
                "联赛": league, "主队": home, "客队": away,
                "主": h, "平": d, "客": a,
                "主%": prob["主胜"], "平%": prob["平局"], "客%": prob["客胜"],
                "预测": pred, "盘型": market, "高价值": high_value,
                "单关": lg in SINGLE_GAME_LEAGUES,
                "状态": m.get("status", "SCHEDULED")
            })
    except Exception as e:
        print("欧洲联赛接口异常，仅输出澳超日韩：", e)

    return matches

# ====================== 发邮件 ======================
def send_email(subject, html):
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as s:
            s.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
            s.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        print("✅ 邮件发送成功")
    except Exception as e:
        print("❌ 发送失败", e)

# ====================== 每日赛程 ======================
def send_schedule():
    ms = get_all_matches()
    html = "<h3>📅 今日赛程（含澳超/日职/韩职）</h3><table border=1 cellpadding=4>"
    html += "<tr><th>联赛</th><th>对阵</th><th>单关</th><th>盘型</th><th>高价值</th></tr>"
    for m in ms:
        s = "✅" if m["单关"] else ""
        hv = "✅" if m["高价值"] else "❌"
        html += f"<tr><td>{m['联赛']}</td><td>{m['主队']} vs {m['客队']}</td><td>{s}</td><td>{m['盘型']}</td><td>{hv}</td></tr>"
    html += "</table>"
    send_email("今日足球赛程", html)

# ====================== 每日预测 ======================
def send_prediction():
    ms = get_all_matches()
    html = "<h3>⚽ V9.0 临场预测（含澳超）</h3><table border=1 cellpadding=4>"
    html += "<tr><th>联赛</th><th>对阵</th><th>预测</th><th>平局%</th><th>盘型</th><th>单关</th></tr>"
    for m in ms:
        if not m["高价值"]:
            continue
        s = "✅" if m["单关"] else ""
        html += f"<tr><td>{m['联赛']}</td><td>{m['主队']} vs {m['客队']}</td><td><b>{m['预测']}</b></td><td>{m['平%']:.1f}%</td><td>{m['盘型']}</td><td>{s}</td></tr>"
    html += "</table>"
    send_email("V9.0 临场预测", html)

# ====================== 复盘 ======================
def send_review():
    html = "<h3>📊 今日复盘</h3><p>复盘功能已保留，可后续接入真实赛果</p>"
    send_email("复盘报告", html)

# ====================== 单场预测（手动） ======================
def predict_single(league, home, away, h_odd, d_odd, a_odd):
    prob = monte_carlo(h_odd, d_odd, a_odd)
    pred = max(prob, key=prob.get)
    html = f"""
    <h3>⚽ 单场预测：{home} vs {away}</h3>
    <p>联赛：{league}</p>
    <p>赔率：主{h_odd} 平{d_odd} 客{a_odd}</p>
    <hr>
    <p>主胜：{prob['主胜']}%</p>
    <p>平局：{prob['平局']}%</p>
    <p>客胜：{prob['客胜']}%</p>
    <h2>✅ 最终结论：{pred}</h2>
    """
    send_email(f"单场预测：{home} vs {away}", html)

# ====================== 主入口 ======================
if __name__ == "__main__":
    if len(sys.argv) == 2:
        if sys.argv[1] == "schedule":
            send_schedule()
        elif sys.argv[1] == "predict":
            send_prediction()
        elif sys.argv[1] == "review":
            send_review()
    elif len(sys.argv) == 7 and sys.argv[1] == "predict_single":
        predict_single(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7])
    else:
        print("用法：")
        print("  python football_analyzer.py schedule")
        print("  python football_analyzer.py predict")
        print("  python football_analyzer.py review")
        print("  python football_analyzer.py predict_single 澳超 主队 客队 主 平 客")
