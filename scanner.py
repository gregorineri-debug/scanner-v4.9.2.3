import streamlit as st
import requests
from datetime import datetime
import pytz
from statistics import mean
import pandas as pd

# ==============================
# CONFIG
# ==============================

TZ = pytz.timezone("America/Sao_Paulo")

# 🔗 MAPA FBREF (VOCÊ VAI EXPANDIR)
TEAM_URLS = {
    # exemplos (adicione conforme for usando)
    # "Palmeiras": "https://fbref.com/en/squads/XXXX/",
}

# ==============================
# INTERVALO DO DIA
# ==============================

def intervalo_hoje():
    agora = datetime.now(TZ)
    inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = agora.replace(hour=23, minute=59, second=59, microsecond=999999)
    return inicio, fim

# ==============================
# DATA
# ==============================

def ajustar_data(timestamp):
    return datetime.fromtimestamp(timestamp, TZ)

# ==============================
# BUSCAR JOGOS
# ==============================

def buscar_jogos():
    hoje = datetime.now().strftime("%Y-%m-%d")

    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{hoje}"

    headers = {"User-Agent": "Mozilla/5.0"}

    inicio, fim = intervalo_hoje()

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        jogos = []

        for e in data.get("events", []):
            try:
                data_jogo = ajustar_data(e["startTimestamp"])

                if not (inicio <= data_jogo <= fim):
                    continue

                jogos.append({
                    "id": e["id"],
                    "home": e["homeTeam"]["name"],
                    "away": e["awayTeam"]["name"],
                    "liga": e["tournament"]["name"],
                    "data": data_jogo,
                    "home_id": e["homeTeam"]["id"],
                    "away_id": e["awayTeam"]["id"]
                })

            except:
                continue

        return jogos

    except:
        return []

# ==============================
# FORMA
# ==============================

def buscar_forma(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        resultados = []

        for j in data.get("events", []):
            try:
                home_id = j["homeTeam"]["id"]
                away_id = j["awayTeam"]["id"]

                gols_home = j["homeScore"]["current"]
                gols_away = j["awayScore"]["current"]

                if gols_home is None or gols_away is None:
                    continue

                if team_id == home_id:
                    resultados.append(1 if gols_home > gols_away else 0.5 if gols_home == gols_away else 0)
                else:
                    resultados.append(1 if gols_away > gols_home else 0.5 if gols_home == gols_away else 0)

            except:
                continue

        return resultados

    except:
        return []

# ==============================
# xG (FBREF)
# ==============================

def get_xg(team_name):
    url = TEAM_URLS.get(team_name)

    if not url:
        return 0  # sem dado → neutro

    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        tables = pd.read_html(res.text)

        for df in tables:
            if "xG" in df.columns and "xGA" in df.columns:

                df = df.dropna(subset=["xG", "xGA"])
                df["xG"] = pd.to_numeric(df["xG"], errors="coerce")
                df["xGA"] = pd.to_numeric(df["xGA"], errors="coerce")
                df = df.dropna()

                if len(df) < 5:
                    return 0

                base = df["xG"].mean() - df["xGA"].mean()

                recent = df.tail(5)
                form = (recent["xG"].mean() - recent["xGA"].mean()) * 1.5

                return base + form

        return 0

    except:
        return 0

# ==============================
# UTIL
# ==============================

def safe_mean(lista):
    return mean(lista) if lista else 0

# ==============================
# MODELO V4.5 + xG
# ==============================

def analisar_jogo(jogo):
    try:
        forma_home = safe_mean(buscar_forma(jogo["home_id"]))
        forma_away = safe_mean(buscar_forma(jogo["away_id"]))

        # xG
        xg_home = get_xg(jogo["home"])
        xg_away = get_xg(jogo["away"])

        # pesos
        casa = 0.15
        peso_xg = 0.35

        score_home = forma_home + casa + (xg_home * peso_xg)
        score_away = forma_away + (xg_away * peso_xg)

        if score_home > score_away:
            pick = "HOME"
            score = score_home - score_away
        else:
            pick = "AWAY"
            score = score_away - score_home

        return {
            "home": jogo["home"],
            "away": jogo["away"],
            "liga": jogo["liga"],
            "data": jogo["data"],
            "pick": pick,
            "score": round(score, 2),
            "xg_diff": round(xg_home - xg_away, 2)
        }

    except:
        return None

# ==============================
# PIPELINE
# ==============================

def gerar_picks():
    jogos = buscar_jogos()
    picks = []

    for j in jogos:
        r = analisar_jogo(j)
        if r:
            picks.append(r)

    return sorted(picks, key=lambda x: x["score"], reverse=True)

# ==============================
# UI
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5 + xG", layout="wide")

st.title("⚽ Greg Stats X V4.5 + xG (PRO)")

if st.button("🚀 Buscar Jogos de Hoje"):
    picks = gerar_picks()

    if not picks:
        st.error("Nenhum jogo encontrado hoje")
    else:
        st.success(f"{len(picks)} jogos analisados")

        for p in picks[:15]:
            st.markdown(f"""
            ### {p['home']} vs {p['away']}
            - 🏆 {p['liga']}
            - 🕒 {p['data'].strftime('%d/%m %H:%M')}
            - 🎯 Pick: **{p['pick']}**
            - 📊 Confiança: **{p['score']}**
            - 📈 xG diff: **{p['xg_diff']}**
            """)
