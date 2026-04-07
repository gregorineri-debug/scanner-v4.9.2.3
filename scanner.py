import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import re

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
# API SOFASCORE
# -------------------------
def get_events(date):
    try:
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
        return requests.get(url, timeout=10).json().get("events", [])
    except:
        return []

# -------------------------
# BETMINES (PEGANDO SÓ PROB %)
# -------------------------
def get_betmines_data():
    try:
        url = "https://betmines.com/pt/palpite-futebol-hoje/dupla-chance"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "pt-BR,pt;q=0.9"
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return pd.DataFrame(columns=["Jogo", "1X", "12", "X2"])

        # pega TODAS as tabelas
        tables = pd.read_html(response.text)

        if not tables:
            return pd.DataFrame(columns=["Jogo", "1X", "12", "X2"])

        df = tables[0]

        jogos = []

        for _, row in df.iterrows():
            try:
                jogo = str(row.iloc[0])

                # pega todos números da linha
                nums = re.findall(r'\d+', str(row))

                # precisa ter pelo menos 3 números
                if len(nums) >= 3:
                    jogos.append({
                        "Jogo": jogo,
                        "1X": nums[-3],
                        "12": nums[-2],
                        "X2": nums[-1],
                    })

            except:
                continue

        return pd.DataFrame(jogos)

    except:
        return pd.DataFrame(columns=["Jogo", "1X", "12", "X2"])

# -------------------------
# MATCH
# -------------------------
def merge_data(df_sofa, df_betmines):

    def normalize(name):
        return str(name).lower().replace(" vs ", " ").strip()

    if df_betmines.empty:
        df_sofa["1X"] = None
        df_sofa["12"] = None
        df_sofa["X2"] = None
        return df_sofa

    df_sofa["key"] = df_sofa["Jogo"].apply(normalize)
    df_betmines["key"] = df_betmines["Jogo"].apply(normalize)

    merged = pd.merge(df_sofa, df_betmines, on="key", how="left")

    return merged.drop(columns=["key"])

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
    br_time = utc.astimezone(BR_TZ)
    return br_time.date() == selected_date

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V6.6 (Probabilidades Betmines)")

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
                "Jogo": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}"
            })

        except:
            continue

    if results:
        df_sofa = pd.DataFrame(results).sort_values(by="Hora")

        df_betmines = get_betmines_data()

        if df_betmines.empty:
            st.warning("⚠️ Betmines não retornou dados.")

        df_final = merge_data(df_sofa, df_betmines)

        st.dataframe(df_final, use_container_width=True)
        st.write(f"Total de jogos: {len(df_final)}")

    else:
        st.warning("Nenhum jogo encontrado.")
