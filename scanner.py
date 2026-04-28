import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(
    page_title="Scanner X10 - SCEM + Consenso PRO",
    layout="wide"
)

# =========================================================
# CONFIGURAÇÕES
# =========================================================

LEAGUE_PROFILES = {
    "Champions League": {"goals": 4, "corners": 4, "cards": 3, "level": 5},
    "Libertadores": {"goals": 2, "corners": 3, "cards": 5, "level": 4},
    "Sudamericana": {"goals": 2, "corners": 3, "cards": 5, "level": 3},
    "Saudi Pro League": {"goals": 4, "corners": 3, "cards": 3, "level": 3},
    "Eredivisie": {"goals": 5, "corners": 4, "cards": 2, "level": 3},
    "Championship": {"goals": 3, "corners": 5, "cards": 3, "level": 4},
    "Egito": {"goals": 2, "corners": 2, "cards": 3, "level": 2},
    "Portugal 2": {"goals": 2, "corners": 3, "cards": 4, "level": 2},
    "Primera Nacional": {"goals": 2, "corners": 2, "cards": 5, "level": 2},
}

STRONG_TEAMS = [
    "Al-Hilal", "Bayern", "Paris Saint-Germain", "PSG",
    "Botafogo", "Cruzeiro", "Boca Juniors", "São Paulo",
    "Southampton", "Ipswich", "Rosario Central",
    "Sporting Cristal", "Junior", "Santos", "LDU",
    "Independiente del Valle", "Al-Shabab"
]

DEFENSIVE_TEAMS = [
    "Boca", "San Lorenzo", "Libertad", "LDU",
    "Independiente del Valle", "Torreense",
    "Feirense", "Almirante Brown"
]

AGGRESSIVE_TEAMS = [
    "Boca", "Cruzeiro", "San Lorenzo", "Santos",
    "Lanús", "LDU", "Independiente", "Botafogo",
    "Millonarios", "São Paulo", "Tolima"
]

HIGH_CORNERS_TEAMS = [
    "Al-Hilal", "PSG", "Paris Saint-Germain", "Bayern",
    "Southampton", "Ipswich", "Botafogo", "Cruzeiro",
    "Roda", "Waalwijk"
]


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def parse_games(text):
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
            "Fora": fora.strip()
        })

    return pd.DataFrame(rows)


def league_profile(liga):
    return LEAGUE_PROFILES.get(
        liga,
        {"goals": 3, "corners": 3, "cards": 3, "level": 2}
    )


def contains_any(text, names):
    text = text.lower()
    return any(name.lower() in text for name in names)


def stars(score):
    if score >= 85:
        return "⭐⭐⭐⭐⭐"
    elif score >= 72:
        return "⭐⭐⭐⭐"
    elif score >= 58:
        return "⭐⭐⭐"
    elif score >= 45:
        return "⭐⭐"
    else:
        return "⭐"


def bet_type(score):
    if score >= 72:
        return "CONSERVADOR"
    elif score >= 58:
        return "VALOR"
    elif score >= 45:
        return "RISCO CONTROLADO"
    return "EVITAR"


def consensus_label(score):
    if score >= 75:
        return "CONSENSO FORTE"
    elif score >= 58:
        return "CONSENSO MÉDIO"
    return "SEM CONSENSO"


def momentum_score(row):
    score = 50

    casa = row["Casa"]
    fora = row["Fora"]
    jogo = row["Jogo"]
    liga = row["Liga"]

    profile = league_profile(liga)

    if contains_any(casa, STRONG_TEAMS):
        score += 18

    if contains_any(fora, STRONG_TEAMS):
        score -= 5

    if profile["level"] >= 4:
        score += 8

    if contains_any(jogo, AGGRESSIVE_TEAMS):
        score += 5

    return max(0, min(100, score))


# =========================================================
# MOTORES DE ANÁLISE
# =========================================================

def analyze_winner(row):
    casa = row["Casa"]
    fora = row["Fora"]
    jogo = row["Jogo"]
    liga = row["Liga"]

    profile = league_profile(liga)
    score = 50
    pick = "Evitar vencedor"

    if contains_any(casa, STRONG_TEAMS):
        score += 25
        pick = f"{casa} vence"

    elif contains_any(fora, STRONG_TEAMS):
        score += 12
        pick = f"{fora} DNB"

    else:
        score += profile["level"] * 3
        pick = f"{casa} DNB"

    if "Libertadores" in liga or "Sudamericana" in liga:
        if not contains_any(casa, STRONG_TEAMS):
            pick = f"{casa} ou empate (1X)"
            score += 5

    if "Egito" in liga or "Primera Nacional" in liga:
        score -= 10

    mom = momentum_score(row)
    score = int((score * 0.75) + (mom * 0.25))

    return {
        "Hora": row["Hora"],
        "Jogo": jogo,
        "Liga": liga,
        "Pick": pick,
        "Força": stars(score),
        "Tipo": bet_type(score),
        "Score": score,
        "Consenso": consensus_label(score),
        "Momentum": mom
    }


def analyze_goals(row):
    jogo = row["Jogo"]
    liga = row["Liga"]
    profile = league_profile(liga)

    score = 45 + profile["goals"] * 8
    pick = "Over 1.5 gols"

    if profile["goals"] >= 4:
        pick = "Over 2.5 gols"
        score += 8

    if contains_any(jogo, DEFENSIVE_TEAMS):
        pick = "Under 2.5 gols"
        score += 8

    if contains_any(jogo, ["Al-Hilal", "PSG", "Bayern", "Roda", "Waalwijk"]):
        pick = "Over 2.5 gols"
        score += 12

    if "Egito" in liga or "Portugal 2" in liga or "Primera Nacional" in liga:
        pick = "Under 2.5 gols"
        score += 5

    mom = momentum_score(row)
    score = int((score * 0.80) + (mom * 0.20))

    return {
        "Hora": row["Hora"],
        "Jogo": jogo,
        "Liga": liga,
        "Pick": pick,
        "Força": stars(score),
        "Tipo": bet_type(score),
        "Score": score,
        "Consenso": consensus_label(score),
        "Momentum": mom
    }


def analyze_corners(row):
    jogo = row["Jogo"]
    liga = row["Liga"]
    profile = league_profile(liga)

    score = 42 + profile["corners"] * 8
    pick = "Over 8.5 escanteios"

    if profile["corners"] >= 4:
        pick = "Over 9.5 escanteios"
        score += 8

    if contains_any(jogo, HIGH_CORNERS_TEAMS):
        pick = "Over 8.5 escanteios"
        score += 15

    if contains_any(jogo, DEFENSIVE_TEAMS):
        pick = "Under 10.5 escanteios"
        score += 4

    if "Egito" in liga or "Primera Nacional" in liga:
        pick = "Evitar escanteios"
        score -= 12

    mom = momentum_score(row)
    score = int((score * 0.80) + (mom * 0.20))

    return {
        "Hora": row["Hora"],
        "Jogo": jogo,
        "Liga": liga,
        "Pick": pick,
        "Força": stars(score),
        "Tipo": bet_type(score),
        "Score": score,
        "Consenso": consensus_label(score),
        "Momentum": mom
    }


def analyze_cards(row):
    jogo = row["Jogo"]
    liga = row["Liga"]
    profile = league_profile(liga)

    score = 40 + profile["cards"] * 9
    pick = "Over 4.5 cartões"

    if profile["cards"] >= 5:
        pick = "Over 5.5 cartões"
        score += 8

    if contains_any(jogo, AGGRESSIVE_TEAMS):
        pick = "Over 4.5 cartões"
        score += 12

    if contains_any(jogo, ["Boca", "Cruzeiro", "San Lorenzo", "Santos"]):
        pick = "Over 5.5 cartões"
        score += 10

    if "Eredivisie" in liga:
        pick = "Under 4.5 cartões"
        score += 4

    if "Saudi" in liga:
        pick = "Under 4.5 cartões"
        score -= 3

    mom = momentum_score(row)
    score = int((score * 0.85) + (mom * 0.15))

    return {
        "Hora": row["Hora"],
        "Jogo": jogo,
        "Liga": liga,
        "Pick": pick,
        "Força": stars(score),
        "Tipo": bet_type(score),
        "Score": score,
        "Consenso": consensus_label(score),
        "Momentum": mom
    }


def to_excel(dfs):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            header_format = workbook.add_format({
                "bold": True,
                "bg_color": "#D9EAF7",
                "border": 1
            })

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 22)

    return output.getvalue()


# =========================================================
# INTERFACE
# =========================================================

st.title("⚽ Scanner X10 — SCEM + Consenso PRO Multi-Mercados")

st.markdown("""
Este scanner analisa os jogos em quatro mercados:

- Vitória
- Gols
- Escanteios
- Cartões

Versão V1: entrada manual, sem API.
""")

default_text = """11:00\tEgito\tPetrojet vs Ismaily
11:00\tEgito\tZED FC vs Pharco FC
13:00\tSaudi Pro League\tAl-Shabab vs Al-Fateh
13:45\tEredivisie\tRoda JC Kerkrade vs RKC Waalwijk
13:45\tSaudi Pro League\tNeom SC vs Al-Hazem
14:00\tEgito\tArab Contractors FC vs Ghazl El Mahalla FC
14:00\tEgito\tIsmailia Electricity Club vs National Bank of Egypt
14:00\tPortugal 2\tFeirense vs Torreense
15:00\tSaudi Pro League\tAl-Hilal vs Damac FC
15:00\tSaudi Pro League\tAl-Khaleej vs Al-Najma SC
15:45\tChampionship\tSouthampton vs Ipswich Town
16:00\tChampions League\tParis Saint-Germain vs FC Bayern München
19:00\tLibertadores\tCA Lanús vs LDU
19:00\tLibertadores\tLibertad vs Independiente del Valle
19:00\tSudamericana\tSan Lorenzo vs Santos
19:00\tSudamericana\tBotafogo vs Club Independiente
19:30\tPrimera Nacional\tClub Ferro Carril Oeste vs Almirante Brown
21:00\tLibertadores\tUniversidad Central vs Rosario Central
21:00\tSudamericana\tBarracas Central vs Audax Italiano
21:30\tLibertadores\tCruzeiro vs Boca Juniors
21:30\tSudamericana\tMillonarios vs São Paulo
21:30\tSudamericana\tRecoleta FC vs Deportivo Cuenca
23:00\tLibertadores\tDeportes Tolima vs Coquimbo Unido
23:00\tLibertadores\tClub Sporting Cristal vs Junior Barranquilla
23:00\tSudamericana\tO'Higgins vs Boston River"""

games_text = st.text_area(
    "Cole aqui os jogos no formato: Hora TAB Liga TAB Jogo",
    value=default_text,
    height=350
)

min_score = st.slider(
    "Score mínimo para exibir nas planilhas",
    min_value=0,
    max_value=100,
    value=55
)

run = st.button("🚀 Rodar Scanner X10")

if run:
    df_games = parse_games(games_text)

    if df_games.empty:
        st.error("Nenhum jogo identificado. Verifique o formato da lista.")
        st.stop()

    victory = pd.DataFrame([analyze_winner(row) for _, row in df_games.iterrows()])
    goals = pd.DataFrame([analyze_goals(row) for _, row in df_games.iterrows()])
    corners = pd.DataFrame([analyze_corners(row) for _, row in df_games.iterrows()])
    cards = pd.DataFrame([analyze_cards(row) for _, row in df_games.iterrows()])

    victory = victory[victory["Score"] >= min_score].sort_values("Score", ascending=False)
    goals = goals[goals["Score"] >= min_score].sort_values("Score", ascending=False)
    corners = corners[corners["Score"] >= min_score].sort_values("Score", ascending=False)
    cards = cards[cards["Score"] >= min_score].sort_values("Score", ascending=False)

    display_cols = ["Hora", "Jogo", "Liga", "Pick", "Força", "Tipo", "Consenso", "Momentum", "Score"]

    st.success(f"{len(df_games)} jogos analisados com sucesso.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Vitória",
        "⚽ Gols",
        "🚩 Escanteios",
        "🟨 Cartões",
        "🎯 Estratégia"
    ])

    with tab1:
        st.subheader("📊 Planilha — Vitória")
        st.dataframe(victory[display_cols], use_container_width=True)

    with tab2:
        st.subheader("⚽ Planilha — Gols")
        st.dataframe(goals[display_cols], use_container_width=True)

    with tab3:
        st.subheader("🚩 Planilha — Escanteios")
        st.dataframe(corners[display_cols], use_container_width=True)

    with tab4:
        st.subheader("🟨 Planilha — Cartões")
        st.dataframe(cards[display_cols], use_container_width=True)

    with tab5:
        st.subheader("🎯 Estratégia Final")

        all_picks = pd.concat([
            victory.assign(Mercado="Vitória"),
            goals.assign(Mercado="Gols"),
            corners.assign(Mercado="Escanteios"),
            cards.assign(Mercado="Cartões")
        ])

        multiplas = all_picks[all_picks["Score"] >= 72].sort_values("Score", ascending=False)
        singles = all_picks[
            (all_picks["Score"] >= 58) & (all_picks["Score"] < 72)
        ].sort_values("Score", ascending=False)

        st.markdown("### 🔒 Picks para múltiplas — 4 e 5 estrelas")
        st.dataframe(
            multiplas[["Mercado", "Hora", "Jogo", "Liga", "Pick", "Força", "Tipo", "Score"]],
            use_container_width=True
        )

        st.markdown("### 💰 Singles de valor — 3 estrelas")
        st.dataframe(
            singles[["Mercado", "Hora", "Jogo", "Liga", "Pick", "Força", "Tipo", "Score"]],
            use_container_width=True
        )

    excel_file = to_excel({
        "Vitoria": victory[display_cols],
        "Gols": goals[display_cols],
        "Escanteios": corners[display_cols],
        "Cartoes": cards[display_cols],
    })

    st.download_button(
        label="📥 Baixar planilha Excel",
        data=excel_file,
        file_name="scanner_x10_scem_consenso.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Cole a lista de jogos e clique em Rodar Scanner X10.")
