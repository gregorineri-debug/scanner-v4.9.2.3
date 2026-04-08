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
# DADOS COMPLETOS DO TIME
# -------------------------
def get_team_events(team_id, limit=10):
    try:
        data = requests.get(
            f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/{limit}",
            timeout=10
        ).json().get("events", [])
        return data
    except:
        return []

# -------------------------
# FEATURES AVANÇADAS
# -------------------------
def extrair_features(team_id):

    events = get_team_events(team_id, 10)

    if not events:
        return 1,0,1,1,1,1

    pontos = []
    gols_marcados = []
    gols_sofridos = []

    for e in events:
        home = e["homeTeam"]["id"] == team_id
        hs = e["homeScore"]["current"]
        as_ = e["awayScore"]["current"]

        if home:
            gm, gs = hs, as_
        else:
            gm, gs = as_, hs

        gols_marcados.append(gm)
        gols_sofridos.append(gs)

        if gm > gs:
            pontos.append(3)
        elif gm == gs:
            pontos.append(1)
        else:
            pontos.append(0)

    pontos = np.array(pontos)

    forma_base = pontos.mean()
    saldo = (np.array(gols_marcados) - np.array(gols_sofridos)).mean()
    defesa = np.mean(gols_sofridos)

    ult3 = pontos[:3].mean() if len(pontos) >= 3 else forma_base
    momento = (forma_base * 0.6) + (ult3 * 0.4)

    volatilidade = pontos.std()
    ataque = np.mean(gols_marcados)

    return forma_base, saldo, ataque, defesa, momento, volatilidade

# -------------------------
# SCORE V1
# -------------------------
def calcular_score_v1(team_id, league_id, is_home):

    forma, saldo, ataque, defesa, momento, vol = extrair_features(team_id)

    forma_n = forma / 3
    saldo_n = max(min(saldo / 3,1),-1)
    ataque_n = min(ataque / 3,1)
    defesa_n = 1 - min(defesa / 3,1)

    momento_n = momento / 3
    vol_penalty = 1 - min(vol / 3, 1)

    estrutural = (
        forma_n * 0.5 +
        saldo_n * 0.3 +
        defesa_n * 0.2
    )

    score = (
        estrutural * 0.45 +
        momento_n * 0.35 +
        vol_penalty * 0.20
    )

    if is_home:
        score *= 1.10
    else:
        score *= 0.93

    liga = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(score * liga * 100, 2)

# -------------------------
# CLASSIFICAÇÃO
# -------------------------
def classificar(diff, vol_home, vol_away):
    risco = max(vol_home, vol_away)

    if abs(diff) >= 15 and risco < 1.2:
        return "🟢 ELITE"
    elif abs(diff) >= 8:
        return "🟡 MÉDIA"
    else:
        return "🔴 EVITAR"

# -------------------------
# CONSENSO PRO (PLACEHOLDER)
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
st.title("⚽ Scanner PRO V1 + Consenso PRO")

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

            score_home = calcular_score_v1(home_id, league_id, True)
            score_away = calcular_score_v1(away_id, league_id, False)

            diff = round(score_home - score_away, 2)

            _, _, _, _, _, vol_home = extrair_features(home_id)
            _, _, _, _, _, vol_away = extrair_features(away_id)

            nivel = classificar(diff, vol_home, vol_away)

            pick = "Casa" if diff > 0 else "Fora"

            # CONSENSO
            consenso_casa, consenso_fora = get_consenso_pro(
                e['homeTeam']['name'],
                e['awayTeam']['name']
            )

            status = validar_consenso(pick, consenso_casa, consenso_fora)

            # FILTRO FINAL
            if status == "🔴 REJEITAR":
                continue

            results.append({
                "Hora": hora,
                "Liga": LEAGUE_NAMES.get(league_id, "Outra"),
                "Jogo": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}",
                "Diff": diff,
                "Pick": pick,
                "Confiança Modelo": nivel,
                "Consenso Casa %": consenso_casa,
                "Consenso Fora %": consenso_fora,
                "Status Final": status
            })

        except:
            continue

    if results:
        df = pd.DataFrame(results).sort_values(by="Diff", ascending=False)
        st.dataframe(df, use_container_width=True)
        st.write(f"Total de picks confirmadas: {len(df)}")
    else:
        st.warning("Nenhuma pick passou no filtro + consenso.")
