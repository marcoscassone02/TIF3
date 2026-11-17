"""Núcleo de entrenamiento, evaluación e inferencia de GrapeSense."""
from pathlib import Path
import argparse
import json

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT
MODEL_PATH = BACKEND_ROOT / "modelos/base/modelo_final.joblib"
TARGET = "dias_hasta_cosecha"
CATEGORICAL = ["variedad", "vinedo"]
FEATURES = [
    "variedad", "vinedo", "Brix", "pH", "acidez_total_g_l",
    "pasado_tavg_7d", "pasado_tmin_7d", "pasado_tmax_7d",
    "pasado_prcp_sum_7d", "pasado_wspd_7d", "pasado_radiacion_sum_7d",
    "pasado_dias_calor_7d", "futuro_historico_tavg_7d",
    "futuro_historico_tmin_7d", "futuro_historico_tmax_7d",
    "futuro_historico_prcp_sum_7d", "futuro_historico_wspd_7d",
    "futuro_historico_radiacion_sum_7d", "futuro_historico_dias_calor_7d",
]


def read_csv(path, require_target=False):
    data = pd.read_csv(path)
    required = FEATURES + ([TARGET] if require_target else [])
    missing = [column for column in required if column not in data]
    if missing:
        raise ValueError(f"Faltan columnas: {', '.join(missing)}")
    if data[required].isna().any().any():
        raise ValueError("Hay valores vacíos en columnas requeridas")
    return data


def load_artifact(path=MODEL_PATH):
    artifact = joblib.load(path)
    if artifact["columnas"] != FEATURES:
        raise ValueError("Las columnas del modelo guardado no coinciden con este código")
    return artifact


def predict(artifact, data):
    return np.maximum(artifact["model"].predict(data[FEATURES]), 0)


def fit_model(data, model_path, candidate="GB_depth3_trees100",
              training_vintages=None, metadata=None):
    preprocessor = ColumnTransformer(
        [("categorias", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL)],
        remainder="passthrough",
    )
    regressor = GradientBoostingRegressor(
        n_estimators=100, max_depth=3, learning_rate=0.05,
        min_samples_leaf=8, loss="squared_error", random_state=42,
    )
    model = Pipeline([("pre", preprocessor), ("reg", regressor)])
    model.fit(data[FEATURES], data[TARGET])
    artifact = {
        "model": model,
        "columnas": FEATURES,
        "escenario": "pasado_futuro_historico",
        "candidato": candidate,
        "politica_prediccion": "max(0, prediccion)",
        "entrenamiento_vendimias": training_vintages or sorted(
            int(year) for year in data["vendimia"].unique()
        ),
        "muestras_entrenamiento": int(len(data)),
        "lotes_entrenamiento": int(data.groupby(["vendimia", "lote_id"]).ngroups),
        "sklearn_version": sklearn.__version__,
    }
    if metadata:
        artifact.update(metadata)
    joblib.dump(artifact, model_path)
    print(f"Modelo entrenado con {len(data)} muestras y guardado en {model_path}")
    return artifact


def evaluation_metrics(data, predicted):
    error = predicted - data[TARGET].to_numpy()
    return {
        "muestras": len(data),
        "mae_dias": float(mean_absolute_error(data[TARGET], predicted)),
        "rmse_dias": float(np.sqrt(mean_squared_error(data[TARGET], predicted))),
        "sesgo_dias": float(error.mean()),
        "dentro_3_dias_porcentaje": float((np.abs(error) <= 3).mean() * 100),
        "dentro_4_dias_porcentaje": float((np.abs(error) <= 4).mean() * 100),
        "error_maximo_dias": float(np.abs(error).max()),
        "r2": float(r2_score(data[TARGET], predicted)),
    }


def evaluate(path, model_path=MODEL_PATH, show=True):
    data = read_csv(path, require_target=True)
    predicted = predict(load_artifact(model_path), data)
    result = {
        "archivo": str(Path(path).resolve()),
        **evaluation_metrics(data, predicted),
    }
    if show:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def predict_date(fecha, variedad, vinedo, brix, ph, acidez, lote_id=None,
                 muestra_id=None, notas="", bodega_id=None, finca_id=None,
                 cuartel_id=None, latitude=None, longitude=None):
    from ..services.clima import obtain_climate
    from ..core.base_datos import connect, initialize, save_predictions

    climate, metadata = obtain_climate(fecha, vinedo, latitude, longitude)
    row = {
        "bodega_id": bodega_id,
        "finca_id": finca_id,
        "cuartel_id": cuartel_id,
        "muestra_id": muestra_id,
        "lote_id": lote_id,
        "vendimia": pd.Timestamp(fecha).year,
        "fecha_medicion": fecha,
        "variedad": variedad,
        "vinedo": vinedo,
        "Brix": brix,
        "pH": ph,
        "acidez_total_g_l": acidez,
        **climate,
        **metadata,
    }
    data = pd.DataFrame([row])
    artifact, registered_version = load_active_artifact(bodega_id)
    predicted = predict(artifact, data)
    version = registered_version or artifact.get(
        "version_datos", artifact.get("candidato", "modelo_final")
    )
    with connect() as connection:
        initialize(connection)
        prediction_ids = save_predictions(connection, data, predicted, version, notas)
    result = {
        "prediccion_id": prediction_ids[0],
        "fecha_medicion": str(pd.Timestamp(fecha).date()),
        "dias_predichos": float(predicted[0]),
        "fecha_cosecha_estimada": str(
            (pd.Timestamp(fecha) + pd.Timedelta(days=round(float(predicted[0])))).date()
        ),
        "origen_clima": metadata["origen_clima"],
        "clima_pasado": f"{metadata['clima_pasado_desde']} a {metadata['clima_pasado_hasta']}",
        "clima_futuro": f"{metadata['clima_futuro_desde']} a {metadata['clima_futuro_hasta']}",
        "tabla": "predicciones_uva",
    }
    return result


def load_active_artifact(bodega_id):
    """Carga el modelo activo de la bodega; usa el modelo base como respaldo."""
    if bodega_id is None:
        artifact = load_artifact()
        return artifact, artifact.get("candidato", "modelo_final")
    from ..core.base_datos import connect
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT version, ruta_artefacto FROM modelos_bodega
                WHERE bodega_id = %s AND activo
                ORDER BY fecha_entrenamiento DESC NULLS LAST, modelo_bodega_id DESC
                LIMIT 1
            """, (bodega_id,))
            row = cursor.fetchone()
    if row and Path(row[1]).exists():
        return load_artifact(Path(row[1])), row[0]
    artifact = load_artifact()
    return artifact, artifact.get("candidato", "modelo_final")


def main():
    parser = argparse.ArgumentParser(description="Evalúa un artefacto con un CSV etiquetado.")
    parser.add_argument("csv")
    parser.add_argument("--modelo", default=str(MODEL_PATH))
    args = parser.parse_args()
    evaluate(args.csv, args.modelo)


if __name__ == "__main__":
    main()
