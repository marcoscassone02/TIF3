import pandas as pd

# Cargar datos
df_clima = pd.read_csv("clima_SanCarlos_2024.csv")
df_uva = pd.read_csv("uva2_con_clima_2024.csv")

# Asegurar que las fechas del clima son datetime
df_clima['time'] = pd.to_datetime(df_clima['time'])



# Crear columnas promedio vacías
columnas_climaticas = ['tavg', 'tmin', 'tmax', 'prcp', 'wspd', 'pres']


# Calcular promedios para viñedos en Agrelo
for idx, row in df_uva.iterrows():
    if row['Viñedo'] != "San Carlos":
        continue

    fecha_cosecha = row['Fecha_Cosecha']
    clima_7d = df_clima[df_clima['time'] < fecha_cosecha].tail(7)

    for col in columnas_climaticas:
        if col in clima_7d.columns:
            promedio = clima_7d[col].mean(skipna=True)
            df_uva.at[idx, f'{col}_avg_7d'] = round(promedio, 2)


# Mostrar resultados
print(df_uva[df_uva['Viñedo'] == "San Carlos"].head(10))

df_uva.to_csv("uvafinal_con_clima_2024.csv", index=False)