import streamlit as st
import requests
import numpy as np
from datetime import date

# =========================
# MODELO SIMPLES COM APRENDIZADO
# =========================
class Model:

    def __init__(self):

        self.weights = np.array([3.0, 2.0, 1.5])
        self.lr = 0.05

    def predict(self, X):
        score = np.dot(X, self.weights)
        return 1 / (1 + np.exp(-score))

    def update(self, X, y):
        pred = self.predict(X)
        error = y - pred
        self.weights += self.lr * error * X


model = Model()

# =========================
# FEATURES (BASE)
# =========================
def get_features():

    return np.array([
        np.random.rand(),  # forma
        np.random.rand(),  # casa/fora
        np.random.rand()   # consistência
    ])

# =========================
# SOFASCORE - JOGOS DO DIA
# =========================
def get_today_matches():

    today = date.today().isoformat()

    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        matches = []

        for event in data.get("events", []):

            matches.append({
                "home": event["homeTeam"]["name"],
                "away": event["awayTeam"]["name"]
            })

        return matches

    except:
        return []

# =========================
# PREVISÃO (VITÓRIA)
# =========================
def predict_match():

    X = get_features()

    prob = model.predict(X)

    if prob > 0.55:
        return "HOME", prob
    elif prob < 0.45:
        return "AWAY", 1 - prob
    else:
        return "NO BET", prob

# =========================
# MULTI-MARKET (BASE)
# =========================
def multi_market_analysis():

    return {
        "victory": predict_match(),
        "goals": "UNDER (base)",
        "corners": "OVER (base)",
        "cards": "OVER (base)"
    }

# =========================
# STREAMLIT
# =========================
st.set_page_config(page_title="Greg Stats X V9", layout="wide")

st.title("📊 Greg Stats X V9 - IA Automática")

st.write("🔍 Buscando jogos automaticamente no SofaScore")

if st.button("📅 Analisar jogos do dia"):

    matches = get_today_matches()

    if not matches:
        st.error("Nenhum jogo encontrado")
        st.stop()

    for match in matches:

        st.write("-----")

        st.write(f"⚽ {match['home']} vs {match['away']}")

        analysis = multi_market_analysis()

        victory, confidence = analysis["victory"]

        if victory == "HOME":
            st.success(f"🔥 APOSTA: {match['home']}")
        elif victory == "AWAY":
            st.success(f"🔥 APOSTA: {match['away']}")
        else:
            st.warning("⚠️ SEM ENTRADA")

        st.write(f"Confiança: {round(confidence, 2)}")

        st.write("📊 Multi-market:")
        st.write(analysis)

        # aprendizado simulado (treino contínuo)
        model.update(np.array([1,1,1]), 1)
