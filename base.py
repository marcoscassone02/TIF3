import sqlite3

def crear_base_datos():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS predicciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            variedad TEXT,
            viniedo TEXT,
            brix REAL,
            ph REAL,
            acidez REAL,
            dias_restantes INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insertar_prediccion(fecha, variedad, viniedo, brix, ph, acidez, dias_restantes):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO predicciones (fecha, variedad, viniedo, brix, ph, acidez, dias_restantes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, variedad, viniedo, brix, ph, acidez, dias_restantes))
    conn.commit()
    conn.close()
