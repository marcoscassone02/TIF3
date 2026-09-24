"""API HTTP del sistema de prediccion de cosecha."""
from datetime import date, datetime
from pathlib import Path
from typing import Literal
import math
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .analisis_modelo import model_analysis
from .base_datos import (
    connect, get_prediction, get_predictions, get_sample_summary, get_samples, initialize,
)
from .clima import SITES
from .modelo import MODEL_PATH, predict_date

ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"


class PredictionInput(BaseModel):
    fecha_medicion: date
    variedad: Literal["Malbec", "Syrah", "Cabernet"]
    vinedo: Literal["Agrelo", "Drummond", "San Carlos"]
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
            raise ValueError("La fecha de medicion no puede estar en el futuro")
        return value

    @field_validator("lote_id", "muestra_id", "notas")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


app = FastAPI(
    title="GrapeSense API",
    version="1.0.0",
    description="Predice dias hasta cosecha y registra quimica y clima en PostgreSQL.",
)

origins = os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def serialize(value):
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def records(frame):
    return [
        {key: serialize(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


@app.get("/api/health")
def health():
    try:
        with connect() as connection:
            initialize(connection)
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"PostgreSQL no responde: {error}") from error
    return {"status": "ok", "database": "connected", "model": MODEL_PATH.exists()}


@app.get("/api/options")
def options():
    return {
        "variedades": ["Malbec", "Syrah", "Cabernet"],
        "vinedos": list(SITES),
        "fecha_maxima": date.today().isoformat(),
    }


@app.post("/api/predictions", status_code=201)
def create_prediction(payload: PredictionInput):
    try:
        return predict_date(
            payload.fecha_medicion,
            payload.variedad,
            payload.vinedo,
            payload.brix,
            payload.ph,
            payload.acidez_total_g_l,
            payload.lote_id,
            payload.muestra_id or None,
            payload.notas,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar el clima o guardar la prediccion: {error}",
        ) from error


@app.get("/api/predictions")
def list_predictions(limit: int = Query(default=500, ge=1, le=1000)):
    try:
        return {"items": records(get_predictions(limit))}
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No se pudo consultar PostgreSQL: {error}") from error


@app.get("/api/predictions/{prediction_id}")
def prediction_detail(prediction_id: int):
    try:
        item = get_prediction(prediction_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No se pudo consultar PostgreSQL: {error}") from error
    if item is None:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")
    return {key: serialize(value) for key, value in item.items()}


@app.get("/api/samples")
def list_samples(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    vendimia: int | None = Query(default=None, ge=2000, le=2100),
    variedad: str | None = None,
    vinedo: str | None = None,
    tipo_muestra: str | None = None,
    search: str | None = None,
):
    try:
        frame, total = get_samples(
            limit=limit, offset=offset, vendimia=vendimia, variedad=variedad,
            vinedo=vinedo, tipo_muestra=tipo_muestra, search=search,
        )
        return {"items": records(frame), "total": total, "limit": limit, "offset": offset}
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No se pudieron consultar las muestras: {error}") from error


@app.get("/api/samples/summary")
def sample_summary():
    try:
        return get_sample_summary()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No se pudo resumir la base de muestras: {error}") from error


@app.get("/api/model/analysis")
def analysis():
    try:
        return model_analysis()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo analizar el modelo: {error}") from error


@app.get("/api/summary")
def summary():
    query = """
        SELECT COUNT(*)::integer,
               COUNT(DISTINCT lote_id)::integer,
               AVG(dias_predichos),
               MAX(fecha_creacion)
        FROM predicciones_uva
    """
    try:
        with connect() as connection:
            initialize(connection)
            with connection.cursor() as cursor:
                cursor.execute(query)
                total, lots, average, last = cursor.fetchone()
        return {
            "total_predicciones": total,
            "lotes_evaluados": lots,
            "promedio_dias": round(float(average), 1) if average is not None else None,
            "ultima_prediccion": serialize(last),
        }
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"No se pudo consultar PostgreSQL: {error}") from error


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
