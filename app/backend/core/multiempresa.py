"""Esquema y operaciones multiempresa de GrapeSense."""
from pathlib import Path
import re
import unicodedata

from psycopg2.extras import RealDictCursor

from ..ml.modelo import MODEL_PATH

DEFAULT_SLUG = "grapesense-demo"
DEFAULT_SITES = {
    "Agrelo": (-33.129376523923625, -68.87193389708483),
    "Drummond": (-33.0239529805325, -68.85196107582618),
    "San Carlos": (-33.665945328401534, -69.17572663787573),
}

DDL = """
CREATE TABLE IF NOT EXISTS bodegas (
    bodega_id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id BIGSERIAL PRIMARY KEY,
    bodega_id BIGINT NOT NULL REFERENCES bodegas(bodega_id),
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('superadmin', 'admin', 'usuario')),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fincas (
    finca_id BIGSERIAL PRIMARY KEY,
    bodega_id BIGINT NOT NULL REFERENCES bodegas(bodega_id),
    nombre TEXT NOT NULL,
    latitud DOUBLE PRECISION NOT NULL CHECK (latitud BETWEEN -90 AND 90),
    longitud DOUBLE PRECISION NOT NULL CHECK (longitud BETWEEN -180 AND 180),
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (bodega_id, nombre)
);

ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_rol_check;
UPDATE usuarios SET rol = 'usuario' WHERE rol IN ('enologo', 'consulta');
ALTER TABLE usuarios ADD CONSTRAINT usuarios_rol_check
    CHECK (rol IN ('superadmin', 'admin', 'usuario'));

CREATE TABLE IF NOT EXISTS cuarteles (
    cuartel_id BIGSERIAL PRIMARY KEY,
    bodega_id BIGINT NOT NULL REFERENCES bodegas(bodega_id),
    finca_id BIGINT NOT NULL REFERENCES fincas(finca_id),
    nombre TEXT NOT NULL,
    variedad TEXT,
    hectareas DOUBLE PRECISION CHECK (hectareas IS NULL OR hectareas > 0),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (finca_id, nombre)
);

CREATE TABLE IF NOT EXISTS modelos_bodega (
    modelo_bodega_id BIGSERIAL PRIMARY KEY,
    bodega_id BIGINT NOT NULL REFERENCES bodegas(bodega_id),
    nombre TEXT NOT NULL,
    version TEXT NOT NULL,
    ruta_artefacto TEXT NOT NULL,
    vendimias_entrenamiento TEXT,
    metricas JSONB,
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_entrenamiento TIMESTAMPTZ,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (bodega_id, version)
);

CREATE TABLE IF NOT EXISTS seguimientos_uva (
    seguimiento_id BIGSERIAL PRIMARY KEY,
    bodega_id BIGINT NOT NULL REFERENCES bodegas(bodega_id),
    finca_id BIGINT NOT NULL REFERENCES fincas(finca_id),
    cuartel_id BIGINT REFERENCES cuarteles(cuartel_id),
    codigo TEXT NOT NULL,
    lote_referencia TEXT,
    variedad TEXT NOT NULL,
    vendimia SMALLINT NOT NULL CHECK (vendimia BETWEEN 2000 AND 2100),
    estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'cosechado')),
    fecha_inicio DATE NOT NULL,
    fecha_cosecha_efectiva DATE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (bodega_id, codigo)
);

ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS bodega_id BIGINT REFERENCES bodegas(bodega_id);
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS finca_id BIGINT REFERENCES fincas(finca_id);
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS cuartel_id BIGINT REFERENCES cuarteles(cuartel_id);
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS codigo_muestra TEXT;
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS fecha_cosecha_efectiva DATE;
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS origen_registro TEXT;
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS origen_clima TEXT;
ALTER TABLE muestras_uva ADD COLUMN IF NOT EXISTS seguimiento_id BIGINT REFERENCES seguimientos_uva(seguimiento_id);
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS bodega_id BIGINT REFERENCES bodegas(bodega_id);
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS finca_id BIGINT REFERENCES fincas(finca_id);
ALTER TABLE predicciones_uva ADD COLUMN IF NOT EXISTS cuartel_id BIGINT REFERENCES cuarteles(cuartel_id);
CREATE INDEX IF NOT EXISTS muestras_uva_bodega_fecha_idx ON muestras_uva (bodega_id, fecha_medicion DESC);
CREATE INDEX IF NOT EXISTS muestras_uva_bodega_codigo_idx ON muestras_uva (bodega_id, codigo_muestra);
CREATE INDEX IF NOT EXISTS muestras_uva_seguimiento_idx ON muestras_uva (seguimiento_id, fecha_medicion);
CREATE INDEX IF NOT EXISTS seguimientos_uva_bodega_estado_idx ON seguimientos_uva (bodega_id, estado, fecha_inicio DESC);
CREATE INDEX IF NOT EXISTS predicciones_uva_bodega_fecha_idx ON predicciones_uva (bodega_id, fecha_creacion DESC);
CREATE INDEX IF NOT EXISTS fincas_bodega_idx ON fincas (bodega_id);
CREATE INDEX IF NOT EXISTS cuarteles_bodega_idx ON cuarteles (bodega_id);
CREATE INDEX IF NOT EXISTS usuarios_bodega_idx ON usuarios (bodega_id);
"""


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "bodega"


def initialize_multitenancy(connection):
    with connection.cursor() as cursor:
        cursor.execute(DDL)
        cursor.execute("""
            INSERT INTO bodegas (nombre, slug) VALUES ('Bodega demostración', %s)
            ON CONFLICT (slug) DO UPDATE SET slug = EXCLUDED.slug
            RETURNING bodega_id
        """, (DEFAULT_SLUG,))
        default_id = cursor.fetchone()[0]
        cursor.execute("UPDATE muestras_uva SET bodega_id = %s WHERE bodega_id IS NULL", (default_id,))
        cursor.execute("UPDATE muestras_uva SET codigo_muestra = muestra_id WHERE codigo_muestra IS NULL")
        cursor.execute("UPDATE muestras_uva SET origen_registro = 'Migración histórica' WHERE origen_registro IS NULL")
        cursor.execute("UPDATE predicciones_uva SET bodega_id = %s WHERE bodega_id IS NULL", (default_id,))
        cursor.execute(f"ALTER TABLE muestras_uva ALTER COLUMN bodega_id SET DEFAULT {int(default_id)}")
        cursor.execute(f"ALTER TABLE predicciones_uva ALTER COLUMN bodega_id SET DEFAULT {int(default_id)}")
        cursor.execute("ALTER TABLE muestras_uva ALTER COLUMN bodega_id SET NOT NULL")
        cursor.execute("ALTER TABLE predicciones_uva ALTER COLUMN bodega_id SET NOT NULL")
        for name, (latitude, longitude) in DEFAULT_SITES.items():
            cursor.execute("""
                INSERT INTO fincas (bodega_id, nombre, latitud, longitud)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (bodega_id, nombre) DO UPDATE
                SET latitud = EXCLUDED.latitud, longitud = EXCLUDED.longitud
                RETURNING finca_id
            """, (default_id, name, latitude, longitude))
            finca_id = cursor.fetchone()[0]
            cursor.execute("""
                UPDATE muestras_uva SET finca_id = %s
                WHERE bodega_id = %s AND vinedo = %s AND finca_id IS NULL
            """, (finca_id, default_id, name))
            cursor.execute("""
                UPDATE predicciones_uva SET finca_id = %s
                WHERE bodega_id = %s AND vinedo = %s AND finca_id IS NULL
            """, (finca_id, default_id, name))
        cursor.execute("ALTER TABLE muestras_uva DROP CONSTRAINT IF EXISTS muestras_uva_lote_id_vendimia_fecha_medicion_key")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS muestras_uva_bodega_lote_vendimia_fecha_key
            ON muestras_uva (bodega_id, lote_id, vendimia, fecha_medicion)
        """)
        cursor.execute("""
            INSERT INTO modelos_bodega
                (bodega_id, nombre, version, ruta_artefacto, vendimias_entrenamiento, activo)
            VALUES (%s, 'Modelo base regional', 'GB_depth3_trees100', %s, '2022, 2023', TRUE)
            ON CONFLICT (bodega_id, version) DO UPDATE
            SET ruta_artefacto = EXCLUDED.ruta_artefacto,
                nombre = EXCLUDED.nombre
        """, (default_id, str(MODEL_PATH)))
        cursor.execute(
            "UPDATE modelos_bodega SET ruta_artefacto = %s WHERE version = 'GB_depth3_trees100'",
            (str(MODEL_PATH),),
        )
    connection.commit()
    return default_id


def bootstrap_required(connection):
    initialize_multitenancy(connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        return cursor.fetchone()[0] == 0


def get_tenant(connection, bodega_id):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT bodega_id, nombre, slug, activa, fecha_creacion FROM bodegas WHERE bodega_id = %s", (bodega_id,))
        return cursor.fetchone()


def list_farms(connection, bodega_id):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT finca_id, nombre, latitud, longitud, activa
            FROM fincas WHERE bodega_id = %s AND activa ORDER BY nombre
        """, (bodega_id,))
        return cursor.fetchall()


def list_blocks(connection, bodega_id):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT c.cuartel_id, c.finca_id, f.nombre AS finca, c.nombre,
                   c.variedad, c.hectareas, c.activo
            FROM cuarteles c JOIN fincas f ON f.finca_id = c.finca_id
            WHERE c.bodega_id = %s ORDER BY f.nombre, c.nombre
        """, (bodega_id,))
        return cursor.fetchall()


def unique_slug(connection, name):
    base = slugify(name)
    candidate = base
    number = 2
    with connection.cursor() as cursor:
        while True:
            cursor.execute("SELECT 1 FROM bodegas WHERE slug = %s", (candidate,))
            if cursor.fetchone() is None:
                return candidate
            candidate = f"{base}-{number}"
            number += 1
