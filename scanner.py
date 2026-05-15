import streamlit as st
import pandas as pd
import requests
import re
import json
from io import BytesIO
from datetime import date

st.set_page_config(page_title="Scanner X10 - Ambos Marcam", layout="wide")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

BTTS_THRESHOLD = 75


def safe_get(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    if r.status_code != 200:
        raise Exception(f"Status {r.status_code} em {url}")
    return r.json()


def stars(score):
    if score >= 90:
        return "⭐⭐⭐⭐⭐"
    if score >= 80:
        return "⭐⭐⭐⭐"
    if score >= 75:
        return "⭐⭐⭐"
    if score >= 65:
        return "⭐⭐"
    return "⭐"


def bet_type(score):
    if score >= 85:
        return "CONSERVADOR"
    if score >= 75:
        return "POSITIVO"
    if score >= 65:
        return "MONITORAR"
    return "EVITAR"


def consensus_label(score):
    if score >= 85:
        return "CONSENSO FORTE"
    if score >= 75:
        return "POSITIVO 75%+"
    if score >= 65:
        return "CONSENSO MÉDIO"
    return "SEM CONSENSO"


def pct(n, d):
    return int(round((n / d) * 100)) if d else 0


def parse_score(ev):
    hs = ev.get("homeScore", {}) or {}
    aw = ev.get("awayScore", {}) or {}
    home_goals = hs.get("current")
    away_goals = aw.get("current")
    if home_goals is None or away_goals is None:
        return None, None
    return int(home_goals), int(away_goals)


def same_league(ev, league_name):
    tournament = (ev.get("tournament", {}) or {}).get("name", "")
    return str(tournament).strip().lower() == str(league_name).strip().lower()


def is_finished(ev):
    status = (ev.get("status", {}) or {}).get("type", "")
    return status == "finished"


def fetch_sofascore_events(selected_date):
    url = f"https://www.sofascore.com/api/v1/sport/football/scheduled-events/{selected_date}"
    data = safe_get(url)
    return parse_sofascore_json(data)


def parse_sofascore_json(data):
    rows = []
    for ev in data.get("events", []):
        try:
            home = ev["homeTeam"]["name"]
            away = ev["awayTeam"]["name"]
            tournament = ev["tournament"]["name"]
            timestamp = ev.get("startTimestamp")

            hora = ""
            if timestamp:
                hora = (
                    pd.to_datetime(timestamp, unit="s", utc=True)
                    .tz_convert("America/Sao_Paulo")
                    .strftime("%H:%M")
                )

            rows.append({
                "Hora": hora,
                "Liga": tournament,
                "Jogo": f"{home} vs {away}",
                "Casa": home,
                "Fora": away,
                "Casa ID": ev.get("homeTeam", {}).get("id", ""),
                "Fora ID": ev.get("awayTeam", {}).get("id", ""),
                "SofaScore ID": ev.get("id", ""),
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


def parse_manual_games(text):
    rows = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = re.split(r"\t+", line)

        if len(parts) >= 3:
            hora = parts[0].strip()
            liga = parts[1].strip()
            jogo = parts[2].strip()
        else:
            match = re.match(r"^(\d{1,2}:\d{2})\s+(.+?)\s{2,}(.+)$", line)
            if not match:
                continue
            hora, liga, jogo = match.groups()

        if " vs " not in jogo:
            continue

        casa, fora = jogo.split(" vs ", 1)

        rows.append({
            "Hora": hora,
            "Liga": liga,
            "Jogo": jogo,
            "Casa": casa.strip(),
            "Fora": fora.strip(),
            "Casa ID": "",
            "Fora ID": "",
            "SofaScore ID": "",
        })

    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def search_team_id(team_name):
    try:
        q = requests.utils.quote(str(team_name))
        url = f"https://www.sofascore.com/api/v1/search/all?q={q}"
        data = safe_get(url)

        for item in data.get("results", []):
            entity = item.get("entity", {}) or {}
            sport = (entity.get("sport", {}) or {}).get("name", "")
            if sport.lower() == "football" and entity.get("id"):
                return entity.get("id", "")

    except Exception:
        return ""

    return ""


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_recent_team_events(team_id, pages=4):
    events = []

    if not team_id:
        return events

    for page in range(pages):
        try:
            url = f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/{page}"
            data = safe_get(url)
            events.extend(data.get("events", []))
        except Exception:
            break

    return events


def filter_team_matches(events, team_id, league_name, venue=None, limit=5):
    out = []

    for ev in events:
        if not is_finished(ev):
            continue

        if not same_league(ev, league_name):
            continue

        home = ev.get("homeTeam", {}) or {}
        away = ev.get("awayTeam", {}) or {}

        is_home = str(home.get("id")) == str(team_id)
        is_away = str(away.get("id")) == str(team_id)

        if not is_home and not is_away:
            continue

        if venue == "home" and not is_home:
            continue

        if venue == "away" and not is_away:
            continue

        hg, ag = parse_score(ev)

        if hg is None or ag is None:
            continue

        out.append({
            "home": home.get("name", ""),
            "away": away.get("name", ""),
            "home_goals": hg,
            "away_goals": ag,
            "btts_yes": hg > 0 and ag > 0,
            "btts_no": not (hg > 0 and ag > 0),
        })

        if len(out) >= limit:
            break

    return out


def stats_from_matches(matches):
    total = len(matches)
    yes = sum(1 for m in matches if m["btts_yes"])
    no = total - yes
    gols = sum(m["home_goals"] + m["away_goals"] for m in matches)

    return {
        "jogos": total,
        "ambos_sim": yes,
        "ambos_nao": no,
        "pct_sim": pct(yes, total),
        "pct_nao": pct(no, total),
        "media_gols": round(gols / total, 2) if total else 0,
    }


def analyze_btts(row):
    casa = row["Casa"]
    fora = row["Fora"]
    liga = row["Liga"]

    home_id = row.get("Casa ID", "") or search_team_id(casa)
    away_id = row.get("Fora ID", "") or search_team_id(fora)

    home_events = fetch_recent_team_events(home_id)
    away_events = fetch_recent_team_events(away_id)

    home_last5 = filter_team_matches(home_events, home_id, liga, venue=None, limit=5)
    away_last5 = filter_team_matches(away_events, away_id, liga, venue=None, limit=5)

    home_home5 = filter_team_matches(home_events, home_id, liga, venue="home", limit=5)
    away_away5 = filter_team_matches(away_events, away_id, liga, venue="away", limit=5)

    s_home = stats_from_matches(home_last5)
    s_away = stats_from_matches(away_last5)
    s_home_venue = stats_from_matches(home_home5)
    s_away_venue = stats_from_matches(away_away5)

    min_sample = min(
        s_home["jogos"],
        s_away["jogos"],
        s_home_venue["jogos"],
        s_away_venue["jogos"],
    )

    general_yes = round((s_home["pct_sim"] + s_away["pct_sim"]) / 2)
    venue_yes = round((s_home_venue["pct_sim"] + s_away_venue["pct_sim"]) / 2)
    score_yes = round((general_yes * 0.45) + (venue_yes * 0.55))

    general_no = round((s_home["pct_nao"] + s_away["pct_nao"]) / 2)
    venue_no = round((s_home_venue["pct_nao"] + s_away_venue["pct_nao"]) / 2)
    score_no = round((general_no * 0.45) + (venue_no * 0.55))

    if score_yes >= score_no:
        pick = "Ambos marcam — SIM"
        score = score_yes
        detalhe = f"Geral SIM {general_yes}% | Casa/Fora SIM {venue_yes}%"
    else:
        pick = "Ambos marcam — NÃO"
        score = score_no
        detalhe = f"Geral NÃO {general_no}% | Casa/Fora NÃO {venue_no}%"

    if min_sample < 3:
        score = min(score, 64)
        detalhe += " | Amostra baixa"

    positivo = "SIM" if score >= BTTS_THRESHOLD else "NÃO"

    return {
        "Hora": row["Hora"],
        "Jogo": row["Jogo"],
        "Liga": liga,
        "Pick": pick if positivo == "SIM" else "Sem entrada",
        "Probabilidade": f"{score}%",
        "Força": stars(score),
        "Tipo": bet_type(score),
        "Consenso": consensus_label(score),
        "Positivo 75%+": positivo,
        "Score": score,
        "Últ.5 Mandante Liga BTTS SIM": f'{s_home["pct_sim"]}% ({s_home["ambos_sim"]}/{s_home["jogos"]})',
        "Últ.5 Visitante Liga BTTS SIM": f'{s_away["pct_sim"]}% ({s_away["ambos_sim"]}/{s_away["jogos"]})',
        "Mandante em casa BTTS SIM": f'{s_home_venue["pct_sim"]}% ({s_home_venue["ambos_sim"]}/{s_home_venue["jogos"]})',
        "Visitante fora BTTS SIM": f'{s_away_venue["pct_sim"]}% ({s_away_venue["ambos_sim"]}/{s_away_venue["jogos"]})',
        "Detalhe": detalhe,
    }


def to_excel(dfs):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]

            for col_cells in ws.columns:
                letter = col_cells[0].column_letter
                max_len = max(
                    len(str(c.value)) if c.value is not None else 0
                    for c in col_cells
                )
                ws.column_dimensions[letter].width = min(max_len + 2, 50)

    return output.getvalue()


st.title("⚽ Scanner X10 — Ambos Marcam / Ambos Não Marcam")

st.markdown("""
Estudo específico para **BTTS**:

- Últimos 5 jogos de cada time na liga
- Últimos 5 jogos do mandante em casa na liga
- Últimos 5 jogos do visitante fora na liga
- Entrada positiva somente com **75% ou mais**
""")

modo = st.radio(
    "Escolha a fonte dos jogos:",
    [
        "SofaScore automático",
        "Colar JSON do SofaScore",
        "Colar lista manual",
    ],
    horizontal=True,
)

df_games = pd.DataFrame()

if modo == "SofaScore automático":
    selected_date = st.date_input("Data dos jogos", value=date.today())
    date_str = selected_date.strftime("%Y-%m-%d")

    if st.button("🔎 Buscar jogos no SofaScore"):
        try:
            df_games = fetch_sofascore_events(date_str)
            st.session_state["df_games"] = df_games
            st.success(f"{len(df_games)} jogos encontrados no SofaScore.")
        except Exception as e:
            st.error(f"Falha ao buscar no SofaScore: {e}")
            st.warning("Use a opção 'Colar JSON do SofaScore' como fallback.")

elif modo == "Colar JSON do SofaScore":
    json_text = st.text_area("Cole aqui o JSON bruto do SofaScore", height=300)

    if st.button("📥 Ler JSON"):
        try:
            data = json.loads(json_text)
            df_games = parse_sofascore_json(data)
            st.session_state["df_games"] = df_games
            st.success(f"{len(df_games)} jogos lidos do JSON.")
        except Exception as e:
            st.error(f"Erro ao ler JSON: {e}")

else:
    manual_text = st.text_area(
        "Cole no formato: Hora TAB Liga TAB Jogo",
        height=300,
        value="""15:00\tPremier League\tArsenal vs Chelsea
16:00\tSerie A\tInter vs Lazio
21:30\tBrazilian Serie A\tFlamengo vs Palmeiras""",
    )

    if st.button("📋 Ler lista manual"):
        df_games = parse_manual_games(manual_text)
        st.session_state["df_games"] = df_games
        st.success(f"{len(df_games)} jogos lidos manualmente.")

if "df_games" in st.session_state:
    df_games = st.session_state["df_games"]

if not df_games.empty:
    st.subheader("Jogos carregados")
    st.dataframe(df_games[["Hora", "Liga", "Jogo"]], use_container_width=True)

    min_score = st.slider("Score mínimo para exibir", 0, 100, 75)

    if st.button("🚀 Rodar Scanner X10 BTTS"):
        with st.spinner("Analisando últimos 5 jogos na liga e recortes casa/fora..."):
            btts = pd.DataFrame([analyze_btts(row) for _, row in df_games.iterrows()])

        btts_filtrado = btts[btts["Score"] >= min_score].sort_values(
            "Score", ascending=False
        )

        positivos = btts[btts["Positivo 75%+"] == "SIM"].sort_values(
            "Score", ascending=False
        )

        monitorar = btts[
            (btts["Score"] >= 65) & (btts["Score"] < 75)
        ].sort_values("Score", ascending=False)

        display_cols = [
            "Hora",
            "Jogo",
            "Liga",
            "Pick",
            "Probabilidade",
            "Força",
            "Tipo",
            "Consenso",
            "Positivo 75%+",
            "Score",
            "Detalhe",
        ]

        detail_cols = [
            "Hora",
            "Jogo",
            "Liga",
            "Pick",
            "Score",
            "Últ.5 Mandante Liga BTTS SIM",
            "Últ.5 Visitante Liga BTTS SIM",
            "Mandante em casa BTTS SIM",
            "Visitante fora BTTS SIM",
            "Detalhe",
        ]

        tab1, tab2, tab3, tab4 = st.tabs([
            "🎯 Entradas 75%+",
            "📊 Todos os estudos",
            "🔎 Detalhamento",
            "📥 Excel",
        ])

        with tab1:
            st.markdown("### ✅ Picks positivas")
            st.dataframe(positivos[display_cols], use_container_width=True)

        with tab2:
            st.markdown("### 📊 Todos os jogos analisados")
            st.dataframe(btts_filtrado[display_cols], use_container_width=True)

            st.markdown("### 👀 Monitorar — abaixo de 75%")
            st.dataframe(monitorar[display_cols], use_container_width=True)

        with tab3:
            st.markdown("### 🔎 Base do cálculo")
            st.dataframe(btts[detail_cols], use_container_width=True)

        excel_file = to_excel({
            "BTTS_75_positivo": positivos[display_cols],
            "Todos_filtrados": btts_filtrado[display_cols],
            "Detalhamento": btts[detail_cols],
            "Monitorar": monitorar[display_cols],
        })

        with tab4:
            st.download_button(
                label="📥 Baixar Excel",
                data=excel_file,
                file_name="scanner_x10_btts.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

else:
    st.info("Carregue os jogos por uma das opções acima.")
