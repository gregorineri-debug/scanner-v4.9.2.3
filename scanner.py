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
# REQUEST SAFE
# -------------------------
def safe_get(url):
    try:
        return requests.get(url, timeout=10).json()
    except:
        return {}

# -------------------------
# SOFASCORE EVENTS
# -------------------------
def get_events(date):
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
    return safe_get(url).get("events", [])

# -------------------------
# FILTRO DE LIGA
# -------------------------
def is_valid_league(event):
    try:
        return event["tournament"]["uniqueTournament"]["id"] in VALID_LEAGUE_IDS
    except:
        return False

# -------------------------
# STANDINGS (TABELA)
# -------------------------
def get_standings(team_id):
    try:
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/unique-tournaments"
        tournaments = safe_get(url).get("uniqueTournaments", [])

        if not tournaments:
            return 0, 0

        tid = tournaments[0]["id"]

        seasons = safe_get(f"https://api.sofascore.com/api/v1/unique-tournament/{tid}/seasons").get("seasons", [])
        if not seasons:
            return 0, 0

        sid = seasons[0]["id"]

        standings = safe_get(
            f"https://api.sofascore.com/api/v1/unique-tournament/{tid}/season/{sid}/standings/total"
        ).get("standings", [])

        if not standings:
            return 0, 0

        for row in standings[0]["rows"]:
            if row["team"]["id"] == team_id:
                return row.get("points", 0), row.get("scoreDiff", 0)

    except:
        pass

    return 0, 0

# -------------------------
# ÚLTIMOS JOGOS
# -------------------------
def get_last_matches(team_id):

    data = safe_get(
        f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"
    ).get("events", [])

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

    return pts / jogos, gm / jogos, gs / jogos

# -------------------------
# H2H
# -------------------------
def get_h2h(home_id, away_id):
    try:
        data = safe_get(
            f"https://api.sofascore.com/api/v1/team/{home_id}/versus/{away_id}"
        ).get("events", [])[:5]

        pts = 0

        for e in data:
            hs = e["homeScore"]["current"]
            as_ = e["awayScore"]["current"]

            if e["homeTeam"]["id"] == home_id:
                pts += 3 if hs > as_ else 1 if hs == as_ else 0
            else:
                pts += 3 if as_ > hs else 1 if as_ == hs else 0

        return pts / len(data) if data else 1

    except:
        return 1

# -------------------------
# STATS (POSSE + XG)
# -------------------------
def get_match_stats(event_id):
    try:
        stats = safe_get(
            f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        ).get("statistics", [])

        posse = 50
        xg = 1

        if stats:
            groups = stats[0].get("groups", [])

            for g in groups:
                for item in g.get("statisticsItems", []):
                    if item.get("name") == "Ball possession":
                        posse = int(item.get("home", "50").replace("%", ""))
                    if item.get("name") == "Expected goals":
                        xg = float(item.get("home", 1))

        return posse, xg

    except:
        return 50, 1

# -------------------------
# FORÇA MULTI-FATOR
# -------------------------
def calcular_forca(team_id, event_id):

    pts_table, saldo = get_standings(team_id)
    forma, gm, gs = get_last_matches(team_id)
    posse, xg = get_match_stats(event_id)

    score = (
        pts_table * 0.5 +
        saldo * 1.0 +
        forma * 8 +
        gm * 5 +
        (3 - gs) * 5 +
        posse * 0.3 +
        xg * 10
    )

    return score

# -------------------------
# PROBABILIDADES
# -------------------------
def gerar_probabilidades(home_id, away_id, event_id):

    home = calcular_forca(home_id, event_id)
    away = calcular_forca(away_id, event_id)

    diff = home - away

    prob_home = 50 + diff * 3
    prob_away = 50 - diff * 3

    prob_home = max(min(prob_home, 90), 20)
    prob_away = max(min(prob_away, 90), 20)

    p1x = round(min(prob_home + 5, 95))
    px2 = round(min(prob_away + 5, 95))
    p12 = round(100 - abs(prob_home - prob_away))

    return p1x, p12, px2

# -------------------------
# CONSENSO
# -------------------------
def aplicar_consenso(df):

    df["Score_Consenso"] = (
        df[["1X","12","X2"]].max(axis=1) * 0.7 +
        abs(df["1X"] - df["X2"]) * 0.3
    ).astype(int)

    return df.sort_values(by="Score_Consenso", ascending=False)

# -------------------------
# GREG STATS
# -------------------------
def aplicar_greg(df):

    df["Pick_Vencedor"] = df.apply(
        lambda x: "Casa (1)" if x["1X"] - x["X2"] > 10
        else "Fora (2)" if x["X2"] - x["1X"] > 10
        else "Equilibrado",
        axis=1
    )

    return df

# -------------------------
# UI
# -------------------------
st.title("⚽ Scanner PRO V13 FINAL (Dados Reais + Filtro de Ligas)")

date = st.date_input("Escolha a data")

events = get_events(date.strftime("%Y-%m-%d"))

filtered_events = [e for e in events if is_valid_league(e)]

st.write(f"Jogos válidos: {len(filtered_events)}")

if st.button("Analisar Jogos"):

    results = []

    for e in filtered_events:
        try:
            utc = datetime.utcfromtimestamp(e["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
            hora = utc.astimezone(BR_TZ).strftime("%H:%M")

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]
            event_id = e["id"]

            p1x, p12, px2 = gerar_probabilidades(home_id, away_id, event_id)

            results.append({
                "Hora": hora,
                "Liga": LEAGUE_NAMES.get(
                    e["tournament"]["uniqueTournament"]["id"], "Outra"
                ),
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
