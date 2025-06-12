
import psycopg2
from datetime import datetime


def insertar_prediccion(variedad, viñedo, dia_desde_1501, brix, ph, acidez, fecha_cosecha):

    conexion = psycopg2.connect(
        dbname="uva_db",
        user="admin",
        password="admin",
        host="localhost",
        port="5432"
    )
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO evolucion_uva ("Variedad", "Viñedo", "Día desde 15/01", "Brix", "pH", "Ac Total", "Fecha_Cosecha")
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (variedad, viñedo, dia_desde_1501, brix, ph, acidez, fecha_cosecha))

    conexion.commit()
    cursor.close()
    conexion.close()



