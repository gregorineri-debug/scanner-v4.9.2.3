import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# =========================
# TIMEZONE
# =========================
SP_TZ = ZoneInfo("America/Sao_Paulo")

# =========================
# MODELO AVANÇADO
# =========================
class AdvancedModel:

    def __init__(self):
        self.weights = np.array([2.5, 2.0, 1.5, 1.5, 1.0])

    def predict(self, X):
        score = np.dot(X, self.weights)
        prob = 1 / (1 + np.exp(-score))
        return prob

model = AdvancedModel()

# =========================
# FEATURES REAIS (BASE)
# =========================
def get_real_stats(team):

    # ⚠️ Placeholder estruturado (pronto pra API real)
    return {
        "xg": np.random.uniform(0.8, 2.2),
        "shots": np.random.randint(8, 18),
        "possession": np.random.uniform(40, 65),
        "corners": np.random.randint(3, 10),
        "cards": np.random.randint(1, 5)
    }

def build_features(home, away):

    h = get_real_stats(home)
    a = get_real_stats(away)

    return np.array([
        h["xg"] - a["xg"],
        h["shots"] - a["shots"],
        h["possession"] - a["possession"],
        h["corners"] - a["corners"],
        h["cards"] - a["cards"]
    ])

# =========================
# DATA FILTER (DATA CORRETA)
# =========================
def is_today(timestamp):

    utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    local_time = utc_time.astimezone(SP_TZ)

    now = datetime.now(SP_TZ)

    return local_time.date() == now.date()

# =========================
# JOGOS DO DIA
# =========================
def get_today_matches():

    url = "https://api.sofascore.com/api/v1/sport/football/scheduled-events/today"

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        data = requests.get(url, headers=headers).json()

        matches = []

        for event in data.get("events", []):

            if not is_today(event["startTimestamp"]):
                continue

            matches.append({
                "home": event["homeTeam"]["name"],
                "away": event["awayTeam"]["name"]
            })

        return matches

    except:
        return []

# =========================
# SNIPER
# =========================
def sniper(prob):
    return prob > 0.7 or prob < 0.3

# =========================
# ANALISE COMPLETA
# =========================
def analyze_match(home, away):

    features = build_features(home, away)

    prob = model.predict(features)

    if prob > 0.55:
        pick = home
    elif prob < 0.45:
        pick = away
    else:
        pick = "NO BET"

    gols = "Over 2.5" if prob > 0.6 else "Under 2.5"
    cantos = "Over 9.5" if prob > 0.55 else "Under 9.5"
    cards = "Over 4.5" if prob > 0.55 else "Under 4.5"

    return {
        "Jogo": f"{home} vs {away}",
        "Pick": pick,
        "Confiança": round(prob, 2),
        "Gols": gols,
        "Cantos": cantos,
        "Cartões": cards,
        "Sniper": "🔥" if sniper(prob) else ""
    }

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(layout="wide")

st.title("📊 Greg Stats X V11 - Scanner Profissional")

sniper_mode = st.checkbox("🔥 Apenas SNIPER")

if st.button("📅 Buscar jogos do dia"):

    matches = get_today_matches()

    data = []

    for m in matches:

        result = analyze_match(m["home"], m["away"])

        if sniper_mode and result["Sniper"] == "":
            continue

        data.append(result)

    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Nenhuma entrada encontrada")
