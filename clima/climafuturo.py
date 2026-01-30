import requests
import pandas as pd


lat = -33.0239529805325
lon = -68.85196107582618
start_date = "2025-06-20"
end_date = "2025-07-10"


url = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={lat}&longitude={lon}"
    f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
    f"precipitation_sum,surface_pressure_mean,windspeed_10m_max,shortwave_radiation_sum"
    f"&start_date={start_date}&end_date={end_date}"
    f"&timezone=America/Argentina/Buenos_Aires"
)



response = requests.get(url)
data = response.json()


if "daily" in data:
    df = pd.DataFrame(data["daily"])
    print(df)
else:
    print("Error en la respuesta de la API:")
    print(data)
