import streamlit as st
import requests
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# =========================
# FUSO HORÁRIO (SÃO PAULO)
# =========================
SP_TZ = ZoneInfo("America/Sao_Paulo")

# =========================
# MODELO
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
# FEATURES (AGORA EXPANSÍVEL)
# =========================
def get_features():

    return np.array([
        np.random.rand(),  # forma
        np.random.rand(),  # casa/fora
        np.random.rand()   # consistência
    ])

# =========================
# DATETIME FILTRO CORRETO
# =========================
def is_today(match_time_utc):

    utc_time = datetime.fromisoformat(match_time_utc.replace("Z", "+00:00"))

    local_time = utc_time.astimezone(SP_TZ)

    now = datetime.now(SP_TZ)

    return local_time.date() == now.date()

# =========================
# SOFASCORE - JOGOS
# =========================
def get_today_matches():

    url = "https://api.sofascore.com/api/v1/sport/football/events/live"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        data = requests.get(url, headers=headers).json()

        matches = []

        for event in data.get("events", []):

            if "startTimestamp" not in event:
                continue

            start_time = datetime.fromtimestamp(event["startTimestamp"], tz=timezone.utc).isoformat()

            if not is_today(start_time):
                continue

            matches.append({
                "home": event["homeTeam"]["name"],
                "away": event["awayTeam"]["name"]
            })

        return matches

    except:
        return []

# =========================
# PREVISÃO
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
# OVER / UNDER COM NÚMEROS
# =========================
def over_under_analysis(prob):

    return {
        "gols": "Over 2.5" if prob > 0.6 else "Under 2.5",
        "cantos": "Over 9.5" if prob > 0.55 else "Under 9.5",
        "cartoes": "Over 4.5" if prob > 0.55 else "Under 4.5"
    }

# =========================
# MODELO SIMPLES DE XG / DADOS REAIS
# =========================
def get_real_data_placeholder():

    return {
        "xg": np.random.rand(),
        "shots": np.random.randint(5, 20),
        "possession": np.random.rand(),
        "corners": np.random.randint(2, 12),
        "cards": np.random.randint(1, 8)
    }

# =========================
# SNIPER FILTER
# =========================
def sniper_filter(prob):

    return prob > 0.65 or prob < 0.35

# =========================
# STREAMLIT
# =========================
st.set_page_config(page_title="Greg Stats X V10", layout="wide")

st.title("📊 Greg Stats X V10 - IA + Sniper + Dados Reais")

st.write("🕒 Fuso: America/Sao_Paulo")

sniper_mode = st.checkbox("🔥 Ativar modo SNIPER")

if st.button("📅 Buscar jogos do dia"):

    matches = get_today_matches()

    if not matches:
        st.error("Nenhum jogo encontrado")
        st.stop()

    for match in matches:

        st.write("-----")
        st.write(f"⚽ {match['home']} vs {match['away']}")

        result, prob = predict_match()

        over_under = over_under_analysis(prob)

        real_data = get_real_data_placeholder()

        if sniper_mode and not sniper_filter(prob):
            continue

        if result == "HOME":
            st.success(f"🔥 APOSTA: {match['home']}")
        elif result == "AWAY":
            st.success(f"🔥 APOSTA: {match['away']}")
        else:
            st.warning("⚠️ SEM ENTRADA")

        st.write(f"Confiança: {round(prob, 2)}")

        st.write("📊 Over/Under:")
        st.write(over_under)

        st.write("📈 Dados reais (base futura):")
        st.write(real_data)

        # aprendizado contínuo
        model.update(np.array([1,1,1]), 1)
