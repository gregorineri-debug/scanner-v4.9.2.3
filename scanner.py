import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
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
# SOFASCORE
# -------------------------
def get_events(date):
    try:
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
        response = requests.get(url, timeout=10)
        return response.json().get("events", [])
    except:
        return []

# -------------------------
# MODELO BASE
# -------------------------
def league_strength(league_id):
    fortes = [17, 8, 23, 35, 34]
    medias = [390, 18, 44, 53, 182]

    if league_id in fortes:
        return 0.75
    elif league_id in medias:
        return 0.65
    else:
        return 0.55

def gerar_probabilidades(row):
    base = league_strength(row["LeagueID"])

    hora = int(row["Hora"].split(":")[0])
    fator_hora = 1.0 if 12 <= hora <= 20 else 0.9

    variacao = random.uniform(-0.05, 0.05)

    prob_base = base * fator_hora + variacao

    prob_1x = round(min(max(prob_base * 100, 55), 90))
    prob_12 = round(min(max((prob_base - 0.05) * 100, 50), 85))
    prob_x2 = round(min(max((prob_base - 0.08) * 100, 45), 80))

    return prob_1x, prob_12, prob_x2

# -------------------------
# CONSENSO PRO (FILTRO)
# -------------------------
def aplicar_consenso(df):
    df["Score_Consenso"] = (df["1X"] + df["12"] + df["X2"]) / 3
    return df[df["Score_Consenso"] >= 65]

# -------------------------
# GREG STATS X V4.5
# -------------------------
def aplicar_greg_stats(df):

    picks = []

    for _, row in df.iterrows():

        # lógica de vencedor baseada em força relativa
        if row["1X"] >= row["X2"]:
            pick = "Casa (1)"
        else:
            pick = "Fora (2)"

        picks.append(pick)

    df["Pick_Vencedor"] = picks

    return df

# -------------------------
# FILTROS
# -------------------------
def is_valid_league(event):
    try:
        return event["tournament"]["uniqueTournament"]["id"] in VALID_LEAGUE_IDS
    except:
        return False

def is_same_day_br(event, selected_date):
    try:
        utc = datetime.utcfromtimestamp(event["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
        br_time = utc.astimezone(BR_TZ)
        return br_time.date() == selected_date
    except:
        return False

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V7 (Consenso PRO + Greg Stats V4.5)")

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
            br_time = utc.astimezone(BR_TZ).strftime("%H:%M")

            results.append({
                "Hora": br_time,
                "Liga": LEAGUE_NAMES.get(
                    e["tournament"]["uniqueTournament"]["id"], "Outra"
                ),
                "LeagueID": e["tournament"]["uniqueTournament"]["id"],
                "Jogo": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}"
            })

        except:
            continue

    if results:
        df = pd.DataFrame(results).sort_values(by="Hora")

        # probabilidades
        probs = df.apply(gerar_probabilidades, axis=1)
        df["1X"], df["12"], df["X2"] = zip(*probs)

        # aplica CONSENSO PRO
        df = aplicar_consenso(df)

        # aplica GREG STATS
        df = aplicar_greg_stats(df)

        st.dataframe(df.drop(columns=["LeagueID"]), use_container_width=True)
        st.write(f"Jogos filtrados: {len(df)}")

    else:
        st.warning("Nenhum jogo encontrado.")
