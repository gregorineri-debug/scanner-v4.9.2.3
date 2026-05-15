import streamlit as st
import pandas as pd
import requests
import re
import json
import zipfile
import unicodedata
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


def normalize_text(text):
    text = str(text).lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\b(fc|sc|cf|afc|jk|u21|club)\b", "", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_get(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    if r.status_code != 200:
        raise Exception(f"Status {r.status_code}")
    return r.json()


def pct(n, d):
    return int(round((n / d) * 100)) if d else 0


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


def is_finished(ev):
    return (ev.get("status", {}) or {}).get("type") == "finished"


def parse_score(ev):
    hs = ev.get("homeScore", {}) or {}
    aw = ev.get("awayScore", {}) or {}

    hg = hs.get("current")
    ag = aw.get("current")

    if hg is None:
        hg = hs.get("normaltime")

    if ag is None:
        ag = aw.get("normaltime")

    if hg is None or ag is None:
        return None, None

    return int(hg), int(ag)


def parse_sofascore_json(data):
    rows = []

    for ev in data.get("events", []):
        try:
            home = ev["homeTeam"]["name"]
            away = ev["awayTeam"]["name"]
            league = ev["tournament"]["name"]
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
                "Liga": league,
                "Jogo": f"{home} vs {away}",
                "Casa": home,
                "Fora": away,
                "Casa ID": ev.get("homeTeam", {}).get("id", ""),
                "Fora ID": ev.get("awayTeam", {}).get("id", ""),
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


def fetch_sofascore_events(selected_date):
    url = f"https://www.sofascore.com/api/v1/sport/football/scheduled-events/{selected_date}"
    return parse_sofascore_json(safe_get(url))


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
        })

    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def search_team_id(team_name):
    name_clean = normalize_text(team_name)
    q = requests.utils.quote(str(team_name))

    urls = [
        f"https://www.sofascore.com/api/v1/search/all?q={q}",
        f"https://www.sofascore.com/api/v1/search/teams?q={q}",
    ]

    candidates = []

    for url in urls:
        try:
            data = safe_get(url)

            items = []
            if isinstance(data.get("results"), list):
                items = data.get("results", [])
            elif isinstance(data.get("teams"), list):
                items = data.get("teams", [])
            elif isinstance(data.get("entities"), list):
                items = data.get("entities", [])

            for item in items:
                entity = item.get("entity", item) or {}

                sport_name = normalize_text((entity.get("sport", {}) or {}).get("name", ""))
                entity_name = entity.get("name", "")

                if sport_name and "football" not in sport_name and "soccer" not in sport_name:
                    continue

                if not entity.get("id") or not entity_name:
                    continue

                e_clean = normalize_text(entity_name)

                score = 0
                if e_clean == name_clean:
                    score += 100
                if name_clean in e_clean or e_clean in name_clean:
                    score += 70

                name_words = set(name_clean.split())
                entity_words = set(e_clean.split())
                common = len(name_words & entity_words)

                score += common * 15

                if score > 0:
                    candidates.append({
                        "id": entity.get("id"),
                        "name": entity_name,
                        "score": score,
                    })

        except Exception:
            continue

    if not candidates:
        return ""

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
    return candidates[0]["id"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_recent_team_events(team_id):
    events = []

    if not team_id:
        return events

    urls = [
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/0",
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/1",
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/2",
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/3",
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/4",
        f"https://www.sofascore.com/api/v1/team/{team_id}/events/last/5",
    ]

    for url in urls:
        try:
            data = safe_get(url)
            events.extend(data.get("events", []))
        except Exception:
            continue

    unique = {}
    for ev in events:
        if ev.get("id"):
            unique[ev["id"]] = ev

    return list(unique.values())


def filter_matches(events, team_id, venue=None, limit=5):
    matches = []

    for ev in events:
        if not is_finished(ev):
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

        matches.append({
            "home": home.get("name", ""),
            "away": away.get("name", ""),
            "home_goals": hg,
            "away_goals": ag,
            "btts_yes": hg > 0 and ag > 0,
            "btts_no": not (hg > 0 and ag > 0),
        })

        if len(matches) >= limit:
            break

    return matches


def stats_from_matches(matches):
    total = len(matches)
    yes = sum(1 for m in matches if m["btts_yes"])
    no = total - yes

    return {
        "jogos": total,
        "sim": yes,
        "nao": no,
        "pct_sim": pct(yes, total),
        "pct_nao": pct(no, total),
    }


def analyze_btts(row):
    casa = row["Casa"]
    fora = row["Fora"]

    home_id = row.get("Casa ID", "") or search_team_id(casa)
    away_id = row.get("Fora ID", "") or search_team_id(fora)

    home_events = fetch_recent_team_events(home_id)
    away_events = fetch_recent_team_events(away_id)

    home_last5 = filter_matches(home_events, home_id, venue=None, limit=5)
    away_last5 = filter_matches(away_events, away_id, venue=None, limit=5)

    home_home5 = filter_matches(home_events, home_id, venue="home", limit=5)
    away_away5 = filter_matches(away_events, away_id, venue="away", limit=5)

    s_home = stats_from_matches(home_last5)
    s_away = stats_from_matches(away_last5)
    s_home_casa = stats_from_matches(home_home5)
    s_away_fora = stats_from_matches(away_away5)

    min_sample = min(
        s_home["jogos"],
        s_away["jogos"],
        s_home_casa["jogos"],
        s_away_fora["jogos"],
    )

    geral_sim = round((s_home["pct_sim"] + s_away["pct_sim"]) / 2)
    casa_fora_sim = round((s_home_casa["pct_sim"] + s_away_fora["pct_sim"]) / 2)
    score_sim = round((geral_sim * 0.45) + (casa_fora_sim * 0.55))

    geral_nao = round((s_home["pct_nao"] + s_away["pct_nao"]) / 2)
    casa_fora_nao = round((s_home_casa["pct_nao"] + s_away_fora["pct_nao"]) / 2)
    score_nao = round((geral_nao * 0.45) + (casa_fora_nao * 0.55))

    if score_sim >= score_nao:
        pick_real = "Ambos marcam — SIM"
        score = score_sim
        detalhe = f"Geral SIM {geral_sim}% | Casa/Fora SIM {casa_fora_sim}%"
    else:
        pick_real = "Ambos marcam — NÃO"
        score = score_nao
        detalhe = f"Geral NÃO {geral_nao}% | Casa/Fora NÃO {casa_fora_nao}%"

    if min_sample == 0:
        score = 0
        detalhe += " | Sem dados encontrados"
    elif min_sample < 3:
        score = min(score, 64)
        detalhe += " | Amostra baixa"

    positivo = "SIM" if score >= BTTS_THRESHOLD else "NÃO"
    pick = pick_real if positivo == "SIM" else "Sem entrada"

    diagnostico = (
        f"Casa ID: {home_id or 'NÃO ACHOU'} | "
        f"Fora ID: {away_id or 'NÃO ACHOU'} | "
        f"Eventos casa: {len(home_events)} | "
        f"Eventos fora: {len(away_events)}"
    )

    return {
        "Hora": row["Hora"],
        "Jogo": row["Jogo"],
        "Liga": row["Liga"],
        "Pick": pick,
        "Probabilidade": f"{score}%",
        "Força": stars(score),
        "Tipo": bet_type(score),
        "Consenso": consensus_label(score),
        "Positivo 75%+": positivo,
        "Score": score,
        "Mandante Geral SIM": f'{s_home["pct_sim"]}% ({s_home["sim"]}/{s_home["jogos"]})',
        "Visitante Geral SIM": f'{s_away["pct_sim"]}% ({s_away["sim"]}/{s_away["jogos"]})',
        "Mandante Casa SIM": f'{s_home_casa["pct_sim"]}% ({s_home_casa["sim"]}/{s_home_casa["jogos"]})',
        "Visitante Fora SIM": f'{s_away_fora["pct_sim"]}% ({s_away_fora["sim"]}/{s_away_fora["jogos"]})',
        "Detalhe": detalhe,
        "Diagnóstico": diagnostico,
    }


def to_excel_or_zip(dfs):
    try:
        import openpyxl

        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet_name, df in dfs.items():
                safe_sheet = sheet_name[:31]
                df.to_excel(writer, sheet_name=safe_sheet, index=False)

        return {
            "data": output.getvalue(),
            "file_name": "scanner_x10_btts.xlsx",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    except ModuleNotFoundError:
        output = BytesIO()

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for sheet_name, df in dfs.items():
                csv_data = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
                zf.writestr(f"{sheet_name}.csv", csv_data)

        return {
            "data": output.getvalue(),
            "file_name": "scanner_x10_btts_csv.zip",
            "mime": "application/zip",
        }


st.title("⚽ Scanner X10 — Ambos Marcam / Ambos Não Marcam")

st.markdown("""
Scanner para **Ambos Marcam SIM/NÃO**.

Agora esta versão:
- busca ID do time de forma mais forte;
- usa últimos jogos gerais;
- usa mandante em casa;
- usa visitante fora;
- mostra diagnóstico de ID e eventos encontrados;
- marca positivo somente com **75% ou mais**.
""")

modo = st.radio(
    "Escolha a fonte dos jogos:",
    ["SofaScore automático", "Colar JSON do SofaScore", "Colar lista manual"],
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
            st.success(f"{len(df_games)} jogos encontrados.")
        except Exception as e:
            st.error(f"Erro ao buscar jogos: {e}")

elif modo == "Colar JSON do SofaScore":
    json_text = st.text_area("Cole aqui o JSON bruto do SofaScore", height=300)

    if st.button("📥 Ler JSON"):
        try:
            data = json.loads(json_text)
            df_games = parse_sofascore_json(data)
            st.session_state["df_games"] = df_games
            st.success(f"{len(df_games)} jogos lidos.")
        except Exception as e:
            st.error(f"Erro ao ler JSON: {e}")

else:
    manual_text = st.text_area(
        "Cole no formato: Hora TAB Liga TAB Jogo",
        height=300,
        value="""09:30\tParaguai Apertura\tOlimpia vs Recoleta FC
10:30\tPolônia\tKS Lechia Gdańsk vs Legia Warszawa
16:00\tPremier League\tAston Villa vs Liverpool FC"""
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
        with st.spinner("Buscando IDs, jogos recentes e calculando BTTS..."):
            btts = pd.DataFrame([analyze_btts(row) for _, row in df_games.iterrows()])

        positivos = btts[btts["Score"] >= 75].sort_values("Score", ascending=False)
        filtrados = btts[btts["Score"] >= min_score].sort_values("Score", ascending=False)
        monitorar = btts[(btts["Score"] >= 65) & (btts["Score"] < 75)].sort_values("Score", ascending=False)

        display_cols = [
            "Hora", "Jogo", "Liga", "Pick", "Probabilidade",
            "Força", "Tipo", "Consenso", "Positivo 75%+",
            "Score", "Detalhe"
        ]

        detail_cols = [
            "Hora", "Jogo", "Liga", "Pick", "Score",
            "Mandante Geral SIM",
            "Visitante Geral SIM",
            "Mandante Casa SIM",
            "Visitante Fora SIM",
            "Detalhe",
            "Diagnóstico",
        ]

        tab1, tab2, tab3, tab4 = st.tabs([
            "🎯 Entradas 75%+",
            "📊 Todos",
            "🔎 Detalhamento",
            "📥 Download"
        ])

        with tab1:
            st.dataframe(positivos[display_cols], use_container_width=True)

        with tab2:
            st.markdown("### Jogos acima do filtro")
            st.dataframe(filtrados[display_cols], use_container_width=True)

            st.markdown("### Monitorar")
            st.dataframe(monitorar[display_cols], use_container_width=True)

            st.markdown("### Todos analisados")
            st.dataframe(btts[display_cols], use_container_width=True)

        with tab3:
            st.dataframe(btts[detail_cols], use_container_width=True)

        arquivo = to_excel_or_zip({
            "BTTS_75": positivos[display_cols],
            "Todos": btts[display_cols],
            "Detalhamento": btts[detail_cols],
            "Monitorar": monitorar[display_cols],
        })

        with tab4:
            st.download_button(
                label="📥 Baixar resultado",
                data=arquivo["data"],
                file_name=arquivo["file_name"],
                mime=arquivo["mime"],
            )

else:
    st.info("Carregue os jogos por uma das opções acima.")
