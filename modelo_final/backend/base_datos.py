"""Base PostgreSQL de muestras de uva usadas por el modelo final."""
from pathlib import Path
import argparse
import getpass
import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datos"

COLUMNS = [
    "muestra_id", "lote_id", "vendimia", "fecha_medicion", "tipo_muestra",
    "numero_muestra", "variedad", "vinedo", "Brix", "pH", "acidez_total_g_l",
    "pasado_tavg_7d", "pasado_tmin_7d", "pasado_tmax_7d",
    "pasado_prcp_sum_7d", "pasado_wspd_7d", "pasado_radiacion_sum_7d",
    "pasado_dias_calor_7d", "futuro_historico_tavg_7d",
    "futuro_historico_tmin_7d", "futuro_historico_tmax_7d",
    "futuro_historico_prcp_sum_7d", "futuro_historico_wspd_7d",
    "futuro_historico_radiacion_sum_7d", "futuro_historico_dias_calor_7d",
    "dias_hasta_cosecha",
]

DDL = """
CREATE TABLE IF NOT EXISTS muestras_uva (
    muestra_id TEXT PRIMARY KEY,
    lote_id TEXT NOT NULL,
    vendimia SMALLINT NOT NULL CHECK (vendimia BETWEEN 2000 AND 2100),
    fecha_medicion DATE NOT NULL,
    tipo_muestra TEXT NOT NULL CHECK (tipo_muestra IN ('seguimiento', 'cosecha')),
    numero_muestra SMALLINT NOT NULL CHECK (numero_muestra > 0),
    variedad TEXT NOT NULL,
    vinedo TEXT NOT NULL,
    "Brix" DOUBLE PRECISION NOT NULL,
    "pH" DOUBLE PRECISION NOT NULL,
    acidez_total_g_l DOUBLE PRECISION NOT NULL,
    pasado_tavg_7d DOUBLE PRECISION NOT NULL,
    pasado_tmin_7d DOUBLE PRECISION NOT NULL,
    pasado_tmax_7d DOUBLE PRECISION NOT NULL,
    pasado_prcp_sum_7d DOUBLE PRECISION NOT NULL,
    pasado_wspd_7d DOUBLE PRECISION NOT NULL,
    pasado_radiacion_sum_7d DOUBLE PRECISION NOT NULL,
    pasado_dias_calor_7d SMALLINT NOT NULL,
    futuro_historico_tavg_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_tmin_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_tmax_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_prcp_sum_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_wspd_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_radiacion_sum_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_dias_calor_7d SMALLINT NOT NULL,
    dias_hasta_cosecha INTEGER CHECK (dias_hasta_cosecha >= 0),
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (lote_id, vendimia, fecha_medicion)
);
CREATE INDEX IF NOT EXISTS muestras_uva_vendimia_idx
    ON muestras_uva (vendimia);
CREATE INDEX IF NOT EXISTS muestras_uva_lote_fecha_idx
    ON muestras_uva (lote_id, fecha_medicion);

CREATE TABLE IF NOT EXISTS predicciones_uva (
    prediccion_id BIGSERIAL PRIMARY KEY,
    muestra_id TEXT,
    lote_id TEXT,
    vendimia SMALLINT CHECK (vendimia BETWEEN 2000 AND 2100),
    fecha_medicion DATE NOT NULL,
    variedad TEXT NOT NULL,
    vinedo TEXT NOT NULL,
    "Brix" DOUBLE PRECISION NOT NULL,
    "pH" DOUBLE PRECISION NOT NULL,
    acidez_total_g_l DOUBLE PRECISION NOT NULL,
    pasado_tavg_7d DOUBLE PRECISION NOT NULL,
    pasado_tmin_7d DOUBLE PRECISION NOT NULL,
    pasado_tmax_7d DOUBLE PRECISION NOT NULL,
    pasado_prcp_sum_7d DOUBLE PRECISION NOT NULL,
    pasado_wspd_7d DOUBLE PRECISION NOT NULL,
    pasado_radiacion_sum_7d DOUBLE PRECISION NOT NULL,
    pasado_dias_calor_7d SMALLINT NOT NULL,
    futuro_historico_tavg_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_tmin_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_tmax_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_prcp_sum_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_wspd_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_radiacion_sum_7d DOUBLE PRECISION NOT NULL,
    futuro_historico_dias_calor_7d SMALLINT NOT NULL,
    dias_predichos DOUBLE PRECISION NOT NULL CHECK (dias_predichos >= 0),
    fecha_cosecha_estimada DATE NOT NULL,
    modelo_version TEXT NOT NULL,
    notas TEXT,
    clima_pasado_desde DATE,
    clima_pasado_hasta DATE,
    clima_futuro_desde DATE,
    clima_futuro_hasta DATE,
    origen_clima TEXT,
    url_clima TEXT,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS clima_pasado_desde DATE;
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS clima_pasado_hasta DATE;
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS clima_futuro_desde DATE;
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS clima_futuro_hasta DATE;
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS origen_clima TEXT;
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS url_clima TEXT;
CREATE INDEX IF NOT EXISTS predicciones_uva_lote_fecha_idx
    ON predicciones_uva (lote_id, fecha_medicion DESC);
CREATE INDEX IF NOT EXISTS predicciones_uva_creacion_idx
    ON predicciones_uva (fecha_creacion DESC);
"""


def connect():
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    params = {
        "dbname": os.getenv("DB_NAME", "tesis_uva"),
        "user": os.getenv("DB_USER", getpass.getuser()),
        "host": os.getenv("DB_HOST", "/var/run/postgresql"),
        "port": os.getenv("DB_PORT", "5432"),
    }
    if os.getenv("DB_PASSWORD"):
        params["password"] = os.environ["DB_PASSWORD"]
    return psycopg2.connect(**params)


def initialize(connection):
    with connection.cursor() as cursor:
        cursor.execute(DDL)
    connection.commit()


def read_samples(path):
    frame = pd.read_csv(path)
    required = [column for column in COLUMNS if column != "dias_hasta_cosecha"]
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError(f"Faltan columnas en {path}: {', '.join(missing)}")
    if frame[required].isna().any().any():
        raise ValueError(f"Hay valores vacíos en columnas obligatorias de {path}")
    if "dias_hasta_cosecha" not in frame:
        frame["dias_hasta_cosecha"] = None
    frame = frame[COLUMNS].copy()
    frame["fecha_medicion"] = pd.to_datetime(frame["fecha_medicion"]).dt.date
    frame = frame.astype(object).where(pd.notna(frame), None)
    return frame


def upsert_csv(connection, path):
    frame = read_samples(path)
    def sql_name(column):
        return f'"{column}"' if column in {"Brix", "pH"} else column

    quoted = [sql_name(column) for column in COLUMNS]
    update_columns = [column for column in COLUMNS if column != "muestra_id"]
    assignments = ", ".join(
        f'{sql_name(column)} = EXCLUDED.{sql_name(column)}'
        for column in update_columns
    )
    sql = f"""
        INSERT INTO muestras_uva ({', '.join(quoted)}) VALUES %s
        ON CONFLICT (muestra_id) DO UPDATE SET
            {assignments}, fecha_actualizacion = NOW()
    """
    rows = [tuple(row) for row in frame.itertuples(index=False, name=None)]
    with connection.cursor() as cursor:
        execute_values(cursor, sql, rows, page_size=500)
    connection.commit()
    print(f"{len(rows)} muestras almacenadas o actualizadas desde {Path(path).name}")


def import_history(connection):
    for filename in ("entrenamiento_2022_2023.csv", "evaluacion_2024.csv"):
        upsert_csv(connection, DATA / filename)


def save_predictions(connection, frame, predictions, model_version, notes=""):
    feature_columns = COLUMNS[6:-1]
    required = ["fecha_medicion"] + feature_columns
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError("No se pueden almacenar las predicciones; faltan: " + ", ".join(missing))
    if frame[required].isna().any().any():
        raise ValueError("Hay valores vacíos en las columnas que se guardarán")
    dates = pd.to_datetime(frame["fecha_medicion"])
    predicted = pd.Series(predictions, index=frame.index, dtype=float)
    harvest_dates = dates + pd.to_timedelta(predicted.round().astype(int), unit="D")
    prediction_columns = [
        "muestra_id", "lote_id", "vendimia", "fecha_medicion", *feature_columns,
        "dias_predichos", "fecha_cosecha_estimada", "modelo_version", "notas",
        "clima_pasado_desde", "clima_pasado_hasta", "clima_futuro_desde",
        "clima_futuro_hasta", "origen_clima", "url_clima",
    ]
    output = pd.DataFrame(index=frame.index)
    for column in ("muestra_id", "lote_id", "vendimia"):
        output[column] = frame[column] if column in frame else None
    output["fecha_medicion"] = dates.dt.date
    for column in feature_columns:
        output[column] = frame[column]
    output["dias_predichos"] = predicted
    output["fecha_cosecha_estimada"] = harvest_dates.dt.date
    output["modelo_version"] = model_version
    output["notas"] = notes or None
    for column in ("clima_pasado_desde", "clima_pasado_hasta", "clima_futuro_desde",
                   "clima_futuro_hasta", "origen_clima", "url_clima"):
        output[column] = frame[column] if column in frame else None
    output = output.astype(object).where(pd.notna(output), None)

    def sql_name(column):
        return f'"{column}"' if column in {"Brix", "pH"} else column

    sql = (
        f"INSERT INTO predicciones_uva ({', '.join(map(sql_name, prediction_columns))}) "
        "VALUES %s RETURNING prediccion_id"
    )
    rows = [tuple(row) for row in output[prediction_columns].itertuples(index=False, name=None)]
    with connection.cursor() as cursor:
        inserted = execute_values(cursor, sql, rows, page_size=500, fetch=True)
    connection.commit()
    print(f"{len(rows)} predicciones almacenadas en predicciones_uva")
    return [item[0] for item in inserted]


def show_summary(connection):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT vendimia, COUNT(*) AS muestras, COUNT(DISTINCT lote_id) AS lotes,
                   MIN(fecha_medicion) AS primera_medicion,
                   MAX(fecha_medicion) AS ultima_medicion
            FROM muestras_uva
            GROUP BY vendimia
            ORDER BY vendimia
        """)
        rows = cursor.fetchall()
    if not rows:
        print("La tabla existe pero todavía no contiene muestras.")
        return
    print("vendimia | muestras | lotes | primera_medicion | ultima_medicion")
    for row in rows:
        print(" | ".join(map(str, row)))
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM predicciones_uva")
        prediction_count = cursor.fetchone()[0]
    print(f"predicciones_uva | {prediction_count} registros")


def get_predictions(limit=500):
    query = """
        SELECT prediccion_id, fecha_medicion, fecha_creacion, muestra_id, lote_id,
               vendimia, variedad, vinedo, "Brix", "pH", acidez_total_g_l,
               dias_predichos, fecha_cosecha_estimada, clima_pasado_desde,
               clima_pasado_hasta, clima_futuro_desde, clima_futuro_hasta,
               origen_clima, modelo_version, notas
        FROM predicciones_uva
        ORDER BY fecha_creacion DESC
        LIMIT %s
    """
    with connect() as connection:
        initialize(connection)
        with connection.cursor() as cursor:
            cursor.execute(query, (int(limit),))
            columns = [item.name for item in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)


def get_prediction(prediction_id):
    with connect() as connection:
        initialize(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM predicciones_uva WHERE prediccion_id = %s", (prediction_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return {item.name: value for item, value in zip(cursor.description, row)}


def get_samples(limit=100, offset=0, vendimia=None, variedad=None, vinedo=None,
                tipo_muestra=None, search=None):
    filters = []
    parameters = []
    for column, value in (
        ("vendimia", vendimia), ("variedad", variedad), ("vinedo", vinedo),
        ("tipo_muestra", tipo_muestra),
    ):
        if value not in (None, ""):
            filters.append(f"{column} = %s")
            parameters.append(value)
    if search:
        filters.append("(muestra_id ILIKE %s OR lote_id ILIKE %s)")
        term = f"%{search.strip()}%"
        parameters.extend([term, term])
    where = " WHERE " + " AND ".join(filters) if filters else ""
    select = f"""
        SELECT muestra_id, lote_id, vendimia, fecha_medicion, tipo_muestra,
               numero_muestra, variedad, vinedo, "Brix", "pH", acidez_total_g_l,
               dias_hasta_cosecha, pasado_tavg_7d, pasado_prcp_sum_7d,
               pasado_radiacion_sum_7d, futuro_historico_tavg_7d,
               futuro_historico_prcp_sum_7d, futuro_historico_radiacion_sum_7d
        FROM muestras_uva{where}
        ORDER BY fecha_medicion DESC, lote_id, numero_muestra
        LIMIT %s OFFSET %s
    """
    with connect() as connection:
        initialize(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM muestras_uva{where}", parameters)
            total = cursor.fetchone()[0]
            cursor.execute(select, [*parameters, int(limit), int(offset)])
            columns = [item.name for item in cursor.description]
            frame = pd.DataFrame(cursor.fetchall(), columns=columns)
    return frame, total


def get_sample_summary():
    with connect() as connection:
        initialize(connection)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT vendimia, COUNT(*)::integer, COUNT(DISTINCT lote_id)::integer,
                       MIN(fecha_medicion), MAX(fecha_medicion)
                FROM muestras_uva GROUP BY vendimia ORDER BY vendimia
            """)
            by_vintage = [
                {
                    "vendimia": row[0], "muestras": row[1], "lotes": row[2],
                    "primera_medicion": row[3].isoformat(),
                    "ultima_medicion": row[4].isoformat(),
                }
                for row in cursor.fetchall()
            ]
            cursor.execute("""
                SELECT COUNT(*)::integer, COUNT(DISTINCT lote_id)::integer,
                       COUNT(*) FILTER (WHERE tipo_muestra = 'cosecha')::integer
                FROM muestras_uva
            """)
            total, lots, harvests = cursor.fetchone()
            cursor.execute("SELECT DISTINCT variedad FROM muestras_uva ORDER BY variedad")
            varieties = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT DISTINCT vinedo FROM muestras_uva ORDER BY vinedo")
            vineyards = [row[0] for row in cursor.fetchall()]
    return {
        "total_muestras": total,
        "total_lotes": lots,
        "muestras_cosecha": harvests,
        "por_vendimia": by_vintage,
        "variedades": varieties,
        "vinedos": vineyards,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inicializar", help="Crea tablas e índices")
    commands.add_parser("importar-historico", help="Carga 2022, 2023 y 2024")
    add_parser = commands.add_parser("agregar", help="Almacena o actualiza un CSV")
    add_parser.add_argument("csv")
    commands.add_parser("resumen", help="Muestra cantidad de muestras por vendimia")
    args = parser.parse_args()
    with connect() as connection:
        initialize(connection)
        if args.command == "importar-historico":
            import_history(connection)
        elif args.command == "agregar":
            upsert_csv(connection, args.csv)
        elif args.command == "resumen":
            show_summary(connection)
    if args.command == "inicializar":
        print("Tablas muestras_uva y predicciones_uva e índices preparados.")


if __name__ == "__main__":
    main()
