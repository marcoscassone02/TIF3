# base.py
import os
import psycopg2
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# ----------------------
# Crear tabla cosechas
# ----------------------
def crear_tabla_si_no_existe():
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cosecha_clima (
            id SERIAL PRIMARY KEY,
            variedad VARCHAR(50),
            viñedo VARCHAR(50),
            fecha_cosecha DATE,
            brix REAL,
            ph REAL,
            acidez REAL,
            tavg_7d REAL,
            tmin_7d REAL,
            tmax_7d REAL,
            prcp_7d REAL,
            wspd_7d REAL,
            pres_7d REAL
        );
    """)
    conexion.commit()
    cursor.close()
    conexion.close()

# ----------------------
# Insertar cosechas
# ----------------------
def insertar_prediccion(variedad, viñedo, fecha_cosecha, brix, ph, acidez,
                        tavg_7d, tmin_7d, tmax_7d, prcp_7d, wspd_7d, pres_7d):
    crear_tabla_si_no_existe()

    def to_float(val):
        return float(val) if val is not None else None

    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO cosecha_clima (
            variedad, viñedo, fecha_cosecha, brix, ph, acidez,
            tavg_7d, tmin_7d, tmax_7d, prcp_7d, wspd_7d, pres_7d
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        variedad, viñedo, fecha_cosecha, to_float(brix), to_float(ph), to_float(acidez),
        to_float(tavg_7d), to_float(tmin_7d), to_float(tmax_7d), to_float(prcp_7d),
        to_float(wspd_7d), to_float(pres_7d)
    ))
    conexion.commit()
    cursor.close()
    conexion.close()

# ----------------------
# Crear tabla predicciones
# ----------------------
def crear_tabla_predicciones_si_no_existe():
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    
    # Crear tabla si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predicciones_modelo (
            id SERIAL PRIMARY KEY,
            variedad VARCHAR(50),
            viñedo VARCHAR(50),
            fecha_cosecha DATE,
            brix REAL,
            ph REAL,
            acidez REAL,
            tavg_7d REAL,
            tmin_7d REAL,
            tmax_7d REAL,
            prcp_7d REAL,
            wspd_7d REAL,
            pres_7d REAL,
            dias_restantes INTEGER,
            fecha_objetivo DATE,
            notas TEXT,
            lote INTEGER,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Verificar si la columna fecha_creacion existe, si no, agregarla
    try:
        cursor.execute("""
            ALTER TABLE predicciones_modelo 
            ADD COLUMN fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
    except psycopg2.errors.DuplicateColumn:
        pass
    
    conexion.commit()
    cursor.close()
    conexion.close()

# ----------------------
# Insertar prediccion modelo
# ----------------------
def insertar_prediccion_modelo(variedad, viñedo, fecha_cosecha, brix, ph, acidez,
                               tavg_7d, tmin_7d, tmax_7d, prcp_7d, wspd_7d, pres_7d,
                               dias_restantes, notas=""):
    crear_tabla_predicciones_si_no_existe()

    def to_float(val):
        return float(val) if val is not None else None

    fecha_objetivo = fecha_cosecha + timedelta(days=int(dias_restantes))

    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO predicciones_modelo (
            variedad, viñedo, fecha_cosecha, brix, ph, acidez,
            tavg_7d, tmin_7d, tmax_7d, prcp_7d, wspd_7d, pres_7d,
            dias_restantes, fecha_objetivo, notas
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        variedad, viñedo, fecha_cosecha, to_float(brix), to_float(ph), to_float(acidez),
        to_float(tavg_7d), to_float(tmin_7d), to_float(tmax_7d), to_float(prcp_7d),
        to_float(wspd_7d), to_float(pres_7d), dias_restantes, fecha_objetivo, notas
    ))
    conexion.commit()
    cursor.close()
    conexion.close()

def obtener_ultimas_predicciones(limite=10):
    """Obtiene las últimas predicciones del modelo"""
    crear_tabla_predicciones_si_no_existe()
    
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    
    # Verificar si la columna fecha_creacion existe
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'predicciones_modelo' 
        AND column_name = 'fecha_creacion';
    """)
    
    tiene_fecha_creacion = cursor.fetchone() is not None
    
    if tiene_fecha_creacion:
        cursor.execute("""
            SELECT id, variedad, viñedo, fecha_cosecha, brix, ph, acidez,
                   dias_restantes, fecha_objetivo, notas, lote, 
                   fecha_creacion
            FROM predicciones_modelo 
            ORDER BY id DESC 
            LIMIT %s
        """, (limite,))
    else:
        cursor.execute("""
            SELECT id, variedad, viñedo, fecha_cosecha, brix, ph, acidez,
                   dias_restantes, fecha_objetivo, notas, lote
            FROM predicciones_modelo 
            ORDER BY id DESC 
            LIMIT %s
        """, (limite,))
    
    columnas = [desc[0] for desc in cursor.description]
    resultados = cursor.fetchall()
    
    cursor.close()
    conexion.close()
    
    # Agregar fecha_creacion como None si no existe
    predicciones = []
    for fila in resultados:
        pred_dict = dict(zip(columnas, fila))
        if 'fecha_creacion' not in pred_dict:
            pred_dict['fecha_creacion'] = None
        predicciones.append(pred_dict)
    
    return predicciones

def obtener_todas_predicciones():
    """Obtiene todas las predicciones del modelo"""
    crear_tabla_predicciones_si_no_existe()
    
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    
    # Verificar si la columna fecha_creacion existe
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'predicciones_modelo' 
        AND column_name = 'fecha_creacion';
    """)
    
    tiene_fecha_creacion = cursor.fetchone() is not None
    
    if tiene_fecha_creacion:
        cursor.execute("""
            SELECT id, variedad, viñedo, fecha_cosecha, brix, ph, acidez,
                   dias_restantes, fecha_objetivo, notas, lote, 
                   fecha_creacion
            FROM predicciones_modelo 
            ORDER BY id DESC
        """)
    else:
        cursor.execute("""
            SELECT id, variedad, viñedo, fecha_cosecha, brix, ph, acidez,
                   dias_restantes, fecha_objetivo, notas, lote
            FROM predicciones_modelo 
            ORDER BY id DESC
        """)
    
    columnas = [desc[0] for desc in cursor.description]
    resultados = cursor.fetchall()
    
    cursor.close()
    conexion.close()
    
    # Agregar fecha_creacion como None si no existe
    predicciones = []
    for fila in resultados:
        pred_dict = dict(zip(columnas, fila))
        if 'fecha_creacion' not in pred_dict:
            pred_dict['fecha_creacion'] = None
        predicciones.append(pred_dict)
    
    return predicciones

def actualizar_notas_prediccion(id_prediccion, nuevas_notas):
    """Actualiza las notas de una predicción específica"""
    crear_tabla_predicciones_si_no_existe()
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    try:
        cursor.execute("""
            UPDATE predicciones_modelo 
            SET notas = %s 
            WHERE id = %s
        """, (nuevas_notas, id_prediccion))
        conexion.commit()
        ok = cursor.rowcount > 0
    except Exception as e:
        conexion.rollback()
        ok = False
    finally:
        cursor.close()
        conexion.close()
    return ok

def actualizar_lote_prediccion(id_prediccion, nuevo_lote):
    """Actualiza el lote de una predicción específica"""
    crear_tabla_predicciones_si_no_existe()
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cursor = conexion.cursor()
    try:
        # Validar que el lote sea un entero o None
        if nuevo_lote is not None and nuevo_lote != '':
            try:
                nuevo_lote = int(nuevo_lote)
            except Exception:
                nuevo_lote = None
        else:
            nuevo_lote = None
        cursor.execute("""
            UPDATE predicciones_modelo 
            SET lote = %s 
            WHERE id = %s
        """, (nuevo_lote, id_prediccion))
        conexion.commit()
        ok = cursor.rowcount > 0
    except Exception as e:
        conexion.rollback()
        ok = False
    finally:
        cursor.close()
        conexion.close()
    return ok