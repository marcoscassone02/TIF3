"""Entrenamiento reproducible por bodega exclusivamente desde PostgreSQL."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import re

import joblib
import numpy as np
import pandas as pd
from psycopg2.extras import Json, RealDictCursor

from .modelo import FEATURES, TARGET, evaluation_metrics, fit_model, predict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# En producción, esta ruta apunta al disco persistente del proveedor. El modelo
# base sigue versionado dentro de la aplicación y funciona como respaldo.
MODELS_DIR = Path(os.getenv("MODEL_STORAGE_DIR", BACKEND_ROOT / "modelos"))
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
    if training[TARGET].nunique() < 2 or evaluation[TARGET].nunique() < 2:
        raise ValueError("Entrenamiento y evaluación deben contener más de un valor de días hasta cosecha")
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


def _train_candidate(connection, bodega_id, data, model_name=None):
    with connection.cursor() as cursor:
        cursor.execute("SELECT nombre, slug FROM bodegas WHERE bodega_id = %s AND activa", (bodega_id,))
        winery = cursor.fetchone()
    if winery is None:
        raise ValueError("La bodega no existe")
    candidate_name = (model_name or f"Candidato {winery[0]}").strip()
    if len(candidate_name) > 120:
        raise ValueError("El nombre del modelo no puede superar 120 caracteres")
    training, evaluation, policy = split_samples(data, bodega_id)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
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
        "fuente_entrenamiento": "PostgreSQL / muestras_uva",
        "vendimias_entrenamiento": artifact["entrenamiento_vendimias"],
        "vendimias_evaluacion": artifact["vendimias_evaluacion"],
        "entrenamiento_muestras": int(len(training)),
        "entrenamiento_lotes": int(training.groupby(["vendimia", "lote_id"]).ngroups),
        "evaluacion_lotes": artifact["lotes_evaluacion"],
    })
    artifact["metricas_evaluacion"] = model_metrics
    joblib.dump(artifact, model_path)
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                INSERT INTO modelos_bodega
                    (bodega_id, nombre, version, ruta_artefacto, vendimias_entrenamiento,
                     metricas, activo, fecha_entrenamiento)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
                RETURNING modelo_bodega_id, nombre, version, vendimias_entrenamiento,
                          metricas, activo, fecha_entrenamiento
            """, (
                bodega_id, candidate_name, version, str(model_path),
                ", ".join(map(str, artifact["entrenamiento_vendimias"])), Json(model_metrics),
            ))
            registered = cursor.fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        model_path.unlink(missing_ok=True)
        raise
    return dict(registered)


def train_winery_model(connection, bodega_id, model_name=None):
    data = load_completed_samples(connection, bodega_id)
    return _train_candidate(connection, bodega_id, data, model_name)


def create_training_job(connection, bodega_id, user_id):
    """Registra un entrenamiento sin bloquear la petición web."""
    readiness_state = readiness(connection, bodega_id)
    if not readiness_state["puede_entrenar"]:
        raise ValueError(readiness_state["motivo"] or "Los datos todavía no permiten entrenar")
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT entrenamiento_id FROM entrenamientos_modelo
            WHERE bodega_id = %s AND estado IN ('pendiente', 'entrenando')
            ORDER BY fecha_solicitud DESC LIMIT 1
        """, (bodega_id,))
        if cursor.fetchone() is not None:
            raise ValueError("Ya existe un entrenamiento en curso para esta bodega")
        cursor.execute("""
            INSERT INTO entrenamientos_modelo (bodega_id, solicitado_por, estado)
            VALUES (%s, %s, 'pendiente')
            ON CONFLICT DO NOTHING
            RETURNING entrenamiento_id, bodega_id, estado, modelo_bodega_id,
                      mensaje_error, fecha_solicitud, fecha_inicio, fecha_fin
        """, (bodega_id, user_id))
        job = cursor.fetchone()
        if job is None:
            raise ValueError("Ya existe un entrenamiento en curso para esta bodega")
    connection.commit()
    return dict(job)


def get_latest_training_job(connection, bodega_id):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT entrenamiento_id, bodega_id, estado, modelo_bodega_id,
                   mensaje_error, fecha_solicitud, fecha_inicio, fecha_fin
            FROM entrenamientos_modelo
            WHERE bodega_id = %s
            ORDER BY fecha_solicitud DESC LIMIT 1
        """, (bodega_id,))
        job = cursor.fetchone()
    return dict(job) if job else None


def run_training_job(job_id):
    """Ejecuta un trabajo registrado usando una conexión independiente."""
    from ..core.base_datos import connect, initialize
    from ..core.multiempresa import initialize_multitenancy

    try:
        with connect() as connection:
            initialize(connection)
            initialize_multitenancy(connection)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    UPDATE entrenamientos_modelo
                    SET estado = 'entrenando', fecha_inicio = NOW(), mensaje_error = NULL
                    WHERE entrenamiento_id = %s AND estado = 'pendiente'
                    RETURNING bodega_id
                """, (job_id,))
                job = cursor.fetchone()
            connection.commit()
            if job is None:
                return
            model = train_winery_model(connection, job["bodega_id"])
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE entrenamientos_modelo
                    SET estado = 'completado', modelo_bodega_id = %s, fecha_fin = NOW()
                    WHERE entrenamiento_id = %s
                """, (model["modelo_bodega_id"], job_id))
            connection.commit()
    except Exception as error:
        try:
            with connect() as connection:
                initialize(connection)
                initialize_multitenancy(connection)
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE entrenamientos_modelo
                        SET estado = 'error', mensaje_error = %s, fecha_fin = NOW()
                        WHERE entrenamiento_id = %s
                    """, (str(error)[:2000], job_id))
                connection.commit()
        except Exception:
            pass


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


def _json_default(value):
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    return str(value)


def main():
    parser = argparse.ArgumentParser(
        description="Entrena, lista y activa modelos por bodega desde PostgreSQL.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bodegas", help="Lista las bodegas y sus identificadores")
    status_parser = commands.add_parser("estado", help="Revisa si la base tiene datos suficientes")
    status_parser.add_argument("--bodega", type=int, required=True)
    database_parser = commands.add_parser("entrenar-db", help="Entrena con muestras_uva")
    database_parser.add_argument("--bodega", type=int, required=True)
    database_parser.add_argument("--nombre")
    list_parser = commands.add_parser("listar", help="Lista los modelos registrados")
    list_parser.add_argument("--bodega", type=int, required=True)
    activate_parser = commands.add_parser("activar", help="Activa un candidato registrado")
    activate_parser.add_argument("--bodega", type=int, required=True)
    activate_parser.add_argument("--modelo", type=int, required=True)
    args = parser.parse_args()

    from ..core.base_datos import connect, initialize
    from ..core.multiempresa import initialize_multitenancy

    with connect() as connection:
        initialize(connection)
        initialize_multitenancy(connection)
        if args.command == "bodegas":
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT bodega_id, nombre, slug, activa FROM bodegas ORDER BY nombre")
                result = {"items": [dict(row) for row in cursor.fetchall()]}
        elif args.command == "estado":
            result = readiness(connection, args.bodega)
        elif args.command == "entrenar-db":
            result = train_winery_model(connection, args.bodega, args.nombre)
        elif args.command == "activar":
            result = activate_model(connection, args.bodega, args.modelo)
        else:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT modelo_bodega_id, nombre, version, vendimias_entrenamiento,
                           metricas, activo, fecha_entrenamiento
                    FROM modelos_bodega WHERE bodega_id = %s
                    ORDER BY fecha_creacion DESC
                """, (args.bodega,))
                result = {"items": [dict(row) for row in cursor.fetchall()]}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
