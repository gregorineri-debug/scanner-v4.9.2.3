import streamlit as st
import requests
from datetime import datetime, timedelta
import pytz
from statistics import mean

# ==============================
# CONFIG
# ==============================

TZ = pytz.timezone("America/Sao_Paulo")

# ==============================
# INTERVALO DO DIA (BRASIL)
# ==============================

def intervalo_hoje():
    agora = datetime.now(TZ)

    inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = agora.replace(hour=23, minute=59, second=59, microsecond=999999)

    return inicio, fim

# ==============================
# CONVERTER TIMESTAMP
# ==============================

def ajustar_data(timestamp):
    return datetime.fromtimestamp(timestamp, TZ)

# ==============================
# BUSCAR JOGOS (SCRAPING REAL)
# ==============================

def buscar_jogos():
    hoje = datetime.now().strftime("%Y-%m-%d")

    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{hoje}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    inicio, fim = intervalo_hoje()

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        jogos = []

        for e in data.get("events", []):
            try:
                data_jogo = ajustar_data(e["startTimestamp"])

                # 🔥 FILTRO CORRETO DO DIA (BRASIL)
                if not (inicio <= data_jogo <= fim):
                    continue

                jogo = {
                    "id": e["id"],
                    "home": e["homeTeam"]["name"],
                    "away": e["awayTeam"]["name"],
                    "liga": e["tournament"]["name"],
                    "data": data_jogo,
                    "home_id": e["homeTeam"]["id"],
                    "away_id": e["awayTeam"]["id"]
                }

                jogos.append(jogo)

            except:
                continue

        return jogos

    except:
        return []

# ==============================
# FORMA REAL (ÚLTIMOS 5 JOGOS)
# ==============================

def buscar_forma(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

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
                    if gols_home > gols_away:
                        resultados.append(1)
                    elif gols_home == gols_away:
                        resultados.append(0.5)
                    else:
                        resultados.append(0)
                else:
                    if gols_away > gols_home:
                        resultados.append(1)
                    elif gols_home == gols_away:
                        resultados.append(0.5)
                    else:
                        resultados.append(0)

            except:
                continue

        return resultados

    except:
        return []

# ==============================
# UTIL
# ==============================

def safe_mean(lista):
    return mean(lista) if lista else 0

# ==============================
# MODELO V4.5 (SOMENTE VENCEDOR)
# ==============================

def analisar_jogo(jogo):
    try:
        forma_home = safe_mean(buscar_forma(jogo["home_id"]))
        forma_away = safe_mean(buscar_forma(jogo["away_id"]))

        casa = 0.15

        score_home = forma_home + casa
        score_away = forma_away

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
            "score": round(score, 2)
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

    # ordenar por confiança
    return sorted(picks, key=lambda x: x["score"], reverse=True)

# ==============================
# UI STREAMLIT
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5 SCRAPER", layout="wide")

st.title("⚽ Greg Stats X V4.5 - Scraping PRO (SofaScore)")

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
            """)
