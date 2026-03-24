import streamlit as st
import requests
from datetime import datetime
import pytz

# ==============================
# CONFIG
# ==============================

TZ = pytz.timezone("America/Sao_Paulo")

# ==============================
# BUSCAR JOGOS (REAL E GRÁTIS)
# ==============================

def buscar_jogos():
    url = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={}&s=Soccer"

    hoje = datetime.now().strftime("%Y-%m-%d")

    try:
        r = requests.get(url.format(hoje), timeout=10)
        data = r.json()

        eventos = data.get("events", [])

        jogos = []

        for e in eventos:
            try:
                jogo = {
                    "home": e["strHomeTeam"],
                    "away": e["strAwayTeam"],
                    "liga": e["strLeague"],
                    "data": ajustar_data(e["dateEvent"] + "T" + (e["strTime"] or "00:00:00"))
                }

                jogos.append(jogo)
            except:
                continue

        return jogos

    except:
        return []

# ==============================
# UTIL
# ==============================

def ajustar_data(data_str):
    try:
        data = datetime.fromisoformat(data_str)
        return TZ.localize(data)
    except:
        return datetime.now(TZ)

# ==============================
# MODELO SIMPLES (V4.5 BASE)
# ==============================

def analisar_jogo(j):
    # modelo simples estável
    score_home = 0.55
    score_away = 0.50

    if score_home > score_away:
        pick = "HOME"
        score = score_home - score_away
    else:
        pick = "AWAY"
        score = score_away - score_home

    return {
        "home": j["home"],
        "away": j["away"],
        "liga": j["liga"],
        "data": j["data"],
        "pick": pick,
        "score": round(score, 2)
    }

# ==============================
# PIPELINE
# ==============================

def gerar_picks():
    jogos = buscar_jogos()

    picks = []

    for j in jogos:
        picks.append(analisar_jogo(j))

    return picks

# ==============================
# UI
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5 - FREE", layout="wide")

st.title("⚽ Greg Stats X V4.5 - SEM LIMITES (FREE)")

if st.button("Buscar Jogos"):
    picks = gerar_picks()

    if not picks:
        st.error("Nenhum jogo encontrado (raríssimo)")
    else:
        st.success(f"{len(picks)} jogos encontrados")

        for p in picks:
            st.markdown(f"""
            ### {p['home']} vs {p['away']}
            - 🏆 {p['liga']}
            - 🕒 {p['data'].strftime('%d/%m %H:%M')}
            - 🎯 Pick: **{p['pick']}**
            - 📊 Score: **{p['score']}**
            """)
