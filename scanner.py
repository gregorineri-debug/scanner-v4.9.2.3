import streamlit as st
import requests
import sqlite3
from datetime import datetime

# ==================================================
# BANCO DE DADOS
# ==================================================
DB_PATH = "betting.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        home TEXT,
        away TEXT,
        league TEXT,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()


# ==================================================
# SCRAPER (SOFASCORE)
# ==================================================
def get_team_id(team_name):
    try:
        url = f"https://api.sofascore.com/api/v1/search/all?q={team_name}"
        data = requests.get(url).json()

        for item in data.get("results", []):
            if item.get("type") == "team":
                return item["entity"]["id"]

    except:
        pass

    return None


def fetch_team_matches(team_name, last_n=10):
    team_id = get_team_id(team_name)

    if not team_id:
        return []

    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/{last_n}"
        data = requests.get(url).json()

        matches = []

        for event in data.get("events", []):

            is_home = event["homeTeam"]["name"] == team_name

            # resultado
            if event["winnerCode"] == 1:
                result = "W" if is_home else "L"
            elif event["winnerCode"] == 2:
                result = "L" if is_home else "W"
            else:
                result = "D"

            matches.append({
                "result": result,
                "is_home": is_home,
                "opponent_position": 10  # fallback (melhorar depois)
            })

        return matches

    except:
        return []


# ==================================================
# FEATURES REAIS
# ==================================================
def calculate_form(matches):
    last = matches[-5:]
    points = 0

    for m in last:
        if m["result"] == "W":
            points += 3
        elif m["result"] == "D":
            points += 1

    return round((points / 15) * 3, 2) if last else 0


def calculate_home_away(matches, is_home):
    filtered = [m for m in matches if m["is_home"] == is_home]

    if not filtered:
        return 0

    points = 0

    for m in filtered:
        if m["result"] == "W":
            points += 3
        elif m["result"] == "D":
            points += 1

    return round((points / (len(filtered) * 3)) * 2.5, 2)


def calculate_opponent_strength(matches):
    weights = []

    for m in matches:
        pos = m["opponent_position"]

        if pos <= 3:
            weights.append(1.5)
        elif pos <= 10:
            weights.append(1.0)
        elif pos <= 15:
            weights.append(0.5)
        else:
            weights.append(0)

    return round(sum(weights) / len(weights), 2) if weights else 0


def calculate_consistency(matches):
    last = matches[-5:]

    if len(last) < 2:
        return 0

    results = [m["result"] for m in last]

    changes = sum(
        1 for i in range(1, len(results)) if results[i] != results[i - 1]
    )

    return round(1 - (changes / len(results)), 2)


def build_features(matches, is_home):
    return {
        "form": calculate_form(matches),
        "home_away": calculate_home_away(matches, is_home),
        "opponent_strength": calculate_opponent_strength(matches),
        "consistency": calculate_consistency(matches)
    }


# ==================================================
# MODELO GREG STATS V4.5
# ==================================================
class GregStatsV45:

    def __init__(self):
        self.weights = {
            "form": 3.0,
            "home_away": 2.5,
            "opponent_strength": 2.0,
            "consistency": 1.5
        }

    def score(self, f):
        return (
            f["form"] * self.weights["form"] +
            f["home_away"] * self.weights["home_away"] +
            f["opponent_strength"] * self.weights["opponent_strength"] +
            f["consistency"] * self.weights["consistency"]
        )

    def predict(self, home_f, away_f):

        home = self.score(home_f)
        away = self.score(away_f)

        diff = abs(home - away)

        if diff < 2:
            return {"status": "IGNORE"}

        if home > away:
            winner = "HOME"
            score = home
        else:
            winner = "AWAY"
            score = away

        confidence = score / (home + away)

        if score < 5:
            return {"status": "IGNORE"}

        return {
            "status": "PICK",
            "prediction": winner,
            "confidence": round(confidence, 2),
            "home_score": round(home, 2),
            "away_score": round(away, 2)
        }


# ==================================================
# SCRAPER DE JOGOS AO VIVO
# ==================================================
def fetch_live_games():
    url = "https://api.sofascore.com/api/v1/sport/football/events/live"
    headers = {"User-Agent": "Mozilla/5.0"}

    data = requests.get(url, headers=headers).json()

    games = []

    for e in data.get("events", []):

        games.append({
            "home": e["homeTeam"]["name"],
            "away": e["awayTeam"]["name"],
            "league": e["tournament"]["name"]
        })

    return games


# ==================================================
# STREAMLIT APP
# ==================================================
st.set_page_config(layout="wide")
st.title("📊 Greg Stats X V4.5 - Sistema Completo")

init_db()

if st.button("🔄 Rodar análise agora"):

    model = GregStatsV45()
    games = fetch_live_games()

    picks = []

    for g in games:

        home_matches = fetch_team_matches(g["home"])
        away_matches = fetch_team_matches(g["away"])

        if not home_matches or not away_matches:
            continue

        home_features = build_features(home_matches, True)
        away_features = build_features(away_matches, False)

        result = model.predict(home_features, away_features)

        # salvar jogo
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO games (home, away, league, date) VALUES (?, ?, ?, ?)",
            (g["home"], g["away"], g["league"], datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()

        if result["status"] == "PICK":
            picks.append({
                "jogo": f"{g['home']} vs {g['away']}",
                "pick": result["prediction"],
                "conf": result["confidence"],
                "score_home": result["home_score"],
                "score_away": result["away_score"]
            })

    st.success("Análise concluída!")

    st.subheader("🎯 PICKS")

    for p in picks:
        st.write(p)


# ==================================================
# DASHBOARD
# ==================================================
st.subheader("📊 Últimos jogos")

conn = get_conn()
c = conn.cursor()

rows = c.execute("SELECT * FROM games ORDER BY id DESC LIMIT 20").fetchall()

for r in rows:
    st.write(r)

conn.close()
