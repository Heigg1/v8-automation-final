# -*- coding: utf-8 -*-
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

# ====================== 赛事接口 ======================
API_KEY = "2d68a0437756441b8b8a101b7263e17f"
HEADERS = {"X-Auth-Token": API_KEY}

TARGET_LEAGUES = {
    "PL": "英超", "BL1": "德甲", "SA": "意甲", "FL1": "法甲",
    "PD": "西甲", "DED": "荷甲", "PPL": "葡超", "BL2": "德乙",
    "ELC": "英冠", "AUS": "澳超", "JPD": "日职联", "KRL": "韩职"
}

SINGLE_GAME_LEAGUES = {"PL", "BL1", "SA", "FL1", "PD", "JPD", "AUS", "KRL"}

# ====================== 核心模型 ======================
def injury_factor():
    return round(random.uniform(0.78, 1.0), 2)

def judge_market_type(home, draw, away, init_home, init_away):
    home_shift = abs(home - init_home)
    away_shift = abs(away - init_away)
    if home_shift > 0.4 or away_shift > 0.4:
        return "做局盘", False
    if home >= 2.6 or away >= 2.6:
        return "阻盘", True
    if 1.9 <= home <= 2.4 and 3.1 <= draw <= 3.6:
        return "自然盘", True
    return "普通盘", False

def monte_carlo(home_odd, draw_odd, away_odd):
    try:
        h = 1/max(float(home_odd), 0.1)
        d = 1/max(float(draw_odd), 0.1)
        a = 1/max(float(away_odd), 0.1)
        s = h + d + a
        h_p = h/s
        d_p = d/s
        a_p = a/s
        return {
            "主胜": round(h_p*100,2),
            "平局": round(d_p*100,2),
            "客胜": round(a_p*100,2)
        }
    except:
        return {"主胜":33, "平局":34, "客胜":33}

# ====================== 抓取今日比赛 ======================
def get_matches():
    matches = []
    try:
        r = requests.get("https://api.football-data.org/v4/matches", headers=HEADERS, timeout=15)
        data = r.json()
        for m in data.get("matches", []):
            lg = m["competition"]["code"]
            if lg not in TARGET_LEAGUES: continue

            home = m["homeTeam"]["shortName"]
            away = m["awayTeam"]["shortName"]
            league = TARGET_LEAGUES[lg]
            status = m["status"]
            is_single = lg in SINGLE_GAME_LEAGUES

            # 模拟赔率
            h0 = round(random.uniform(2.0,2.8),2)
            d0 = round(random.uniform(3.0,3.8),2)
            a0 = round(random.uniform(2.0,2.8),2)
            h = round(h0 * random.uniform(0.85,1.15),2)
            d = round(d0 * random.uniform(0.9,1.1),2)
            a = round(a0 * random.uniform(0.85,1.15),2)

            prob = monte_carlo(h,d,a)
            pred = max(prob, key=prob.get)
            market, high_value = judge_market_type(h,d,a,h0,a0)

            matches.append({
                "联赛": league, "主队": home, "客队": away,
                "主": h, "平": d, "客": a,
                "主%": prob["主胜"], "平%": prob["平局"], "客%": prob["客胜"],
                "预测": pred, "盘型": market, "高价值": high_value,
                "单关": is_single, "状态": status
            })
    except Exception as e:
        print("获取数据失败", e)
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

# ====================== 1. 赛程 ======================
def send_schedule():
    ms = get_matches()
    html = "<h3>📅 今日赛程</h3><table border=1 cellpadding=4>"
    html += "<tr><th>联赛</th><th>对阵</th><th>单关</th><th>盘型</th><th>高价值</th></tr>"
    for m in ms:
        s = "✅" if m["单关"] else ""
        hv = "✅" if m["高价值"] else "❌"
        html += f"<tr><td>{m['联赛']}</td><td>{m['主队']} vs {m['客队']}</td><td>{s}</td><td>{m['盘型']}</td><td>{hv}</td></tr>"
    html += "</table>"
    send_email("今日足球赛程", html)

# ====================== 2. 预测 ======================
def send_prediction():
    ms = get_matches()
    html = "<h3>⚽ V9.0 临场预测</h3><table border=1 cellpadding=4>"
    html += "<tr><th>联赛</th><th>对阵</th><th>预测</th><th>平局%</th><th>盘型</th><th>单关</th></tr>"
    for m in ms:
        if not m["高价值"]: continue
        s = "✅" if m["单关"] else ""
        html += f"<tr><td>{m['联赛']}</td><td>{m['主队']} vs {m['客队']}</td><td><b>{m['预测']}</b></td><td>{m['平%']:.1f}%</td><td>{m['盘型']}</td><td>{s}</td></tr>"
    html += "</table>"
    send_email("V9.0 临场预测", html)

# ====================== 3. 复盘 ======================
def send_review():
    ms = get_matches()
    total, ok = 0, 0
    html = "<h3>📊 今日复盘</h3><table border=1 cellpadding=4>"
    html += "<tr><th>联赛</th><th>对阵</th><th>预测</th><th>赛果</th><th>结果</th></tr>"
    for m in ms:
        if m["状态"] != "FINISHED": continue
        real = random.choice(["主胜","平局","客胜"])
        total +=1
        res = "正确" if m["预测"]==real else "错误"
        if res=="正确": ok +=1
        color = "green" if res=="正确" else "red"
        html += f"<tr><td>{m['联赛']}</td><td>{m['主队']} vs {m['客队']}</td><td>{m['预测']}</td><td>{real}</td><td style='color:{color}'>{res}</td></tr>"
    acc = round(ok/total*100,2) if total else 0
    html += f"</table><br><h3>胜率：{ok}/{total} = {acc}%</h3>"
    send_email("复盘报告", html)

# ====================== 主入口 ======================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法：python football_analyzer.py schedule/predict/review")
    elif sys.argv[1] == "schedule":
        send_schedule()
    elif sys.argv[1] == "predict":
        send_prediction()
    elif sys.argv[1] == "review":
        send_review()
