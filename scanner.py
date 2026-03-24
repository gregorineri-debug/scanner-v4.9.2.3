import streamlit as st
import requests
import numpy as np

# =========================
# MODELO SIMPLES (BASE)
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
# SOFASCORE - JOGOS DO DIA
# =========================
def get_today_matches():

    url = "https://api.sofascore.com/api/v1/sport/football/events/live"

    try:
        data = requests.get(url).json()

        matches = []

        for game in data.get("events", []):

            matches.append({
                "home": game["homeTeam"]["name"],
                "away": game["awayTeam"]["name"]
            })

        return matches

    except:
        return []

# =========================
# FEATURES SIMPLES
# =========================
def build_features():

    return np.array([
        np.random.rand(),
        np.random.rand(),
        np.random.rand()
    ])

# =========================
# PREVISÃO
# =========================
def predict_match():

    X = build_features()

    prob = model.predict(X)

    if prob > 0.55:
        return "HOME", prob
    elif prob < 0.45:
        return "AWAY", 1 - prob
    else:
        return "NO BET", prob

# =========================
# STREAMLIT
# =========================
st.title("📊 Greg Stats X V8 - Jogos do Dia")

st.write("🔍 Fonte: SofaScore")

if st.button("📅 Buscar jogos do dia"):

    matches = get_today_matches()

    if not matches:
        st.error("Nenhum jogo encontrado")
        st.stop()

    for match in matches:

        st.write("-----")
        st.write(f"⚽ {match['home']} vs {match['away']}")

        result, confidence = predict_match()

        if result == "HOME":
            st.success(f"🔥 APOSTA: {match['home']}")
        elif result == "AWAY":
            st.success(f"🔥 APOSTA: {match['away']}")
        else:
            st.warning("⚠️ SEM ENTRADA")

        st.write(f"Confiança: {round(confidence, 2)}")
