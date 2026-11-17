"""Información interpretable del modelo para la vista del enólogo."""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..core.base_datos import connect
from .modelo import FEATURES, TARGET, MODEL_PATH, load_artifact, predict, read_csv, ROOT

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


def model_analysis(bodega_id):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT mb.nombre, mb.version, mb.ruta_artefacto, b.nombre
                FROM modelos_bodega mb JOIN bodegas b ON b.bodega_id = mb.bodega_id
                WHERE mb.bodega_id = %s AND mb.activo
                ORDER BY mb.fecha_entrenamiento DESC NULLS LAST, mb.modelo_bodega_id DESC
                LIMIT 1
            """, (bodega_id,))
            registered = cursor.fetchone()
    if registered:
        model_name, registered_version, path, winery_name = registered
        try:
            artifact = load_artifact(path)
        except FileNotFoundError:
            artifact = load_artifact(MODEL_PATH)
            model_name, registered_version = "Modelo base regional", artifact.get("candidato", "modelo_final")
    else:
        artifact = load_artifact(MODEL_PATH)
        model_name, registered_version, winery_name = "Modelo base regional", artifact.get("candidato", "modelo_final"), "Bodega"

    pipeline = artifact["model"]
    snapshot = artifact.get("evaluacion_snapshot")
    if snapshot:
        evaluation = pd.DataFrame(snapshot)
        training_count = int(artifact.get("muestras_entrenamiento", 0))
        evaluation_label = "Vendimias " + " y ".join(
            map(str, artifact.get("vendimias_evaluacion", sorted(evaluation["vendimia"].unique())))
        )
        evaluation_lots = int(artifact.get(
            "lotes_evaluacion", evaluation.groupby(["vendimia", "lote_id"]).ngroups
        ))
        data_origin = "Base PostgreSQL de la bodega"
    else:
        evaluation = read_csv(ROOT / "datos/evaluacion_2024.csv", require_target=True)
        training = read_csv(ROOT / "datos/entrenamiento_2022_2023.csv", require_target=True)
        training_count = int(len(training))
        evaluation_label = "Vendimia 2024"
        evaluation_lots = int(evaluation["lote_id"].nunique())
        data_origin = "Sintético"
    predicted = predict(artifact, evaluation)

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

    comparison = [
        {
            "real": round(float(real), 2),
            "predicho": round(float(estimate), 2),
            "error_absoluto": round(abs(float(estimate - real)), 2),
        }
        for real, estimate in zip(actual, predicted)
    ]
    main_metrics = metrics(actual, predicted)
    return {
        "modelo": {
            "nombre": model_name,
            "algoritmo": "Gradient Boosting Regressor",
            "version": registered_version,
            "bodega": winery_name,
            "objetivo": "Días restantes hasta la cosecha efectiva",
            "variables": len(FEATURES),
            "vendimias_entrenamiento": artifact.get("entrenamiento_vendimias", [2022, 2023]),
        },
        "datos": {
            "entrenamiento_muestras": training_count,
            "evaluacion_muestras": int(len(evaluation)),
            "evaluacion_lotes": evaluation_lots,
            "evaluacion_etiqueta": evaluation_label,
            "origen_uva": data_origin,
            "origen_clima": "Histórico reconstruido por Open-Meteo / ERA5",
        },
        "evaluacion": main_metrics,
        "evaluacion_2024": main_metrics,
        "rendimiento_por_anticipacion": horizon_rows,
        "importancia_variables": importances,
        "importancia_grupos": [
            {"grupo": key, "importancia_porcentaje": round(value, 2)}
            for key, value in sorted(group_values.items(), key=lambda item: item[1], reverse=True)
        ],
        "comparacion": comparison,
        "comparacion_2024": comparison,
        "advertencias": [
            "La calidad de la evaluación depende de la cantidad de lotes y de que las cosechas efectivas estén correctamente registradas.",
            "Los lotes de evaluación se mantienen separados de los lotes de entrenamiento.",
            "La importancia describe cuánto usa el modelo una variable; no demuestra causalidad agronómica.",
            "En operación, los siete días futuros son pronósticos y pueden cambiar después de la predicción.",
            "La decisión final debe combinar el resultado con inspección visual, sanidad y criterio enológico.",
        ],
    }
