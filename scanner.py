import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

BR_TZ = ZoneInfo("America/Sao_Paulo")

VALID_LEAGUE_IDS = [
    325,390,17,18,8,54,35,44,23,53,34,182,955,
    155,703,45,38,247,172,11653,11539,11536,
    170,39,808,36,242,185,37,131,192,937,
    11621,11620,20,11540,11541,406,202,
    238,239,152,40,215,52,278
]

LEAGUE_STRENGTH = {
    17: 1.0, 8: 1.0, 23: 1.0, 35: 1.0,
    34: 0.95, 238: 0.9,
    325: 0.9,
    955: 0.85,
    52: 0.85,
    247: 0.75,
    808: 0.7,
    703: 0.7
}

DEFAULT_LEAGUE_STRENGTH = 0.8

# -------------------------
# API
# -------------------------
def get_events(date):
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
    return requests.get(url, timeout=10).json().get("events", [])

def get_finished_events(date):
    url = f"https://api.sofascore.com/api/v1/sport/football/events/{date}"
    return requests.get(url, timeout=10).json().get("events", [])

# -------------------------
# DADOS DO TIME
# -------------------------
def get_team_data(team_id):
    try:
        data = requests.get(
            f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5",
            timeout=10
        ).json().get("events", [])

        pts, gm, gs = 0, 0, 0

        for e in data:
            home = e["homeTeam"]["id"] == team_id
            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            if home:
                gm += hs; gs += as_
                pts += 3 if hs > as_ else 1 if hs == as_ else 0
            else:
                gm += as_; gs += hs
                pts += 3 if as_ > hs else 1 if as_ == hs else 0

        jogos = len(data) if data else 1

        return pts / jogos, (gm - gs) / jogos, gm / jogos

    except:
        return 1, 0, 1

# -------------------------
# NORMALIZAÇÃO
# -------------------------
def normalizar(forma, saldo, gols):
    return forma/3, max(min(saldo/3,1),-1), min(gols/3,1)

# -------------------------
# SCORE
# -------------------------
def calcular_score(f, s, g, league_id):
    fn, sn, gn = normalizar(f, s, g)

    base = fn*10 + sn*12 + gn*5
    liga = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(base * liga, 2)

# -------------------------
# PICK
# -------------------------
def definir_pick(diff):
    if diff >= 3:
        return "Casa"
    elif diff <= -5:
        return "Fora"
    else:
        return "Skip"

# -------------------------
# FILTRO V16
# -------------------------
def passar_filtros(fh, sh, gh, fa, sa, ga, league_id):

    liga = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    if fh < 1.2 and fa < 1.2:
        return False
    if sh < 0 and sa < 0:
        return False
    if abs(fh-fa) < 0.4:
        return False
    if liga < 0.8:
        return False
    if (gh>2 and sh<0.3) or (ga>2 and sa<0.3):
        return False

    return True

# -------------------------
# FAIXAS
# -------------------------
def faixa_diff(diff):
    d = abs(diff)
    if d >= 7:
        return "7+"
    elif d >= 6:
        return "6-7"
    elif d >= 5:
        return "5-6"
    elif d >= 4:
        return "4-5"
    else:
        return "baixo"

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V17 + Backtest")

modo = st.radio("Modo", ["Scanner", "Backtest"])

date = st.date_input("Escolha a data")

if modo == "Scanner":

    events = get_events(date.strftime("%Y-%m-%d"))

    results = []

    for e in events:
        try:
            league_id = e["tournament"]["uniqueTournament"]["id"]

            if league_id not in VALID_LEAGUE_IDS:
                continue

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            fh, sh, gh = get_team_data(home_id)
            fa, sa, ga = get_team_data(away_id)

            if not passar_filtros(fh, sh, gh, fa, sa, ga, league_id):
                continue

            shome = calcular_score(fh, sh, gh, league_id)
            saway = calcular_score(fa, sa, ga, league_id)

            diff = shome - saway

            if not (diff >= 4 or diff <= -5):
                continue

            results.append(diff)

        except:
            continue

    st.write("Picks encontrados:", len(results))


# -------------------------
# BACKTEST
# -------------------------
if modo == "Backtest":

    events = get_finished_events(date.strftime("%Y-%m-%d"))

    total = 0
    acertos = 0

    stats = {}

    for e in events:
        try:
            league_id = e["tournament"]["uniqueTournament"]["id"]

            if league_id not in VALID_LEAGUE_IDS:
                continue

            if "homeScore" not in e or "awayScore" not in e:
                continue

            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            fh, sh, gh = get_team_data(home_id)
            fa, sa, ga = get_team_data(away_id)

            if not passar_filtros(fh, sh, gh, fa, sa, ga, league_id):
                continue

            shome = calcular_score(fh, sh, gh, league_id)
            saway = calcular_score(fa, sa, ga, league_id)

            diff = shome - saway

            if not (diff >= 4 or diff <= -5):
                continue

            pick = definir_pick(diff)

            if pick == "Skip":
                continue

            total += 1

            resultado = "Casa" if hs > as_ else "Fora" if as_ > hs else "Empate"

            win = (pick == resultado)

            if win:
                acertos += 1

            faixa = faixa_diff(diff)

            if faixa not in stats:
                stats[faixa] = {"total":0,"win":0}

            stats[faixa]["total"] += 1
            if win:
                stats[faixa]["win"] += 1

        except:
            continue

    if total > 0:
        st.write("Acerto geral:", round(acertos/total*100,2), "%")

        tabela = []
        for f in stats:
            t = stats[f]["total"]
            w = stats[f]["win"]
            taxa = round(w/t*100,2) if t else 0

            tabela.append([f, t, taxa])

        df = pd.DataFrame(tabela, columns=["Faixa Diff","Jogos","Acerto %"])
        st.dataframe(df)

    else:
        st.write("Sem dados suficientes.")
