# GrapeSense

GrapeSense es una plataforma web multiempresa para el seguimiento de la maduración de la uva y la estimación de días hasta cosecha. Integra mediciones químicas, información climática, modelos de aprendizaje automático y trazabilidad de lotes en una única aplicación orientada al trabajo del enólogo.

## Estado del proyecto

La aplicación se encuentra desplegada en **Render** mediante una imagen Docker y utiliza los siguientes recursos de producción:

- un servicio web que ejecuta React y FastAPI;
- una base PostgreSQL administrada por Render;
- un disco persistente para conservar los modelos entrenados de cada bodega;
- conexión con Open-Meteo para obtener clima histórico y pronósticos.

La dirección pública se administra desde el panel de Render y no se incluye en el repositorio. El estado del servicio puede comprobarse mediante el endpoint `/api/health`.

> **Alcance científico.** GrapeSense es una herramienta de apoyo a la decisión. Sus resultados deben interpretarse junto con el criterio del enólogo, la inspección del viñedo y otros indicadores de madurez. La validación comercial requiere incorporar y evaluar seguimientos reales de cada bodega durante nuevas vendimias.

## Funciones principales

- administración independiente de múltiples bodegas;
- usuarios con permisos de plataforma, administración de bodega y operación;
- registro de Brix, pH y acidez total en g/L de ácido tartárico;
- seguimiento de lotes desde la primera medición hasta la cosecha efectiva;
- consulta automática del clima según la finca y la fecha de medición;
- importación de muestras históricas mediante CSV;
- almacenamiento de muestras y predicciones en PostgreSQL;
- entrenamiento y evaluación de modelos específicos para cada bodega;
- administración de modelos candidatos y modelos activos;
- análisis de métricas, anticipación e importancia de variables;
- historial trazable de las predicciones realizadas.

## Arquitectura de producción

```text
Usuarios
   │ HTTPS
   ▼
Render · Servicio web Docker
   ├── React + TypeScript      Interfaz web
   ├── FastAPI                 API, autenticación y servicios
   └── scikit-learn            Entrenamiento e inferencia
          │
          ├── PostgreSQL administrado
          │      Usuarios, bodegas, muestras, seguimientos,
          │      predicciones, métricas y estados de entrenamiento
          │
          ├── Disco persistente /var/data/models
          │      Modelos entrenados por bodega
          │
          └── Open-Meteo
                 Clima histórico y pronóstico semanal
```

React se compila como una aplicación estática y FastAPI sirve tanto la interfaz como los endpoints. De esta forma, GrapeSense funciona mediante un único servicio web. PostgreSQL y el almacenamiento de modelos permanecen separados de la imagen Docker, por lo que una actualización del código no elimina los datos ni los modelos entrenados.

## Tecnologías

- **Frontend:** React, TypeScript, Vite, Recharts, Lucide y CSS.
- **Backend:** FastAPI, Python, Pydantic y Uvicorn.
- **Aprendizaje automático:** scikit-learn, pandas, NumPy y Joblib.
- **Persistencia:** PostgreSQL y psycopg2.
- **Seguridad:** JWT y autorización basada en roles.
- **Clima:** Open-Meteo.
- **Despliegue:** Docker y Render.

## Estructura del repositorio

```text
Tesis/
├── app/
│   ├── backend/
│   │   ├── api.py                 # endpoints de la aplicación
│   │   ├── core/                  # PostgreSQL, autenticación y multiempresa
│   │   ├── ml/                    # entrenamiento, inferencia y análisis
│   │   ├── services/              # clima, muestras, importación y seguimientos
│   │   ├── datos/                 # datos de referencia del modelo base
│   │   └── modelos/
│   │       ├── base/              # modelo inicial incluido en la imagen
│   │       └── bodega_<id>/       # modelos generados por bodega
│   ├── frontend/
│   │   ├── src/components/        # componentes reutilizables
│   │   ├── src/lib/               # utilidades
│   │   ├── src/api.ts             # comunicación con FastAPI
│   │   ├── src/types.ts           # contratos TypeScript
│   │   └── src/App.tsx            # pantallas y flujo principal
│   └── iniciar.sh                 # inicio opcional para desarrollo local
├── scripts/
│   ├── verificar_proyecto.sh      # verificación integral
│   └── respaldo_postgresql.sh     # respaldo privado de PostgreSQL
├── Dockerfile                     # imagen de producción
├── render.yaml                    # recursos y variables de Render
├── requirements.txt               # dependencias Python
└── DEPLOY_RENDER.md               # guía de despliegue y operación
```

Los modelos particulares de las bodegas, los respaldos, los secretos y los archivos `.env` no se almacenan en Git.

## Flujo de trabajo

### 1. Incorporación de una bodega

El administrador de plataforma crea la organización y su primer administrador. Cada bodega mantiene aislados sus usuarios, fincas, muestras, predicciones y modelos.

### 2. Registro de fincas

Cada finca se registra con latitud y longitud. Estas coordenadas permiten consultar las condiciones climáticas correspondientes a cada medición.

### 3. Seguimiento de la vendimia

1. Se crea un seguimiento para una finca, variedad y vendimia.
2. Se incorporan controles de Brix, pH y acidez.
3. Mientras la uva no haya sido cosechada, `dias_hasta_cosecha` permanece pendiente.
4. Al registrar la cosecha final, GrapeSense completa automáticamente `fecha_cosecha_efectiva` y `dias_hasta_cosecha` en todas las mediciones anteriores del seguimiento.

Las muestras y los seguimientos pueden editarse o eliminarse según el rol. Si se elimina la muestra final, el seguimiento vuelve a quedar pendiente.

### 4. Importación de muestras históricas

La sección **Base de muestras → Cargar nuevas muestras** permite cargar un CSV de hasta 250 filas por operación. El archivo debe contener, como mínimo:

```text
muestra_id,lote_id,fecha_medicion,tipo_muestra,numero_muestra,variedad,Brix,pH,acidez_total_g_l
```

También puede incluir `vendimia`, `fecha_cosecha_efectiva` y `dias_hasta_cosecha`.

Durante la importación, GrapeSense:

- valida columnas, fechas, rangos y duplicados;
- consulta automáticamente el clima de cada fecha;
- guarda los registros en `muestras_uva`;
- detecta la fila con `tipo_muestra=cosecha`;
- propaga la fecha de cosecha y calcula los días restantes del lote completo.

PostgreSQL es la fuente única de entrenamiento: el modelo nunca se entrena directamente sobre el archivo CSV.

### 5. Predicción

La predicción combina:

- Brix, pH y acidez total de la medición actual;
- variedad y finca;
- clima de los siete días anteriores;
- pronóstico disponible para los siete días siguientes.

Cada resultado se almacena en `predicciones_uva` junto con la fecha estimada, las entradas utilizadas, el origen del clima y la versión del modelo.

La química representa el estado actual de la uva; el clima representa la velocidad esperada de evolución. Una importancia climática menor no significa que el clima no afecte la maduración: parte de ese efecto ya puede encontrarse reflejado en Brix, pH y acidez.

## Entrenamiento por bodega

El entrenamiento utiliza exclusivamente los datos de `muestras_uva` correspondientes a la bodega seleccionada. Sólo incorpora lotes que tengan una muestra final de cosecha, el objetivo completo y todas las variables requeridas.

La política automática evita compartir un mismo lote entre entrenamiento y evaluación:

- con una sola vendimia, reserva aproximadamente el 25 % de los lotes;
- con varias vendimias, evalúa principalmente sobre la vendimia más reciente;
- si la vendimia más reciente tiene menos de 150 mediciones, incorpora un tercio de los lotes de la anterior;
- exige al menos 30 mediciones para entrenamiento y 12 para evaluación.

Desde **Administración → Modelos de la bodega**, el administrador de plataforma puede iniciar un entrenamiento sin bloquear el uso de la aplicación. El trabajo muestra los estados:

```text
Pendiente → Entrenando → Candidato generado
                         └── Error, si no pudo completarse
```

El resultado queda registrado como candidato junto con sus métricas. No interviene en las predicciones hasta que sea revisado y activado. Los modelos anteriores se conservan para mantener trazabilidad y permitir una reversión.

### Entrenamiento desde el editor

El mismo proceso puede ejecutarse fuera de la interfaz, siempre utilizando PostgreSQL:

```bash
# Consultar bodegas
python -m app.backend.ml.entrenamiento_bodega bodegas

# Comprobar si una bodega posee datos suficientes
python -m app.backend.ml.entrenamiento_bodega estado --bodega 1

# Entrenar un candidato
python -m app.backend.ml.entrenamiento_bodega entrenar-db \
  --bodega 1 --nombre "Modelo vendimia actualizada"

# Consultar modelos registrados
python -m app.backend.ml.entrenamiento_bodega listar --bodega 1

# Activar un candidato después de revisar sus métricas
python -m app.backend.ml.entrenamiento_bodega activar --bodega 1 --modelo 3
```

## Modelo predictivo

El algoritmo utilizado es `GradientBoostingRegressor` y el objetivo es `dias_hasta_cosecha`. Trabaja con 19 variables:

- variedad y viñedo;
- Brix, pH y acidez total;
- temperatura media, mínima y máxima;
- precipitación acumulada;
- velocidad del viento;
- radiación acumulada;
- cantidad de días de calor;
- las variables climáticas equivalentes para la ventana pasada y la ventana futura histórica o pronosticada.

El análisis disponible en la plataforma presenta:

- MAE, RMSE, R² y sesgo;
- porcentaje de predicciones dentro de ±3 y ±4 días;
- rendimiento según la anticipación;
- comparación entre días reales y estimados;
- importancia individual y agrupada de las variables.

## Persistencia

Las entidades principales son:

- `bodegas`: organizaciones de la plataforma;
- `usuarios`: cuentas y roles;
- `fincas`: ubicaciones geográficas;
- `muestras_uva`: mediciones históricas y actuales;
- `seguimientos_uva`: evolución de cada lote;
- `predicciones_uva`: inferencias realizadas;
- `modelos_bodega`: versiones candidatas y activas;
- `entrenamientos_modelo`: estado de los entrenamientos iniciados desde la aplicación.

Los datos se conservan en PostgreSQL administrado. Los archivos Joblib generados por cada bodega se guardan en `/var/data/models`, dentro del disco persistente asociado al servicio de Render.

## Roles

- **Usuario de bodega:** consulta la base, realiza predicciones y administra seguimientos y muestras.
- **Administrador de bodega:** además gestiona las fincas y los usuarios de su organización.
- **Administrador de plataforma:** administra todas las bodegas y controla el entrenamiento, evaluación y activación de modelos.

## Despliegue y actualizaciones

La infraestructura está declarada en [`render.yaml`](render.yaml):

- servicio web Docker `grapesense`;
- PostgreSQL administrado `grapesense-db`;
- disco persistente `grapesense-models`;
- variables seguras `DATABASE_URL`, `GRAPESENSE_SECRET_KEY` y `MODEL_STORAGE_DIR`.

Render construye el frontend, instala el backend e inicia Uvicorn a partir del [`Dockerfile`](Dockerfile). Los cambios publicados en la rama conectada generan una nueva imagen y un nuevo despliegue, conservando la base y el disco de modelos.

La guía de operación, migración y respaldo está disponible en [`DEPLOY_RENDER.md`](DEPLOY_RENDER.md).

## Desarrollo local opcional

El entorno local se mantiene únicamente para desarrollo, pruebas y mantenimiento. No es el entorno de uso de las bodegas.

### Requisitos

- Python 3.10 o superior;
- Node.js 20 o superior;
- PostgreSQL;
- Git.

### Preparación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd app/frontend
npm install
npm run build
cd ../..
```

Configurar `DATABASE_URL` o las variables `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`. La plantilla [`.env.example`](.env.example) contiene un ejemplo sin secretos reales.

Inicializar PostgreSQL y ejecutar la plataforma:

```bash
python -m app.backend.core.base_datos inicializar
./app/iniciar.sh
```

La instancia de desarrollo queda disponible en `http://127.0.0.1:8000`. Esta dirección no corresponde a la aplicación desplegada para las bodegas.

## Verificación

Antes de publicar cambios:

```bash
./scripts/verificar_proyecto.sh
```

La verificación comprueba:

- sintaxis del backend;
- carga y evaluación del modelo base;
- tipos y compilación del frontend;
- formato del diff de Git.

El repositorio también incluye una verificación automática mediante GitHub Actions.

## Seguridad y operación

- Los secretos se configuran como variables privadas de Render.
- Las contraseñas se almacenan con hash.
- Los endpoints aplican autenticación JWT y control por roles.
- Cada consulta queda limitada a la bodega del usuario autenticado.
- Los modelos nuevos no se activan automáticamente.
- Los respaldos de PostgreSQL se mantienen fuera de Git.
- La decisión final de cosecha permanece bajo responsabilidad profesional del enólogo.
