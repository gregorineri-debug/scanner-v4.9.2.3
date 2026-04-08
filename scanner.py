import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

BR_TZ = ZoneInfo("America/Sao_Paulo")

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
# DADOS BASE DO TIME
# -------------------------
def get_team_stats(team_id):

    try:
        # últimos jogos
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"
        data = requests.get(url, timeout=10).json()["events"]

        pontos = 0
        gm = 0
        gs = 0

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

        jogos = len(data) if len(data) > 0 else 1

        forma = pontos / jogos
        saldo = (gm - gs) / jogos

        # proxies avançados
        posse = gm * 10  # proxy simples
        xg = gm - (gs * 0.8)

        return {
            "forma": forma,
            "saldo": saldo,
            "posse": posse,
            "xg": xg
        }

    except:
        return {"forma":1, "saldo":0, "posse":5, "xg":0}

# -------------------------
# FORÇA MULTI-FATOR
# -------------------------
def calcular_forca(team_id):

    stats = get_team_stats(team_id)

    score = (
        stats["forma"] * 8 +      # últimos 5
        stats["saldo"] * 8 +      # saldo
        stats["posse"] * 0.9 +    # posse
        stats["xg"] * 10          # xG
    )

    return score

# -------------------------
# PROBABILIDADES
# -------------------------
def gerar_probabilidades(home_id, away_id):

    home = calcular_forca(home_id)
    away = calcular_forca(away_id)

    diff = home - away

    prob_home = 50 + diff * 4
    prob_away = 50 - diff * 4

    prob_home = max(min(prob_home, 90), 20)
    prob_away = max(min(prob_away, 90), 20)

    p1x = round(prob_home + 5)
    px2 = round(prob_away + 5)
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
# GREG
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
# UI (IGUAL)
# -------------------------
st.title("⚽ Scanner PRO V12 (Modelo Multi-Fator)")

date = st.date_input("Escolha a data")

events = get_events(date.strftime("%Y-%m-%d"))

if st.button("Analisar Jogos"):

    results = []

    for e in events:
        try:
            utc = datetime.utcfromtimestamp(e["startTimestamp"]).replace(tzinfo=ZoneInfo("UTC"))
            hora = utc.astimezone(BR_TZ).strftime("%H:%M")

            home_id = e["homeTeam"]["id"]
            away_id = e["awayTeam"]["id"]

            p1x, p12, px2 = gerar_probabilidades(home_id, away_id)

            results.append({
                "Hora": hora,
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

        st.dataframe(df)
