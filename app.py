import streamlit as st
import pandas as pd
import joblib
from datetime import datetime, date
from base import insertar_prediccion

model = joblib.load("modelo_entrenado_2.pkl")
df = pd.read_csv("evolucion_uva_con_fecha_cosecha.csv")

st.title("Predicción de Cosecha de Uvas")

variedad = st.selectbox("Variedad", df["Variedad"].unique())
viñedo = st.selectbox("Viñedo", df["Viñedo"].unique())
brix = st.number_input("Brix", min_value=10.0, max_value=30.0, value=14.5)
ph = st.number_input("pH", min_value=2.5, max_value=4.5, value=3.3)
acidez = st.number_input("Acidez Total", min_value=4.0, max_value=15.0, value=10.0)

dia = st.number_input("Día de cosecha", min_value=1, max_value=31, value=14)
mes = st.number_input("Mes de cosecha", min_value=1, max_value=12, value=5)

if st.button("Predecir días restantes"):
    fecha_base = date(datetime.now().year, 1, 15)
    fecha_cosecha_obj = date(datetime.now().year, mes, dia)  
    dias_desde_1501 = (fecha_cosecha_obj - fecha_base).days

    fecha_cosecha = f"{dia:02}/{mes:02}"  

    # Crear el dataframe para la predicción
    entrada = pd.DataFrame([{
        "Variedad": variedad,
        "Viñedo": viñedo,
        "Brix": brix,
        "pH": ph,
        "Ac Total": acidez
    }])

    prediccion = model.predict(entrada)
    dias_restantes = int(prediccion[0])
    st.success(f"Faltan aproximadamente {dias_restantes} días para la cosecha.")

    # Mostrar valores estimados al momento de cosecha
    filtrado = df[
        (df["Variedad"] == variedad) &
        (df["Viñedo"] == viñedo) &
        (df["Días hasta cosecha"] == 0)
    ]

    if not filtrado.empty:
        brix_final = filtrado["Brix"].mean()
        ph_final = filtrado["pH"].mean()
        acidez_final = filtrado["Ac Total"].mean()

        st.info("Valores estimados al momento de la cosecha:")
        st.write(f"- **Brix**: {brix_final:.2f}")
        st.write(f"- **pH**: {ph_final:.2f}")
        st.write(f"- **Acidez Total**: {acidez_final:.2f}")
    else:
        st.warning("No hay registros de cosecha para esa combinación.")

    # Insertar en la base de datos — aquí sí está definida la variable
    insertar_prediccion(
        variedad=variedad,
        viñedo=viñedo,
        dia_desde_1501=dia_desde_1501,
        brix=brix,
        ph=ph,
        acidez=acidez,
        fecha_cosecha=fecha_cosecha
    )
    st.success("Datos almacenados correctamente en la base de datos.")

