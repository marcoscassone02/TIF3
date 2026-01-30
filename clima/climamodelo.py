from datetime import datetime
from meteostat import Point, Daily
import pandas as pd


lat = -33.129376523923625
lon = -68.87193389708483
alt = 1023  


ubicacion = Point(lat, lon, alt)

fecha_inicio = datetime(2024, 1, 20)
fecha_fin = datetime(2024, 3, 27)


datos = Daily(ubicacion, fecha_inicio, fecha_fin)
datos = datos.fetch()

print(datos.head())
datos.to_csv("clima_Agrelo_2024.csv")

