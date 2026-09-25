"""API multiempresa de GrapeSense."""
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal
import math
import os

import pandas as pd
import psycopg2
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, EmailStr, Field, field_validator

from .ml.analisis_modelo import model_analysis
from .core.auth import (
    CurrentUser, authenticate, create_token, get_current_user, password_hash, require_roles,
)
from .core.base_datos import (
    connect, get_prediction, get_predictions, get_sample_summary, get_samples, initialize,
)
from .ml.modelo import MODEL_PATH, predict_date
from .services.importacion_muestras import import_samples
from .services.gestion_muestras import delete_sample, update_sample
from .ml.entrenamiento_bodega import activate_model, readiness, train_winery_model
from .services.seguimientos import (
    add_measurement, close_followup, create_followup, delete_followup,
    list_followups, update_followup,
)
from .core.multiempresa import (
    DEFAULT_SLUG, bootstrap_required, get_tenant, initialize_multitenancy,
    list_blocks, list_farms, unique_slug,
)

ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
AdminUser = Annotated[CurrentUser, Depends(require_roles("superadmin", "admin"))]
PlatformAdmin = Annotated[CurrentUser, Depends(require_roles("superadmin"))]
PredictionUser = Annotated[CurrentUser, Depends(require_roles("superadmin", "admin", "usuario"))]


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class BootstrapInput(BaseModel):
    bodega_nombre: str = Field(min_length=2, max_length=120)
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class PredictionInput(BaseModel):
    fecha_medicion: date
    variedad: Literal["Malbec", "Syrah", "Cabernet"]
    finca_id: int
    cuartel_id: int | None = None
    brix: float = Field(ge=10, le=30)
    ph: float = Field(ge=2.5, le=4.5)
    acidez_total_g_l: float = Field(ge=2, le=15)
    lote_id: str = Field(min_length=1, max_length=80)
    muestra_id: str | None = Field(default=None, max_length=100)
    notas: str = Field(default="", max_length=1000)

    @field_validator("fecha_medicion")
    @classmethod
    def date_cannot_be_future(cls, value):
        if value > date.today():
            raise ValueError("La fecha de medición no puede estar en el futuro")
        return value

    @field_validator("lote_id", "muestra_id", "notas")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class SampleImportInput(BaseModel):
    finca_id: int
    cuartel_id: int | None = None
    csv_text: str = Field(min_length=1, max_length=2_000_000)
    sobrescribir: bool = False


class SampleEditInput(BaseModel):
    fecha_medicion: date
    brix: float = Field(ge=10, le=35)
    ph: float = Field(ge=2.5, le=4.5)
    acidez_total_g_l: float = Field(ge=2, le=20)


class FollowupInput(BaseModel):
    finca_id: int
    cuartel_id: int | None = None
    variedad: str = Field(min_length=1, max_length=80)
    vendimia: int = Field(ge=2000, le=2100)
    fecha_inicio: date
    lote_referencia: str | None = Field(default=None, max_length=120)


class MeasurementInput(BaseModel):
    fecha_medicion: date
    brix: float = Field(ge=10, le=35)
    ph: float = Field(ge=2.5, le=4.5)
    acidez_total_g_l: float = Field(ge=2, le=20)


class CloseFollowupInput(BaseModel):
    fecha_cosecha: date
    brix: float = Field(ge=10, le=35)
    ph: float = Field(ge=2.5, le=4.5)
    acidez_total_g_l: float = Field(ge=2, le=20)


class FarmInput(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)


class UserEditInput(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    rol: Literal["admin", "usuario"]
    password: str | None = Field(default=None, min_length=10, max_length=128)


class BlockInput(BaseModel):
    finca_id: int
    nombre: str = Field(min_length=1, max_length=120)
    variedad: str | None = Field(default=None, max_length=80)
    hectareas: float | None = Field(default=None, gt=0)


class UserInput(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    rol: Literal["admin", "usuario"]


class WineryInput(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    admin_nombre: str = Field(min_length=2, max_length=120)
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=128)


app = FastAPI(
    title="GrapeSense API",
    version="2.0.0",
    description="Plataforma multiempresa para seguimiento y predicción de cosecha.",
)
origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def prepare(connection):
    initialize(connection)
    return initialize_multitenancy(connection)


def serialize(value):
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def records(frame):
    return [{key: serialize(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def token_response(user):
    return {"access_token": create_token(user), "token_type": "bearer", "user": user}


@app.get("/api/health")
def health():
    try:
        with connect() as connection:
            prepare(connection)
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"PostgreSQL no responde: {error}") from error
    return {"status": "ok", "database": "connected", "model": MODEL_PATH.exists()}


@app.get("/api/auth/status")
def auth_status():
    with connect() as connection:
        prepare(connection)
        required = bootstrap_required(connection)
    return {"bootstrap_required": required}


@app.post("/api/auth/bootstrap", status_code=201)
def bootstrap(payload: BootstrapInput):
    with connect() as connection:
        default_id = prepare(connection)
        if not bootstrap_required(connection):
            raise HTTPException(status_code=409, detail="La plataforma ya fue configurada")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE bodegas SET nombre = %s WHERE bodega_id = %s",
                (payload.bodega_nombre.strip(), default_id),
            )
            cursor.execute("""
                INSERT INTO usuarios (bodega_id, nombre, email, password_hash, rol)
                VALUES (%s, %s, LOWER(%s), %s, 'superadmin') RETURNING usuario_id
            """, (default_id, payload.nombre.strip(), str(payload.email), password_hash.hash(payload.password)))
            user_id = cursor.fetchone()[0]
        connection.commit()
    user = {
        "usuario_id": user_id, "bodega_id": default_id, "nombre": payload.nombre.strip(),
        "email": str(payload.email).lower(), "rol": "superadmin",
        "bodega_nombre": payload.bodega_nombre.strip(),
    }
    return token_response(user)


@app.post("/api/auth/login")
def login(payload: LoginInput):
    user = authenticate(str(payload.email), payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    return token_response(user)


@app.get("/api/auth/me")
def me(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return user


@app.get("/api/options")
def options(user: Annotated[CurrentUser, Depends(get_current_user)]):
    with connect() as connection:
        prepare(connection)
        farms = list_farms(connection, user.bodega_id)
        blocks = list_blocks(connection, user.bodega_id)
    return {
        "variedades": ["Malbec", "Syrah", "Cabernet"],
        "fincas": farms,
        "cuarteles": blocks,
        "fecha_maxima": date.today().isoformat(),
    }


@app.post("/api/predictions", status_code=201)
def create_prediction(payload: PredictionInput, user: PredictionUser):
    with connect() as connection:
        prepare(connection)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT finca_id, nombre, latitud, longitud FROM fincas
                WHERE finca_id = %s AND bodega_id = %s AND activa
            """, (payload.finca_id, user.bodega_id))
            farm = cursor.fetchone()
            if farm is None:
                raise HTTPException(status_code=404, detail="Finca no encontrada")
            if payload.cuartel_id is not None:
                cursor.execute("""
                    SELECT 1 FROM cuarteles WHERE cuartel_id = %s AND finca_id = %s
                    AND bodega_id = %s AND activo
                """, (payload.cuartel_id, payload.finca_id, user.bodega_id))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail="Cuartel no encontrado")
    try:
        return predict_date(
            payload.fecha_medicion, payload.variedad, farm["nombre"], payload.brix,
            payload.ph, payload.acidez_total_g_l, payload.lote_id,
            payload.muestra_id or None, payload.notas, user.bodega_id,
            payload.finca_id, payload.cuartel_id, farm["latitud"], farm["longitud"],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible consultar el clima o guardar la predicción: {error}") from error


@app.get("/api/predictions")
def list_predictions(user: Annotated[CurrentUser, Depends(get_current_user)], limit: int = Query(default=500, ge=1, le=1000)):
    return {"items": records(get_predictions(user.bodega_id, limit))}


@app.get("/api/predictions/{prediction_id}")
def prediction_detail(prediction_id: int, user: Annotated[CurrentUser, Depends(get_current_user)]):
    item = get_prediction(user.bodega_id, prediction_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")
    return {key: serialize(value) for key, value in item.items()}


@app.get("/api/samples")
def list_samples(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0),
    vendimia: int | None = Query(default=None, ge=2000, le=2100), variedad: str | None = None,
    vinedo: str | None = None, tipo_muestra: str | None = None, search: str | None = None,
):
    frame, total = get_samples(
        user.bodega_id, limit=limit, offset=offset, vendimia=vendimia,
        variedad=variedad, vinedo=vinedo, tipo_muestra=tipo_muestra, search=search,
    )
    return {"items": records(frame), "total": total, "limit": limit, "offset": offset}


@app.get("/api/followups")
def followups(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    estado: Literal["pendiente", "cosechado"] | None = None,
):
    with connect() as connection:
        prepare(connection)
        items = list_followups(connection, user.bodega_id, estado)
    return {"items": [{key: serialize(value) for key, value in item.items()} for item in items]}


@app.post("/api/followups", status_code=201)
def start_followup(payload: FollowupInput, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            item = create_followup(
                connection, bodega_id=user.bodega_id, finca_id=payload.finca_id,
                cuartel_id=payload.cuartel_id, variety=payload.variedad,
                vintage=payload.vendimia, start_date=payload.fecha_inicio,
                lot_reference=(payload.lote_referencia or "").strip() or None,
            )
        return {key: serialize(value) for key, value in item.items()}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/followups/{followup_id}")
def edit_followup(followup_id: int, payload: FollowupInput, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            item = update_followup(
                connection, bodega_id=user.bodega_id, seguimiento_id=followup_id,
                finca_id=payload.finca_id, cuartel_id=payload.cuartel_id,
                variety=payload.variedad, vintage=payload.vendimia,
                start_date=payload.fecha_inicio,
                lot_reference=(payload.lote_referencia or "").strip() or None,
            )
        return {key: serialize(value) for key, value in item.items()}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="La modificación produciría un lote o una muestra duplicada") from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible actualizar el seguimiento: {error}") from error


@app.delete("/api/followups/{followup_id}")
def remove_followup(followup_id: int, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            return delete_followup(
                connection, bodega_id=user.bodega_id, seguimiento_id=followup_id,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible eliminar el seguimiento: {error}") from error


@app.post("/api/followups/{followup_id}/samples", status_code=201)
def add_followup_sample(followup_id: int, payload: MeasurementInput, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            return add_measurement(
                connection, bodega_id=user.bodega_id, seguimiento_id=followup_id,
                measurement_date=payload.fecha_medicion, brix=payload.brix,
                ph=payload.ph, acidity=payload.acidez_total_g_l,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe una medición de este seguimiento en esa fecha") from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible consultar el clima o guardar la muestra: {error}") from error


@app.post("/api/followups/{followup_id}/close")
def finish_followup(followup_id: int, payload: CloseFollowupInput, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            return close_followup(
                connection, bodega_id=user.bodega_id, seguimiento_id=followup_id,
                harvest_date=payload.fecha_cosecha, brix=payload.brix,
                ph=payload.ph, acidity=payload.acidez_total_g_l,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible cerrar el seguimiento: {error}") from error


@app.post("/api/samples/import", status_code=201)
def upload_samples(payload: SampleImportInput, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            return import_samples(
                connection, bodega_id=user.bodega_id, finca_id=payload.finca_id,
                cuartel_id=payload.cuartel_id, csv_text=payload.csv_text,
                overwrite=payload.sobrescribir,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible completar la importación o consultar el clima: {error}") from error


@app.patch("/api/samples/{sample_id}")
def edit_sample(sample_id: str, payload: SampleEditInput, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            return update_sample(
                connection, bodega_id=user.bodega_id, sample_id=sample_id,
                measurement_date=payload.fecha_medicion, brix=payload.brix,
                ph=payload.ph, acidity=payload.acidez_total_g_l,
            )
    except ValueError as error:
        raise HTTPException(status_code=404 if "no existe" in str(error) else 422, detail=str(error)) from error
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe otra muestra de ese lote en la fecha indicada") from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible editar la muestra: {error}") from error


@app.delete("/api/samples/{sample_id}")
def remove_sample(sample_id: str, user: PredictionUser):
    try:
        with connect() as connection:
            prepare(connection)
            return delete_sample(connection, bodega_id=user.bodega_id, sample_id=sample_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No fue posible eliminar la muestra: {error}") from error


@app.get("/api/samples/export")
def export_samples(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    vendimia: int | None = Query(default=None, ge=2000, le=2100), variedad: str | None = None,
    vinedo: str | None = None, tipo_muestra: str | None = None, search: str | None = None,
):
    frame, total = get_samples(
        user.bodega_id, limit=10_000, offset=0, vendimia=vendimia,
        variedad=variedad, vinedo=vinedo, tipo_muestra=tipo_muestra, search=search,
    )
    if total > 10_000:
        raise HTTPException(status_code=422, detail="La exportación supera 10.000 filas; aplica filtros antes de continuar")
    return {"items": records(frame), "total": total}


@app.get("/api/samples/summary")
def sample_summary(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return get_sample_summary(user.bodega_id)


@app.get("/api/model/analysis")
def analysis(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return model_analysis(user.bodega_id)


@app.get("/api/summary")
def summary(user: Annotated[CurrentUser, Depends(get_current_user)]):
    query = """
        SELECT COUNT(*)::integer, COUNT(DISTINCT lote_id)::integer,
               AVG(dias_predichos), MAX(fecha_creacion)
        FROM predicciones_uva WHERE bodega_id = %s
    """
    with connect() as connection:
        prepare(connection)
        with connection.cursor() as cursor:
            cursor.execute(query, (user.bodega_id,))
            total, lots, average, last = cursor.fetchone()
    return {
        "total_predicciones": total, "lotes_evaluados": lots,
        "promedio_dias": round(float(average), 1) if average is not None else None,
        "ultima_prediccion": serialize(last),
    }


@app.get("/api/admin/organization")
def organization(user: AdminUser):
    with connect() as connection:
        prepare(connection)
        tenant = get_tenant(connection, user.bodega_id)
        farms = list_farms(connection, user.bodega_id)
        blocks = list_blocks(connection, user.bodega_id)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT usuario_id, nombre, email, rol, activo, fecha_creacion
                FROM usuarios WHERE bodega_id = %s ORDER BY nombre
            """, (user.bodega_id,))
            users = cursor.fetchall()
            cursor.execute("""
                SELECT modelo_bodega_id, nombre, version, vendimias_entrenamiento,
                       metricas, activo, fecha_entrenamiento
                FROM modelos_bodega WHERE bodega_id = %s ORDER BY fecha_creacion DESC
            """, (user.bodega_id,))
            models = cursor.fetchall()
    return {"bodega": tenant, "fincas": farms, "cuarteles": blocks, "usuarios": users, "modelos": models}


@app.get("/api/admin/models/readiness")
def model_readiness(user: AdminUser):
    with connect() as connection:
        prepare(connection)
        return readiness(connection, user.bodega_id)


@app.post("/api/admin/models/train", status_code=201)
def train_model(user: PlatformAdmin):
    try:
        with connect() as connection:
            prepare(connection)
            return train_winery_model(connection, user.bodega_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/admin/models/{model_id}/activate")
def activate_winery_model(model_id: int, user: PlatformAdmin):
    try:
        with connect() as connection:
            prepare(connection)
            return activate_model(connection, user.bodega_id, model_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/admin/farms", status_code=201)
def create_farm(payload: FarmInput, user: AdminUser):
    try:
        with connect() as connection:
            prepare(connection)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO fincas (bodega_id, nombre, latitud, longitud)
                    VALUES (%s, %s, %s, %s)
                    RETURNING finca_id, nombre, latitud, longitud, activa
                """, (user.bodega_id, payload.nombre.strip(), payload.latitud, payload.longitud))
                row = cursor.fetchone()
            connection.commit()
        return row
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe una finca con ese nombre") from error


@app.patch("/api/admin/farms/{farm_id}")
def edit_farm(farm_id: int, payload: FarmInput, user: AdminUser):
    try:
        with connect() as connection:
            prepare(connection)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    UPDATE fincas SET nombre = %s, latitud = %s, longitud = %s
                    WHERE finca_id = %s AND bodega_id = %s AND activa
                    RETURNING finca_id, nombre, latitud, longitud, activa
                """, (payload.nombre.strip(), payload.latitud, payload.longitud,
                      farm_id, user.bodega_id))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="Finca no encontrada")
                cursor.execute(
                    "UPDATE muestras_uva SET vinedo = %s WHERE finca_id = %s AND bodega_id = %s",
                    (payload.nombre.strip(), farm_id, user.bodega_id),
                )
                cursor.execute(
                    "UPDATE predicciones_uva SET vinedo = %s WHERE finca_id = %s AND bodega_id = %s",
                    (payload.nombre.strip(), farm_id, user.bodega_id),
                )
            connection.commit()
        return row
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe una finca con ese nombre") from error


@app.delete("/api/admin/farms/{farm_id}")
def remove_farm(farm_id: int, user: AdminUser):
    with connect() as connection:
        prepare(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT nombre FROM fincas WHERE finca_id = %s AND bodega_id = %s AND activa",
                (farm_id, user.bodega_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Finca no encontrada")
            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM muestras_uva WHERE finca_id = %s) +
                    (SELECT COUNT(*) FROM predicciones_uva WHERE finca_id = %s) +
                    (SELECT COUNT(*) FROM seguimientos_uva WHERE finca_id = %s) +
                    (SELECT COUNT(*) FROM cuarteles WHERE finca_id = %s)
            """, (farm_id, farm_id, farm_id, farm_id))
            related = cursor.fetchone()[0]
            if related:
                # Se oculta de la operacion cotidiana, pero se conserva la referencia
                # para no romper la trazabilidad de muestras y predicciones historicas.
                cursor.execute(
                    "UPDATE fincas SET activa = FALSE WHERE finca_id = %s AND bodega_id = %s",
                    (farm_id, user.bodega_id),
                )
                cursor.execute(
                    "UPDATE cuarteles SET activo = FALSE WHERE finca_id = %s AND bodega_id = %s",
                    (farm_id, user.bodega_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM fincas WHERE finca_id = %s AND bodega_id = %s",
                    (farm_id, user.bodega_id),
                )
        connection.commit()
    return {"eliminada": row[0], "historial_conservado": bool(related)}


@app.post("/api/admin/blocks", status_code=201)
def create_block(payload: BlockInput, user: AdminUser):
    try:
        with connect() as connection:
            prepare(connection)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT 1 FROM fincas WHERE finca_id = %s AND bodega_id = %s", (payload.finca_id, user.bodega_id))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail="Finca no encontrada")
                cursor.execute("""
                    INSERT INTO cuarteles (bodega_id, finca_id, nombre, variedad, hectareas)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING cuartel_id, finca_id, nombre, variedad, hectareas, activo
                """, (user.bodega_id, payload.finca_id, payload.nombre.strip(), payload.variedad, payload.hectareas))
                row = cursor.fetchone()
            connection.commit()
        return row
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe ese cuartel en la finca") from error


@app.post("/api/admin/users", status_code=201)
def create_user(payload: UserInput, user: AdminUser):
    try:
        with connect() as connection:
            prepare(connection)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (bodega_id, nombre, email, password_hash, rol)
                    VALUES (%s, %s, LOWER(%s), %s, %s)
                    RETURNING usuario_id, nombre, email, rol, activo, fecha_creacion
                """, (user.bodega_id, payload.nombre.strip(), str(payload.email), password_hash.hash(payload.password), payload.rol))
                row = cursor.fetchone()
            connection.commit()
        return row
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo") from error


@app.patch("/api/admin/users/{user_id}")
def edit_user(user_id: int, payload: UserEditInput, user: AdminUser):
    try:
        with connect() as connection:
            prepare(connection)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT usuario_id, rol FROM usuarios
                    WHERE usuario_id = %s AND bodega_id = %s AND activo
                    FOR UPDATE
                """, (user_id, user.bodega_id))
                target = cursor.fetchone()
                if target is None:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")
                if target["rol"] == "superadmin" and user.rol != "superadmin":
                    raise HTTPException(status_code=403, detail="No podés modificar al administrador de plataforma")
                new_role = "superadmin" if target["rol"] == "superadmin" else payload.rol
                if payload.password:
                    cursor.execute("""
                        UPDATE usuarios SET nombre = %s, email = LOWER(%s), rol = %s,
                            password_hash = %s
                        WHERE usuario_id = %s
                        RETURNING usuario_id, nombre, email, rol, activo, fecha_creacion
                    """, (payload.nombre.strip(), str(payload.email), new_role,
                          password_hash.hash(payload.password), user_id))
                else:
                    cursor.execute("""
                        UPDATE usuarios SET nombre = %s, email = LOWER(%s), rol = %s
                        WHERE usuario_id = %s
                        RETURNING usuario_id, nombre, email, rol, activo, fecha_creacion
                    """, (payload.nombre.strip(), str(payload.email), new_role, user_id))
                result = cursor.fetchone()
            connection.commit()
        return result
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo") from error


@app.delete("/api/admin/users/{user_id}")
def remove_user(user_id: int, user: AdminUser):
    if user_id == user.usuario_id:
        raise HTTPException(status_code=409, detail="No podés eliminar tu propia cuenta mientras la estás usando")
    with connect() as connection:
        prepare(connection)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT nombre, rol FROM usuarios
                WHERE usuario_id = %s AND bodega_id = %s AND activo
                FOR UPDATE
            """, (user_id, user.bodega_id))
            target = cursor.fetchone()
            if target is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            if target[1] == "superadmin":
                raise HTTPException(status_code=409, detail="La cuenta del administrador de plataforma no puede eliminarse")
            cursor.execute("DELETE FROM usuarios WHERE usuario_id = %s", (user_id,))
        connection.commit()
    return {"eliminado": target[0]}


@app.get("/api/admin/wineries")
def list_wineries(user: Annotated[CurrentUser, Depends(require_roles("superadmin"))]):
    with connect() as connection:
        prepare(connection)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT b.bodega_id, b.nombre, b.slug, b.activa,
                       COUNT(DISTINCT u.usuario_id)::integer AS usuarios,
                       COUNT(DISTINCT f.finca_id)::integer AS fincas
                FROM bodegas b LEFT JOIN usuarios u ON u.bodega_id = b.bodega_id
                LEFT JOIN fincas f ON f.bodega_id = b.bodega_id
                GROUP BY b.bodega_id ORDER BY b.nombre
            """)
            return {"items": cursor.fetchall()}


@app.post("/api/admin/wineries", status_code=201)
def create_winery(payload: WineryInput, user: Annotated[CurrentUser, Depends(require_roles("superadmin"))]):
    try:
        with connect() as connection:
            prepare(connection)
            slug = unique_slug(connection, payload.nombre)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("INSERT INTO bodegas (nombre, slug) VALUES (%s, %s) RETURNING bodega_id, nombre, slug, activa", (payload.nombre.strip(), slug))
                winery = cursor.fetchone()
                cursor.execute("""
                    INSERT INTO usuarios (bodega_id, nombre, email, password_hash, rol)
                    VALUES (%s, %s, LOWER(%s), %s, 'admin')
                """, (winery["bodega_id"], payload.admin_nombre.strip(), str(payload.admin_email), password_hash.hash(payload.admin_password)))
                cursor.execute("""
                    INSERT INTO modelos_bodega (bodega_id, nombre, version, ruta_artefacto, activo)
                    VALUES (%s, 'Modelo base regional', 'GB_depth3_trees100', %s, TRUE)
                """, (winery["bodega_id"], str(MODEL_PATH)))
            connection.commit()
        return winery
    except psycopg2.IntegrityError as error:
        raise HTTPException(status_code=409, detail="El correo del administrador ya está registrado") from error


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        requested = FRONTEND_DIST / full_path
        if full_path and requested.is_file() and FRONTEND_DIST in requested.resolve().parents:
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
