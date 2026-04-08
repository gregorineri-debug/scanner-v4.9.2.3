# -------------------------
# SCORE SIMPLES INTELIGENTE (NOVO MOTOR)
# -------------------------
def calcular_score_simples(team_id, league_id, is_home):

    forma, saldo, ataque, defesa, _, vol = extrair_features(team_id)

    # NORMALIZAÇÃO
    forma_n = forma / 3
    saldo_n = max(min(saldo / 3,1),-1)
    defesa_n = 1 - min(defesa / 3,1)

    # 🔥 AJUSTE AUTOMÁTICO DE PESO
    # jogo equilibrado → defesa pesa mais
    if abs(forma - 1.5) < 0.3:
        peso_forma = 4
        peso_saldo = 3
        peso_defesa = 7
    else:
        peso_forma = 6
        peso_saldo = 4
        peso_defesa = 6

    score = (
        forma_n * peso_forma +
        saldo_n * peso_saldo +
        defesa_n * peso_defesa
    )

    # casa/fora
    if is_home:
        score *= 1.08
    else:
        score *= 0.95

    liga = LEAGUE_STRENGTH.get(league_id, DEFAULT_LEAGUE_STRENGTH)

    return round(score * liga * 10, 2)

# -------------------------
# NOVA CLASSIFICAÇÃO
# -------------------------
def classificar(diff, vol_home, vol_away):

    risco = max(vol_home, vol_away)

    if abs(diff) >= 6 and risco < 1.2:
        return "🟢 ELITE"
    elif abs(diff) >= 3:
        return "🟡 MÉDIA"
    else:
        return "🔴 SKIP"
