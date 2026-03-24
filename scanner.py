import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# =========================
# SCRAPER
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

    home_perf = df[df["is_home"] == is_home]["result"].mean()
    home_perf = home_perf if not np.isnan(home_perf) else 0

    consistency = 1 - df["result"].std()
    consistency = consistency if not np.isnan(consistency) else 0

    return [form, home_perf, consistency]

# =========================
# MODELO SIMPLES (SEM SKLEARN)
# =========================
class SimpleModel:

    def __init__(self):
        self.weights = np.array([3.0, 2.5, 1.5])
        self.bias = -2.0

    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def predict_proba(self, features):
        score = np.dot(features, self.weights) + self.bias
        return self.sigmoid(score)

    def predict(self, home_feat, away_feat):

        diff = np.array(home_feat) - np.array(away_feat)

        prob = self.predict_proba(diff)

        if prob > 0.55:
            return "HOME", prob
        elif prob < 0.45:
            return "AWAY", 1 - prob
        else:
            return "IGNORE", prob

# =========================
# BACKTEST
# =========================
def get_historical_games(date):

    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"

    try:
        data = requests.get(url).json()

        games = []

        for e in data.get("events", []):

            games.append({
                "home": e["homeTeam"]["name"],
                "away": e["awayTeam"]["name"],
                "home_score": e["homeScore"].get("current", 0),
                "away_score": e["awayScore"].get("current", 0)
            })

        return games

    except:
        return []


def run_backtest(start_date, end_date, model):

    results = []

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:

        date_str = current.strftime("%Y-%m-%d")

        games = get_historical_games(date_str)

        for g in games:

            home_matches = fetch_team_matches(g["home"])
            away_matches = fetch_team_matches(g["away"])

            if not home_matches or not away_matches:
                continue

            home_feat = build_features(home_matches, True)
            away_feat = build_features(away_matches, False)

            pred, conf = model.predict(home_feat, away_feat)

            if pred == "IGNORE":
                continue

            real = "HOME" if g["home_score"] > g["away_score"] else "AWAY"

            win = 1 if pred == real else 0

            profit = 1 if win else -1

            results.append({
                "game": f"{g['home']} vs {g['away']}",
                "pred": pred,
                "real": real,
                "win": win,
                "profit": profit,
                "confidence": round(conf, 2)
            })

        current += timedelta(days=1)

    return results


def metrics(results):

    total = len(results)

    if total == 0:
        return {}

    wins = sum(r["win"] for r in results)
    profit = sum(r["profit"] for r in results)

    return {
        "total": total,
        "win_rate": round(wins / total * 100, 2),
        "profit": profit,
        "roi": round((profit / total) * 100, 2)
    }

# =========================
# STREAMLIT
# =========================
st.title("📊 Greg Stats X V5 - Sistema Seguro (Sem erro)")

start = st.text_input("Data inicial", "2024-01-01")
end = st.text_input("Data final", "2024-01-03")

if st.button("Rodar Backtest"):

    model = SimpleModel()

    results = run_backtest(start, end, model)

    m = metrics(results)

    st.write("### Métricas")
    st.json(m)

    st.write("### Resultados")

    df = pd.DataFrame(results)
    st.dataframe(df)
