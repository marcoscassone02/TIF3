"""Seguimientos semanales de lotes y cierre con cosecha efectiva."""
from datetime import date
import re
import unicodedata

from psycopg2.extras import RealDictCursor

from .clima import obtain_climate
from .importacion_muestras import CLIMATE_COLUMNS


def _identifier_part(value):
    """Convierte nombres visibles a la convención usada por el histórico."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")


def _validate_chemistry(brix, ph, acidity):
    if not 10 <= brix <= 35 or not 2.5 <= ph <= 4.5 or not 2 <= acidity <= 20:
        raise ValueError("Brix, pH o acidez están fuera de los rangos admitidos")


def _farm_and_block(connection, bodega_id, finca_id, cuartel_id):
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
                raise ValueError("El cuartel no pertenece a la finca")
    return farm


def list_followups(connection, bodega_id, status=None):
    params = [bodega_id]
    status_filter = ""
    if status:
        status_filter = " AND s.estado = %s"
        params.append(status)
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(f"""
            SELECT s.seguimiento_id, s.codigo, s.lote_referencia, s.variedad,
                   s.vendimia, s.estado, s.fecha_inicio, s.fecha_cosecha_efectiva,
                   s.finca_id, f.nombre AS finca, s.cuartel_id, c.nombre AS cuartel,
                   COUNT(m.muestra_id)::integer AS muestras,
                   MAX(m.fecha_medicion) AS ultima_medicion,
                   MAX(m.numero_muestra)::integer AS ultima_muestra
            FROM seguimientos_uva s
            JOIN fincas f ON f.finca_id = s.finca_id
            LEFT JOIN cuarteles c ON c.cuartel_id = s.cuartel_id
            LEFT JOIN muestras_uva m ON m.seguimiento_id = s.seguimiento_id
            WHERE s.bodega_id = %s {status_filter}
            GROUP BY s.seguimiento_id, f.nombre, c.nombre
            ORDER BY (s.estado = 'pendiente') DESC, s.fecha_inicio DESC, s.seguimiento_id DESC
        """, params)
        return cursor.fetchall()


def _next_lot_code(connection, bodega_id, farm_name, variety):
    prefix = f"{_identifier_part(farm_name)}_{_identifier_part(variety)}_"
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT lote_id AS codigo FROM muestras_uva
            WHERE bodega_id = %s AND LEFT(lote_id, %s) = %s
            UNION
            SELECT codigo FROM seguimientos_uva
            WHERE bodega_id = %s AND LEFT(codigo, %s) = %s
        """, (bodega_id, len(prefix), prefix, bodega_id, len(prefix), prefix))
        numbers = []
        for row in cursor.fetchall():
            suffix = row["codigo"][len(prefix):]
            if suffix.isdigit():
                numbers.append(int(suffix))
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def create_followup(connection, *, bodega_id, finca_id, cuartel_id, variety, vintage, start_date, lot_reference=None):
    if start_date > date.today():
        raise ValueError("La fecha inicial no puede estar en el futuro")
    if not 2000 <= vintage <= 2100:
        raise ValueError("La vendimia está fuera de rango")
    farm = _farm_and_block(connection, bodega_id, finca_id, cuartel_id)
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (int(bodega_id),))
        code = _next_lot_code(connection, bodega_id, farm["nombre"], variety)
        cursor.execute("""
            INSERT INTO seguimientos_uva
                (bodega_id, finca_id, cuartel_id, codigo, lote_referencia,
                 variedad, vendimia, fecha_inicio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING seguimiento_id, codigo, lote_referencia, variedad, vendimia,
                      estado, fecha_inicio, finca_id, cuartel_id
        """, (bodega_id, finca_id, cuartel_id, code, lot_reference or None,
              variety.strip(), vintage, start_date))
        result = cursor.fetchone()
        result["finca"] = farm["nombre"]
    connection.commit()
    return result


def update_followup(connection, *, bodega_id, seguimiento_id, finca_id, cuartel_id,
                    variety, vintage, start_date, lot_reference=None):
    tracking = _get_followup(connection, bodega_id, seguimiento_id)
    if start_date > date.today():
        raise ValueError("La fecha inicial no puede estar en el futuro")
    if not 2000 <= vintage <= 2100:
        raise ValueError("La vendimia está fuera de rango")
    farm = _farm_and_block(connection, bodega_id, finca_id, cuartel_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT MIN(fecha_medicion) FROM muestras_uva WHERE seguimiento_id = %s", (seguimiento_id,))
        first_measurement = cursor.fetchone()[0]
    if first_measurement and start_date > first_measurement:
        raise ValueError("El inicio no puede quedar después de la primera medición")

    identity_changed = farm["nombre"] != tracking["finca"] or variety.strip() != tracking["variedad"]
    code = tracking["codigo"]
    if identity_changed:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (int(bodega_id),))
        code = _next_lot_code(connection, bodega_id, farm["nombre"], variety)

    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT muestra_id, fecha_medicion FROM muestras_uva
            WHERE seguimiento_id = %s ORDER BY fecha_medicion
        """, (seguimiento_id,))
        samples = cursor.fetchall()
    farm_changed = finca_id != tracking["finca_id"]
    for sample in samples:
        features = None
        climate_origin = None
        if farm_changed:
            features, metadata = obtain_climate(
                sample["fecha_medicion"], farm["nombre"], farm["latitud"], farm["longitud"],
            )
            climate_origin = metadata["origen_clima"]
        visible_id = f"{code}_{vintage}_{sample['fecha_medicion'].strftime('%Y%m%d')}"
        assignments = [
            "muestra_id = %s", "codigo_muestra = %s", "lote_id = %s", "vendimia = %s",
            "finca_id = %s", "cuartel_id = %s", "variedad = %s", "vinedo = %s",
            "fecha_actualizacion = NOW()",
        ]
        values = [f"{bodega_id}:{visible_id}", visible_id, code, vintage, finca_id,
                  cuartel_id, variety.strip(), farm["nombre"]]
        if features is not None:
            assignments.extend(f"{column} = %s" for column in CLIMATE_COLUMNS)
            assignments.append("origen_clima = %s")
            values.extend(features[column] for column in CLIMATE_COLUMNS)
            values.append(climate_origin)
        values.append(sample["muestra_id"])
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE muestras_uva SET {', '.join(assignments)} WHERE muestra_id = %s",
                values,
            )
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            UPDATE seguimientos_uva SET finca_id = %s, cuartel_id = %s, codigo = %s,
                lote_referencia = %s, variedad = %s, vendimia = %s, fecha_inicio = %s,
                fecha_actualizacion = NOW()
            WHERE seguimiento_id = %s AND bodega_id = %s
            RETURNING seguimiento_id, codigo, lote_referencia, variedad, vendimia,
                      estado, fecha_inicio, finca_id, cuartel_id
        """, (finca_id, cuartel_id, code, lot_reference or None, variety.strip(), vintage,
              start_date, seguimiento_id, bodega_id))
        result = cursor.fetchone()
        result["finca"] = farm["nombre"]
    connection.commit()
    return result


def delete_followup(connection, *, bodega_id, seguimiento_id):
    tracking = _get_followup(connection, bodega_id, seguimiento_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM muestras_uva WHERE seguimiento_id = %s", (seguimiento_id,))
        sample_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM muestras_uva WHERE seguimiento_id = %s", (seguimiento_id,))
        cursor.execute("""
            DELETE FROM seguimientos_uva
            WHERE seguimiento_id = %s AND bodega_id = %s AND estado = 'pendiente'
        """, (seguimiento_id, bodega_id))
    connection.commit()
    return {"eliminado": tracking["codigo"], "muestras_eliminadas": sample_count}


def _get_followup(connection, bodega_id, seguimiento_id, only_pending=True):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT s.*, f.nombre AS finca, f.latitud, f.longitud
            FROM seguimientos_uva s JOIN fincas f ON f.finca_id = s.finca_id
            WHERE s.seguimiento_id = %s AND s.bodega_id = %s
        """, (seguimiento_id, bodega_id))
        item = cursor.fetchone()
    if item is None:
        raise ValueError("El seguimiento no existe")
    if only_pending and item["estado"] != "pendiente":
        raise ValueError("El seguimiento ya fue cerrado")
    return item


def _store_sample(connection, tracking, measurement_date, brix, ph, acidity, sample_type="seguimiento"):
    _validate_chemistry(brix, ph, acidity)
    if measurement_date > date.today():
        raise ValueError("La fecha de medición no puede estar en el futuro")
    if measurement_date < tracking["fecha_inicio"]:
        raise ValueError("La medición no puede ser anterior al inicio del seguimiento")
    features, metadata = obtain_climate(
        measurement_date, tracking["finca"], tracking["latitud"], tracking["longitud"],
    )
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COALESCE(MAX(numero_muestra), 0) + 1
            FROM muestras_uva WHERE seguimiento_id = %s
        """, (tracking["seguimiento_id"],))
        number = cursor.fetchone()[0]
        sample_code = (
            f"{tracking['codigo']}_{tracking['vendimia']}_"
            f"{measurement_date.strftime('%Y%m%d')}"
        )
        values = {
            "muestra_id": f"{tracking['bodega_id']}:{sample_code}",
            "codigo_muestra": sample_code, "bodega_id": tracking["bodega_id"],
            "finca_id": tracking["finca_id"], "cuartel_id": tracking["cuartel_id"],
            "seguimiento_id": tracking["seguimiento_id"], "lote_id": tracking["codigo"],
            "vendimia": tracking["vendimia"], "fecha_medicion": measurement_date,
            "tipo_muestra": sample_type, "numero_muestra": number,
            "variedad": tracking["variedad"], "vinedo": tracking["finca"],
            "Brix": brix, "pH": ph, "acidez_total_g_l": acidity,
            **features, "dias_hasta_cosecha": 0 if sample_type == "cosecha" else None,
            "fecha_cosecha_efectiva": measurement_date if sample_type == "cosecha" else None,
            "origen_registro": "Seguimiento operativo", "origen_clima": metadata["origen_clima"],
        }
        columns = [
            "muestra_id", "codigo_muestra", "bodega_id", "finca_id", "cuartel_id",
            "seguimiento_id", "lote_id", "vendimia", "fecha_medicion", "tipo_muestra",
            "numero_muestra", "variedad", "vinedo", "Brix", "pH", "acidez_total_g_l",
            *CLIMATE_COLUMNS, "dias_hasta_cosecha", "fecha_cosecha_efectiva",
            "origen_registro", "origen_clima",
        ]
        quoted = [f'"{name}"' if name in {"Brix", "pH"} else name for name in columns]
        cursor.execute(
            f"INSERT INTO muestras_uva ({', '.join(quoted)}) VALUES ({', '.join(['%s'] * len(columns))})",
            [values[column] for column in columns],
        )
        cursor.execute("""
            UPDATE seguimientos_uva SET fecha_actualizacion = NOW()
            WHERE seguimiento_id = %s
        """, (tracking["seguimiento_id"],))
    return {"muestra_id": sample_code, "numero_muestra": number, "origen_clima": metadata["origen_clima"]}


def add_measurement(connection, *, bodega_id, seguimiento_id, measurement_date, brix, ph, acidity):
    tracking = _get_followup(connection, bodega_id, seguimiento_id)
    result = _store_sample(connection, tracking, measurement_date, brix, ph, acidity)
    connection.commit()
    return result


def close_followup(connection, *, bodega_id, seguimiento_id, harvest_date, brix, ph, acidity):
    tracking = _get_followup(connection, bodega_id, seguimiento_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT MAX(fecha_medicion) FROM muestras_uva WHERE seguimiento_id = %s", (seguimiento_id,))
        last_date = cursor.fetchone()[0]
    if harvest_date > date.today():
        raise ValueError("La fecha de cosecha no puede estar en el futuro")
    if harvest_date < tracking["fecha_inicio"] or (last_date and harvest_date < last_date):
        raise ValueError("La cosecha no puede ser anterior a las mediciones del seguimiento")

    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT muestra_id, fecha_medicion FROM muestras_uva
            WHERE seguimiento_id = %s ORDER BY fecha_medicion
        """, (seguimiento_id,))
        previous = cursor.fetchall()
    refreshed_forecasts = 0
    with connection.cursor() as cursor:
        for sample in previous:
            features, metadata = obtain_climate(
                sample["fecha_medicion"], tracking["finca"], tracking["latitud"], tracking["longitud"],
            )
            assignments = ", ".join(
                f'{name} = %s' for name in CLIMATE_COLUMNS
            )
            cursor.execute(
                f"""UPDATE muestras_uva SET {assignments}, dias_hasta_cosecha = %s,
                    fecha_cosecha_efectiva = %s, origen_clima = %s,
                    fecha_actualizacion = NOW() WHERE muestra_id = %s""",
                [*[features[name] for name in CLIMATE_COLUMNS],
                 (harvest_date - sample["fecha_medicion"]).days, harvest_date,
                 metadata["origen_clima"], sample["muestra_id"]],
            )
            if "pronóstico" in metadata["origen_clima"].lower(): refreshed_forecasts += 1

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT muestra_id FROM muestras_uva
            WHERE seguimiento_id = %s AND fecha_medicion = %s
        """, (seguimiento_id, harvest_date))
        same_day = cursor.fetchone()
    if same_day:
        _validate_chemistry(brix, ph, acidity)
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE muestras_uva SET tipo_muestra = 'cosecha', "Brix" = %s, "pH" = %s,
                    acidez_total_g_l = %s, dias_hasta_cosecha = 0,
                    fecha_cosecha_efectiva = %s, fecha_actualizacion = NOW()
                WHERE muestra_id = %s
            """, (brix, ph, acidity, harvest_date, same_day[0]))
        final_sample = {"muestra_id": same_day[0].split(":", 1)[-1], "origen_clima": "Clima actualizado"}
    else:
        final_sample = _store_sample(connection, tracking, harvest_date, brix, ph, acidity, "cosecha")
        if "pronóstico" in final_sample["origen_clima"].lower(): refreshed_forecasts += 1
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE seguimientos_uva SET estado = 'cosechado', fecha_cosecha_efectiva = %s,
                fecha_actualizacion = NOW() WHERE seguimiento_id = %s
        """, (harvest_date, seguimiento_id))
    connection.commit()
    return {
        "seguimiento_id": seguimiento_id, "codigo": tracking["codigo"],
        "muestras_actualizadas": len(previous) + (0 if same_day else 1),
        "muestra_final": final_sample["muestra_id"],
        "ventanas_con_pronostico": refreshed_forecasts,
    }
