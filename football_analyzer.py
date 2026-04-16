import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import json

# ====================== 配置区 ======================
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# 联赛列表
LEAGUES = [
    "soccer_epl",
    "soccer_bundesliga",
    "soccer_serie_a",
    "soccer_laliga",
    "soccer_ligue_1",
    "soccer_china_super"
]

# 盘路数据库文件
DB_FILE = "v8_evolution_db.json"

# ====================== 盘路数据库初始化 ======================
def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({
                "total": 0,
                "correct": 0,
                "draw_correct": 0,
                "predictions": []
            }, f, indent=2)

def save_prediction(match_id, match_info, predict, confidence):
    with open(DB_FILE, "r") as f:
        db = json.load(f)
    db["predictions"].append({
        "id": match_id,
        "match": match_info,
        "predict": predict,
        "confidence": confidence,
        "time": datetime.now().isoformat(),
        "result": None
    })
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def update_result(match_id, actual_result):
    with open(DB_FILE, "r") as f:
        db = json.load(f)
    for pred in db["predictions"]:
        if pred["id"] == match_id and pred["result"] is None:
            pred["result"] = actual_result
            db["total"] += 1
            if pred["predict"] == actual_result:
                db["correct"] += 1
                if pred["predict"] == "平局":
                    db["draw_correct"] += 1
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def get_accuracy():
    with open(DB_FILE, "r") as f:
        db = json.load(f)
    if db["total"] == 0:
        return 0, 0
    return round(db["correct"] / db["total"] * 100, 2), round(db["draw_correct"] / max(1, db["total"]) * 100, 2)

# ====================== 拉取赛事+实时赔率+临场盘变 ======================
def get_matches_with_odds():
    matches = []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for league in LEAGUES:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {
                "apiKey": "",
                "regions": "eu",
                "markets": "h2h,spreads,totals",
                "dateFormat": "iso"
            }
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for g in data:
                if g["commence_time"].startswith(today):
                    h2h = next((m for m in g["bookmakers"][0]["markets"] if m["key"] == "h2h"), None)
                    spreads = next((m for m in g["bookmakers"][0]["markets"] if m["key"] == "spreads"), None)
                    totals = next((m for m in g["bookmakers"][0]["markets"] if m["key"] == "totals"), None)
                    if not h2h or not spreads or not totals:
                        continue
                    outcomes = h2h["outcomes"]
                    home_odds = next((o["price"] for o in outcomes if o["name"] == g["home_team"]), None)
                    draw_odds = next((o["price"] for o in outcomes if o["name"] == "Draw"), None)
                    away_odds = next((o["price"] for o in outcomes if o["name"] == g["away_team"]), None)
                    if not home_odds or not draw_odds or not away_odds:
                        continue
                    spread = spreads["outcomes"][0]["point"]
                    over_under = totals["outcomes"][0]["point"]
                    matches.append({
                        "id": g["id"],
                        "home": g["home_team"],
                        "away": g["away_team"],
                        "kickoff": g["commence_time"],
                        "league": league,
                        "h": home_odds,
                        "d": draw_odds,
                        "a": away_odds,
                        "spread": spread,
                        "over_under": over_under,
                        "is_single": "【单关】" if league in ["soccer_epl", "soccer_china_super"] else ""
                    })
        except Exception as e:
            print(f"拉取{league}失败: {e}")
    return matches

# ====================== V8.0 人性化盘 + 亚盘深浅 + 庄路识别 ======================
def v8_analysis(match):
    h, d, a = match["h"], match["d"], match["a"]
    spread = match["spread"]
    implied = (1/h + 1/d + 1/a)
    p_h = round((1/h)/implied * 100)
    p_d = round((1/d)/implied * 100)
    p_a = round((1/a)/implied * 100)
    trap = ""
    confidence = 60

    # 1. 亚盘深浅判断
    if spread < -0.5 and h > 1.8:
        trap += "主队让盘过浅，防冷平"
    elif spread > 0.5 and a > 1.8:
        trap += "客队让盘过浅，防冷平"
    elif abs(spread) < 0.3 and d < 3.2:
        trap += "盘口胶着，平局优先"

    # 2. 庄路识别（人性化盘）
    if h > 2.0 and d < 3.3 and a > 3.2:
        trap += " | 诱主盘，大众偏爱主胜，庄送舒服盘"
        final = "平局"
        confidence = 78
    elif abs(h - a) < 0.3 and d < 3.2:
        trap += " | 实力均衡，庄藏平局"
        final = "平局"
        confidence = 82
    elif h < 1.85 and a > 4.2:
        trap += " | 主胜格局，机构态度一致"
        final = "主胜"
        confidence = 70
    elif a < 1.85 and h > 4.2:
        trap += " | 客胜格局，机构态度一致"
        final = "客胜"
        confidence = 70
    else:
        final = "平局" if p_d > 35 else ("主胜" if h < a else "客胜")
        confidence = 68

    return {
        "match_id": match["id"],
        "match": f"{match['is_single']} {match['home']} vs {match['away']}",
        "time": match["kickoff"],
        "odds": f"{h:.2f} / {d:.2f} / {a:.2f}",
        "prob": f"胜{p_h}% / 平{p_d}% / 负{p_a}%",
        "spread": f"亚盘 {spread}",
        "over_under": f"大小球 {match['over_under']}",
        "predict": final,
        "confidence": confidence,
        "trap": trap.strip(" | ")
    }

# ====================== 赛后复盘更新 ======================
def fetch_and_update_results():
    try:
        url = "https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": ""}
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        params = {"date": yesterday}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return
        data = resp.json()
        for match in data.get("matches", []):
            if match["status"] == "FINISHED":
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                home_goals = match["score"]["fullTime"]["home"]
                away_goals = match["score"]["fullTime"]["away"]
                if home_goals > away_goals:
                    result = "主胜"
                elif home_goals < away_goals:
                    result = "客胜"
                else:
                    result = "平局"
                update_result(match["id"], result)
    except Exception as e:
        print(f"复盘更新失败: {e}")

# ====================== 发送邮件（带复盘+命中率） ======================
def send_report(analysis_list):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    acc, draw_acc = get_accuracy()
    if not analysis_list:
        body = f"""
        <h2>✅ V8.0 人性化盘系统正常运行</h2>
        <p>时间：{now}</p>
        <p>今日无主流联赛赛事</p>
        <p>历史命中率：{acc}% | 平局命中率：{draw_acc}%</p>
        """
    else:
        body = f"<h2>⚽ V8.0 今日赛事分析报告 {now}</h2>"
        body += f"<p>历史命中率：{acc}% | 平局命中率：{draw_acc}%</p><hr>"
        for item in analysis_list:
            body += f"""
            <p><b>{item['match']}</b></p>
            <p>开球：{item['time']}</p>
            <p>赔率：{item['odds']}</p>
            <p>概率：{item['prob']}</p>
            <p>盘口：{item['spread']} | {item['over_under']}</p>
            <p>推荐：<b>{item['predict']}</b>（置信度 {item['confidence']}%）</p>
            <p>庄路提示：{item['trap']}</p>
            <hr>
            """
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = "V8.0 人性化盘分析报告"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PWD)
            smtp.send_message(msg)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 发邮件失败：{e}")

# ====================== 主程序 ======================
if __name__ == "__main__":
    init_db()
    print("=== V8.0 系统启动 ===")
    fetch_and_update_results()
    matches = get_matches_with_odds()
    analysis = [v8_analysis(m) for m in matches]
    for a in analysis:
        save_prediction(a["match_id"], a["match"], a["predict"], a["confidence"])
    send_report(analysis)
    print("=== 任务结束 ===")
