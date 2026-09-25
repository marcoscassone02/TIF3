"""Entrenamiento reproducible por bodega directamente desde PostgreSQL."""
from datetime import datetime, timezone
from pathlib import Path
import re

import joblib
import numpy as np
import pandas as pd
from psycopg2.extras import Json, RealDictCursor

from .modelo import FEATURES, TARGET, evaluation_metrics, fit_model, predict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = BACKEND_ROOT / "modelos"
MIN_TRAIN_SAMPLES = 30
MIN_EVALUATION_SAMPLES = 12
SMALL_LATEST_VINTAGE = 150


def _safe_name(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "bodega"


def load_completed_samples(connection, bodega_id):
    quoted_features = [f'"{item}"' if item in {"Brix", "pH"} else item for item in FEATURES]
    query = f"""
        SELECT muestra_id, lote_id, vendimia, fecha_medicion, tipo_muestra,
               {', '.join(quoted_features)}, dias_hasta_cosecha
        FROM muestras_uva m
        WHERE m.bodega_id = %s
          AND m.dias_hasta_cosecha IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM muestras_uva harvest
              WHERE harvest.bodega_id = m.bodega_id
                AND harvest.lote_id = m.lote_id
                AND harvest.vendimia = m.vendimia
                AND harvest.tipo_muestra = 'cosecha'
                AND harvest.dias_hasta_cosecha = 0
          )
        ORDER BY vendimia, lote_id, fecha_medicion, muestra_id
    """
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query, (bodega_id,))
        rows = cursor.fetchall()
    data = pd.DataFrame(rows)
    if data.empty:
        return data
    required = FEATURES + [TARGET]
    data = data.dropna(subset=required).copy()
    data["vendimia"] = data["vendimia"].astype(int)
    return data


def _reserve_lots(data, fraction, rng):
    selected = set()
    for _, group in data.groupby(["vinedo", "variedad"], sort=True):
        lots = np.array(sorted(group["lote_id"].unique()))
        if len(lots) < 2:
            continue
        count = max(1, int(round(len(lots) * fraction)))
        count = min(count, len(lots) - 1)
        selected.update(rng.choice(lots, size=count, replace=False).tolist())
    return selected


def split_samples(data, bodega_id):
    if data.empty:
        raise ValueError("La bodega todavía no tiene lotes cosechados utilizables")
    years = sorted(int(year) for year in data["vendimia"].unique())
    rng = np.random.default_rng(42 + int(bodega_id))
    if len(years) == 1:
        holdout_lots = _reserve_lots(data, 0.25, rng)
        evaluation_mask = data["lote_id"].isin(holdout_lots)
        policy = f"25 % de los lotes de {years[0]}, separados por finca y variedad"
    else:
        latest = years[-1]
        evaluation_mask = data["vendimia"].eq(latest)
        policy = f"vendimia más reciente completa ({latest})"
        if int(evaluation_mask.sum()) < SMALL_LATEST_VINTAGE:
            previous = years[-2]
            previous_data = data[data["vendimia"].eq(previous)]
            extra_lots = _reserve_lots(previous_data, 1 / 3, rng)
            evaluation_mask |= data["vendimia"].eq(previous) & data["lote_id"].isin(extra_lots)
            policy += f" y un tercio de los lotes de {previous}"
    training = data.loc[~evaluation_mask].copy()
    evaluation = data.loc[evaluation_mask].copy()
    if len(training) < MIN_TRAIN_SAMPLES:
        raise ValueError(f"Sólo hay {len(training)} muestras de entrenamiento; se necesitan al menos {MIN_TRAIN_SAMPLES}")
    if len(evaluation) < MIN_EVALUATION_SAMPLES:
        raise ValueError(f"Sólo hay {len(evaluation)} muestras de evaluación; se necesitan al menos {MIN_EVALUATION_SAMPLES}")
    train_keys = set(zip(training["vendimia"], training["lote_id"]))
    evaluation_keys = set(zip(evaluation["vendimia"], evaluation["lote_id"]))
    if train_keys & evaluation_keys:
        raise ValueError("La división mezcló un lote entre entrenamiento y evaluación")
    return training, evaluation, policy


def readiness(connection, bodega_id):
    data = load_completed_samples(connection, bodega_id)
    if data.empty:
        return {"puede_entrenar": False, "muestras": 0, "lotes": 0, "vendimias": [],
                "motivo": "No hay lotes cosechados con objetivo completo"}
    base = {
        "muestras": int(len(data)),
        "lotes": int(data.groupby(["vendimia", "lote_id"]).ngroups),
        "vendimias": sorted(int(year) for year in data["vendimia"].unique()),
    }
    try:
        training, evaluation, policy = split_samples(data, bodega_id)
        return {
            **base, "puede_entrenar": True, "motivo": None, "politica": policy,
            "entrenamiento_muestras": int(len(training)),
            "entrenamiento_lotes": int(training.groupby(["vendimia", "lote_id"]).ngroups),
            "evaluacion_muestras": int(len(evaluation)),
            "evaluacion_lotes": int(evaluation.groupby(["vendimia", "lote_id"]).ngroups),
            "vendimias_entrenamiento": sorted(int(year) for year in training["vendimia"].unique()),
            "vendimias_evaluacion": sorted(int(year) for year in evaluation["vendimia"].unique()),
        }
    except ValueError as error:
        return {**base, "puede_entrenar": False, "motivo": str(error)}


def train_winery_model(connection, bodega_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT nombre, slug FROM bodegas WHERE bodega_id = %s AND activa", (bodega_id,))
        winery = cursor.fetchone()
    if winery is None:
        raise ValueError("La bodega no existe")
    data = load_completed_samples(connection, bodega_id)
    training, evaluation, policy = split_samples(data, bodega_id)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    version = f"GB_{_safe_name(winery[0])}_{timestamp}"
    directory = MODELS_DIR / f"bodega_{bodega_id}"
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / f"{version}.joblib"
    evaluation_columns = [
        "muestra_id", "lote_id", "vendimia", "fecha_medicion", "tipo_muestra",
        *FEATURES, TARGET,
    ]
    metadata = {
        "bodega_id": int(bodega_id),
        "bodega_nombre": winery[0],
        "fuente_entrenamiento": "PostgreSQL / muestras_uva",
        "politica_evaluacion": policy,
        "vendimias_evaluacion": sorted(int(year) for year in evaluation["vendimia"].unique()),
        "lotes_evaluacion": int(evaluation.groupby(["vendimia", "lote_id"]).ngroups),
        "evaluacion_snapshot": evaluation[evaluation_columns].to_dict(orient="records"),
        "ids_entrenamiento": training["muestra_id"].tolist(),
        "ids_evaluacion": evaluation["muestra_id"].tolist(),
    }
    artifact = fit_model(
        training, model_path, version,
        sorted(int(year) for year in training["vendimia"].unique()), metadata,
    )
    predicted = predict(artifact, evaluation)
    model_metrics = evaluation_metrics(evaluation, predicted)
    model_metrics.update({
        "politica": policy,
        "vendimias_entrenamiento": artifact["entrenamiento_vendimias"],
        "vendimias_evaluacion": artifact["vendimias_evaluacion"],
        "entrenamiento_muestras": int(len(training)),
        "entrenamiento_lotes": int(training.groupby(["vendimia", "lote_id"]).ngroups),
        "evaluacion_lotes": artifact["lotes_evaluacion"],
    })
    artifact["metricas_evaluacion"] = model_metrics
    joblib.dump(artifact, model_path)
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            INSERT INTO modelos_bodega
                (bodega_id, nombre, version, ruta_artefacto, vendimias_entrenamiento,
                 metricas, activo, fecha_entrenamiento)
            VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
            RETURNING modelo_bodega_id, nombre, version, vendimias_entrenamiento,
                      metricas, activo, fecha_entrenamiento
        """, (
            bodega_id, f"Candidato {winery[0]}", version, str(model_path),
            ", ".join(map(str, artifact["entrenamiento_vendimias"])), Json(model_metrics),
        ))
        registered = cursor.fetchone()
    connection.commit()
    return dict(registered)


def activate_model(connection, bodega_id, model_id):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT modelo_bodega_id, ruta_artefacto, version FROM modelos_bodega
            WHERE modelo_bodega_id = %s AND bodega_id = %s
            FOR UPDATE
        """, (model_id, bodega_id))
        model = cursor.fetchone()
        if model is None:
            raise ValueError("El modelo no pertenece a la bodega seleccionada")
        if not Path(model["ruta_artefacto"]).exists():
            raise ValueError("No se encuentra el archivo de este modelo")
        cursor.execute("UPDATE modelos_bodega SET activo = FALSE WHERE bodega_id = %s", (bodega_id,))
        cursor.execute("""
            UPDATE modelos_bodega SET activo = TRUE
            WHERE modelo_bodega_id = %s
            RETURNING modelo_bodega_id, nombre, version, vendimias_entrenamiento,
                      metricas, activo, fecha_entrenamiento
        """, (model_id,))
        activated = cursor.fetchone()
    connection.commit()
    return dict(activated)
