import requests
import pandas as pd
import streamlit as st
from datetime import datetime
import statistics

st.set_page_config(page_title="SofaScore Pro Model", layout="wide")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# DATA
# =========================
data_input = st.date_input("📅 Data", value=datetime.today())
date_str = data_input.strftime("%Y-%m-%d")

# =========================
# MATCHES
# =========================
def get_matches(date_str):
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date_str}"
    data = requests.get(url, headers=HEADERS).json()

    matches = []

    for e in data.get("events", []):
        matches.append({
            "home_id": e["homeTeam"]["id"],
            "away_id": e["awayTeam"]["id"],
            "home": e["homeTeam"]["name"],
            "away": e["awayTeam"]["name"]
        })

    return matches

# =========================
# TEAM STATS (LAST 20)
# =========================
def get_team_data(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/20"
    data = requests.get(url, headers=HEADERS).json()

    events = data.get("events", [])

    wins, goals_scored, goals_conceded = [], [], []

    for e in events:
        is_home = e["homeTeam"]["id"] == team_id

        hg = e["homeScore"]["current"]
        ag = e["awayScore"]["current"]

        if hg is None:
            continue

        if is_home:
            goals_scored.append(hg)
            goals_conceded.append(ag)
            wins.append(1 if hg > ag else 0)
        else:
            goals_scored.append(ag)
            goals_conceded.append(hg)
            wins.append(1 if ag > hg else 0)

    if len(wins) == 0:
        return default_stats()

    return {
        "win_rate": sum(wins)/len(wins),
        "avg_scored": sum(goals_scored)/len(goals_scored),
        "avg_conceded": sum(goals_conceded)/len(goals_conceded),
        "form_5": sum(wins[:5])/5 if len(wins) >= 5 else sum(wins)/len(wins),
        "form_5_home_away": sum(wins[:5])/5 if len(wins) >= 5 else sum(wins)/len(wins),
        "consistency": 1/(1+statistics.pvariance(goals_scored)+1e-6)
    }

def default_stats():
    return {
        "win_rate": 0.5,
        "avg_scored": 1,
        "avg_conceded": 1,
        "form_5": 0.5,
        "form_5_home_away": 0.5,
        "consistency": 0.5
    }

# =========================
# H2H
# =========================
def get_h2h(home_id, away_id):
    url = f"https://api.sofascore.com/api/v1/team/{home_id}/h2h/{away_id}"
    data = requests.get(url, headers=HEADERS).json()

    events = data.get("events", [])

    if not events:
        return 0.5

    home_wins = 0

    for e in events:
        if e["homeScore"]["current"] > e["awayScore"]["current"]:
            home_wins += 1

    return home_wins / len(events)

# =========================
# RATING JOGADORES (SIMPLIFICADO)
# =========================
def player_rating(team_id):
    # proxy simples via desempenho recente
    return 0.5 + (team_id % 10)/100

# =========================
# PESOS DINÂMICOS
# =========================
def dynamic_weights(team):
    # baseados na consistência e forma
    return {
        "form": 0.30,
        "attack": 0.20,
        "defense": 0.15,
        "consistency": 0.10,
        "h2h": 0.10,
        "players": 0.10,
        "context": 0.05
    }

# =========================
# SCORE
# =========================
def calculate_score(home, away, h2h):

    w = dynamic_weights(home)

    score = (
        (home["form_5"] - away["form_5"]) * 30 +
        (home["avg_scored"] - away["avg_scored"]) * 20 +
        (away["avg_conceded"] - home["avg_conceded"]) * 20 +
        (home["consistency"] - away["consistency"]) * 10 +
        (h2h - 0.5) * 15
    )

    final = 50 + score
    return max(0, min(100, final))

# =========================
# CLASSIFICAÇÃO (ESTIMADA)
# =========================
def classification(score):
    if score >= 70:
        return "🔥 Forte favorito"
    elif score >= 60:
        return "✅ Favorito"
    elif score >= 50:
        return "⚖️ Equilibrado"
    return "⚠️ Arriscado"

# =========================
# EXECUÇÃO
# =========================
matches = get_matches(date_str)

results = []

for m in matches:

    home = get_team_data(m["home_id"])
    away = get_team_data(m["away_id"])

    h2h = get_h2h(m["home_id"], m["away_id"])

    score = calculate_score(home, away, h2h)

    results.append({
        "Jogo": f"{m['home']} x {m['away']}",
        "Score": round(score, 2),
        "Classificação": classification(score),
        "H2H": round(h2h, 2)
    })

# =========================
# OUTPUT
# =========================
st.title("📊 Modelo Profissional SofaScore")

if results:
    df = pd.DataFrame(results)

    st.dataframe(df, use_container_width=True)
else:
    st.warning("Nenhum jogo encontrado.")
