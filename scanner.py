def definir_pick(diff):

    if diff >= 6:
        return "Casa (1) 🔥"
    elif diff > 0:
        return "Casa (1)"

    elif diff <= -6:
        return "Fora (2) 🔥"
    elif diff < 0:
        return "Fora (2)"

    else:
        return "Equilibrado"
