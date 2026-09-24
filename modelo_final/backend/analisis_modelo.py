"""Información interpretable del modelo para la vista del enólogo."""
from functools import lru_cache

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .modelo import FEATURES, TARGET, load_artifact, predict, read_csv, ROOT

LABELS = {
    "variedad": "Variedad",
    "vinedo": "Viñedo / zona",
    "Brix": "Brix",
    "pH": "pH",
    "acidez_total_g_l": "Acidez total",
    "pasado_tavg_7d": "Temperatura media pasada",
    "pasado_tmin_7d": "Temperatura mínima pasada",
    "pasado_tmax_7d": "Temperatura máxima pasada",
    "pasado_prcp_sum_7d": "Lluvia acumulada pasada",
    "pasado_wspd_7d": "Viento medio pasado",
    "pasado_radiacion_sum_7d": "Radiación acumulada pasada",
    "pasado_dias_calor_7d": "Días de calor pasados",
    "futuro_historico_tavg_7d": "Temperatura media futura",
    "futuro_historico_tmin_7d": "Temperatura mínima futura",
    "futuro_historico_tmax_7d": "Temperatura máxima futura",
    "futuro_historico_prcp_sum_7d": "Lluvia acumulada futura",
    "futuro_historico_wspd_7d": "Viento medio futuro",
    "futuro_historico_radiacion_sum_7d": "Radiación acumulada futura",
    "futuro_historico_dias_calor_7d": "Días de calor futuros",
}


def original_feature(transformed):
    name = transformed.split("__", 1)[-1]
    if name.startswith("variedad_"):
        return "variedad"
    if name.startswith("vinedo_"):
        return "vinedo"
    return name


def feature_group(feature):
    if feature in {"Brix", "pH", "acidez_total_g_l"}:
        return "Química de la uva"
    if feature in {"variedad", "vinedo"}:
        return "Variedad y zona"
    if feature.startswith("pasado_"):
        return "Clima de los 7 días anteriores"
    return "Clima de los 7 días siguientes"


def metrics(actual, predicted):
    error = predicted - actual
    return {
        "muestras": int(len(actual)),
        "mae_dias": round(float(mean_absolute_error(actual, predicted)), 2),
        "rmse_dias": round(float(np.sqrt(mean_squared_error(actual, predicted))), 2),
        "sesgo_dias": round(float(error.mean()), 2),
        "dentro_3_dias_porcentaje": round(float((np.abs(error) <= 3).mean() * 100), 1),
        "dentro_4_dias_porcentaje": round(float((np.abs(error) <= 4).mean() * 100), 1),
        "r2": round(float(r2_score(actual, predicted)), 3),
    }


@lru_cache(maxsize=1)
def model_analysis():
    artifact = load_artifact()
    pipeline = artifact["model"]
    evaluation = read_csv(ROOT / "datos/evaluacion_2024.csv", require_target=True)
    training = read_csv(ROOT / "datos/entrenamiento_2022_2023.csv", require_target=True)
    evaluation_2026 = read_csv(ROOT / "datos/evaluacion_2026_sintetica.csv", require_target=True)
    predicted = predict(artifact, evaluation)
    predicted_2026 = predict(artifact, evaluation_2026)

    transformed = pipeline.named_steps["pre"].get_feature_names_out()
    raw_importance = pipeline.named_steps["reg"].feature_importances_
    aggregated = {feature: 0.0 for feature in FEATURES}
    for name, importance in zip(transformed, raw_importance):
        aggregated[original_feature(name)] += float(importance)
    importances = [
        {
            "variable": feature,
            "etiqueta": LABELS[feature],
            "grupo": feature_group(feature),
            "importancia_porcentaje": round(value * 100, 2),
        }
        for feature, value in sorted(aggregated.items(), key=lambda item: item[1], reverse=True)
    ]
    group_values = {}
    for item in importances:
        group_values[item["grupo"]] = group_values.get(item["grupo"], 0) + item["importancia_porcentaje"]

    actual = evaluation[TARGET].to_numpy(dtype=float)
    horizon_rows = []
    for lower, upper, label in (
        (0, 7, "0–7 días"), (8, 14, "8–14 días"),
        (15, 21, "15–21 días"), (22, 999, "22 días o más"),
    ):
        mask = (actual >= lower) & (actual <= upper)
        if mask.any():
            horizon_rows.append({"rango": label, **metrics(actual[mask], predicted[mask])})

    return {
        "modelo": {
            "algoritmo": "Gradient Boosting Regressor",
            "version": artifact.get("candidato", "modelo_final"),
            "objetivo": "Días restantes hasta la cosecha efectiva",
            "variables": len(FEATURES),
            "vendimias_entrenamiento": artifact.get("entrenamiento_vendimias", [2022, 2023]),
        },
        "datos": {
            "entrenamiento_muestras": int(len(training)),
            "evaluacion_2024_muestras": int(len(evaluation)),
            "evaluacion_2026_muestras": int(len(evaluation_2026)),
            "origen_uva": "Sintético",
            "origen_clima": "Histórico reconstruido por Open-Meteo / ERA5",
        },
        "evaluacion_2024": metrics(actual, predicted),
        "evaluacion_2026_sintetica": metrics(
            evaluation_2026[TARGET].to_numpy(dtype=float), predicted_2026
        ),
        "rendimiento_por_anticipacion": horizon_rows,
        "importancia_variables": importances,
        "importancia_grupos": [
            {"grupo": key, "importancia_porcentaje": round(value, 2)}
            for key, value in sorted(group_values.items(), key=lambda item: item[1], reverse=True)
        ],
        "comparacion_2024": [
            {
                "real": round(float(real), 2),
                "predicho": round(float(estimate), 2),
                "error_absoluto": round(abs(float(estimate - real)), 2),
            }
            for real, estimate in zip(actual, predicted)
        ],
        "advertencias": [
            "Las mediciones de uva y las fechas de cosecha usadas para entrenar son sintéticas.",
            "La evaluación 2024 es una separación temporal, pero pertenece al mismo generador sintético.",
            "La importancia describe cuánto usa el modelo una variable; no demuestra causalidad agronómica.",
            "En operación, los siete días futuros son pronósticos y pueden cambiar después de la predicción.",
            "La decisión final debe combinar el resultado con inspección visual, sanidad y criterio enológico.",
        ],
    }
