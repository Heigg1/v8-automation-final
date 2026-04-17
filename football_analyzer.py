# -*- coding: utf-8 -*-
import requests
import random
import smtplib
from email.mime.text import MIMEText

# ====================== 你的配置 ======================
SENDER_EMAIL = "150102030@qq.com"
EMAIL_AUTH_CODE = "czlspwmcdqqnbjii"
RECEIVER_EMAIL = "150102030@qq.com"

API_KEY = "2d68a0437756441b8b8a101b7263e17f"
HEADERS = {"X-Auth-Token": API_KEY}

# 竞彩单关主流联赛
SINGLE_LEAGUES = {"PL", "BL1", "SA", "FL1", "DED", "PD", "PPL", "BSA", "CLB", "MEX", "ARG", "TUR", "URS"}

# ====================== 竞彩网标准联赛中文映射 ======================
LEAGUE_CN = {
    "PL": "英超",
    "BL1": "德甲",
    "SA": "意甲",
    "FL1": "法甲",
    "DED": "荷甲",
    "PD": "西甲",
    "PPL": "葡超",
    "BSA": "巴甲",
    "CLB": "哥伦甲",
    "MEX": "墨超",
    "ARG": "阿超",
    "URS": "乌超",
    "TUR": "土超",
    "CL": "欧冠",
    "EL": "欧联",
    "EC": "欧协联"
}

# ====================== 球队中文名称 ======================
TEAM_CN = {
    "US Sassuolo Calcio": "萨索洛",
    "Como 1907": "科莫",
    "1. FC Köln": "科隆",
    "FC St. Pauli 1910": "圣保利",
    "FC Internazionale Milano": "国际米兰",
    "Cagliari Calcio": "卡利亚里",
    "Racing Club de Lens": "朗斯",
    "Toulouse FC": "图卢兹",
    "Blackburn Rovers FC": "布莱克本",
    "Coventry City FC": "考文垂",
    "Rio Ave FC": "里奥阿维",
    "AVS": "阿维斯",
    "Arsenal FC": "阿森纳",
    "Liverpool FC": "利物浦",
    "Manchester United FC": "曼联",
    "Manchester City FC": "曼城",
    "Chelsea FC": "切尔西",
    "Tottenham Hotspur FC": "热刺",
    "FC Bayern München": "拜仁",
    "Borussia Dortmund": "多特",
    "FC Barcelona": "巴萨",
    "Real Madrid CF": "皇马",
    "Atlético Madrid": "马竞",
    "Juventus FC": "尤文",
    "AC Milan": "AC米兰",
    "SSC Napoli": "那不勒斯"
}

def team_cn(name):
    return TEAM_CN.get(name, name)

def league_cn(code):
    return LEAGUE_CN.get(code, code)

# ====================== 蒙特卡洛概率模型 ======================
def monte_carlo(home, draw, away, sims=3000):
    try:
        h = 1/float(home)
        d = 1/float(draw)
        a = 1/float(away)
        total = h + d + a
        h /= total
        d /= total
        a /= total
        ch, cd, ca = 0, 0, 0
        for _ in range(sims):
            r = random.random()
            if r < h:
                ch +=1
            elif r < h+d:
                cd +=1
            else:
                ca +=1
        s = ch+cd+ca
        return {
            "主胜": round(ch/s*100,2),
            "平局": round(cd/s*100,2),
            "客胜": round(ca/s*100,2)
        }
    except:
        return {"主胜":0, "平局":0, "客胜":0}

# ====================== 获取今日赛事 ======================
def get_today_matches():
    try:
        res = requests.get("https://api.football-data.org/v4/matches", headers=HEADERS, timeout=15)
        matches = []
        for m in res.json().get("matches", []):
            if m["status"] in ["SCHEDULED","TIMED","IN_PLAY","PAUSED","FINISHED"]:
                c = m["competition"]["code"]
                matches.append({
                    "id": m["id"],
                    "home": team_cn(m["homeTeam"]["name"]),
                    "away": team_cn(m["awayTeam"]["name"]),
                    "league": league_cn(c),
                    "status": m["status"],
                    "result": m.get("score",{}).get("fullTime",{}),
                    "is_single": c in SINGLE_LEAGUES
                })
        return matches
    except:
        return []

# ====================== 获取赔率 ======================
def get_odds(mid):
    try:
        res = requests.get(f"https://api.football-data.org/v4/odds/{mid}", headers=HEADERS, timeout=10)
        o = res.json().get("odds",[{}])[0]
        return {"home": o.get("homeWin",2.5), "draw": o.get("draw",3.2), "away": o.get("awayWin",2.7)}
    except:
        return {"home":2.5,"draw":3.2,"away":2.7}

# ====================== 生成预测 ======================
def make_predict(matches):
    res = []
    for m in matches:
        if m["status"] not in ["SCHEDULED","TIMED"]:
            continue
        od = get_odds(m["id"])
        prob = monte_carlo(od["home"], od["draw"], od["away"])
        pred = max(prob, key=prob.get)
        res.append({
            "home": m["home"],
            "away": m["away"],
            "league": m["league"],
            "pred": pred,
            "draw_rate": prob["平局"],
            "is_single": m["is_single"]
        })
    return res

# ====================== 复盘赛果 ======================
def check_results(matches):
    correct = 0
    draw_ok = 0
    total = 0
    detail = []
    for m in matches:
        if m["status"] != "FINISHED":
            continue
        h = m["result"].get("homeTeam")
        a = m["result"].get("awayTeam")
        if h is None or a is None:
            continue
        if h > a:
            real = "主胜"
        elif h < a:
            real = "客胜"
        else:
            real = "平局"
        od = get_odds(m["id"])
        prob = monte_carlo(od["home"], od["draw"], od["away"])
        pred = max(prob, key=prob.get)
        total +=1
        ok = (pred == real)
        if ok:
            correct +=1
        if real == "平局" and pred == "平局":
            draw_ok +=1
        detail.append({
            "home": m["home"],
            "away": m["away"],
            "pred": pred,
            "real": real,
            "correct": ok
        })
    hit = round(correct/total*100,2) if total>0 else 0
    return correct, draw_ok, total, hit, detail

# ====================== 发邮件 ======================
def send(title, html):
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = title
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
            s.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
            s.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
    except:
        pass

# ====================== 主程序 ======================
def main():
    matches = get_today_matches()
    if not matches:
        send("今日无赛事", "<p>暂无比赛</p>")
        return

    # 1. 赛程
    html1 = f"""
<div style="padding:15px; font-family:Arial; background:#f5f5f5; border-radius:8px;">
<h2 style="border-bottom:2px solid #4285F4; padding-bottom:8px;">📅 今日赛程</h2>
"""
    for m in matches:
        st = {"FINISHED":"✅已结束","IN_PLAY":"⚽进行中","PAUSED":"⏸暂停"}.get(m["status"],"⏳未开始")
        tag = "<span style='color:red; font-weight:bold;'>【单关】</span>" if m["is_single"] else ""
        html1 += f"<p>{m['league']}｜{m['home']} vs {m['away']} {st} {tag}</p>"
    html1 += "</div>"
    send("今日赛程", html1)

    # 2. 预测
    preds = make_predict(matches)
    html2 = f"""
<div style="padding:15px; font-family:Arial; background:#f5f5f5; border-radius:8px;">
<h2 style="border-bottom:2px solid #FF9800; padding-bottom:8px;">⚽ V9.0 赛前预测</h2>
<table width="100%" border="1" cellspacing="0" cellpadding="6">
<tr style="background:#eee;"><th>联赛</th><th>对阵</th><th>预测</th><th>平局概率</th><th>类型</th></tr>
"""
    for p in preds:
        t = "【单关】" if p["is_single"] else "普通"
        html2 += f"<tr><td>{p['league']}</td><td>{p['home']} vs {p['away']}</td><td>{p['pred']}</td><td>{p['draw_rate']}%</td><td>{t}</td></tr>"
    html2 += "</table></div>"
    send("今日赛事预测", html2)

    # 3. 复盘
    correct, draw_ok, total, hit, details = check_results(matches)
    html3 = f"""
<div style="padding:15px; font-family:Arial; background:#f5f5f5; border-radius:8px;">
<h2 style="border-bottom:2px solid #0F9D58; padding-bottom:8px;">📊 赛果复盘</h2>
<p>完赛场次：{total}　正确：{correct}　命中率：{hit}%</p>
<p>平局命中：{draw_ok}</p>
<hr>
"""
    for d in details:
        ok = "✅正确" if d["correct"] else "❌错误"
        html3 += f"<p>{d['home']} vs {d['away']}｜预测：{d['pred']}｜真实：{d['real']} {ok}</p>"
    html3 += "</div>"
    send("V9.0 复盘报告", html3)

if __name__ == "__main__":
    main()
