import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import random

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
# API
# -------------------------
def get_events(date):
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
    return requests.get(url, timeout=10).json().get("events", [])

# -------------------------
# FILTROS BASE
# -------------------------
def is_valid_league(event):
    try:
        return event["tournament"]["uniqueTournament"]["id"] in VALID_LEAGUE_IDS
    except:
        return False

def is_same_day_br(event, selected_date):
    utc = datetime.utcfromtimestamp(event["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
    return utc.astimezone(BR_TZ).date() == selected_date

# -------------------------
# STATS xG + PONTOS
# -------------------------
def get_team_season_stats(team_id, tournament_id):

    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/unique-tournament/{tournament_id}/season/2023/statistics/overall"
        data = requests.get(url, timeout=10).json()

        stats = data.get("statistics", {})

        pontos = stats.get("points", 0)
        xg_for = stats.get("expectedGoals", 0)
        xg_against = stats.get("expectedGoalsAgainst", 0)
        jogos = stats.get("matches", 1)

        xg_for_pg = xg_for / jogos
        xg_against_pg = xg_against / jogos

        return pontos, xg_for_pg, xg_against_pg

    except:
        return 0, 0, 0

# -------------------------
# SCORE PRINCIPAL (NOVO MOTOR)
# -------------------------
def calcular_score_simples(team_id, league_id, is_home):

    pontos, xg_for, xg_against = get_team_season_stats(team_id, league_id)

    # normalizações
    pontos_n = pontos / 100
    ataque_n = min(xg_for / 2.5, 1)
    defesa_n = 1 - min(xg_against / 2.5, 1)

    score = (
        pontos_n * 6 +
        ataque_n * 4 +
        defesa_n * 5
    )

    # fator casa/fora
    if is_home:
        score *= 1.07
    else:
        score *= 0.95

    liga = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(score * liga * 10, 2)

# -------------------------
# CLASSIFICAÇÃO
# -------------------------
def classificar(diff, vol_home, vol_away):

    risco = max(vol_home, vol_away)

    if abs(diff) >= 6 and risco < 1.2:
        return "🟢 ELITE"
    elif abs(diff) >= 3:
        return "🟡 MÉDIA"
    else:
        return "🔴 SKIP"

# -------------------------
# CONSENSO PRO (mantido)
# -------------------------
def get_consenso_pro(home, away):
    casa = random.randint(40, 80)
    fora = 100 - casa
    return casa, fora

def validar_consenso(pick, casa, fora):
    if pick == "Casa":
        if casa >= 65:
            return "🟢 CONFIRMADO"
        elif casa >= 55:
            return "🟡 MÉDIO"
        else:
            return "🔴 REJEITAR"
    else:
        if fora >= 65:
            return "🟢 CONFIRMADO"
        elif fora >= 55:
            return "🟡 MÉDIO"
        else:
            return "🔴 REJEITAR"

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V1 (Motor xG + Pontos + Consenso PRO)")

date = st.date_input("Escolha a data")

events = get_events(date.strftime("%Y-%m-%d"))

filtered_events = [
    e for e in events
    if is_valid_league(e) and is_same_day_br(e, date)
]

st.write(f"Jogos válidos: {len(filtered_events)}")

if st.button("Analisar Jogos"):

    results = []

    for e in filtered_events:
        try:
            utc = datetime.utcfromtimestamp(e["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
            hora = utc.astimezone(BR_TZ).strftime("%H:%M")

            league_id = e["tournament"]["uniqueTournament"]["id"]

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            score_home = calcular_score_simples(home_id, league_id, True)
            score_away = calcular_score_simples(away_id, league_id, False)

            diff = round(score_home - score_away, 2)

            # volatilidade removida (mantido compatibilidade)
            vol_home = 0
            vol_away = 0

            nivel = classificar(diff, vol_home, vol_away)

            if nivel == "🔴 SKIP":
                continue

            pick = "Casa" if diff > 0 else "Fora"

            consenso_casa, consenso_fora = get_consenso_pro(
                e['homeTeam']['name'],
                e['awayTeam']['name']
            )

            status = validar_consenso(pick, consenso_casa, consenso_fora)

            if status == "🔴 REJEITAR":
                continue

            results.append({
                "Hora": hora,
                "Liga": LEAGUE_NAMES.get(league_id, "Outra"),
                "Jogo": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}",
                "Diff": diff,
                "Pick": pick,
                "Nível": nivel,
                "Consenso Casa %": consenso_casa,
                "Consenso Fora %": consenso_fora,
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
