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
# TIME RANGE (CORRIGIDO)
# ==============================

def obter_intervalo_hoje():
    agora = datetime.now(TZ)
    inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = agora.replace(hour=23, minute=59, second=59, microsecond=999999)
    return inicio, fim

# ==============================
# FETCH DADOS (MOCK / ESTRUTURA)
# ==============================

def buscar_sofascore():
    return []

def buscar_footystats():
    return []

def buscar_fbref():
    return []

# ==============================
# FILTRO DATA
# ==============================

def filtrar_por_data(jogos):
    inicio, fim = obter_intervalo_hoje()
    filtrados = []

    for j in jogos:
        if inicio <= j["data"] <= fim:
            filtrados.append(j)

    return filtrados

# ==============================
# DEDUPLICAÇÃO
# ==============================

def consolidar_jogos():
    fontes = [buscar_sofascore, buscar_footystats, buscar_fbref]
    jogos_unicos = {}

    for fonte in fontes:
        jogos = fonte()
        jogos = filtrar_por_data(jogos)

        for jogo in jogos:
            jogo_id = gerar_id_jogo(jogo)

            if jogo_id not in jogos_unicos:
                jogos_unicos[jogo_id] = jogo
            else:
                # MERGE SIMPLES (prioridade: dados existentes + novos)
                jogos_unicos[jogo_id].update({
                    k: v for k, v in jogo.items() if v is not None
                })

    return jogos_unicos

# ==============================
# SEGURANÇA ESTATÍSTICA
# ==============================

def safe_mean(lista):
    if not lista or len(lista) == 0:
        return 0
    return mean(lista)

# ==============================
# MODELO V4.5 (SOMENTE VENCEDOR)
# ==============================

def analisar_jogo(jogo):
    try:
        forma_home = safe_mean(jogo.get("forma_home", []))
        forma_away = safe_mean(jogo.get("forma_away", []))

        forca_home = jogo.get("forca_home", 0)
        forca_away = jogo.get("forca_away", 0)

        casa = jogo.get("casa", 0.1)  # leve vantagem casa

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
            "liga": jogo.get("liga", ""),
            "data": jogo["data"],
            "pick": pick,
            "score": round(score, 2)
        }

    except Exception as e:
        return None

# ==============================
# BLOQUEIO DE DUPLICIDADE FINAL
# ==============================

def gerar_picks():
    jogos = consolidar_jogos()
    picks = {}

    for jogo_id, jogo in jogos.items():
        resultado = analisar_jogo(jogo)

        if not resultado:
            continue

        if jogo_id not in picks:
            picks[jogo_id] = resultado
        else:
            existente = picks[jogo_id]

            # mantém maior confiança
            if resultado["score"] > existente["score"]:
                picks[jogo_id] = resultado

    return list(picks.values())

# ==============================
# UI STREAMLIT
# ==============================

st.set_page_config(page_title="Greg Stats X V4.5", layout="wide")

st.title("⚽ Greg Stats X V4.5 - Scanner de Valor")

if st.button("🔍 Buscar Jogos do Dia"):
    picks = gerar_picks()

    if not picks:
        st.warning("Nenhum jogo encontrado.")
    else:
        st.success(f"{len(picks)} jogos analisados")

        for p in picks:
            st.markdown(f"""
            ### {p['home']} vs {p['away']}
            - 🏆 Liga: {p['liga']}
            - 🕒 Data: {p['data'].strftime('%d/%m %H:%M')}
            - 🎯 Pick: **{p['pick']}**
            - 📊 Confiança: **{p['score']}**
            """)
