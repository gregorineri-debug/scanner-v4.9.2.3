import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

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
    325: "Brasileirão", 390: "Série B", 17: "Premier League",
    18: "Championship", 8: "La Liga", 54: "La Liga 2",
    35: "Bundesliga", 44: "2. Bundesliga", 23: "Serie A",
    53: "Serie B Itália", 34: "Ligue 1", 182: "Ligue 2",
    955: "Saudi Pro League", 155: "Argentina Liga",
    703: "Primera Nacional", 45: "Áustria", 38: "Bélgica",
    247: "Bulgária", 172: "Rep. Tcheca", 11653: "Chile",
    11539: "Colômbia Apertura", 11536: "Colômbia Finalización",
    170: "Croácia", 39: "Dinamarca", 808: "Egito",
    36: "Escócia", 242: "MLS", 185: "Grécia",
    37: "Eredivisie", 131: "Eerste Divisie", 192: "Irlanda",
    937: "Marrocos", 11621: "Liga MX Apertura",
    11620: "Liga MX Clausura", 20: "Noruega",
    11540: "Paraguai Apertura", 11541: "Paraguai Clausura",
    406: "Peru", 202: "Polônia", 238: "Portugal",
    239: "Portugal 2", 152: "Romênia", 40: "Suécia",
    215: "Suíça", 52: "Turquia", 278: "Uruguai"
}

# -------------------------
# FORÇA DA LIGA (ANTI-ZEBRA)
# -------------------------
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

# -------------------------
# FILTROS
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

        forma = pts / jogos
        saldo = (gm - gs) / jogos
        gols = gm / jogos

        return forma, saldo, gols

    except:
        return 1, 0, 1

# -------------------------
# NORMALIZAÇÃO
# -------------------------
def normalizar(forma, saldo, gols):
    forma_n = forma / 3
    saldo_n = max(min(saldo / 3, 1), -1)
    ataque_n = min(gols / 3, 1)

    return forma_n, saldo_n, ataque_n

# -------------------------
# SCORE COM LIGA
# -------------------------
def calcular_score(team_id, league_id):
    forma, saldo, gols = get_team_data(team_id)
    forma_n, saldo_n, ataque_n = normalizar(forma, saldo, gols)

    base_score = (
        forma_n * 8 +
        saldo_n * 8 +
        ataque_n * 10
    )

    liga_strength = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    final_score = base_score * liga_strength

    return round(final_score, 2)

# -------------------------
# PICK (AJUSTADO)
# -------------------------
def definir_pick(diff):

    # CASA → diferença >= 3
    if diff >= 3:
        return "Casa (1) 🔥" if diff >= 5 else "Casa (1)"

    # FORA → diferença <= -5
    elif diff <= -5:
        return "Fora (2) 🔥" if diff <= -7 else "Fora (2)"

    # RESTO → neutro
    else:
        return "Equilibrado"

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V15 (Anti-Zebra Ativado)")

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

            score_home = calcular_score(home_id, league_id)
            score_away = calcular_score(away_id, league_id)

            diff = round(score_home - score_away, 2)

            pick = definir_pick(diff)

            results.append({
                "Hora": hora,
                "Liga": LEAGUE_NAMES.get(league_id, "Outra"),
                "Jogo": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}",
                "Score_Casa": score_home,
                "Score_Fora": score_away,
                "Diferença": diff,
                "Pick": pick
            })

        except:
            continue

    if results:
        df = pd.DataFrame(results).sort_values(by="Hora")
        st.dataframe(df, use_container_width=True)
        st.write(f"Total de jogos: {len(df)}")
    else:
        st.warning("Nenhum jogo encontrado.")
