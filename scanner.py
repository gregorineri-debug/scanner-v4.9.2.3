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

        pontos, gm, gs = 0, 0, 0

        for e in data:
            home = e["homeTeam"]["id"] == team_id
            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            if home:
                gm += hs; gs += as_
                pontos += 3 if hs > as_ else 1 if hs == as_ else 0
            else:
                gm += as_; gs += hs
                pontos += 3 if as_ > hs else 1 if as_ == hs else 0

        jogos = len(data)
        if jogos == 0:
            return 1,1,1

        return pontos/jogos, gm/jogos, gs/jogos

    except:
        return 1,1,1

# -------------------------
# FORÇA NORMALIZADA (CORRIGIDA)
# -------------------------
def get_team_strength(team_id):

    forma, ataque, defesa = get_team_last_matches(team_id)

    forma_score = forma * 20          # até ~60
    ataque_score = ataque * 10
    defesa_score = (3 - defesa) * 10

    strength = forma_score + ataque_score + defesa_score

    return strength

# -------------------------
# PROBABILIDADES (ESCALA REAL)
# -------------------------
def gerar_probabilidades(home_id, away_id):

    home = get_team_strength(home_id)
    away = get_team_strength(away_id)

    diff = home - away

    # 🔥 ESCALA CORRIGIDA (AGORA FUNCIONA)
    prob_home = 50 + diff * 5
    prob_away = 50 - diff * 5

    prob_home = max(min(prob_home, 90), 20)
    prob_away = max(min(prob_away, 90), 20)

    prob_1x = round(min(prob_home + 5, 95))
    prob_x2 = round(min(prob_away + 5, 95))
    prob_12 = round(100 - abs(prob_home - prob_away))

    return prob_1x, prob_12, prob_x2

# -------------------------
# CONSENSO INTELIGENTE
# -------------------------
def aplicar_consenso(df):

    scores = []

    for _, row in df.iterrows():

        favorito = max(row["1X"], row["X2"])
        diferenca = abs(row["1X"] - row["X2"])

        score = (
            favorito * 0.7 +
            diferenca * 0.3
        )

        scores.append(int(score))

    df["Score_Consenso"] = scores

    return df.sort_values(by="Score_Consenso", ascending=False)

# -------------------------
# GREG STATS REAL
# -------------------------
def aplicar_greg(df):

    picks = []

    for _, row in df.iterrows():

        diff = row["1X"] - row["X2"]

        if diff >= 10:
            picks.append("Casa (1)")
        elif diff <= -10:
            picks.append("Fora (2)")
        else:
            picks.append("Equilibrado")

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
        return utc.astimezone(BR_TZ).date() == selected_date
    except:
        return False

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V11 FINAL (Escala Corrigida)")

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
