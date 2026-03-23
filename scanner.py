import requests
import pandas as pd
import streamlit as st
from datetime import datetime
import statistics

st.set_page_config(page_title="Scanner V4.9 PRO", layout="wide")

st.title("🌍 Scanner Automático V4.9 PRO (MODO LUCRO)")

HEADERS = {"User-Agent": "Mozilla/5.0"}

@st.cache_data(ttl=600)
def get_matches():
    url = "https://api.sofascore.com/api/v1/sport/football/scheduled-events/" + datetime.today().strftime("%Y-%m-%d")
    data = requests.get(url, headers=HEADERS).json()
    matches = []

    for event in data.get("events", []):
        matches.append({
            "home_id": event["homeTeam"]["id"],
            "away_id": event["awayTeam"]["id"],
            "home": event["homeTeam"]["name"],
            "away": event["awayTeam"]["name"],
            "tournament": event["tournament"]["name"],
            "country": event["tournament"]["category"]["name"]
        })

    return matches

@st.cache_data(ttl=600)
def get_last_matches(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/10"
    try:
        data = requests.get(url, headers=HEADERS).json()
        events = data.get("events", [])

        wins = 0
        goals_scored = []
        goals_conceded = []
        home_wins = 0
        away_wins = 0
        home_games = 0
        away_games = 0

        for e in events:
            is_home = e["homeTeam"]["id"] == team_id
            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            if is_home:
                home_games += 1
                goals_scored.append(hs)
                goals_conceded.append(as_)
                if hs > as_:
                    wins += 1
                    home_wins += 1
            else:
                away_games += 1
                goals_scored.append(as_)
                goals_conceded.append(hs)
                if as_ > hs:
                    wins += 1
                    away_wins += 1

        win_rate = wins / max(1, len(events))
        avg_scored = sum(goals_scored) / max(1, len(goals_scored))
        avg_conceded = sum(goals_conceded) / max(1, len(goals_conceded))
        home_win_rate = home_wins / max(1, home_games)
        away_win_rate = away_wins / max(1, away_games)

        consistency = 1 / (1 + (statistics.pvariance(goals_scored) + statistics.pvariance(goals_conceded)))

        return {
            "win_rate": win_rate,
            "avg_scored": avg_scored,
            "avg_conceded": avg_conceded,
            "home_win_rate": home_win_rate,
            "away_win_rate": away_win_rate,
            "consistency": consistency
        }

    except:
        return {
            "win_rate": 0.5,
            "avg_scored": 1,
            "avg_conceded": 1,
            "home_win_rate": 0.5,
            "away_win_rate": 0.5,
            "consistency": 0.5
        }

def calculate_score(home, away):
    forma = home["win_rate"] - away["win_rate"]
    ataque = home["avg_scored"] - away["avg_scored"]
    defesa = away["avg_conceded"] - home["avg_conceded"]
    casa_fora = home["home_win_rate"] - away["away_win_rate"]
    consistencia = home["consistency"] - away["consistency"]

    score = (forma * 30 + ataque * 20 + defesa * 20 + casa_fora * 20 + consistencia * 10)
    score = max(0, min(100, 50 + score))
    return score

def score_to_probability(score):
    return round(score / 100, 2)

def calculate_ev(prob, odd):
    return round((prob * odd) - 1, 3)

#⚠️ TROCAR AQUI DEPOIS POR API REAL
def get_real_odds():
    return 1.80

matches = get_matches()
results = []

for m in matches:
    home = get_last_matches(m["home_id"])
    away = get_last_matches(m["away_id"])

    score = calculate_score(home, away)
    prob = score_to_probability(score)
    odd = get_real_odds()
    ev = calculate_ev(prob, odd)

    results.append({
        "Jogo": f"{m['home']} x {m['away']}",
        "Liga": m["tournament"],
        "Score": round(score, 1),
        "Prob": prob,
        "Odd": odd,
        "EV": ev
    })

if results:
    df = pd.DataFrame(results)

    st.subheader("📊 Todos os Jogos")
    st.dataframe(df, use_container_width=True)

    st.subheader("💰 Apostas com Valor (EV > 0)")
    st.dataframe(df[df["EV"] > 0], use_container_width=True)

else:
    st.warning("Nenhum jogo encontrado.")