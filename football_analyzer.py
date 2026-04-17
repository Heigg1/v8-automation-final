# -*- coding: utf-8 -*-
import requests
import json
import random
import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText

# ====================== 你的固定配置 ======================
SENDER_EMAIL = "150102030@qq.com"
EMAIL_AUTH_CODE = "czlspwmcdqqnbjii"
RECEIVER_EMAIL = "150102030@qq.com"

API_KEY = "2d68a0437756441b8b8a101b7263e17f"
HEADERS = {"X-Auth-Token": API_KEY}

SINGLE_LEAGUES = {"PL", "BL1", "SA", "FL1", "DED"}

# ====================== 蒙特卡洛赔率模型 ======================
def monte_carlo(home, draw, away, sims=3000):
    try:
        h = 1/float(home)
        d = 1/float(draw)
        a = 1/float(away)
        total = h+d+a
        h /= total
        d /= total
        a /= total

        ch, cd, ca = 0,0,0
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
        return {"主胜":0,"平局":0,"客胜":0}

# ====================== API1：今日赛事 ======================
def get_today_matches():
    try:
        res = requests.get("https://api.football-data.org/v4/matches", headers=HEADERS, timeout=15)
        matches = []
        for m in res.json().get("matches", []):
            if m["status"] in ["SCHEDULED","TIMED","IN_PLAY","PAUSED","FINISHED"]:
                c = m["competition"]["code"]
                matches.append({
                    "id": m["id"],
                    "home": m["homeTeam"]["name"],
                    "away": m["awayTeam"]["name"],
                    "status": m["status"],
                    "result": m.get("score",{}).get("fullTime",{}),
                    "league": c,
                    "is_single": c in SINGLE_LEAGUES
                })
        return matches
    except:
        return []

# ====================== API2：真实赔率 ======================
def get_odds(mid):
    try:
        res = requests.get(f"https://api.football-data.org/v4/odds/{mid}", headers=HEADERS, timeout=10)
        o = res.json().get("odds",[{}])[0]
        return {
            "home": o.get("homeWin",2.5),
            "draw": o.get("draw",3.2),
            "away": o.get("awayWin",2.7)
        }
    except:
        return {"home":2.5,"draw":3.2,"away":2.7}

# ====================== 生成预测 ======================
def make_predict(matches):
    res = []
    for m in matches:
        if m["status"] != "SCHEDULED" and m["status"] != "TIMED":
            continue
        od = get_odds(m["id"])
        prob = monte_carlo(od["home"], od["draw"], od["away"])
        pred = max(prob, key=prob.get)
        res.append({
            "home": m["home"],
            "away": m["away"],
            "pred": pred,
            "draw_rate": prob["平局"],
            "is_single": m["is_single"],
            "match_id": m["id"]
        })
    return res

# ====================== 真实赛果自动对比（核心进化） ======================
def check_real_results(matches):
    correct = 0
    draw_correct = 0
    total = 0
    detail = []

    for m in matches:
        if m["status"] != "FINISHED":
            continue

        h = m["result"].get("homeTeam")
        a = m["result"].get("awayTeam")
        if h is None or a is None:
            continue

        # 真实赛果
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
            draw_correct +=1

        detail.append({
            "home": m["home"],
            "away": m["away"],
            "pred": pred,
            "real": real,
            "correct": ok
        })

    hit_rate = round(correct/total*100,2) if total>0 else 0
    return correct, draw_correct, total, hit_rate, detail

# ====================== 发邮件 ======================
def send(title, body):
    msg = MIMEText(body, "html", "utf-8")
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
        send("今日无赛事", "暂无比赛")
        return

    # ---------- 1. 今日赛程 ----------
    html1 = "<h3>📅 今日赛事</h3>"
    for m in matches:
        s = m["status"]
        if s == "FINISHED":
            st = "已结束"
        elif s in ["IN_PLAY","PAUSED"]:
            st = "进行中"
        else:
            st = "未开始"
        html1 += f"<p>{m['home']} vs {m['away']} {st} {'【单关】' if m['is_single'] else ''}</p>"
    send("今日赛程", html1)

    # ---------- 2. 赛前预测 ----------
    preds = make_predict(matches)
    html2 = "<h3>⚽ V9.0 预测</h3>"
    for p in preds:
        html2 += f"<p>{p['home']} vs {p['away']} → 预测：{p['pred']} | 平局概率：{p['draw_rate']}% {'【单关】' if p['is_single'] else ''}</p>"
    send("今日预测", html2)

    # ---------- 3. 真实赛果复盘（自动对比） ----------
    correct, draw_correct, total, hit_rate, details = check_real_results(matches)

    html3 = f"""
<h3>📊 V9.0 真实赛果复盘</h3>
<p>已完赛场次：{total}</p>
<p>预测正确：{correct}</p>
<p>总命中率：{hit_rate}%</p>
<p>平局命中：{draw_correct}</p>
<hr>
"""
    for d in details:
        ok = "✅ 正确" if d["correct"] else "❌ 错误"
        html3 += f"<p>{d['home']} vs {d['away']} | 预测：{d['pred']} | 真实：{d['real']} {ok}</p>"

    send("V9.0 真实赛果复盘", html3)

if __name__ == "__main__":
    main()
