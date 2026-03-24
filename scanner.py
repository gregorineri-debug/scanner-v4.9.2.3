import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import LogisticRegression

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

    last5 = df.tail(5)

    form = last5["result"].mean()

    home_games = df[df["is_home"] == is_home]

    home_perf = home_games["result"].mean() if not home_games.empty else 0

    consistency = 1 - df["result"].std()

    return [form, home_perf, consistency if not np.isnan(consistency) else 0]


# =========================
# BACKTEST DATASET
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


# =========================
# DATASET BUILDER
# =========================
def build_dataset(start_date, end_date):

    X = []
    y = []

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

            features = [
                home_feat[0] - away_feat[0],  # form diff
                home_feat[1] - away_feat[1],  # home advantage
                home_feat[2] - away_feat[2]   # consistency
            ]

            # label: 1 = home win, 0 = away/draw
            if g["home_score"] > g["away_score"]:
                label = 1
            else:
                label = 0

            X.append(features)
            y.append(label)

        current += timedelta(days=1)

    return np.array(X), np.array(y)


# =========================
# MODELO ML
# =========================
def train_model(X, y):

    model = LogisticRegression()

    model.fit(X, y)

    return model


def predict(model, home_feat, away_feat):

    features = np.array([[
        home_feat[0] - away_feat[0],
        home_feat[1] - away_feat[1],
        home_feat[2] - away_feat[2]
    ]])

    prob = model.predict_proba(features)[0][1]

    if prob > 0.55:
        return "HOME", prob
    elif prob < 0.45:
        return "AWAY", 1 - prob
    else:
        return "IGNORE", prob


# =========================
# BACKTEST
# =========================
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

            pred, conf = predict(model, home_feat, away_feat)

            if pred == "IGNORE":
                continue

            if g["home_score"] > g["away_score"]:
                real = "HOME"
            else:
                real = "AWAY"

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
# STREAMLIT UI
# =========================
st.title("📊 Greg Stats X V5 - ML Auto Weights")

start = st.text_input("Data inicial", "2024-01-01")
end = st.text_input("Data final", "2024-01-03")

if st.button("Treinar modelo + Backtest"):

    st.info("Construindo dataset...")

    X, y = build_dataset(start, end)

    if len(X) == 0:
        st.error("Sem dados suficientes")
        st.stop()

    st.success(f"Dataset criado: {len(X)} registros")

    st.info("Treinando modelo...")

    model = train_model(X, y)

    st.success("Modelo treinado!")

    st.info("Rodando backtest...")

    results = run_backtest(start, end, model)

    m = metrics(results)

    st.write("### Métricas")
    st.json(m)

    st.write("### Resultados")

    df = pd.DataFrame(results)
    st.dataframe(df)
