import streamlit as st
from datetime import datetime, date, timedelta
from predictor import predecir
from clima import obtener_promedios_clima_pasado, obtener_promedios_clima_futuro
from base import insertar_prediccion, insertar_prediccion_modelo

st.title("GrapeSense: Predicción de Cosecha de Uvas")

# Entrada de datos
variedad = st.selectbox("Variedad", ["Cabernet", "Syrah", "Malbec"])
viñedo = st.selectbox("Viñedo", ["Agrelo", "Drummond", "San Carlos"])
brix = st.number_input("Brix", min_value=10.0, max_value=30.0, value=14.5)
ph = st.number_input("pH", min_value=2.5, max_value=4.5, value=3.3)
acidez = st.number_input("Acidez Total", min_value=4.0, max_value=15.0, value=10.0)
dia = st.number_input("Día de cosecha", min_value=1, max_value=31, value=14)
mes = st.number_input("Mes de cosecha", min_value=1, max_value=12, value=5)
modo = st.radio("Modo de consulta", ["Pasado", "Actualidad"])

# Selección de fuente de clima
obtener_promedios_clima = (
    obtener_promedios_clima_pasado if modo == "Pasado" else obtener_promedios_clima_futuro
)

# Botón de predicción
if st.button("Predecir días restantes"):
    fecha_cosecha = date(datetime.now().year, mes, dia)

    # Clima para predicción (7 días hacia adelante)
    inicio_pred = fecha_cosecha
    fin_pred = fecha_cosecha + timedelta(days=6)
    clima_pred = obtener_promedios_clima(viñedo, inicio_pred.isoformat(), fin_pred.isoformat())

    # Clima para base de datos (7 días hacia atrás)
    inicio_db = fecha_cosecha - timedelta(days=6)
    fin_db = fecha_cosecha
    clima_db = obtener_promedios_clima(viñedo, inicio_db.isoformat(), fin_db.isoformat())

    # Predicción
    dias_restantes = predecir(
        variedad, viñedo, brix, ph, acidez,
        clima_pred["tavg_7d"], clima_pred["tmin_7d"], clima_pred["tmax_7d"],
        clima_pred["prcp_7d"], clima_pred["wspd_7d"], clima_pred["pres_7d"]
    )

    st.success(f"Faltan aproximadamente {dias_restantes} días para la cosecha.")

    # Insertar en tabla de clima observado
    insertar_prediccion(
        variedad=variedad,
        viñedo=viñedo,
        fecha_cosecha=fecha_cosecha,
        brix=brix,
        ph=ph,
        acidez=acidez,
        tavg_7d=clima_db["tavg_7d"],
        tmin_7d=clima_db["tmin_7d"],
        tmax_7d=clima_db["tmax_7d"],
        prcp_7d=clima_db["prcp_7d"],
        wspd_7d=clima_db["wspd_7d"],
        pres_7d=clima_db["pres_7d"]
    )

    # Insertar en tabla de predicciones
    insertar_prediccion_modelo(
        variedad=variedad,
        viñedo=viñedo,
        fecha_cosecha=fecha_cosecha,
        brix=brix,
        ph=ph,
        acidez=acidez,
        tavg_7d=clima_pred["tavg_7d"],
        tmin_7d=clima_pred["tmin_7d"],
        tmax_7d=clima_pred["tmax_7d"],
        prcp_7d=clima_pred["prcp_7d"],
        wspd_7d=clima_pred["wspd_7d"],
        pres_7d=clima_pred["pres_7d"],
        dias_restantes=dias_restantes,
        notas=notas
    )

    st.success("Datos almacenados correctamente en ambas tablas.")
