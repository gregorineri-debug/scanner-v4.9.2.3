import streamlit as st
import requests
import sqlite3
from datetime import datetime

# =========================
# CONFIG BANCO
# =========================
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


# =========================
# SCRAPER (SOFASCORE)
# =========================
def fetch_sofascore_games():
    url = "https://api.sofascore.com/api/v1/sport/football/events/live"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    data = response.json()

    games = []

    for event in data.get("events", []):
        games.append({
            "home": event["homeTeam"]["name"],
            "away": event["awayTeam"]["name"],
            "league": event["tournament"]["name"],
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return games


# =========================
# FEATURES (SIMPLIFICADO)
# =========================
def mock_features():
    """
    Aqui ainda é simulado (depois conectamos ao histórico real)
    """

    return {
        "form": 2,
        "home_away": 2,
        "opponent_strength": 1,
        "consistency": 1
    }


# =========================
# MODELO GREG STATS V4.5
# =========================
class GregStatsV45:

    def __init__(self):
        self.weights = {
            "form": 3.0,
            "home_away": 2.5,
            "opponent_strength": 2.0,
            "consistency": 1.5
        }

    def calculate_score(self, f):
        return (
            (f["form"] * self.weights["form"]) +
            (f["home_away"] * self.weights["home_away"]) +
            (f["opponent_strength"] * self.weights["opponent_strength"]) +
            (f["consistency"] * self.weights["consistency"])
        )

    def predict(self, home_features, away_features):

        home_score = self.calculate_score(home_features)
        away_score = self.calculate_score(away_features)

        diff = abs(home_score - away_score)

        if diff < 2:
            return {"status": "IGNORE"}

        if home_score > away_score:
            winner = "HOME"
            score_winner = home_score
        else:
            winner = "AWAY"
            score_winner = away_score

        confidence = score_winner / (home_score + away_score)

        if score_winner < 5:
            return {"status": "IGNORE"}

        return {
            "status": "PICK",
            "prediction": winner,
            "confidence": round(confidence, 2),
            "home_score": round(home_score, 2),
            "away_score": round(away_score, 2)
        }


# =========================
# SALVAR NO BANCO
# =========================
def save_game(home, away, league, date):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        INSERT INTO games (home, away, league, date)
        VALUES (?, ?, ?, ?)
    """, (home, away, league, date))

    conn.commit()
    conn.close()


# =========================
# UI STREAMLIT
# =========================
st.set_page_config(layout="wide")

st.title("📊 Greg Stats X V4.5 - Betting System")

init_db()

if st.button("🔄 Atualizar jogos (SofaScore)"):

    games = fetch_sofascore_games()

    model = GregStatsV45()

    picks = []

    for g in games:

        # FEATURES (mock por enquanto)
        home_features = mock_features()
        away_features = mock_features()

        result = model.predict(home_features, away_features)

        save_game(g["home"], g["away"], g["league"], g["date"])

        if result["status"] == "PICK":
            picks.append({
                "game": f"{g['home']} vs {g['away']}",
                "prediction": result["prediction"],
                "confidence": result["confidence"]
            })

    st.success("Atualizado com sucesso!")

    st.subheader("🎯 Picks")

    for p in picks:
        st.write(p)

# =========================
# DASHBOARD SIMPLES
# =========================
st.subheader("📊 Jogos carregados")

conn = get_conn()
c = conn.cursor()

data = c.execute("SELECT * FROM games ORDER BY id DESC LIMIT 20").fetchall()

for row in data:
    st.write(row)

conn.close()
