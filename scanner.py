import requests
import pandas as pd
import streamlit as st
from datetime import datetime
import pytz
import statistics

st.set_page_config(page_title="Scanner V5 PRO", layout="wide")

st.title("🌍 Scanner Automático V5 PRO (SOFASCORE + API)")

API_KEY = "SUA_API_KEY_AQUI"

HEADERS_API = {
    "x-apisports-key": API_KEY,
    "User-Agent": "Mozilla/5.0"
}

HEADERS_SOFA = {
    "User-Agent": "Mozilla/5.0"
}

# =============================
# DATA
# =============================
data_input = st.date_input("📅 Selecione a data:", value=datetime.today())

data_alvo = data_input.strftime('%Y-%m-%d')

st.write(f"🔎 Data: **{data_alvo}**")

# =============================
# JOGOS VIA SOFASCORE
# =============================
@st.cache_data(ttl=600)
def get_matches_sofascore(data_alvo):
    try:
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{data_alvo}"

        response = requests.get(url, headers=HEADERS_SOFA)
        data = response.json()

        matches = []

        for event in data.get("events", []):
            matches.append({
                "home": event["homeTeam"]["name"],
                "away": event["awayTeam"]["name"],
                "home_id": event["homeTeam"]["id"],
                "away_id": event["awayTeam"]["id"],
                "league": event["tournament"]["name"]
            })

        return matches

    except Exception as e:
        st.error(f"Erro SofaScore: {e}")
        return []

# =============================
# DADOS API (API-FOOTBALL)
# =============================
@st.cache_data(ttl=600)
def get_last_matches(team_id):
    try:
        url = "https://v3.football.api-sports.io/fixtures"

        params = {
            "team": team_id,
            "last": 10
        }

        response = requests.get(url, headers=HEADERS_API, params=params)
        data = response.json()

        events = data.get("response", [])

        goals_scored = []
        goals_conceded = []
        wins = []

        for e in events:
            home_id = e["teams"]["home"]["id"]

            hg = e["goals"]["home"]
            ag = e["goals"]["away"]

            if hg is None or ag is None:
                continue

            if home_id == team_id:
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

    score = max(0, min(100, 50 + score))
    return score

def get_prediction(score):
    if score >= 60:
        return "Casa vence"
    elif score <= 40:
        return "Visitante vence"
    return "Sem aposta"

def get_strength(score):
    if score >= 75 or score <= 25:
        return "🔥 Forte"
    elif score >= 65 or score <= 35:
        return "✅ Boa"
    return "⚠️ Arriscada"

# =============================
# EXECUÇÃO
# =============================
matches = get_matches_sofascore(data_alvo)

st.write(f"Jogos encontrados: {len(matches)}")

results = []

for m in matches:

    home = get_last_matches(m["home_id"])
    away = get_last_matches(m["away_id"])

    score = calculate_score(home, away)

    results.append({
        "Jogo": f"{m['home']} x {m['away']}",
        "Liga": m["league"],
        "Score": round(score, 1),
        "Aposta": get_prediction(score),
        "Força": get_strength(score)
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
