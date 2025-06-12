
import psycopg2
from datetime import datetime


def insertar_prediccion(variedad, viñedo, dia_desde_1501, brix, ph, acidez, fecha_cosecha):

    conexion = psycopg2.connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"]
    )
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO evolucion_uva ("Variedad", "Viñedo", "Día desde 15/01", "Brix", "pH", "Ac Total", "Fecha_Cosecha")
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (variedad, viñedo, dia_desde_1501, brix, ph, acidez, fecha_cosecha))

    conexion.commit()
    cursor.close()
    conexion.close()



