# -*- coding: utf-8 -*-
import sys
import requests
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# ====================== 只改这里！ ======================
ODDS_API_KEY = "你的API Key"  # 把你的Key粘贴在这里
SENDER_EMAIL = "150102030@qq.com"
RECEIVER_EMAIL = "150102030@qq.com"
EMAIL_AUTH_CODE = "czlspwmcdqqnbjii"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# 你关注的联赛（可增删）
TARGET_LEAGUES = {
    "england-premier-league": "英超",
    "germany-bundesliga": "德甲",
    "italy-serie-a": "意甲",
    "france-ligue-1": "法甲",
    "spain-la-liga": "西甲",
    "australia-a-league": "澳超",
    "japan-j1-league": "日职联",
    "korea-k-league-1": "韩职"
}
DATA_FILE = "match_data.json"

# ====================== 工具函数 ======================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ====================== 1. 每日11:10 抓取真实赛程+初盘 ======================
def fetch_schedule():
    matches = []
    url = f"https://api.odds-api.io/v3/events?apiKey={ODDS_API_KEY}&sport=football&status=pending"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        events = res.json()
    except Exception as e:
        send_email("赛程抓取失败", f"错误：{str(e)}")
        return 0

    for ev in events:
        league_slug = ev["league"]["slug"]
        if league_slug not in TARGET_LEAGUES:
            continue
        league = TARGET_LEAGUES[league_slug]
        match_id = ev["id"]
        home = ev["home"]
        away = ev["away"]
        kickoff = ev["date"].replace("T", " ").split(".")[0]
        single = league in ["英超","德甲","澳超","日职联","韩职"]

        # 取初盘（Bet365）
        odds_url = f"https://api.odds-api.io/v3/odds?apiKey={ODDS_API_KEY}&eventId={match_id}&bookmakers=Bet365&markets=h2h,spreads,totals"
        try:
            odds_res = requests.get(odds_url, timeout=10)
            odds_res.raise_for_status()
            odds_data = odds_res.json()
            h2h = next((m for m in odds_data.get("markets",[]) if m["key"]=="h2h"), None)
            spread = next((m for m in odds_data.get("markets",[]) if m["key"]=="spreads"), None)
            totals = next((m for m in odds_data.get("markets",[]) if m["key"]=="totals"), None)
            home_odd = h2h["outcomes"][0]["price"] if h2h else None
            draw_odd = h2h["outcomes"][1]["price"] if h2h else None
            away_odd = h2h["outcomes"][2]["price"] if h2h else None
            asian_handicap = spread["name"] if spread else None
            total_line = totals["name"] if totals else None
        except:
            home_odd = draw_odd = away_odd = None
            asian_handicap = total_line = None

        matches.append({
            "match_id": match_id, "联赛": league, "主队": home, "客队": away,
            "时间": kickoff, "单关": single,
            "初盘_主": home_odd, "初盘_平": draw_odd, "初盘_客": away_odd,
            "初盘_亚盘": asian_handicap, "初盘_大小球": total_line,
            "临盘_主": None, "临盘_平": None, "临盘_客": None,
            "临盘_亚盘": None, "临盘_大小球": None,
            "抓取_初盘": now(), "抓取_临盘": None,
            "赛果": None, "比分": None, "大小球赛果": None, "亚盘赛果": None
        })

    save_data(matches)
    send_email("今日真实赛程已抓取", f"✅ 共抓取 {len(matches)} 场比赛")
    return len(matches)

# ====================== 2. 赛前45分钟抓取真实临盘 ======================
def fetch_live_odds():
    data = load_data()
    cnt = 0
    for m in data:
        if m["抓取_临盘"]:
            continue
        try:
            kt = datetime.strptime(m["时间"], "%Y-%m-%d %H:%M")
        except:
            continue
        if datetime.now() >= kt - timedelta(minutes=45):
            odds_url = f"https://api.odds-api.io/v3/odds?apiKey={ODDS_API_KEY}&eventId={m['match_id']}&bookmakers=Bet365&markets=h2h,spreads,totals"
            try:
                odds_res = requests.get(odds_url, timeout=10)
                odds_res.raise_for_status()
                odds_data = odds_res.json()
                h2h = next((mkt for mkt in odds_data.get("markets",[]) if mkt["key"]=="h2h"), None)
                spread = next((mkt for mkt in odds_data.get("markets",[]) if mkt["key"]=="spreads"), None)
                totals = next((mkt for mkt in odds_data.get("markets",[]) if mkt["key"]=="totals"), None)
                m["临盘_主"] = h2h["outcomes"][0]["price"] if h2h else None
                m["临盘_平"] = h2h["outcomes"][1]["price"] if h2h else None
                m["临盘_客"] = h2h["outcomes"][2]["price"] if h2h else None
                m["临盘_亚盘"] = spread["name"] if spread else None
                m["临盘_大小球"] = totals["name"] if totals else None
                m["抓取_临盘"] = now()
                cnt += 1
            except Exception as e:
                print(f"抓取临盘失败：{e}")
                continue
    save_data(data)
    send_email("赛前45分钟临盘已抓取", f"✅ 更新 {cnt} 场临场赔率")
    return cnt

# ====================== 3. 抓取真实赛果 ======================
def fetch_result():
    data = load_data()
    cnt = 0
    url = f"https://api.odds-api.io/v3/events?apiKey={ODDS_API_KEY}&sport=football&status=completed"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        events = res.json()
    except Exception as e:
        send_email("赛果抓取失败", f"错误：{str(e)}")
        return 0

    for ev in events:
        match_id = ev["id"]
        for m in data:
            if m["match_id"] == match_id and m["赛果"] is None:
                m["比分"] = f"{ev['homeScore']}-{ev['awayScore']}"
                if ev["homeScore"] > ev["awayScore"]:
                    m["赛果"] = "主胜"
                elif ev["homeScore"] < ev["awayScore"]:
                    m["赛果"] = "客胜"
                else:
                    m["赛果"] = "平局"
                total_goals = ev["homeScore"] + ev["awayScore"]
                if m["初盘_大小球"]:
                    line = float(m["初盘_大小球"].split(" ")[1])
                    m["大小球赛果"] = "大" if total_goals > line else "小"
                cnt += 1
    save_data(data)
    send_email("赛果已更新", f"✅ 更新 {cnt} 场比赛结果")
    return cnt

# ====================== 4. 复盘：初盘 vs 临盘 ======================
def generate_review():
    data = load_data()
    rows = []
    total = 0
    init_correct = 0
    live_correct = 0

    for m in data:
        if not m["赛果"]:
            continue
        total += 1
        # 初盘预测
        if m["初盘_主"] and m["初盘_平"] and m["初盘_客"]:
            init_odds = [m["初盘_主"], m["初盘_平"], m["初盘_客"]]
            init_pred = ["主胜","平局","客胜"][init_odds.index(min(init_odds))]
        else:
            init_pred = "无"
        # 临盘预测
        if m["临盘_主"] and m["临盘_平"] and m["临盘_客"]:
            live_odds = [m["临盘_主"], m["临盘_平"], m["临盘_客"]]
            live_pred = ["主胜","平局","客胜"][live_odds.index(min(live_odds))]
        else:
            live_pred = init_pred
        # 统计
        if init_pred == m["赛果"]:
            init_correct += 1
        if live_pred == m["赛果"]:
            live_correct += 1
        rows.append(f"""
        <tr>
            <td>{m['联赛']}</td>
            <td>{m['主队']} vs {m['客队']}</td>
            <td>{init_pred}</td>
            <td>{live_pred}</td>
            <td>{m['赛果']} ({m['比分']})</td>
            <td>{"✅" if init_pred == m['赛果'] else "❌"}</td>
            <td>{"✅" if live_pred == m['赛果'] else "❌"}</td>
        </tr>
        """)

    html = f"""
    <h3>📊 复盘报告：初盘 vs 赛前45分钟临盘</h3>
    <table border="1" cellpadding="4">
        <tr>
            <th>联赛</th><th>对阵</th><th>初盘预测</th><th>临盘预测</th><th>赛果</th><th>初盘</th><th>临盘</th>
        </tr>
        {''.join(rows)}
    </table>
    <br>
    <h3>📈 准确率对比</h3>
    <p>总场次：{total}</p>
    <p>初盘准确率：{init_correct}/{total} = {round(init_correct/total*100,2) if total else 0}%</p>
    <p>临盘准确率：{live_correct}/{total} = {round(live_correct/total*100,2) if total else 0}%</p>
    <h2>结论：{"临盘更准" if live_correct>init_correct else "初盘更准" if init_correct>live_correct else "持平"}</h2>
    """
    send_email("复盘报告（真实数据版）", html)
    return html

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
        print(f"❌ 发送失败：{e}")

# ====================== 主入口 ======================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  python football_analyzer.py schedule   # 抓取赛程+初盘")
        print("  python football_analyzer.py live       # 赛前45分钟抓临盘")
        print("  python football_analyzer.py result     # 抓赛果")
        print("  python football_analyzer.py review     # 生成复盘")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "schedule":
        fetch_schedule()
    elif cmd == "live":
        fetch_live_odds()
    elif cmd == "result":
        fetch_result()
    elif cmd == "review":
        generate_review()
