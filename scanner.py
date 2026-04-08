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
# SOFASCORE
# -------------------------
def get_events(date):
    try:
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
        return requests.get(url, timeout=10).json().get("events", [])
    except:
        return []

# -------------------------
# ÚLTIMOS JOGOS
# -------------------------
def get_team_last_matches(team_id):
    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"
        data = requests.get(url, timeout=10).json()["events"]

        pontos = 0
        gols_marcados = 0
        gols_sofridos = 0

        for e in data:
            home = e["homeTeam"]["id"] == team_id
            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            if home:
                gols_marcados += hs
                gols_sofridos += as_
                pontos += 3 if hs > as_ else 1 if hs == as_ else 0
            else:
                gols_marcados += as_
                gols_sofridos += hs
                pontos += 3 if as_ > hs else 1 if as_ == hs else 0

        jogos = len(data)
        if jogos == 0:
            return 1,1,1

        return pontos/jogos, gols_marcados/jogos, gols_sofridos/jogos

    except:
        return 1,1,1

# -------------------------
# FORÇA
# -------------------------
def get_team_strength(team_id):
    forma, ataque, defesa = get_team_last_matches(team_id)
    xg = ataque - defesa

    return (
        forma * 10 +
        ataque * 5 +
        (2 - defesa) * 5 +
        xg * 5
    )

# -------------------------
# PROBABILIDADES
# -------------------------
def gerar_probabilidades(home_id, away_id):

    home = get_team_strength(home_id)
    away = get_team_strength(away_id)

    diff = home - away

    prob_home = max(min(50 + diff * 1.2, 85), 35)
    prob_away = max(min(50 - diff * 1.2, 85), 35)

    prob_1x = round(min(prob_home + 10, 95))
    prob_x2 = round(min(prob_away + 10, 95))
    prob_12 = round((prob_home + prob_away) / 2)

    return prob_1x, prob_12, prob_x2

# -------------------------
# CONSENSO (CORRIGIDO)
# -------------------------
def aplicar_consenso(df):

    df["Score_Consenso"] = (
        (df["1X"] + df["12"] + df["X2"]) / 3
    ).astype(int)

    return df.sort_values(by="Score_Consenso", ascending=False)

# -------------------------
# GREG
# -------------------------
def aplicar_greg(df):
    df["Pick_Vencedor"] = df.apply(
        lambda x: "Casa (1)" if x["1X"] > x["X2"] else "Fora (2)",
        axis=1
    )
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
        return utc.astimezone(BR_TZ).date() == selected_date
    except:
        return False

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V10 (Modelo Avançado Real)")

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

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            p1x, p12, px2 = gerar_probabilidades(home_id, away_id)

            results.append({
                "Hora": hora,
                "Liga": LEAGUE_NAMES.get(e["tournament"]["uniqueTournament"]["id"], "Outra"),
                "Jogo": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}",
                "1X": p1x,
                "12": p12,
                "X2": px2
            })

        except:
            continue

    if results:
        df = pd.DataFrame(results)

        df = aplicar_consenso(df)
        df = aplicar_greg(df)

        st.dataframe(df, use_container_width=True)
        st.write(f"Total de jogos avaliados: {len(df)}")

    else:
        st.warning("Nenhum jogo encontrado.")
