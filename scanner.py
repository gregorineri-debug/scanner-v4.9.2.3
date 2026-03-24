import streamlit as st
import requests
from datetime import datetime
import pytz
from statistics import mean
import pandas as pd
from difflib import get_close_matches

# ==============================
# CONFIG
# ==============================

TZ = pytz.timezone("America/Sao_Paulo")

# CACHE GLOBAL
xg_cache = {}

# ==============================
# INTERVALO
# ==============================

def intervalo_hoje():
    agora = datetime.now(TZ)
    inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = agora.replace(hour=23, minute=59, second=59, microsecond=999999)
    return inicio, fim

def ajustar_data(timestamp):
    return datetime.fromtimestamp(timestamp, TZ)

# ==============================
# BUSCAR JOGOS
# ==============================

def buscar_jogos():
    hoje = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{hoje}"

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()

        inicio, fim = intervalo_hoje()
        jogos = []

        for e in data.get("events", []):
            data_jogo = ajustar_data(e["startTimestamp"])

            if not (inicio <= data_jogo <= fim):
                continue

            jogos.append({
                "home": e["homeTeam"]["name"],
                "away": e["awayTeam"]["name"],
                "liga": e["tournament"]["name"],
                "data": data_jogo,
                "home_id": e["homeTeam"]["id"],
                "away_id": e["awayTeam"]["id"]
            })

        return jogos

    except:
        return []

# ==============================
# FORMA
# ==============================

def buscar_forma(team_id):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/5"

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()

        resultados = []

        for j in data.get("events", []):
            home_id = j["homeTeam"]["id"]
            gols_home = j["homeScore"]["current"]
            gols_away = j["awayScore"]["current"]

            if gols_home is None:
                continue

            if team_id == home_id:
                resultados.append(1 if gols_home > gols_away else 0.5 if gols_home == gols_away else 0)
            else:
                resultados.append(1 if gols_away > gols_home else 0.5 if gols_home == gols_away else 0)

        return resultados

    except:
        return []

# ==============================
# MATCHING INTELIGENTE
# ==============================

def normalizar_nome(nome):
    return nome.lower().replace("fc", "").replace("club", "").strip()

def match_time(nome, lista):
    nome = normalizar_nome(nome)
    lista_norm = [normalizar_nome(x) for x in lista]

    match = get_close_matches(nome, lista_norm, n=1, cutoff=0.6)

    if match:
        idx = lista_norm.index(match[0])
        return lista[idx]

    return None

# ==============================
# xG AUTOMÁTICO COM CACHE
# ==============================

def get_xg(team_name):

    # CACHE
    if team_name in xg_cache:
        return xg_cache[team_name]

    try:
        search = team_name.replace(" ", "+")
        search_url = f"https://fbref.com/en/search/search.fcgi?search={search}"

        res = requests.get(search_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        tables = pd.read_html(res.text)

        squad_names = []
        squad_links = []

        for table in tables:
            if "Squad" in table.columns:
                squad_names = table["Squad"].tolist()
                squad_links = table["Squad"].tolist()
                break

        if not squad_names:
            xg_cache[team_name] = 0
            return 0

        best_match = match_time(team_name, squad_names)

        if not best_match:
            xg_cache[team_name] = 0
            return 0

        idx = squad_names.index(best_match)
        team_url = squad_links[idx]

        res = requests.get(team_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        tables = pd.read_html(res.text)

        for df in tables:
            if "xG" in df.columns and "xGA" in df.columns:

                df = df.dropna(subset=["xG", "xGA"])
                df["xG"] = pd.to_numeric(df["xG"], errors="coerce")
                df["xGA"] = pd.to_numeric(df["xGA"], errors="coerce")
                df = df.dropna()

                if len(df) < 5:
                    xg_cache[team_name] = 0
                    return 0

                base = df["xG"].mean() - df["xGA"].mean()
                recent = df.tail(5)

                form = (recent["xG"].mean() - recent["xGA"].mean()) * 1.5

                value = base + form

                xg_cache[team_name] = value
                return value

        xg_cache[team_name] = 0
        return 0

    except:
        xg_cache[team_name] = 0
        return 0

# ==============================
# UTIL
# ==============================

def safe_mean(lista):
    return mean(lista) if lista else 0

# ==============================
# MODELO ELITE
# ==============================

def analisar_jogo(jogo):
    forma_home = safe_mean(buscar_forma(jogo["home_id"]))
    forma_away = safe_mean(buscar_forma(jogo["away_id"]))

    xg_home = get_xg(jogo["home"])
    xg_away = get_xg(jogo["away"])

    casa = 0.15

    # PESO DINÂMICO
    peso_xg = 0.25 if abs(xg_home - xg_away) < 0.5 else 0.4

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

# ==============================
# PIPELINE
# ==============================

def gerar_picks():
    jogos = buscar_jogos()
    picks = [analisar_jogo(j) for j in jogos]
    return sorted(picks, key=lambda x: x["score"], reverse=True)

# ==============================
# UI
# ==============================

st.set_page_config(page_title="Greg Stats ELITE", layout="wide")

st.title("⚽ Greg Stats X V4.5 ELITE")

if st.button("🚀 Rodar Scanner Elite"):
    picks = gerar_picks()

    st.success(f"{len(picks)} jogos analisados")

    for p in picks[:15]:
        st.markdown(f"""
        ### {p['home']} vs {p['away']}
        - 🏆 {p['liga']}
        - 🕒 {p['data'].strftime('%d/%m %H:%M')}
        - 🎯 Pick: **{p['pick']}**
        - 📊 Score: **{p['score']}**
        - 📈 xG diff: **{p['xg_diff']}
        """)
