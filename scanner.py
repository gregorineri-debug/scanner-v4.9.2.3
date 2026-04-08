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
# FORÇA DA LIGA
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
# SCORE
# -------------------------
def calcular_score(forma, saldo, gols, league_id):
    forma_n, saldo_n, ataque_n = normalizar(forma, saldo, gols)

    base_score = (
        forma_n * 10 +
        saldo_n * 12 +
        ataque_n * 5
    )

    liga_strength = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(base_score * liga_strength, 2)

# -------------------------
# PICK
# -------------------------
def definir_pick(diff):
    if diff >= 3:
        return "Casa (1) 🔥" if diff >= 5 else "Casa (1)"
    elif diff <= -5:
        return "Fora (2) 🔥" if diff <= -7 else "Fora (2)"
    else:
        return "Equilibrado"

# -------------------------
# FILTRO V16
# -------------------------
def passar_filtros(f_home, s_home, g_home, f_away, s_away, g_away, league_id):

    liga_strength = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    # 1. Forma mínima
    if f_home < 1.2 and f_away < 1.2:
        return False

    # 2. Saldo não negativo (pelo menos um)
    if s_home < 0 and s_away < 0:
        return False

    # 3. Diferença de forma
    if abs(f_home - f_away) < 0.4:
        return False

    # 4. Liga forte
    if liga_strength < 0.8:
        return False

    # 5. Ataque falso
    if (g_home > 2 and s_home < 0.3) or (g_away > 2 and s_away < 0.3):
        return False

    return True

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V16 (Filtro Anti-Loss Ativado)")

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

            f_home, s_home, g_home = get_team_data(home_id)
            f_away, s_away, g_away = get_team_data(away_id)

            # FILTRO V16
            if not passar_filtros(f_home, s_home, g_home, f_away, s_away, g_away, league_id):
                continue

            score_home = calcular_score(f_home, s_home, g_home, league_id)
            score_away = calcular_score(f_away, s_away, g_away, league_id)

            diff = round(score_home - score_away, 2)

            # FILTRO FINAL DE ENTRADA
            if not (diff >= 4 or diff <= -5):
                continue

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
        st.write(f"Total de jogos filtrados: {len(df)}")
    else:
        st.warning("Nenhum jogo passou nos filtros V16.")
