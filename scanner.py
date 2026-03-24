import streamlit as st
import numpy as np
import pandas as pd
import requests

# =========================
# TENTA USAR XGBOOST
# =========================
try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except:
    HAS_XGB = False

# =========================
# MODELO BASE (FALLBACK)
# =========================
class SimpleModel:

    def __init__(self, weights):

        self.weights = np.array(weights)
        self.lr = 0.05

    def predict(self, X):

        score = np.dot(X, self.weights)
        return 1 / (1 + np.exp(-score))

    def update(self, X, y):

        pred = self.predict(X)
        error = y - pred

        self.weights += self.lr * error * X


# =========================
# MODELO AVANÇADO (XGBOOST)
# =========================
class AdvancedModel:

    def __init__(self):

        self.model = XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="logloss"
        )

        self.trained = False

    def train(self, X, y):

        self.model.fit(X, y)
        self.trained = True

    def predict(self, X):

        if not self.trained:
            return 0.5

        return self.model.predict_proba([X])[0][1]


# =========================
# MODELOS POR MERCADO
# =========================
models = {
    "victory": AdvancedModel() if HAS_XGB else SimpleModel([3,2,1]),
    "goals": AdvancedModel() if HAS_XGB else SimpleModel([2,2,2]),
    "corners": AdvancedModel() if HAS_XGB else SimpleModel([2,1,2]),
    "cards": AdvancedModel() if HAS_XGB else SimpleModel([2,1,3])
}

# =========================
# FEATURES (SIMPLIFICADAS)
# =========================
def build_features(data):

    return np.array([
        data.get("form", 0),
        data.get("home_adv", 0),
        data.get("consistency", 0)
    ])


# =========================
# BUSCA DADOS (EXEMPLO)
# =========================
def get_team_data(team):

    # aqui você pluga SofaScore depois
    return {
        "form": np.random.rand(),
        "home_adv": np.random.rand(),
        "consistency": np.random.rand()
    }


# =========================
# TREINO COM HISTÓRICO REAL
# =========================
def train_models(history):

    for market in models:

        X = []
        y = []

        for game in history:

            features = build_features(game["features"][market])
            result = game["result"][market]

            X.append(features)
            y.append(result)

        X = np.array(X)
        y = np.array(y)

        model = models[market]

        if HAS_XGB:
            model.train(X, y)
        else:
            for xi, yi in zip(X, y):
                model.update(xi, yi)


# =========================
# PREVISÃO
# =========================
def predict_match(home_data, away_data):

    results = {}

    for market in models:

        model = models[market]

        X_home = build_features(home_data)
        X_away = build_features(away_data)

        prob_home = model.predict(X_home)
        prob_away = model.predict(X_away)

        if prob_home > 0.55:
            results[market] = "HOME"
        elif prob_home < 0.45:
            results[market] = "AWAY"
        else:
            results[market] = "NO BET"

    return results


# =========================
# HISTÓRICO SIMULADO
# =========================
history = []

# =========================
# STREAMLIT
# =========================
st.title("📊 Greg Stats X V7 - IA Forte")

st.write("Modo IA:", "XGBoost 🚀" if HAS_XGB else "Modelo simples ⚠️")

home = st.text_input("Casa")
away = st.text_input("Visitante")

if st.button("Treinar modelo"):

    # simulação de histórico
    for _ in range(50):

        history.append({
            "features": {
                "victory": {
                    "form": np.random.rand(),
                    "home_adv": np.random.rand(),
                    "consistency": np.random.rand()
                },
                "goals": {
                    "form": np.random.rand(),
                    "home_adv": np.random.rand(),
                    "consistency": np.random.rand()
                },
                "corners": {
                    "form": np.random.rand(),
                    "home_adv": np.random.rand(),
                    "consistency": np.random.rand()
                },
                "cards": {
                    "form": np.random.rand(),
                    "home_adv": np.random.rand(),
                    "consistency": np.random.rand()
                }
            },
            "result": {
                "victory": np.random.randint(0,2),
                "goals": np.random.randint(0,2),
                "corners": np.random.randint(0,2),
                "cards": np.random.randint(0,2)
            }
        })

    train_models(history)

    st.success("Modelo treinado com histórico!")


if st.button("Analisar jogo"):

    home_data = get_team_data(home)
    away_data = get_team_data(away)

    prediction = predict_match(home_data, away_data)

    st.write("### 🎯 PICKS")

    for market, pick in prediction.items():
        st.write(f"{market}: **{pick}**")
