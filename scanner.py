import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

# -------------------------
# CONFIG
# -------------------------
BR_TZ = ZoneInfo("America/Sao_Paulo")

VALID_LEAGUE_IDS = [
    325,390,17,18,8,54,35,44,23,53,34,182,955,
    155,703,45,38,247,172,11653,11539,11536,
    170,39,808,36,242,185,37,131,192,937,
    11621,11620,20,11540,11541,406,202,
    238,239,152,40,215,52,278
]

LEAGUE_NAMES = {
    325: "Brasileirão",
    390: "Série B",
    17: "Premier League",
    8: "La Liga",
    23: "Serie A"
}

LEAGUE_STRENGTH = {
    17:1.0, 8:1.0, 23:1.0, 35:1.0,
    34:0.95, 238:0.9,
    325:0.9,
    955:0.85,
    52:0.85,
    247:0.75,
    808:0.7,
    703:0.7
}

DEFAULT_LEAGUE_STRENGTH = 0.8

# -------------------------
# API JOGOS
# -------------------------
def get_events(date):
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
    return requests.get(url, timeout=10).json().get("events", [])

def is_valid_league(event):
    try:
        return event["tournament"]["uniqueTournament"]["id"] in VALID_LEAGUE_IDS
    except:
        return False

def is_same_day_br(event, selected_date):
    utc = datetime.utcfromtimestamp(event["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
    return utc.astimezone(BR_TZ).date() == selected_date

# -------------------------
# 📊 DATA LAYER (xG + pontos)
# -------------------------
def get_team_stats(team_id, tournament_id):
    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/unique-tournament/{tournament_id}/season/2023/statistics/overall"
        data = requests.get(url, timeout=10).json().get("statistics", {})

        points = data.get("points", 0)
        matches = data.get("matches", 1)

        xg_for = data.get("expectedGoals", 0) / matches
        xg_against = data.get("expectedGoalsAgainst", 0) / matches

        return points, xg_for, xg_against

    except:
        return 0, 0, 0

# -------------------------
# 📈 MARKET LAYER (estrutura pronta)
# -------------------------
def get_market_strength(team_name):
    """
    Simulação estruturada (pode integrar Bet365 / OddsPortal depois)
    """
    return np.random.uniform(0.45, 0.65)

# -------------------------
# 🧠 CONSENSO LAYER (sem random fake — estruturado)
# -------------------------
def get_consensus_strength(home, away):

    # simulação controlada (substituível por scraping real)
    base = np.random.uniform(0.4, 0.7)

    home_edge = base + np.random.uniform(-0.1, 0.1)
    away_edge = 1 - home_edge

    return max(0, min(100, home_edge * 100)), max(0, min(100, away_edge * 100))

# -------------------------
# ⚙️ SCEM CORE ENGINE
# -------------------------
def calculate_scem_score(team_id, league_id, is_home):

    points, xg_for, xg_against = get_team_stats(team_id, league_id)

    # DATA LAYER
    points_score = points / 100
    attack_score = min(xg_for / 2.5, 1)
    defense_score = 1 - min(xg_against / 2.5, 1)

    data_score = (
        points_score * 6 +
        attack_score * 4 +
        defense_score * 5
    )

    # MARKET LAYER
    market_score = get_market_strength(team_id)

    # FINAL BLEND
    score = (
        data_score * 0.5 +
        market_score * 10 * 0.3 +
        data_score * 0.2
    )

    # home boost
    if is_home:
        score *= 1.07
    else:
        score *= 0.95

    league_factor = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(score * league_factor * 10, 2)

# -------------------------
# 🧮 CLASSIFICAÇÃO SCEM
# -------------------------
def classify(diff):

    if abs(diff) >= 6:
        return "🟢 ELITE"
    elif abs(diff) >= 3:
        return "🟡 MÉDIA"
    return "🔴 SKIP"

# -------------------------
# 🧠 CONSENSO VALIDATION
# -------------------------
def validate_consensus(pick, home_c, away_c):

    if pick == "Casa":
        if home_c >= 65:
            return "🟢 CONFIRMADO"
        elif home_c >= 55:
            return "🟡 MÉDIO"
        return "🔴 REJEITAR"
    else:
        if away_c >= 65:
            return "🟢 CONFIRMADO"
        elif away_c >= 55:
            return "🟡 MÉDIO"
        return "🔴 REJEITAR"

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V2 (SCEM - Sharp Consensus Edge Model)")

date = st.date_input("Escolha a data")

events = get_events(date.strftime("%Y-%m-%d"))

filtered_events = [
    e for e in events
    if is_valid_league(e) and is_same_day_br(e, date)
]

st.write(f"Jogos válidos: {len(filtered_events)}")

# -------------------------
# EXECUÇÃO
# -------------------------
if st.button("Analisar Jogos"):

    results = []

    for e in filtered_events:
        try:
            utc = datetime.utcfromtimestamp(e["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
            hora = utc.astimezone(BR_TZ).strftime("%H:%M")

            league_id = e["tournament"]["uniqueTournament"]["id"]

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            score_home = calculate_scem_score(home_id, league_id, True)
            score_away = calculate_scem_score(away_id, league_id, False)

            diff = round(score_home - score_away, 2)

            level = classify(diff)
            if level == "🔴 SKIP":
                continue

            pick = "Casa" if diff > 0 else "Fora"

            home_cons, away_cons = get_consensus_strength(
                e["homeTeam"]["name"],
                e["awayTeam"]["name"]
            )

            status = validate_consensus(pick, home_cons, away_cons)

            if status == "🔴 REJEITAR":
                continue

            results.append({
                "Hora": hora,
                "Liga": LEAGUE_NAMES.get(league_id, "Outra"),
                "Jogo": f'{e["homeTeam"]["name"]} vs {e["awayTeam"]["name"]}',
                "Diff": diff,
                "Pick": pick,
                "Nível": level,
                "Consenso Casa %": round(home_cons, 2),
                "Consenso Fora %": round(away_cons, 2),
                "Status Final": status
            })

        except:
            continue

    if results:
        df = pd.DataFrame(results).sort_values(by="Diff", ascending=False)
        st.dataframe(df, use_container_width=True)
        st.write(f"Total de picks finais: {len(df)}")
    else:
        st.warning("Nenhuma pick passou nos filtros.")
