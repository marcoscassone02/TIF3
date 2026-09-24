# GrapeSense

Esta carpeta contiene solamente el modelo, el código necesario para usarlo y los datos empleados para entrenarlo y evaluarlo.

## Contenido

- `backend/modelo_final.joblib`: modelo Gradient Boosting ya entrenado.
- `backend/modelo.py`: permite entrenar, evaluar y predecir.
- `backend/base_datos.py`: crea, consulta y actualiza PostgreSQL.
- `backend/clima.py`: obtiene y resume las ventanas climáticas.
- `backend/analisis_modelo.py`: calcula métricas e interpretación para el enólogo.
- `backend/api.py`: backend FastAPI y endpoints HTTP.
- `frontend/`: interfaz React + TypeScript construida con Vite.
- `iniciar.sh`: inicia backend e interfaz con un solo comando.
- `backend/requirements.txt`: dependencias de Python.
- `backend/datos/entrenamiento_2022_2023.csv`: 370 muestras de entrenamiento.
- `backend/datos/evaluacion_2024.csv`: 224 muestras de evaluación temporal.
- `backend/datos/evaluacion_2026_sintetica.csv`: 108 muestras sintéticas adicionales de evaluación.

Los datos de uva y las fechas de cosecha son sintéticos. El clima es histórico reconstruido. Estos resultados no constituyen validación con mediciones reales de la bodega.

## Preparación

Desde la raíz del proyecto:

```bash
python -m venv venv
source venv/bin/activate
pip install -r modelo_final/backend/requirements.txt
```

## Evaluar el modelo guardado

```bash
python -m modelo_final.backend.modelo evaluar modelo_final/backend/datos/evaluacion_2024.csv
python -m modelo_final.backend.modelo evaluar modelo_final/backend/datos/evaluacion_2026_sintetica.csv
```

## Realizar predicciones

El archivo de entrada debe contener las 19 columnas utilizadas por el modelo. Las columnas pueden consultarse con:

```bash
python -c "import joblib; print(joblib.load('modelo_final/backend/modelo_final.joblib')['columnas'])"
```

Después, ejecutar:

```bash
python -m modelo_final.backend.modelo predecir entrada.csv predicciones.csv
```

## Reentrenar

```bash
python -m modelo_final.backend.modelo entrenar
```

La evaluación debe realizarse con archivos que no se hayan incorporado al entrenamiento.

## Base de datos PostgreSQL

PostgreSQL utiliza dos tablas:

- `muestras_uva`: mediciones históricas y nuevas muestras. `muestra_id` evita duplicados y permite actualizar el resultado cuando se conozca la cosecha.
- `predicciones_uva`: historial de predicciones, fecha de cosecha estimada, entradas del modelo, versión y notas para consulta del enólogo.

En esta computadora la configuración predeterminada usa la base `tesis_uva`, el usuario de Linux actual y el socket local seguro. No requiere guardar una contraseña. En un servidor remoto se puede configurar una URL:

```bash
export DATABASE_URL="postgresql://usuario:contraseña@localhost:5432/tesis_uva"
```

También se admiten las variables `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT` utilizadas por la aplicación original.

Crear la tabla e importar las 594 muestras de 2022, 2023 y 2024:

```bash
python -m modelo_final.backend.base_datos inicializar
python -m modelo_final.backend.base_datos importar-historico
python -m modelo_final.backend.base_datos resumen
```

Agregar posteriormente otro CSV compatible, sin duplicar muestras existentes:

```bash
python -m modelo_final.backend.base_datos agregar nuevas_muestras.csv
```

`dias_hasta_cosecha` puede estar vacío al almacenar una muestra nueva y actualizarse cuando se conozca la cosecha efectiva. No guardes contraseñas dentro del código ni de los CSV.

Para predecir y almacenar el resultado en `predicciones_uva`:

```bash
python -m modelo_final.backend.modelo predecir entrada.csv predicciones.csv --guardar-db --notas "Control semanal"
```

Para una predicción operativa, el modo recomendado obtiene automáticamente el clima según la fecha y guarda todo junto:

```bash
python -m modelo_final.backend.modelo predecir-fecha \
  --fecha 2026-02-10 \
  --variedad Malbec \
  --vinedo Agrelo \
  --brix 19.2 \
  --ph 3.25 \
  --acidez 7.4 \
  --lote-id LOTE_01 \
  --muestra-id LOTE_01_20260210 \
  --notas "Control semanal"
```

La ventana pasada comprende los siete días anteriores a `fecha`, sin incluirla. La ventana futura comprende esa fecha y los seis días siguientes. En una fecha reciente se usa el pronóstico operativo; en una fecha antigua se usa ERA5 histórico reconstruido. La predicción, las 19 entradas, las ventanas y la URL climática quedan en `predicciones_uva`.

## Aplicación operativa

La aplicación utiliza React en el frontend y FastAPI en el backend. Para abrirla:

```bash
cd /home/marcospc/Escritorio/Tesis
./modelo_final/iniciar.sh
```

Después, abrir `http://127.0.0.1:8000`. El panel permite:

- registrar una muestra y consultar automáticamente el clima;
- calcular y almacenar la predicción en PostgreSQL;
- consultar el detalle químico y climático de cada predicción;
- buscar y exportar el historial de predicciones;
- consultar las 594 muestras históricas con filtros de vendimia, variedad, viñedo y etapa;
- exportar muestras filtradas a CSV;
- estudiar el error 2024 por anticipación, la importancia de variables y los límites del modelo.

La documentación técnica interactiva del backend está en `http://127.0.0.1:8000/docs`.

### Desarrollo del frontend

Solo es necesario al modificar la interfaz:

```bash
cd modelo_final/frontend
npm install
npm run build
```

La compilación queda en `frontend/dist` y FastAPI la sirve junto con la API, por lo que para el uso diario no es necesario ejecutar dos procesos.
