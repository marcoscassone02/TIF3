import joblib
import pandas as pd

model = joblib.load("modelo_entrenado_2.pkl")

def predecir(variedad, viniedo, brix, ph, acidez):
    entrada = pd.DataFrame([{
        "Variedad": variedad,
        "Viñedo": viniedo,
        "Brix": brix,
        "pH": ph,
        "Ac Total": acidez
    }])
    prediccion = model.predict(entrada)
    return int(prediccion[0])
