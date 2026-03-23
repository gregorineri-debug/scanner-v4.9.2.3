import requests
import pandas as pd
import streamlit as st
from datetime import datetime
import pytz
import statistics

st.set_page_config(page_title="Scanner SofaScore V6", layout="wide")

st.title("🌍 Scanner Automático V6 (SOFASCORE ONLY)")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =============================
# DATA
# =============================
data_input = st.date_input("📅 Data dos jogos:", value=datetime.today())
data_alvo = data_input.strftime('%Y-%m-%d')

st.write(f"🔎 Buscando jogos: **{data_alvo}**")

# =============================
# JOGOS DO DIA (SOFASCORE)
# =============================
@st.cache_data(ttl=600)
def get_matches(data_alvo):
    try:
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{data_alvo}"
        data = requests.get(url, headers=HEADERS).json()

        matches = []

        for e in data.get("events", []):
            matches.append({
                "home": e["homeTeam"]["name"],
                "away": e["awayTeam"]["name"],
                "home_id": e["homeTeam"]["id"],
                "away_id": e["awayTeam"]["id"],
                "league": e["tournament"]["name"]
            })

        return matches

    except:
        return []

# =============================
# ESTATÍSTICAS (SOFASCORE)
# =============================
@st.cache_data(ttl=600)
def get_team_stats(team_id):
    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/10"
        data = requests.get(url, headers=HEADERS).json()

        events = data.get("events", [])

        if not events:
            return default_stats()

        goals_scored = []
        goals_conceded = []
        wins = []

        for e in events:
            is_home = e["homeTeam"]["id"] == team_id

            hg = e["homeScore"]["current"]
            ag = e["awayScore"]["current"]

            if hg is None or ag is None:
                continue

            if is_home:
                goals_scored.append(hg)
                goals_conceded.append(ag)
                wins.append(1 if hg > ag else 0)
            else:
                goals_scored.append(ag)
                goals_conceded.append(hg)
                wins.append(1 if ag > hg else 0)

        if len(goals_scored) == 0:
            return default_stats()

        return {
            "win_rate": sum(wins) / len(wins),
            "avg_scored": sum(goals_scored) / len(goals_scored),
            "avg_conceded": sum(goals_conceded) / len(goals_conceded),
            "recent_form": sum(wins[:3]) / min(3, len(wins)),
            "consistency": 1 / (1 + (statistics.pvariance(goals_scored) + 1e-6))
        }

    except:
        return default_stats()

def default_stats():
    return {
        "win_rate": 0.5,
        "avg_scored": 1,
        "avg_conceded": 1,
        "recent_form": 0.5,
        "consistency": 0.5
    }

# =============================
# SCORE
# =============================
def calculate_score(home, away):

    score = (
        (home["win_rate"] - away["win_rate"]) * 30 +
        (home["avg_scored"] - away["avg_scored"]) * 20 +
        (away["avg_conceded"] - home["avg_conceded"]) * 20 +
        (home["recent_form"] - away["recent_form"]) * 20 +
        (home["consistency"] - away["consistency"]) * 10
    )

    score = 50 + score
    return max(0, min(100, score))

def prediction(score):
    if score >= 60:
        return "Casa vence"
    elif score <= 40:
        return "Visitante vence"
    return "Sem aposta"

def strength(score):
    if score >= 75 or score <= 25:
        return "🔥 Forte"
    elif score >= 65 or score <= 35:
        return "✅ Boa"
    return "⚠️ Arriscada"

# =============================
# EXECUÇÃO
# =============================
matches = get_matches(data_alvo)

st.write(f"Jogos encontrados: {len(matches)}")

results = []

for m in matches:

    home_stats = get_team_stats(m["home_id"])
    away_stats = get_team_stats(m["away_id"])

    score = calculate_score(home_stats, away_stats)

    results.append({
        "Jogo": f"{m['home']} x {m['away']}",
        "Liga": m["league"],
        "Score": round(score, 1),
        "Aposta": prediction(score),
        "Força": strength(score)
    })

# =============================
# OUTPUT
# =============================
if results:
    df = pd.DataFrame(results)

    st.subheader("📊 Jogos do Dia")
    st.dataframe(df, use_container_width=True)

    st.subheader("💰 Apostas")
    st.dataframe(
        df[df["Aposta"] != "Sem aposta"],
        use_container_width=True
    )
else:
    st.warning("Nenhum jogo encontrado.")
