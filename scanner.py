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
# FEATURES
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

        gm = hs if home else as_
        gs = as_ if home else hs

        gols_marcados.append(gm)
        gols_sofridos.append(gs)

        if gm > gs:
            pontos.append(3)
        elif gm == gs:
            pontos.append(1)
        else:
            pontos.append(0)

    pontos = np.array(pontos)

    forma = pontos.mean()
    saldo = (np.array(gols_marcados) - np.array(gols_sofridos)).mean()
    defesa = np.mean(gols_sofridos)
    volatilidade = pontos.std()

    return forma, saldo, defesa, volatilidade

# -------------------------
# SCORE SIMPLES
# -------------------------
def calcular_score(team_id, league_id, is_home):

    forma, saldo, defesa, vol = extrair_features(team_id)

    forma_n = forma / 3
    saldo_n = max(min(saldo / 3,1),-1)
    defesa_n = 1 - min(defesa / 3,1)

    # ajuste dinâmico
    if abs(forma - 1.5) < 0.3:
        pf, ps, pd = 4, 3, 7
    else:
        pf, ps, pd = 6, 4, 6

    score = (forma_n * pf) + (saldo_n * ps) + (defesa_n * pd)

    if is_home:
        score *= 1.08
    else:
        score *= 0.95

    liga = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(score * liga * 10, 2)

# -------------------------
# PROBABILIDADE + EV
# -------------------------
def calcular_probabilidade(diff):
    prob = 0.5 + (abs(diff) * 0.04)
    return min(prob, 0.85)

def calcular_ev(prob, odd):
    return (prob * odd) - 1

def classificar_ev(ev):
    if ev > 0.15:
        return "🟢 ELITE"
    elif ev > 0.08:
        return "🟡 BOA"
    elif ev > 0:
        return "⚪ FRACA"
    else:
        return "❌ RUIM"

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V2 (EV+ Value Bet)")

date = st.date_input("Escolha a data")

events = get_events(date.strftime("%Y-%m-%d"))

filtered_events = events

st.write(f"Jogos: {len(filtered_events)}")

st.subheader("Inserir odds manualmente")

odds_input = st.text_area(
    "Formato: TimeA vs TimeB = odd_casa,odd_fora\nEx:\nFlamengo vs Santos = 1.80,4.50"
)

# -------------------------
# PARSE ODDS
# -------------------------
odds_dict = {}

for line in odds_input.split("\n"):
    try:
        jogo, odds = line.split("=")
        casa, fora = odds.split(",")
        odds_dict[jogo.strip()] = (float(casa), float(fora))
    except:
        continue

# -------------------------
# PROCESSAMENTO
# -------------------------
if st.button("Analisar com EV+"):

    results = []

    for e in filtered_events:
        try:
            league_id = e["tournament"]["uniqueTournament"]["id"]

            home = e["homeTeam"]["name"]
            away = e["awayTeam"]["name"]

            match_name = f"{home} vs {away}"

            if match_name not in odds_dict:
                continue

            odd_home, odd_away = odds_dict[match_name]

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            score_home = calcular_score(home_id, league_id, True)
            score_away = calcular_score(away_id, league_id, False)

            diff = score_home - score_away

            if abs(diff) < 3:
                continue

            pick = "Casa" if diff > 0 else "Fora"

            prob = calcular_probabilidade(diff)

            odd = odd_home if pick == "Casa" else odd_away

            ev = calcular_ev(prob, odd)

            if ev <= 0:
                continue

            qualidade = classificar_ev(ev)

            results.append({
                "Jogo": match_name,
                "Pick": pick,
                "Odd": odd,
                "Prob": round(prob*100,1),
                "EV": round(ev,3),
                "Qualidade": qualidade
            })

        except:
            continue

    if results:
        df = pd.DataFrame(results).sort_values(by="EV", ascending=False)
        st.dataframe(df, use_container_width=True)
        st.write(f"Apostas com valor: {len(df)}")
    else:
        st.warning("Nenhuma aposta com EV+ encontrada.")
