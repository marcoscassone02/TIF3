"""Obtención automática del clima pasado y futuro para una predicción."""
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen
import json

import pandas as pd

SITES = {
    "Agrelo": (-33.129376523923625, -68.87193389708483),
    "Drummond": (-33.0239529805325, -68.85196107582618),
    "San Carlos": (-33.665945328401534, -69.17572663787573),
}
DAILY = {
    "temperature_2m_mean": "tavg_c",
    "temperature_2m_min": "tmin_c",
    "temperature_2m_max": "tmax_c",
    "precipitation_sum": "prcp_mm",
    "wind_speed_10m_mean": "wspd_kmh",
    "shortwave_radiation_sum": "radiacion_mj_m2",
}


def summarize(window):
    if len(window) != 7:
        raise ValueError(f"La ventana climática tiene {len(window)} días en lugar de 7")
    return {
        "tavg_7d": float(window.tavg_c.mean()),
        "tmin_7d": float(window.tmin_c.mean()),
        "tmax_7d": float(window.tmax_c.mean()),
        "prcp_sum_7d": float(window.prcp_mm.sum()),
        "wspd_7d": float(window.wspd_kmh.mean()),
        "radiacion_sum_7d": float(window.radiacion_mj_m2.sum()),
        "dias_calor_7d": int((window.tmax_c > 35).sum()),
    }


def obtain_climate(prediction_date, site, latitude=None, longitude=None):
    prediction_date = pd.Timestamp(prediction_date).date()
    if prediction_date > date.today():
        raise ValueError("La fecha de medición no puede estar en el futuro")
    if latitude is None or longitude is None:
        if site not in SITES:
            raise ValueError(f"Viñedo desconocido. Opciones: {', '.join(SITES)}")
        latitude, longitude = SITES[site]
    if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180):
        raise ValueError(f"Viñedo desconocido. Opciones: {', '.join(SITES)}")
    start = prediction_date - timedelta(days=7)
    end = prediction_date + timedelta(days=6)
    # ERA5 suele publicarse con demora. Para una predicción reciente se usa la
    # API operativa, que entrega pasado reciente y pronóstico en el mismo formato.
    historical = end <= date.today() - timedelta(days=5)
    if historical:
        endpoint = "https://archive-api.open-meteo.com/v1/archive"
        origin = "Open-Meteo ERA5 histórico reconstruido"
    else:
        endpoint = "https://api.open-meteo.com/v1/forecast"
        origin = "Open-Meteo: pasado reciente y pronóstico operativo"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY),
        "timezone": "America/Argentina/Mendoza",
        "wind_speed_unit": "kmh",
    }
    if historical:
        params["models"] = "era5"
    url = endpoint + "?" + urlencode(params)
    with urlopen(url, timeout=40) as response:
        payload = json.load(response)
    if "daily" not in payload:
        raise RuntimeError(f"Open-Meteo no devolvió datos diarios: {payload}")
    weather = pd.DataFrame(payload["daily"]).rename(columns=DAILY)
    weather.index = pd.to_datetime(weather.pop("time")).dt.date
    expected = pd.date_range(start, end).date
    if list(weather.index) != list(expected):
        raise RuntimeError("Open-Meteo no devolvió todos los días solicitados")
    if weather[list(DAILY.values())].isna().any().any():
        raise RuntimeError("Open-Meteo devolvió valores climáticos vacíos")
    past = weather.loc[start:prediction_date - timedelta(days=1)]
    future = weather.loc[prediction_date:end]
    features = {"pasado_" + key: value for key, value in summarize(past).items()}
    features.update({"futuro_historico_" + key: value for key, value in summarize(future).items()})
    metadata = {
        "clima_pasado_desde": start,
        "clima_pasado_hasta": prediction_date - timedelta(days=1),
        "clima_futuro_desde": prediction_date,
        "clima_futuro_hasta": end,
        "origen_clima": origin,
        "url_clima": url,
    }
    return features, metadata
