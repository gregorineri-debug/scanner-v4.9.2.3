import requests
import pandas as pd
import streamlit as st
from datetime import datetime, date
import pytz
import statistics

st.set_page_config(page_title="Scanner V5 PRO", layout="wide")

st.title("🌍 Scanner Automático V5 PRO (MODO DECISÃO)")

# =============================
# CONFIG API
# =============================
API_KEY = "SUA_API_KEY_AQUI"

HEADERS = {
    "x-apisports-key": API_KEY
}

# =============================
# DATA
# =============================
data_input = st.date_input(
    "📅 Selecione a data dos jogos:",
    value=date.today()
)

data_alvo = data_input.strftime('%Y-%m-%d')

st.write(f"🔎 Buscando jogos do dia: **{data_alvo}**")

# =============================
# BUSCAR JOGOS (API-Football)
# =============================
@st.cache_data(ttl=600)
def get_matches(data_alvo):
    try:
        url = "https://v3.football.api-sports.io/fixtures"

        params = {
            "date": data_alvo
        }

        response = requests.get(url, headers=HEADERS, params=params)
        data = response.json()

        matches = []

        for event in data.get("response", []):
            matches.append({
                "home_id": event["teams"]["home"]["id"],
                "away_id": event["teams"]["away"]["id"],
                "home": event["teams"]["home"]["name"],
                "away": event["teams"]["away"]["name"],
                "tournament": event["league"]["name"],
                "country": event["league"]["country"]
            })

        return matches

    except Exception as e:
        st.error(f"Erro ao buscar jogos: {e}")
        return []

# =============================
# DADOS DOS TIMES
# =============================
@st.cache_data(ttl=600)
def get_last_matches(team_id):
    try:
        url = "https://v3.football.api-sports.io/fixtures"

        params = {
            "team": team_id,
            "last": 10
        }

        response = requests.get(url, headers=HEADERS, params=params)
        data = response.json()

        events = data.get("response", [])

        goals_scored = []
        goals_conceded = []
        wins = []

        for e in events:
            is_home = e["teams"]["home"]["id"] == team_id

            home_goals = e["goals"]["home"]
            away_goals = e["goals"]["away"]

            if home_goals is None or away_goals is None:
                continue

            if is_home:
                goals_scored.append(home_goals)
                goals_conceded.append(away_goals)
                wins.append(1 if home_goals > away_goals else 0)
            else:
                goals_scored.append(away_goals)
                goals_conceded.append(home_goals)
                wins.append(1 if away_goals > home_goals else 0)

        if len(goals_scored) == 0:
            return {
                "win_rate": 0.5,
                "avg_scored": 1,
                "avg_conceded": 1,
                "home_win_rate": 0.5,
                "away_win_rate": 0.5,
                "recent_form": 0.5,
                "consistency": 0.5
            }

        return {
            "win_rate": sum(wins) / len(wins),
            "avg_scored": sum(goals_scored) / len(goals_scored),
            "avg_conceded": sum(goals_conceded) / len(goals_conceded),
            "home_win_rate": sum(wins) / len(wins),
            "away_win_rate": sum(wins) / len(wins),
            "recent_form": sum(wins[:3]) / min(3, len(wins)),
            "consistency": 1 / (1 + (statistics.pvariance(goals_scored) + 1e-6))
        }

    except Exception as e:
        return {
            "win_rate": 0.5,
            "avg_scored": 1,
            "avg_conceded": 1,
            "home_win_rate": 0.5,
            "away_win_rate": 0.5,
            "recent_form": 0.5,
            "consistency": 0.5
        }

# =============================
# SCORE
# =============================
def calculate_score(home, away):
    score = (
        (home["win_rate"] - away["win_rate"]) * 25 +
        (home["avg_scored"] - away["avg_scored"]) * 15 +
        (away["avg_conceded"] - home["avg_conceded"]) * 15 +
        (home["home_win_rate"] - away["away_win_rate"]) * 20 +
        (home["recent_form"] - away["recent_form"]) * 15 +
        (home["consistency"] - away["consistency"]) * 10
    )

    score = max(0, min(100, 50 + score))
    return score

def score_to_probability(score):
    return round(score / 100, 2)

# =============================
# FILTRO
# =============================
def is_valid_bet(score, home, away):
    if 45 <= score <= 55:
        return False

    if home["consistency"] < 0.3 or away["consistency"] < 0.3:
        return False

    return True

# =============================
# DECISÃO
# =============================
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
matches = get_matches(data_alvo)

results = []

for m in matches:
    home = get_last_matches(m["home_id"])
    away = get_last_matches(m["away_id"])

    score = calculate_score(home, away)

    if not is_valid_bet(score, home, away):
        continue

    prob = score_to_probability(score)

    results.append({
        "Jogo": f"{m['home']} x {m['away']}",
        "Liga": m["tournament"],
        "Score": round(score, 1),
        "Probabilidade": prob,
        "Aposta": get_prediction(score),
        "Força": get_strength(score)
    })

# =============================
# OUTPUT
# =============================
if results:
    df = pd.DataFrame(results)

    st.subheader("📊 Jogos Analisados")
    st.dataframe(df, use_container_width=True)

    st.subheader("💰 Apostas Recomendadas")
    st.dataframe(
        df[(df["Aposta"] != "Sem aposta") & (df["Força"] != "⚠️ Arriscada")],
        use_container_width=True
    )
else:
    st.warning("Nenhum jogo válido encontrado.")
