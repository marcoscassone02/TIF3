import requests
import pandas as pd

VIÑEDOS_COORDS = {
    "Agrelo": {"lat": -33.129376523923625, "lon": -68.87193389708483},
    "Drummond": {"lat": -33.0239529805325, "lon": -68.85196107582618},
    "San Carlos": {"lat": -33.665945328401534, "lon": -69.17572663787573}
}

def obtener_promedios_clima_futuro(vinedo, fecha_inicio, fecha_fin):
    coords = VIÑEDOS_COORDS[vinedo]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={coords['lat']}&longitude={coords['lon']}"
        f"&start_date={fecha_inicio}&end_date={fecha_fin}"
        "&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
        "precipitation_sum,windspeed_10m_max,surface_pressure_mean"
        "&timezone=auto"
    )
    return _procesar_respuesta(url)

def obtener_promedios_clima_pasado(vinedo, fecha_inicio, fecha_fin):
    coords = VIÑEDOS_COORDS[vinedo]
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={coords['lat']}&longitude={coords['lon']}"
        f"&start_date={fecha_inicio}&end_date={fecha_fin}"
        "&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
        "precipitation_sum,windspeed_10m_max,surface_pressure_mean"
        "&timezone=auto"
    )
    return _procesar_respuesta(url)

def _procesar_respuesta(url):
    r = requests.get(url)
    try:
        data = r.json()
        if "daily" not in data:
            print("Clave 'daily' no encontrada.")
            return _nulos()

        df = pd.DataFrame({
            "tavg_7d": data["daily"]["temperature_2m_mean"],
            "tmin_7d": data["daily"]["temperature_2m_min"],
            "tmax_7d": data["daily"]["temperature_2m_max"],
            "prcp_7d": data["daily"]["precipitation_sum"],
            "wspd_7d": data["daily"]["windspeed_10m_max"],
            "pres_7d": data["daily"]["surface_pressure_mean"]
        })

        return {
            "tavg_7d": round(df["tavg_7d"].mean(), 2),
            "tmin_7d": round(df["tmin_7d"].mean(), 2),
            "tmax_7d": round(df["tmax_7d"].mean(), 2),
            "prcp_7d": round(df["prcp_7d"].mean(), 2),
            "wspd_7d": round(df["wspd_7d"].mean(), 2),
            "pres_7d": round(df["pres_7d"].mean(), 2)
        }
    except Exception as e:
        print("Error al procesar datos climáticos:", e)
        return _nulos()

def _nulos():
    return {
        "tavg_7d": None, "tmin_7d": None, "tmax_7d": None,
        "prcp_7d": None, "wspd_7d": None, "pres_7d": None
    }


