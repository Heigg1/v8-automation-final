import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import json
import math

# ====================== 核心配置 ======================
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "150102030@qq.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "czlspwmcdqqnbjii")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "150102030@qq.com")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")

HIGH_LEAGUES = ["soccer_epl", "soccer_bundesliga", "soccer_serie_a", "soccer_laliga", "soccer_ligue_1"]
ALL_LEAGUES = HIGH_LEAGUES + [
    "soccer_efl_championship", "soccer_eredivisie",
    "soccer_japan_j_league", "soccer_korea_k_league1",
    "soccer_europa_league", "soccer_afc_champions_league"
]

# 数据库文件（用新的文件名，避免和旧文件冲突）
DB_FILE = "v99_evolution_db.json"

# ====================== 基础工具（修复版） ======================
def init_system_db():
    if not os.path.exists(DB_FILE):
        base = {"total":0, "correct":0, "draw_correct":0, "matches":[], "sent_live":{}}
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)

def load_system_db():
    # 找不到文件时，先创建再加载
    init_system_db()
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_system_db(db_obj):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db_obj, f, ensure_ascii=False, indent=2)

def send_email_report(subject, body):
    try:
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        server.quit()
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# ====================== V9.9 终极核心模型 ======================
# 1. 平局概率评分
def calc_draw_score(h, d, a):
    score = 0.0
    if abs(d - min(h, a)) < 0.25: score += 0.35
    if abs(h - a) < 0.15: score += 0.25
    if 3.0 <= d <= 3.6: score += 0.2
    if d < 3.3 and abs(h - a) > 0.7: score += 0.25
    return round(min(score, 1.0), 2)

# 2. 做局识别（防AI反杀）
def detect_trap(h, d, a):
    if (h < 1.9 or a < 1.9) and d > 4.2: return True
    if abs(h - a) < 0.1 and d > 4.0: return True
    if abs(h - a) > 1.5 and d < 2.9: return True
    return False

# 3. 战意强度
def get_moral_weight(h, a):
    w = 0.5
    if h < 1.8: w += 0.2
    if a < 1.8: w += 0.2
    if abs(h - a) > 1.2: w += 0.15
    return round(w, 2)

# 4. 盘型分类
def get_panel_type(h, d, a):
    if h < 1.6: return "深主"
    if a < 1.6: return "深客"
    if abs(h - a) < 0.2: return "浅盘"
    return "中盘"

# 5. 球队状态模拟
def get_form_weight(h, a):
    hw, aw = 0.5, 0.5
    if h < 1.7: hw += 0.3
    if a < 1.7: aw += 0.3
    if abs(h - a) > 1.0:
        if h < a: hw += 0.2
        else: aw += 0.2
    return round(hw, 2), round(aw, 2)

# 6. 交叉盘校验
def cross_check(h, a):
    if abs(h - a) < 0.1 and (h < 2.0 or a < 2.0):
        return "异常"
    if (h < 1.7 or a < 1.7) and abs(h - a) > 1.0:
        return "高度一致"
    return "正常"

# 7. 联赛基因
def league_attr(league):
    if "epl" in league: return {"draw":0.15, "big":0.25}
    if "bundes" in league: return {"draw":0.10, "big":0.35}
    if "serie" in league: return {"draw":0.20, "big":0.15}
    if "laliga" in league: return {"draw":0.18, "big":0.20}
    if "ligue" in league: return {"draw":0.17, "big":0.22}
    return {"draw":0.15, "big":0.20}

# 8. 疲劳惩罚
def fatigue_penal(h, a):
    if h < 1.6 or a < 1.6: return 0.10
    if abs(h - a) < 0.3: return 0.20
    return 0.15

# 9. 历史盘路胜率
def history_panel_win(panel):
    if panel == "深主": return 0.68
    if panel == "深客": return 0.65
    if panel == "浅盘": return 0.42
    return 0.55

# 10. 泊松概率（大小球+胜平负）
def poisson_prob(h, d, a):
    total = 1/h + 1/d + 1/a
    h_p = round((1/h)/total * 100, 1)
    d_p = round((1/d)/total * 100, 1)
    a_p = round((1/a)/total * 100, 1)
    big = 48 if h_p + a_p > 55 else 42
    small = 100 - big
    return {"h":h_p, "d":d_p, "a":a_p, "big":big, "small":small}

# 11. 凯利最优仓位
def kelly_size(prob, risk=0.05):
    if prob <= 50: return 0
    edge = (prob / 100) - 0.5
    kelly = max(0, edge * 2)
    return round(kelly * risk, 3)

# 12. V9.9 终极决策（仅预判一层，绝不套娃）
def final_decision(match):
    h = match["h"]
    d = match["d"]
    a = match["a"]
    trap = match["trap"]
    panel = match["panel"]
    cross = match["cross"]
    gene = match["league_gene"]
    fatigue = match["fatigue"]
    hist_win = match["history_win"]
    moral = match["moral"]
    h_form, a_form = match["form"]
    draw_s = match["draw_score"]
    is_single = 1 if match["league"] in HIGH_LEAGUES else 0
    prob = match["poisson"]

    # 基础分
    home = (1/h)*0.4 + moral*0.2 + h_form*0.15 + hist_win*0.15 - fatigue*0.1
    away = (1/a)*0.4 + moral*0.2 + a_form*0.15 + hist_win*0.15 - fatigue*0.1
    draw = draw_s + gene["draw"] + (0.1 if is_single else 0.05)

    # ========== V9.9 核心：只预判庄一层，不无限反向 ==========
    if trap and cross == "正常":
        home *= 0.7
        away *= 0.7
        draw *= 0.8
    if cross == "异常":
        home *= 0.75
        away *= 0.75

    # 防聪明反被聪明误：不强行反向
    max_raw = max(home, draw, away)
    res = "主胜" if home == max_raw else "客胜" if away == max_raw else "平局"

    # 风险过滤
    if trap and res in ["主胜", "客胜"]:
        res = "平局" if draw > 0.4 else "规避"
    if cross == "异常" and prob["d"] < 25:
        res = "规避"

    # 平局概率（最终展示用）
    draw_pct = round(prob["d"] + gene["draw"]*10 + (5 if is_single else 2), 1)
    return res, min(draw_pct, 65.0)

# ====================== 比赛数据抓取 ======================
def fetch_today_matches():
    matches = []
    mock_data = [
        {
            "league": "soccer_epl",
            "home": "曼联", "away": "利物浦",
            "h": 2.35, "d": 3.25, "a": 2.80,
            "time": (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        }
    ]
    for item in mock_data:
        league = item["league"]
        h = item["h"]
        d = item["d"]
        a = item["a"]
        trap = detect_trap(h, d, a)
        panel = get_panel_type(h, d, a)
        cross = cross_check(h, a)
        gene = league_attr(league)
        fatigue = fatigue_penal(h, a)
        hist_win = history_panel_win(panel)
        moral = get_moral_weight(h, a)
        form = get_form_weight(h, a)
        draw_s = calc_draw_score(h, d, a)
        prob = poisson_prob(h, d, a)
        res, draw_p = final_decision({
            **item, "trap": trap, "panel": panel, "cross": cross,
            "league_gene": gene, "fatigue": fatigue, "history_win": hist_win,
            "moral": moral, "form": form, "draw_score": draw_s, "poisson": prob
        })
        kelly = kelly_size(prob["h"] if res == "主胜" else prob["a"] if res == "客胜" else prob["d"])
        matches.append({
            **item,
            "is_single": "【单关】" if league in HIGH_LEAGUES else "",
            "trap": trap, "cross": cross, "result": res,
            "draw_pct": draw_p, "kelly": kelly, "poisson": prob
        })
    return matches

# ====================== 定时任务 ======================
def send_daily_schedule():
    db = load_system_db()
    matches = fetch_today_matches()
    html = "<h2>📅 V9.9 今日赛程（终极版）</h2><table border='1' cellpadding='4'>"
    html += "<tr><th>赛事</th><th>对阵</th><th>时间</th><th>单关</th><th>推荐</th><th>平局%</th><th>仓位</th></tr>"
    for m in matches:
        html += f"<tr><td>{m['league']}</td><td>{m['home']}-{m['away']}</td><td>{m['time']}</td>"
        html += f"<td>{m['is_single']}</td><td>{m['result']}</td><td>{m['draw_pct']}%</td><td>{m['kelly']}</td></tr>"
    html += "</table>"
    send_email_report("V9.9 今日赛程", html)

def send_live_picks():
    db = load_system_db()
    matches = fetch_today_matches()
    valid = [m for m in matches if m["result"] != "规避" and m["kelly"] > 0]
    if not valid:
        send_email_report("V9.9 临场推荐", "<h3>今日无符合安全条件的比赛</h3>")
        return
    html = "<h2>⚽ V9.9 临场推荐（终极防庄版）</h2>"
    for m in valid:
        html += f"<p>{m['is_single']} {m['home']} vs {m['away']}</p>"
        html += f"<p>推荐：<b>{m['result']}</b> | 平局概率：{m['draw_pct']}% | 仓位：{m['kelly']}</p>"
        html += f"<p>胜平负概率：{m['poisson']['h']}% / {m['poisson']['d']}% / {m['poisson']['a']}%</p><hr>"
    send_email_report("V9.9 临场推荐", html)

def send_review():
    db = load_system_db()
    total = db["total"]
    correct = db["correct"]
    draw_c = db["draw_correct"]
    rate = round(correct/total*100,1) if total>0 else 0
    draw_rate = round(draw_c/total*100,1) if total>0 else 0
    body = f"<h2>✅ V9.9 复盘报告</h2><p>总场次：{total}</p><p>正确：{correct}</p>"
    body += f"<p>综合命中率：{rate}%</p><p>平局命中：{draw_c} ({draw_rate}%)</p>"
    send_email_report("V9.9 每日复盘", body)

# ====================== 主程序 ======================
if __name__ == "__main__":
    now = datetime.now()
    h, m = now.hour, now.minute
    # 11:10 赛程
    if h == 11 and 9 <= m <= 11:
        send_daily_schedule()
    # 赛前45分钟左右临场
    elif (h == 19 and 30 <= m <= 35) or (h == 20 and 0 <= m <= 5):
        send_live_picks()
    # 23点后复盘
    elif h >= 23:
        send_review()
    else:
        print("当前不在任务时段，运行测试")
        send_live_picks()
