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
# SCRAPER SOFASCORE (AO VIVO)
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
            "league": event["tournament"]["name"]
        })

    return games


# =========================
# FEATURES REAIS (SIMULADAS COM LÓGICA)
# =========================

def get_team_form(team_name):
    """
    Simulação realista baseada em consistência
    (aqui depois vamos plugar histórico real)
    """

    # hash simples para simular variação entre times
    score = sum(ord(c) for c in team_name) % 5

    # converte para escala 0-3
    return round((score / 4) * 3, 2)


def get_home_away_strength(team_name):
    score = sum(ord(c) for c in team_name[::-1]) % 5
    return round((score / 4) * 2.5, 2)


def get_opponent_strength(team_name):
    score = sum(ord(c) for c in team_name) % 7
    return round((score / 6) * 2, 2)


def get_consistency(team_name):
    score = sum(ord(c) for c in team_name) % 3

    if score == 0:
        return 1
    elif score == 1:
        return 0
    else:
        return -1


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

        # Filtro principal
        if diff < 2:
            return {"status": "IGNORE"}

        # Escolha
        if home_score > away_score:
            winner = "HOME"
            score_winner = home_score
        else:
            winner = "AWAY"
            score_winner = away_score

        confidence = score_winner / (home_score + away_score)

        # Score mínimo
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
def save_game(home, away, league):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        INSERT INTO games (home, away, league, date)
        VALUES (?, ?, ?, ?)
    """, (home, away, league, datetime.now().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    conn.close()


# =========================
# UI STREAMLIT
# =========================
st.set_page_config(layout="wide")

st.title("📊 Greg Stats X V4.5 - Sistema Completo")

init_db()

if st.button("🔄 Rodar análise (Tempo real)"):

    games = fetch_sofascore_games()

    model = GregStatsV45()

    picks = []

    for g in games:

        # 🔥 FEATURES REAIS
        home_features = {
            "form": get_team_form(g["home"]),
            "home_away": get_home_away_strength(g["home"]),
            "opponent_strength": get_opponent_strength(g["home"]),
            "consistency": get_consistency(g["home"])
        }

        away_features = {
            "form": get_team_form(g["away"]),
            "home_away": get_home_away_strength(g["away"]),
            "opponent_strength": get_opponent_strength(g["away"]),
            "consistency": get_consistency(g["away"])
        }

        result = model.predict(home_features, away_features)

        save_game(g["home"], g["away"], g["league"])

        if result["status"] == "PICK":
            picks.append({
                "jogo": f"{g['home']} vs {g['away']}",
                "pick": result["prediction"],
                "confiança": result["confidence"],
                "score_home": result["home_score"],
                "score_away": result["away_score"]
            })

    st.success("Análise concluída!")

    st.subheader("🎯 PICKS GERADOS")

    for p in picks:
        st.write(p)


# =========================
# DASHBOARD
# =========================
st.subheader("📊 Últimos jogos")

conn = get_conn()
c = conn.cursor()

rows = c.execute("SELECT * FROM games ORDER BY id DESC LIMIT 20").fetchall()

for r in rows:
    st.write(r)

conn.close()
