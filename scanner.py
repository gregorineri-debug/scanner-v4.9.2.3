import streamlit as st
import requests
import numpy as np
import pandas as pd

# =========================
# CONFIG
# =========================
ODDS_API_KEY = "SUA_API_KEY_AQUI"
SPORT = "soccer"

# =========================
# SCRAPER (TIME)
# =========================
def get_team_id(team_name):
    try:
        url = f"https://api.sofascore.com/api/v1/search/all?q={team_name}"
        data = requests.get(url).json()

        for item in data.get("results", []):
            if item.get("type") == "team":
                return item["entity"]["id"]
    except:
        return None


def fetch_team_matches(team_name, last_n=10):
    team_id = get_team_id(team_name)

    if not team_id:
        return []

    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/{last_n}"
        data = requests.get(url).json()

        matches = []

        for e in data.get("events", []):

            is_home = e["homeTeam"]["name"] == team_name

            if e["winnerCode"] == 1:
                result = 1 if is_home else 0
            elif e["winnerCode"] == 2:
                result = 0 if is_home else 1
            else:
                result = 0.5

            matches.append({
                "result": result,
                "is_home": is_home
            })

        return matches

    except:
        return []

# =========================
# FEATURES
# =========================
def build_features(matches, is_home):

    df = pd.DataFrame(matches)

    if df.empty:
        return [0, 0, 0]

    form = df["result"].tail(5).mean()

    home_games = df[df["is_home"] == is_home]
    home_perf = home_games["result"].mean() if not home_games.empty else 0

    consistency = 1 - df["result"].std()
    if np.isnan(consistency):
        consistency = 0

    return [form, home_perf, consistency]

# =========================
# ODDS API
# =========================
def get_odds(home, away):

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h,totals",
        "oddsFormat": "decimal"
    }

    try:
        response = requests.get(url, params=params).json()

        for event in response:

            if home.lower() in event["home_team"].lower() and away.lower() in event["away_team"].lower():

                bookmakers = event["bookmakers"][0]["markets"]

                odds = {}

                for market in bookmakers:

                    if market["key"] == "h2h":
                        outcomes = market["outcomes"]

                        for o in outcomes:
                            if o["name"] == event["home_team"]:
                                odds["home"] = o["price"]
                            elif o["name"] == event["away_team"]:
                                odds["away"] = o["price"]

                    if market["key"] == "totals":
                        odds["over_under"] = market["outcomes"][0]["price"]

                return odds

    except:
        pass

    return {"home": 2.0, "away": 2.0, "over_under": 2.0}

# =========================
# MODELO COM AUTO APRENDIZADO
# =========================
class AdaptiveModel:

    def __init__(self):

        self.weights = np.array([3.0, 2.5, 1.5])
        self.lr = 0.1  # learning rate

    def predict_score(self, features):
        return np.dot(features, self.weights)

    def predict(self, home_feat, away_feat):

        diff = np.array(home_feat) - np.array(away_feat)

        score = self.predict_score(diff)

        prob = 1 / (1 + np.exp(-score))  # sigmoid

        if prob > 0.55:
            return "HOME", prob
        elif prob < 0.45:
            return "AWAY", 1 - prob
        else:
            return "IGNORE", prob

    def update(self, features, target):

        pred = self.predict_score(features)
        prob = 1 / (1 + np.exp(-pred))

        error = target - prob

        # ajuste dos pesos
        self.weights += self.lr * error * features

# =========================
# EV (EXPECTED VALUE)
# =========================
def expected_value(prob, odds):
    return (prob * odds) - 1

# =========================
# STREAMLIT
# =========================
st.title("📊 Greg Stats X V5 - PRO MODE")

model = AdaptiveModel()

st.subheader("🎯 Análise")

home = st.text_input("Time casa")
away = st.text_input("Time visitante")

if st.button("Analisar"):

    home_matches = fetch_team_matches(home)
    away_matches = fetch_team_matches(away)

    if not home_matches or not away_matches:
        st.error("Erro ao buscar dados")
        st.stop()

    home_feat = build_features(home_matches, True)
    away_feat = build_features(away_matches, False)

    prediction, prob = model.predict(home_feat, away_feat)

    odds = get_odds(home, away)

    ev_home = expected_value(prob, odds["home"])
    ev_away = expected_value(1 - prob, odds["away"])

    st.write("### 📈 Resultado")

    st.write(f"Predição: **{prediction}**")
    st.write(f"Confiança: {round(prob, 2)}")

    st.write("### 💰 Odds")

    st.write(odds)

    st.write("### 📊 EV")

    st.write(f"EV Casa: {round(ev_home, 2)}")
    st.write(f"EV Visitante: {round(ev_away, 2)}")

    st.write("### 🎯 Multi-market (base)")

    st.write("✔ Vitória (H2H)")
    st.write("✔ Over/Under (em evolução)")

# =========================
# AUTO LEARNING SIMPLES
# =========================
st.subheader("🧠 Auto Aprendizado (manual por enquanto)")

if st.button("Simular aprendizado"):

    # simulação de aprendizado
    model.update(np.array([1,1,1]), 1)

    st.success("Pesos atualizados automaticamente!")

    st.write("Pesos atuais:")
    st.write(model.weights)
