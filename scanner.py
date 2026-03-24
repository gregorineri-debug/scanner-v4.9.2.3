import streamlit as st
import requests
from datetime import datetime
import pytz
from statistics import mean

# ==============================
# CONFIG
# ==============================

API_KEY = "SUA_API_KEY_SPORTSRC"
BASE_URL = "https://api.sportsrc.org/v2"

TZ = pytz.timezone("America/Sao_Paulo")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}"
}

# ==============================
# UTIL
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

def ajustar_data(data_str):
    try:
        data = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return data.astimezone(TZ)
    except:
        return datetime.now(TZ)

def safe_mean(lista):
    if not lista:
        return 0
    return mean(lista)

# ==============================
# API REQUEST
# ==============================

def fetch(endpoint):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {}
    except:
        return {}

# ==============================
# DADOS REAIS
# ==============================

def buscar_jogos():
    hoje = datetime.now(TZ).strftime("%Y-%m-%d")

    data = fetch(f"/fixtures?date={hoje}")

    jogos = []

    for item in data.get("data", []):
        try:
            jogo = {
                "id_api": item.get("id"),
                "home": item["home"]["name"],
                "away": item["away"]["name"],
                "data": ajustar_data(item["date"]),
                "liga": item.get("league", {}).get("name", ""),

                "odd_home": item.get("odds", {}).get("home", 0),
                "odd_away": item.get("odds", {}).get("away", 0)
            }

            jogos.append(jogo)
        except:
            continue

    return jogos

# ==============================
# FORMA DOS TIMES
# ==============================

def buscar_forma(team_id):
    data = fetch(f"/teams/{team_id}/last_matches")

    resultados = []

    for m in data.get("data", []):
        try:
            if m["winner"] == "home":
                resultados.append(1)
            elif m["winner"] == "away":
                resultados.append(0.5)
            else:
                resultados.append(0)
        except:
            continue

    return resultados

# ==============================
# MODELO V4.5 PRO
# ==============================

def analisar_jogo(jogo):
    try:
        forma_home = safe_mean(buscar_forma(jogo.get("home_id", 0)))
        forma_away = safe_mean(buscar_forma(jogo.get("away_id", 0)))

        odd_home = jogo.get("odd_home", 0)
        odd_away = jogo.get("odd_away", 0)

        casa = 0.15

        score_home = forma_home + casa
        score_away = forma_away

        if score_home > score_away:
            pick = "HOME"
            confianca = score_home - score_away
            odd = odd_home
        else:
            pick = "AWAY"
            confianca = score_away - score_home
            odd = odd_away

        # cálculo simples de valor
        valor = confianca * odd if odd else 0

        return {
            "id": gerar_id_jogo(jogo),
            "home": jogo["home"],
            "away": jogo["away"],
            "liga": jogo["liga"],
            "data": jogo["data"],
            "pick": pick,
            "score": round(confianca, 2),
            "odd": odd,
            "valor": round(valor, 2)
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
        jid = gerar_id_jogo(j)
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
            if r["valor"] > picks[jid]["valor"]:
                picks[jid] = r

    # ranking
    return sorted(picks.values(), key=lambda x: x["valor"], reverse=True)

# ==============================
# UI
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5 PRO", layout="wide")

st.title("⚽ Greg Stats X V4.5 PRO - Scanner Profissional")

if st.button("🚀 Buscar Picks do Dia"):
    picks = gerar_picks()

    if not picks:
        st.warning("Nenhum jogo encontrado (verifique API)")
    else:
        st.success(f"{len(picks)} jogos analisados")

        for p in picks[:10]:
            st.markdown(f"""
            ### {p['home']} vs {p['away']}
            - 🏆 {p['liga']}
            - 🕒 {p['data'].strftime('%d/%m %H:%M')}
            - 🎯 Pick: **{p['pick']}**
            - 📊 Confiança: **{p['score']}**
            - 💰 Odd: **{p['odd']}**
            - 🔥 Valor: **{p['valor']}**
            """)
