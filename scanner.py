import streamlit as st
import http.client
import json
from datetime import datetime
import pytz
from statistics import mean

# ==============================
# CONFIG
# ==============================

API_KEY = "XxXxXxXxXxXxXxXxXxXxXxXx"

TZ = pytz.timezone("America/Sao_Paulo")

# ==============================
# CONEXÃO API (HTTP.CLIENT)
# ==============================

def conectar_api(endpoint):
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")

    headers = {
        'x-apisports-key': API_KEY
    }

    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()

    return json.loads(data.decode("utf-8"))

# ==============================
# NORMALIZAÇÃO
# ==============================

def normalizar_nome(nome):
    return nome.lower().strip()

def gerar_id_jogo(jogo):
    return (
        normalizar_nome(jogo["home"]) +
        "_vs_" +
        normalizar_nome(jogo["away"]) +
        "_" +
        jogo["data"].strftime("%Y-%m-%d")
    )

# ==============================
# TIMEZONE
# ==============================

def ajustar_timezone(data_str):
    data = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    return data.astimezone(TZ)

# ==============================
# BUSCAR JOGOS REAIS
# ==============================

def buscar_jogos():
    hoje = datetime.now(TZ).strftime("%Y-%m-%d")

    endpoint = f"/fixtures?date={hoje}"

    data = conectar_api(endpoint)

    jogos = []

    for item in data.get("response", []):
        try:
            jogo = {
                "home": item["teams"]["home"]["name"],
                "away": item["teams"]["away"]["name"],
                "data": ajustar_timezone(item["fixture"]["date"]),
                "liga": item["league"]["name"],

                # Estrutura inicial (vamos evoluir depois)
                "forma_home": [],
                "forma_away": [],
                "forca_home": 0,
                "forca_away": 0,
                "casa": 0.1
            }

            jogos.append(jogo)

        except:
            continue

    return jogos

# ==============================
# SEGURANÇA
# ==============================

def safe_mean(lista):
    if not lista:
        return 0
    return mean(lista)

# ==============================
# MODELO V4.5
# ==============================

def analisar_jogo(jogo):
    forma_home = safe_mean(jogo.get("forma_home", []))
    forma_away = safe_mean(jogo.get("forma_away", []))

    forca_home = jogo.get("forca_home", 0)
    forca_away = jogo.get("forca_away", 0)

    casa = jogo.get("casa", 0.1)

    score_home = forma_home + forca_home + casa
    score_away = forma_away + forca_away

    if score_home > score_away:
        pick = "HOME"
        score = score_home - score_away
    else:
        pick = "AWAY"
        score = score_away - score_home

    return {
        "id": gerar_id_jogo(jogo),
        "home": jogo["home"],
        "away": jogo["away"],
        "liga": jogo["liga"],
        "data": jogo["data"],
        "pick": pick,
        "score": round(score, 2)
    }

# ==============================
# PIPELINE
# ==============================

def gerar_picks():
    jogos = buscar_jogos()

    jogos_unicos = {}
    picks = {}

    # DEDUPLICAÇÃO
    for jogo in jogos:
        jogo_id = gerar_id_jogo(jogo)

        if jogo_id not in jogos_unicos:
            jogos_unicos[jogo_id] = jogo

    # ANÁLISE
    for jogo_id, jogo in jogos_unicos.items():
        resultado = analisar_jogo(jogo)

        if jogo_id not in picks:
            picks[jogo_id] = resultado
        else:
            if resultado["score"] > picks[jogo_id]["score"]:
                picks[jogo_id] = resultado

    return list(picks.values())

# ==============================
# UI STREAMLIT
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5", layout="wide")

st.title("⚽ Greg Stats X V4.5 - Scanner Profissional")

if st.button("🔍 Buscar Jogos de Hoje"):
    picks = gerar_picks()

    if not picks:
        st.warning("Nenhum jogo encontrado (verifique API ou data)")
    else:
        st.success(f"{len(picks)} jogos encontrados")

        for p in picks:
            st.markdown(f"""
            ### {p['home']} vs {p['away']}
            - 🏆 Liga: {p['liga']}
            - 🕒 {p['data'].strftime('%d/%m %H:%M')}
            - 🎯 Pick: **{p['pick']}**
            - 📊 Confiança: **{p['score']}**
            """)
