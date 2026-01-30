import joblib
import pandas as pd

# Cargar modelo entrenado
model = joblib.load("modelo_entrenado.pkl")

def predecir(variedad, viñedo, brix, ph, acidez, tavg_7d, tmin_7d, tmax_7d, prcp_7d, wspd_7d, pres_7d):
    entrada = pd.DataFrame([{
        "Variedad": variedad,
        "Viñedo": viñedo,
        "Brix": brix,
        "pH": ph,
        "Ac Total": acidez,
        "tavg_7d": tavg_7d,
        "tmin_7d": tmin_7d,
        "tmax_7d": tmax_7d,
        "prcp_7d": prcp_7d,
        "wspd_7d": wspd_7d,
        "pres_7d": pres_7d
    }])
    prediccion = model.predict(entrada)
    return int(prediccion[0])
