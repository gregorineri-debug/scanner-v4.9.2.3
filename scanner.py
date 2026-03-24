import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

SP_TZ = ZoneInfo("America/Sao_Paulo")

# =========================
# BUSCA JOGOS DO DIA (CORRIGIDO)
# =========================
def get_today_matches():

    today = datetime.now(SP_TZ).strftime("%Y-%m-%d")

    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today}"

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        data = requests.get(url, headers=headers).json()

        matches = []

        for e in data.get("events", []):

            matches.append({
                "home": e["homeTeam"]["name"],
                "away": e["awayTeam"]["name"],
                "home_id": e["homeTeam"]["id"],
                "away_id": e["awayTeam"]["id"]
            })

        return matches

    except:
        return []

# =========================
# HISTÓRICO REAL DO TIME
# =========================
def get_team_last_matches(team_id, n=10):

    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/{n}"

    try:
        data = requests.get(url).json()

        matches = []

        for e in data.get("events", []):

            home = e["homeScore"]["current"]
            away = e["awayScore"]["current"]

            if home is None or away is None:
                continue

            matches.append((home, away))

        return matches

    except:
        return []

# =========================
# FEATURES REAIS
# =========================
def build_features(team_id):

    matches = get_team_last_matches(team_id)

    if not matches:
        return [0,0,0]

    goals_for = np.mean([m[0] for m in matches])
    goals_against = np.mean([m[1] for m in matches])

    form = sum([1 if m[0]>m[1] else 0 for m in matches]) / len(matches)

    return [goals_for, goals_against, form]

# =========================
# MODELO CALIBRADO
# =========================
def predict(home_feat, away_feat):

    attack_diff = home_feat[0] - away_feat[1]
    defense_diff = away_feat[0] - home_feat[1]
    form_diff = home_feat[2] - away_feat[2]

    score = (attack_diff * 2.5) + (form_diff * 2.0) - (defense_diff * 1.5)

    prob = 1 / (1 + np.exp(-score))

    if prob > 0.60:
        pick = "HOME"
    elif prob < 0.40:
        pick = "AWAY"
    else:
        pick = "NO BET"

    return pick, prob

# =========================
# MERCADOS
# =========================
def markets(prob):

    return {
        "Gols": "Over 2.5" if prob > 0.55 else "Under 2.5",
        "Cantos": "Over 9.5" if prob > 0.52 else "Under 9.5",
        "Cartões": "Over 4.5" if prob > 0.52 else "Under 4.5"
    }

# =========================
# SNIPER
# =========================
def sniper(prob):
    return prob > 0.70 or prob < 0.30

# =========================
# STREAMLIT
# =========================
st.set_page_config(layout="wide")

st.title("📊 Greg Stats X V12 - Scanner REAL")

sniper_mode = st.checkbox("🔥 Modo SNIPER")

if st.button("📅 Buscar jogos do dia"):

    matches = get_today_matches()

    if not matches:
        st.error("Erro ao buscar jogos")
        st.stop()

    rows = []

    for m in matches:

        home_feat = build_features(m["home_id"])
        away_feat = build_features(m["away_id"])

        if home_feat == [0,0,0] or away_feat == [0,0,0]:
            continue

        pick, prob = predict(home_feat, away_feat)

        if sniper_mode and not sniper(prob):
            continue

        mk = markets(prob)

        rows.append({
            "Jogo": f"{m['home']} vs {m['away']}",
            "Pick": pick,
            "Confiança": round(prob,2),
            "Gols": mk["Gols"],
            "Cantos": mk["Cantos"],
            "Cartões": mk["Cartões"],
            "Sniper": "🔥" if sniper(prob) else ""
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Nenhuma entrada encontrada")
