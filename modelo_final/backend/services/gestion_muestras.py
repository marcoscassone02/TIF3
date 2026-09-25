"""Edición y eliminación segura de muestras almacenadas."""
from datetime import date

from psycopg2.extras import RealDictCursor

from .clima import obtain_climate
from .importacion_muestras import CLIMATE_COLUMNS


def _sample_for_update(connection, bodega_id, sample_id):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT m.*, f.nombre AS finca_nombre, f.latitud, f.longitud,
                   s.codigo AS seguimiento_codigo, s.estado AS seguimiento_estado,
                   s.fecha_inicio, s.fecha_cosecha_efectiva AS seguimiento_cosecha
            FROM muestras_uva m
            LEFT JOIN fincas f ON f.finca_id = m.finca_id
            LEFT JOIN seguimientos_uva s ON s.seguimiento_id = m.seguimiento_id
            WHERE (m.muestra_id = %s OR m.codigo_muestra = %s) AND m.bodega_id = %s
            FOR UPDATE OF m
        """, (sample_id, sample_id, bodega_id))
        sample = cursor.fetchone()
    if sample is None:
        raise ValueError("La muestra no existe o pertenece a otra bodega")
    return sample


def update_sample(connection, *, bodega_id, sample_id, measurement_date, brix, ph, acidity):
    if measurement_date > date.today():
        raise ValueError("La fecha de medición no puede estar en el futuro")
    if not 10 <= brix <= 35 or not 2.5 <= ph <= 4.5 or not 2 <= acidity <= 20:
        raise ValueError("Brix, pH o acidez están fuera de los rangos admitidos")
    sample = _sample_for_update(connection, bodega_id, sample_id)
    tracking_id = sample["seguimiento_id"]
    is_final = bool(
        tracking_id and sample["seguimiento_estado"] == "cosechado"
        and (
            sample["tipo_muestra"] == "cosecha"
            or sample["fecha_medicion"] == sample["seguimiento_cosecha"]
        )
    )
    if tracking_id and measurement_date < sample["fecha_inicio"]:
        raise ValueError("La medición no puede ser anterior al inicio del seguimiento")
    if tracking_id and sample["seguimiento_cosecha"] and not is_final and measurement_date > sample["seguimiento_cosecha"]:
        raise ValueError("La medición no puede quedar después de la cosecha efectiva")
    if is_final:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT MAX(fecha_medicion) FROM muestras_uva
                WHERE seguimiento_id = %s AND muestra_id <> %s
            """, (tracking_id, sample["muestra_id"]))
            previous_date = cursor.fetchone()[0]
        if previous_date and measurement_date < previous_date:
            raise ValueError("La cosecha no puede quedar antes de las otras mediciones del seguimiento")

    date_changed = measurement_date != sample["fecha_medicion"]
    features = None
    climate_origin = sample["origen_clima"]
    if date_changed:
        if sample["finca_id"] is None or sample["latitud"] is None:
            raise ValueError("La muestra no tiene una finca con coordenadas para recalcular el clima")
        features, metadata = obtain_climate(
            measurement_date, sample["finca_nombre"], sample["latitud"], sample["longitud"],
        )
        climate_origin = metadata["origen_clima"]

    stored_id = sample["muestra_id"]
    new_internal_id = stored_id
    new_visible_id = sample["codigo_muestra"] or sample_id
    if tracking_id and date_changed:
        new_visible_id = (
            f"{sample['seguimiento_codigo']}_{sample['vendimia']}_"
            f"{measurement_date.strftime('%Y%m%d')}"
        )
        new_internal_id = f"{bodega_id}:{new_visible_id}"

    assignments = [
        "muestra_id = %s", "codigo_muestra = %s", "fecha_medicion = %s",
        '"Brix" = %s', '"pH" = %s', "acidez_total_g_l = %s",
        "origen_clima = %s", "fecha_actualizacion = NOW()",
    ]
    values = [new_internal_id, new_visible_id, measurement_date, brix, ph, acidity, climate_origin]
    if features is not None:
        assignments.extend(f"{column} = %s" for column in CLIMATE_COLUMNS)
        values.extend(features[column] for column in CLIMATE_COLUMNS)
    values.extend([stored_id, bodega_id])
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE muestras_uva SET {', '.join(assignments)} WHERE muestra_id = %s AND bodega_id = %s",
            values,
        )
        if tracking_id:
            effective_harvest = measurement_date if is_final else sample["seguimiento_cosecha"]
            if is_final:
                cursor.execute("""
                    UPDATE seguimientos_uva SET fecha_cosecha_efectiva = %s,
                        fecha_actualizacion = NOW() WHERE seguimiento_id = %s
                """, (effective_harvest, tracking_id))
            if effective_harvest:
                cursor.execute("""
                    UPDATE muestras_uva
                    SET dias_hasta_cosecha = %s - fecha_medicion,
                        fecha_cosecha_efectiva = %s, fecha_actualizacion = NOW()
                    WHERE seguimiento_id = %s
                """, (effective_harvest, effective_harvest, tracking_id))
            cursor.execute("""
                UPDATE seguimientos_uva SET fecha_actualizacion = NOW()
                WHERE seguimiento_id = %s
            """, (tracking_id,))
    connection.commit()
    return {
        "muestra_id": new_visible_id,
        "fecha_medicion": measurement_date,
        "clima_recalculado": date_changed,
    }


def delete_sample(connection, *, bodega_id, sample_id):
    sample = _sample_for_update(connection, bodega_id, sample_id)
    tracking_id = sample["seguimiento_id"]
    reactivated = bool(
        tracking_id and sample["seguimiento_estado"] == "cosechado"
        and (
            sample["tipo_muestra"] == "cosecha"
            or sample["fecha_medicion"] == sample["seguimiento_cosecha"]
        )
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM muestras_uva WHERE muestra_id = %s AND bodega_id = %s",
            (sample["muestra_id"], bodega_id),
        )
        if reactivated:
            cursor.execute("""
                UPDATE seguimientos_uva SET estado = 'pendiente', fecha_cosecha_efectiva = NULL,
                    fecha_actualizacion = NOW() WHERE seguimiento_id = %s
            """, (tracking_id,))
            cursor.execute("""
                UPDATE muestras_uva SET dias_hasta_cosecha = NULL,
                    fecha_cosecha_efectiva = NULL, fecha_actualizacion = NOW()
                WHERE seguimiento_id = %s
            """, (tracking_id,))
        elif tracking_id:
            cursor.execute("""
                UPDATE seguimientos_uva SET fecha_actualizacion = NOW()
                WHERE seguimiento_id = %s
            """, (tracking_id,))
    connection.commit()
    return {
        "eliminada": sample["codigo_muestra"] or sample_id,
        "seguimiento_reabierto": reactivated,
    }
