import streamlit as st
import http.client
import json
from datetime import datetime, timedelta
import pytz
from statistics import mean

# ==============================
# CONFIG
# ==============================

API_KEY = "SUA_API_KEY"
TZ = pytz.timezone("America/Sao_Paulo")

# ==============================
# API CONNECTION
# ==============================

def conectar_api(endpoint):
    try:
        conn = http.client.HTTPSConnection("v3.football.api-sports.io")

        headers = {
            'x-apisports-key': API_KEY
        }

        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))
    except:
        return {}

# ==============================
# FETCH JOGOS (API + FALLBACK)
# ==============================

def buscar_jogos():
    datas = [
        datetime.now(TZ),
        datetime.now(TZ) + timedelta(days=1),
        datetime.now(TZ) - timedelta(days=1)
    ]

    for d in datas:
        endpoint = f"/fixtures?date={d.strftime('%Y-%m-%d')}"
        data = conectar_api(endpoint)

        jogos = data.get("response", [])

        if jogos:
            return jogos

    return []

# ==============================
# FORMA REAL (API)
# ==============================

def buscar_forma(team_id):
    try:
        endpoint = f"/fixtures?team={team_id}&last=5"
        data = conectar_api(endpoint)

        resultados = []

        for j in data.get("response", []):
            gols_home = j["goals"]["home"]
            gols_away = j["goals"]["away"]

            if gols_home is None or gols_away is None:
                continue

            if gols_home > gols_away:
                resultados.append(1)
            elif gols_home == gols_away:
                resultados.append(0.5)
            else:
                resultados.append(0)

        return resultados

    except:
        return []

# ==============================
# FALLBACK SCRAPING (SIMULADO)
# ==============================

def fallback_scraping(jogo):
    """
    Estrutura pronta para scraping real (SofaScore, etc)
    Aqui você pode plugar BeautifulSoup futuramente
    """
    return {
        "extra_forca_home": 0.1,
        "extra_forca_away": 0.1
    }

# ==============================
# UTIL
# ==============================

def ajustar_data(data_str):
    data = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    return data.astimezone(TZ)

def gerar_id(jogo):
    return f"{jogo['teams']['home']['name']}_vs_{jogo['teams']['away']['name']}_{jogo['fixture']['date'][:10]}"

def safe_mean(lista):
    return mean(lista) if lista else 0

# ==============================
# MODELO V4.5 PRO
# ==============================

def analisar_jogo(j):
    try:
        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        home_id = j["teams"]["home"]["id"]
        away_id = j["teams"]["away"]["id"]

        data = ajustar_data(j["fixture"]["date"])
        liga = j["league"]["name"]

        # forma real
        forma_home = safe_mean(buscar_forma(home_id))
        forma_away = safe_mean(buscar_forma(away_id))

        # fallback scraping
        extra = fallback_scraping(j)

        score_home = forma_home + 0.15 + extra["extra_forca_home"]
        score_away = forma_away + extra["extra_forca_away"]

        if score_home > score_away:
            pick = "HOME"
            score = score_home - score_away
        else:
            pick = "AWAY"
            score = score_away - score_home

        return {
            "id": gerar_id(j),
            "home": home,
            "away": away,
            "liga": liga,
            "data": data,
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

    jogos_unicos = {}
    picks = {}

    # deduplicação
    for j in jogos:
        jid = gerar_id(j)
        if jid not in jogos_unicos:
            jogos_unicos[jid] = j

    # análise
    for jid, jogo in jogos_unicos.items():
        r = analisar_jogo(jogo)

        if not r:
            continue

        if jid not in picks:
            picks[jid] = r
        else:
            if r["score"] > picks[jid]["score"]:
                picks[jid] = r

    return sorted(picks.values(), key=lambda x: x["score"], reverse=True)

# ==============================
# UI
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5 PRO Híbrido", layout="wide")

st.title("⚽ Greg Stats X V4.5 PRO - Híbrido (API + Scraping)")

if st.button("🚀 Buscar Picks"):
    picks = gerar_picks()

    if not picks:
        st.error("Nenhum jogo encontrado")
    else:
        st.success(f"{len(picks)} jogos analisados")

        for p in picks[:10]:
            st.markdown(f"""
            ### {p['home']} vs {p['away']}
            - 🏆 {p['liga']}
            - 🕒 {p['data'].strftime('%d/%m %H:%M')}
            - 🎯 Pick: **{p['pick']}**
            - 📊 Confiança: **{p['score']}**
            """)
