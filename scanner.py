import requests
import pandas as pd
import streamlit as st
from datetime import datetime, date
import pytz
import statistics

st.set_page_config(page_title="Scanner V5 PRO", layout="wide")

st.title("🌍 Scanner Automático V5 PRO (MODO DECISÃO)")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# SELETOR DE DATA
# =============================
data_input = st.date_input(
    "📅 Selecione a data dos jogos:",
    value=date.today()
)

data_alvo = data_input.strftime('%Y-%m-%d')

st.write(f"🔎 Buscando jogos do dia: **{data_alvo}**")

# =============================
# BUSCAR JOGOS
# =============================
@st.cache_data(ttl=600)
def get_matches(data_alvo):
    try:
        tz = pytz.timezone("America/Sao_Paulo")

        start_day = tz.localize(datetime.strptime(data_alvo, "%Y-%m-%d"))
        end_day = tz.localize(datetime.strptime(data_alvo + " 23:59:59", "%Y-%m-%d %H:%M:%S"))

        start_ts = int(start_day.timestamp())
        end_ts = int(end_day.timestamp())

        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{data_alvo}"
        data = requests.get(url, headers=HEADERS).json()

        matches = []

        for event in data.get("events", []):
            event_ts = event.get("startTimestamp", 0)

            if start_ts <= event_ts <= end_ts:
                matches.append({
                    "home_id": event["homeTeam"]["id"],
                    "away_id": event["awayTeam"]["id"],
                    "home": event["homeTeam"]["name"],
                    "away": event["awayTeam"]["name"],
                    "tournament": event["tournament"]["name"],
                    "country": event["tournament"]["category"]["name"]
                })

        return matches

    except:
        return []

# =============================
# DADOS DOS TIMES (REFINADO)
# =============================
@st.cache_data(ttl=600)
def get_last_matches(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/10"
    try:
        data = requests.get(url, headers=HEADERS).json()
        events = data.get("events", [])

        weighted_wins = 0
        total_weight = 0

        goals_scored = []
        goals_conceded = []

        home_perf = []
        away_perf = []

        for i, e in enumerate(events):
            weight = 1 - (i * 0.07)
            total_weight += weight

            is_home = e["homeTeam"]["id"] == team_id
            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            if is_home:
                goals_scored.append(hs)
                goals_conceded.append(as_)
                home_perf.append(1 if hs > as_ else 0)

                if hs > as_:
                    weighted_wins += weight
            else:
                goals_scored.append(as_)
                goals_conceded.append(hs)
                away_perf.append(1 if as_ > hs else 0)

                if as_ > hs:
                    weighted_wins += weight

        win_rate = weighted_wins / max(1, total_weight)

        avg_scored = sum(goals_scored) / max(1, len(goals_scored))
        avg_conceded = sum(goals_conceded) / max(1, len(goals_conceded))

        home_win_rate = sum(home_perf) / max(1, len(home_perf))
        away_win_rate = sum(away_perf) / max(1, len(away_perf))

        recent_games = home_perf + away_perf
        recent_form = sum(recent_games[:3]) / max(1, len(recent_games[:3]))

        consistency = 1 / (1 + (statistics.pvariance(goals_scored) + statistics.pvariance(goals_conceded)))

        return {
            "win_rate": win_rate,
            "avg_scored": avg_scored,
            "avg_conceded": avg_conceded,
            "home_win_rate": home_win_rate,
            "away_win_rate": away_win_rate,
            "recent_form": recent_form,
            "consistency": consistency
        }

    except:
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
# SCORE REFINADO
# =============================
def calculate_score(home, away):
    forma = home["win_rate"] - away["win_rate"]
    ataque = home["avg_scored"] - away["avg_scored"]
    defesa = away["avg_conceded"] - home["avg_conceded"]
    casa_fora = home["home_win_rate"] - away["away_win_rate"]
    momento = home["recent_form"] - away["recent_form"]
    consistencia = home["consistency"] - away["consistency"]

    score = (
        forma * 25 +
        ataque * 15 +
        defesa * 15 +
        casa_fora * 20 +
        momento * 15 +
        consistencia * 10
    )

    score = max(0, min(100, 50 + score))
    return score

def score_to_probability(score):
    return round(score / 100, 2)

# =============================
# FILTRO V5 (NOVO)
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
    else:
        return "Sem aposta"

def get_strength(score):
    if score >= 75 or score <= 25:
        return "🔥 Forte"
    elif score >= 65 or score <= 35:
        return "✅ Boa"
    else:
        return "⚠️ Arriscada"

# =============================
# PROCESSAMENTO
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
    prediction = get_prediction(score)
    strength = get_strength(score)

    results.append({
        "Jogo": f"{m['home']} x {m['away']}",
        "Liga": m["tournament"],
        "Score": round(score, 1),
        "Probabilidade": prob,
        "Aposta": prediction,
        "Força": strength
    })

# =============================
# OUTPUT
# =============================
if results:
    df = pd.DataFrame(results)

    st.subheader("📊 Todos os Jogos (Filtrados)")
    st.dataframe(df, use_container_width=True)

    st.subheader("💰 Apostas Recomendadas")
    st.dataframe(
        df[(df["Aposta"] != "Sem aposta") & (df["Força"] != "⚠️ Arriscada")],
        use_container_width=True
    )

else:
    st.warning("Nenhum jogo válido encontrado (filtro V5).")
