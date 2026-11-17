"""Validación, enriquecimiento climático e importación multiempresa de muestras."""
from datetime import date
from io import StringIO

import pandas as pd
from psycopg2.extras import RealDictCursor

from .clima import obtain_climate

MAX_ROWS = 250
MAX_CLIMATE_DATES = 60
REQUIRED = [
    "muestra_id", "lote_id", "fecha_medicion", "tipo_muestra",
    "numero_muestra", "variedad", "Brix", "pH", "acidez_total_g_l",
]
ALIASES = {
    "brix": "Brix", "ph": "pH", "acidez": "acidez_total_g_l",
    "acidez_total": "acidez_total_g_l", "fecha_cosecha": "fecha_cosecha_efectiva",
}
CLIMATE_COLUMNS = [
    "pasado_tavg_7d", "pasado_tmin_7d", "pasado_tmax_7d",
    "pasado_prcp_sum_7d", "pasado_wspd_7d", "pasado_radiacion_sum_7d",
    "pasado_dias_calor_7d", "futuro_historico_tavg_7d",
    "futuro_historico_tmin_7d", "futuro_historico_tmax_7d",
    "futuro_historico_prcp_sum_7d", "futuro_historico_wspd_7d",
    "futuro_historico_radiacion_sum_7d", "futuro_historico_dias_calor_7d",
]


def parse_csv(csv_text):
    if not csv_text.strip():
        raise ValueError("El archivo CSV está vacío")
    try:
        frame = pd.read_csv(StringIO(csv_text), sep=None, engine="python", dtype=str)
    except Exception as error:
        raise ValueError(f"No se pudo leer el CSV: {error}") from error
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = frame.rename(columns={column: ALIASES.get(column.lower(), column) for column in frame.columns})
    if frame.empty:
        raise ValueError("El archivo no contiene muestras")
    if len(frame) > MAX_ROWS:
        raise ValueError(f"Se permiten hasta {MAX_ROWS} muestras por importación")
    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(missing))
    if "vendimia" not in frame.columns:
        frame["vendimia"] = ""
    if "dias_hasta_cosecha" not in frame.columns:
        frame["dias_hasta_cosecha"] = ""
    if "fecha_cosecha_efectiva" not in frame.columns:
        frame["fecha_cosecha_efectiva"] = ""
    return frame.fillna("")


def validate_rows(frame):
    rows, errors = [], []
    seen_codes, seen_natural = set(), set()
    for index, raw in frame.iterrows():
        line = index + 2
        try:
            measurement = pd.to_datetime(raw["fecha_medicion"], errors="raise").date()
            if measurement > date.today():
                raise ValueError("fecha_medicion no puede estar en el futuro")
            vintage = int(raw["vendimia"]) if str(raw["vendimia"]).strip() else measurement.year
            sample_type = str(raw["tipo_muestra"]).strip().lower()
            if sample_type not in {"seguimiento", "cosecha"}:
                raise ValueError("tipo_muestra debe ser seguimiento o cosecha")
            row = {
                "codigo_muestra": str(raw["muestra_id"]).strip(),
                "lote_id": str(raw["lote_id"]).strip(),
                "vendimia": vintage,
                "fecha_medicion": measurement,
                "tipo_muestra": sample_type,
                "numero_muestra": int(raw["numero_muestra"]),
                "variedad": str(raw["variedad"]).strip(),
                "Brix": float(str(raw["Brix"]).replace(",", ".")),
                "pH": float(str(raw["pH"]).replace(",", ".")),
                "acidez_total_g_l": float(str(raw["acidez_total_g_l"]).replace(",", ".")),
            }
            if not row["codigo_muestra"] or not row["lote_id"] or not row["variedad"]:
                raise ValueError("muestra_id, lote_id y variedad no pueden estar vacíos")
            if not 2000 <= vintage <= 2100 or row["numero_muestra"] <= 0:
                raise ValueError("vendimia o numero_muestra fuera de rango")
            if not 10 <= row["Brix"] <= 35 or not 2.5 <= row["pH"] <= 4.5 or not 2 <= row["acidez_total_g_l"] <= 20:
                raise ValueError("Brix, pH o acidez fuera de los rangos admitidos")
            harvest_text = str(raw["fecha_cosecha_efectiva"]).strip()
            harvest = pd.to_datetime(harvest_text, errors="raise").date() if harvest_text else None
            if harvest is not None and harvest > date.today():
                raise ValueError("fecha_cosecha_efectiva no puede estar en el futuro")
            days_text = str(raw["dias_hasta_cosecha"]).strip()
            days = int(float(days_text.replace(",", "."))) if days_text else None
            if harvest is not None:
                days_from_date = (harvest - measurement).days
                if days_from_date < 0:
                    raise ValueError("fecha_cosecha_efectiva es anterior a la medición")
                if days is not None and days != days_from_date:
                    raise ValueError("dias_hasta_cosecha no coincide con fecha_cosecha_efectiva")
                days = days_from_date
            if sample_type == "cosecha":
                if days not in (None, 0):
                    raise ValueError("una muestra de cosecha debe tener 0 días hasta cosecha")
                days, harvest = 0, harvest or measurement
            if days is not None and days < 0:
                raise ValueError("dias_hasta_cosecha no puede ser negativo")
            row["dias_hasta_cosecha"] = days
            row["fecha_cosecha_efectiva"] = harvest
            natural = (row["lote_id"].lower(), vintage, measurement)
            if row["codigo_muestra"].lower() in seen_codes or natural in seen_natural:
                raise ValueError("la muestra está duplicada dentro del archivo")
            seen_codes.add(row["codigo_muestra"].lower()); seen_natural.add(natural)
            rows.append(row)
        except Exception as error:
            errors.append(f"Fila {line}: {error}")
    if errors:
        preview = errors[:15]
        if len(errors) > len(preview):
            preview.append(f"... y {len(errors) - len(preview)} errores más")
        raise ValueError("\n".join(preview))
    return complete_harvest_targets(rows)


def complete_harvest_targets(rows):
    """Propaga la cosecha final a todas las mediciones del mismo lote y vendimia."""
    groups = {}
    for row in rows:
        key = (row["lote_id"].strip().lower(), row["vendimia"])
        groups.setdefault(key, []).append(row)

    for (_, vintage), samples in groups.items():
        harvest_samples = [sample for sample in samples if sample["tipo_muestra"] == "cosecha"]
        if len(harvest_samples) > 1:
            raise ValueError(
                f"El lote {samples[0]['lote_id']} de {vintage} tiene más de una muestra de cosecha"
            )
        explicit_dates = {
            sample["fecha_cosecha_efectiva"]
            for sample in samples
            if sample["fecha_cosecha_efectiva"] is not None
        }
        if harvest_samples:
            explicit_dates.add(harvest_samples[0]["fecha_medicion"])
        if len(explicit_dates) > 1:
            raise ValueError(
                f"El lote {samples[0]['lote_id']} de {vintage} tiene fechas de cosecha incompatibles"
            )
        if not explicit_dates:
            continue

        harvest_date = explicit_dates.pop()
        if harvest_date > date.today():
            raise ValueError(
                f"La cosecha del lote {samples[0]['lote_id']} de {vintage} no puede estar en el futuro"
            )
        for sample in samples:
            days = (harvest_date - sample["fecha_medicion"]).days
            if days < 0:
                raise ValueError(
                    f"El lote {sample['lote_id']} de {vintage} contiene una medición posterior a la cosecha"
                )
            if sample["dias_hasta_cosecha"] is not None and sample["dias_hasta_cosecha"] != days:
                raise ValueError(
                    f"dias_hasta_cosecha no coincide con la cosecha del lote {sample['lote_id']} de {vintage}"
                )
            sample["fecha_cosecha_efectiva"] = harvest_date
            sample["dias_hasta_cosecha"] = days
    return rows


def import_samples(connection, *, bodega_id, finca_id, cuartel_id, csv_text, overwrite=False):
    frame = parse_csv(csv_text)
    rows = validate_rows(frame)
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT finca_id, nombre, latitud, longitud FROM fincas
            WHERE finca_id = %s AND bodega_id = %s AND activa
        """, (finca_id, bodega_id))
        farm = cursor.fetchone()
        if farm is None:
            raise ValueError("La finca seleccionada no existe")
        if cuartel_id is not None:
            cursor.execute("""
                SELECT 1 FROM cuarteles WHERE cuartel_id = %s AND finca_id = %s
                AND bodega_id = %s AND activo
            """, (cuartel_id, finca_id, bodega_id))
            if cursor.fetchone() is None:
                raise ValueError("El cuartel seleccionado no pertenece a la finca")

    unique_dates = sorted({row["fecha_medicion"] for row in rows})
    if len(unique_dates) > MAX_CLIMATE_DATES:
        raise ValueError(
            f"El archivo contiene {len(unique_dates)} fechas distintas. Divídelo en cargas de hasta "
            f"{MAX_CLIMATE_DATES} fechas para consultar el clima de forma segura."
        )
    climate_by_date = {}
    for measurement in unique_dates:
        features, metadata = obtain_climate(
            measurement, farm["nombre"], farm["latitud"], farm["longitud"],
        )
        climate_by_date[measurement] = (features, metadata)

    inserted = updated = skipped = completed_targets = 0
    with connection.cursor() as cursor:
        for row in rows:
            features, metadata = climate_by_date[row["fecha_medicion"]]
            cursor.execute("""
                SELECT muestra_id FROM muestras_uva
                WHERE bodega_id = %s AND (
                    LOWER(COALESCE(codigo_muestra, muestra_id)) = LOWER(%s)
                    OR (LOWER(lote_id) = LOWER(%s) AND vendimia = %s AND fecha_medicion = %s)
                ) LIMIT 1
            """, (bodega_id, row["codigo_muestra"], row["lote_id"], row["vendimia"], row["fecha_medicion"]))
            existing = cursor.fetchone()
            if existing and not overwrite:
                skipped += 1
                continue
            internal_id = existing[0] if existing else f"{bodega_id}:{row['codigo_muestra']}"
            values = {
                **row, **features, "muestra_id": internal_id, "bodega_id": bodega_id,
                "finca_id": finca_id, "cuartel_id": cuartel_id, "vinedo": farm["nombre"],
                "origen_registro": "Importación CSV", "origen_clima": metadata["origen_clima"],
            }
            columns = [
                "muestra_id", "codigo_muestra", "bodega_id", "finca_id", "cuartel_id",
                "lote_id", "vendimia", "fecha_medicion", "tipo_muestra", "numero_muestra",
                "variedad", "vinedo", "Brix", "pH", "acidez_total_g_l", *CLIMATE_COLUMNS,
                "dias_hasta_cosecha", "fecha_cosecha_efectiva", "origen_registro", "origen_clima",
            ]
            quoted = [f'"{name}"' if name in {"Brix", "pH"} else name for name in columns]
            placeholders = ", ".join(["%s"] * len(columns))
            if existing:
                assignments = ", ".join(f"{name} = EXCLUDED.{name}" for name in quoted if name != "muestra_id")
                sql = f"""INSERT INTO muestras_uva ({', '.join(quoted)}) VALUES ({placeholders})
                    ON CONFLICT (muestra_id) DO UPDATE SET {assignments}, fecha_actualizacion = NOW()"""
                updated += 1
            else:
                sql = f"INSERT INTO muestras_uva ({', '.join(quoted)}) VALUES ({placeholders})"
                inserted += 1
            cursor.execute(sql, [values[column] for column in columns])

        harvest_targets = {
            (row["lote_id"], row["vendimia"], row["fecha_cosecha_efectiva"])
            for row in rows if row["fecha_cosecha_efectiva"] is not None
        }
        for lot_id, vintage, harvest_date in harvest_targets:
            cursor.execute("""
                SELECT fecha_medicion FROM muestras_uva
                WHERE bodega_id = %s AND LOWER(lote_id) = LOWER(%s) AND vendimia = %s
                  AND fecha_medicion > %s
                LIMIT 1
            """, (bodega_id, lot_id, vintage, harvest_date))
            if cursor.fetchone() is not None:
                raise ValueError(
                    f"El lote {lot_id} de {vintage} tiene mediciones posteriores a la cosecha"
                )
            cursor.execute("""
                SELECT DISTINCT fecha_medicion FROM muestras_uva
                WHERE bodega_id = %s AND LOWER(lote_id) = LOWER(%s) AND vendimia = %s
                  AND tipo_muestra = 'cosecha'
            """, (bodega_id, lot_id, vintage))
            harvest_rows = {item[0] for item in cursor.fetchall()}
            if len(harvest_rows) > 1 or (harvest_rows and harvest_date not in harvest_rows):
                raise ValueError(
                    f"El lote {lot_id} de {vintage} tiene más de una fecha final de cosecha"
                )
            cursor.execute("""
                UPDATE muestras_uva
                SET fecha_cosecha_efectiva = %s,
                    dias_hasta_cosecha = %s::date - fecha_medicion,
                    fecha_actualizacion = NOW()
                WHERE bodega_id = %s AND LOWER(lote_id) = LOWER(%s) AND vendimia = %s
            """, (harvest_date, harvest_date, bodega_id, lot_id, vintage))
            completed_targets += cursor.rowcount
    connection.commit()
    recent = sum(1 for _, metadata in climate_by_date.values() if "pronóstico" in metadata["origen_clima"].lower())
    return {
        "filas_recibidas": len(rows), "insertadas": inserted, "actualizadas": updated,
        "omitidas": skipped, "fechas_climaticas_consultadas": len(climate_by_date),
        "fechas_con_pronostico": recent,
        "objetivos_cosecha_completados": completed_targets,
    }
