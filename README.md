# GrapeSense

Plataforma multiempresa de apoyo a la decisión de cosecha. GrapeSense reúne mediciones de uva, contexto climático, seguimientos de lotes y modelos predictivos específicos por bodega en una única aplicación web.

> **Alcance científico.** Las muestras actualmente incluidas son sintéticas y el clima histórico proviene de datos reconstruidos. El sistema sirve para desarrollar y estudiar la metodología, pero todavía debe validarse con vendimias reales antes de utilizar una predicción como decisión enológica autónoma.

## Funciones principales

- registra Brix, pH y acidez total expresada como g/L de ácido tartárico;
- consulta automáticamente los siete días climáticos anteriores y la ventana futura de siete días;
- almacena muestras, seguimientos y predicciones en PostgreSQL;
- mantiene los datos aislados por bodega, finca y usuario;
- permite completar un seguimiento cuando se conoce la cosecha efectiva;
- entrena y evalúa un modelo independiente para cada bodega desde su propia base de datos;
- conserva modelos candidatos sin reemplazar automáticamente el modelo activo;
- muestra métricas, error por anticipación e importancia de variables para el análisis enológico.

## Tecnologías

- **Frontend:** React, TypeScript, Vite, Recharts y Lucide.
- **Backend:** FastAPI, Python y Uvicorn.
- **Modelo:** scikit-learn, pandas, NumPy y joblib.
- **Datos:** PostgreSQL.
- **Clima:** Open-Meteo; histórico reconstruido para fechas pasadas y pronóstico para fechas futuras disponibles.

## Estructura del proyecto

```text
Tesis/
├── modelo_final/
│   ├── backend/
│   │   ├── api.py                 # rutas HTTP y validación de solicitudes
│   │   ├── core/                  # autenticación, PostgreSQL y multiempresa
│   │   ├── ml/                    # entrenamiento, inferencia y análisis
│   │   ├── services/              # clima, muestras, importaciones y seguimientos
│   │   ├── datos/                 # CSV de referencia del modelo base
│   │   └── modelos/
│   │       ├── base/              # modelo inicial versionado
│   │       └── bodega_<id>/       # modelos creados por la aplicación
│   ├── frontend/
│   │   ├── src/components/        # componentes visuales compartidos
│   │   ├── src/lib/               # utilidades del frontend
│   │   ├── src/api.ts             # cliente HTTP
│   │   ├── src/types.ts           # contratos TypeScript
│   │   └── src/App.tsx            # pantallas y flujo principal
│   └── iniciar.sh                 # inicio local de toda la aplicación
├── documentacion/                 # material de tesis
├── clima/                         # trabajo climático previo; no es el código operativo
└── requirements.txt               # dependencias Python
```

Los modelos de cada bodega se generan durante el uso y no se suben a Git. El modelo de `modelos/base/` funciona como respaldo inicial.

## Puesta en marcha local

### 1. Preparar PostgreSQL

La configuración local predeterminada usa la base `tesis_uva`, el usuario actual de Linux y el socket local `/var/run/postgresql`.

También se puede definir una conexión explícita:

```bash
export DATABASE_URL="postgresql://usuario:contraseña@localhost:5432/tesis_uva"
```

Como alternativa se admiten `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`.

### 2. Instalar dependencias

Desde la raíz del proyecto:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd modelo_final/frontend
npm install
npm run build
cd ../..
```

### 3. Inicializar la base

```bash
python -m modelo_final.backend.core.base_datos inicializar
```

Las migraciones necesarias también se ejecutan de forma segura al iniciar la API.

### 4. Iniciar GrapeSense

```bash
./modelo_final/iniciar.sh
```

Abrir [http://127.0.0.1:8000](http://127.0.0.1:8000). La documentación interactiva de la API está disponible en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

La primera ejecución muestra un asistente para crear la primera bodega y el administrador de plataforma. El secreto que firma las sesiones se genera localmente y está excluido de Git.

## Flujo de uso

### Vendimia en curso

1. Crear o seleccionar la finca, cuya ubicación determina el clima consultado.
2. Abrir un seguimiento desde **Base de muestras**.
3. Agregar cada control de Brix, pH y acidez. GrapeSense genera los identificadores correlativos.
4. Mientras no exista cosecha, `dias_hasta_cosecha` queda pendiente.
5. Al cosechar, registrar la fecha y química final. La aplicación completa el objetivo de todas las mediciones del lote.

Las muestras y seguimientos pueden editarse o eliminarse según el rol. Si se elimina la cosecha final, el seguimiento vuelve a estado pendiente para no conservar objetivos incorrectos.

### Predicción

La predicción operativa combina:

- el estado actual de la uva: Brix, pH y acidez;
- la identidad varietal y la zona representada por la finca/viñedo;
- el clima de los siete días anteriores;
- el clima de la ventana siguiente disponible como pronóstico.

La química representa el estado actual de la uva; el clima representa la velocidad esperada de evolución. Una importancia climática menor no implica que el clima no afecte la maduración: parte de su efecto ya está reflejado en la química observada.

Cada resultado queda guardado en `predicciones_uva` junto con las entradas, ventanas climáticas, origen del clima y versión del modelo.

### Importación de datos

La pantalla **Base de muestras → Cargar nuevas muestras** acepta un CSV de hasta 250 filas por operación. La plantilla incluye identificadores, fecha, variedad, química y el objetivo cuando ya se conoce. El entrenamiento no depende de separar manualmente CSV de entrenamiento y evaluación: usa PostgreSQL directamente.

## Entrenamiento por bodega

El entrenamiento se ejecuta desde **Administración → Modelos de la bodega**. Sólo utiliza muestras de la bodega activa que:

- tengan `dias_hasta_cosecha` completo;
- pertenezcan a un lote con muestra final de cosecha en cero días;
- contengan las 19 variables requeridas sin valores vacíos.

La política automática evita que mediciones del mismo lote y vendimia aparezcan a ambos lados de la evaluación:

- con una sola vendimia, reserva aproximadamente el 25 % de los lotes;
- con varias vendimias, evalúa sobre la vendimia más reciente completa;
- si esa vendimia tiene menos de 150 mediciones, agrega un tercio de los lotes de la vendimia anterior;
- exige al menos 30 mediciones de entrenamiento y 12 de evaluación.

El resultado se registra como **candidato**. No afecta las predicciones hasta que el administrador de plataforma lo revise y lo active. El artefacto guarda métricas, vendimias, identificadores de ambos conjuntos y una copia de la evaluación para reproducir el análisis.

## Modelo y variables

El modelo actual es un `GradientBoostingRegressor`. Predice `dias_hasta_cosecha` mediante 19 entradas:

- variedad y viñedo;
- Brix, pH y acidez total;
- temperatura media, mínima y máxima;
- precipitación acumulada;
- velocidad del viento;
- radiación acumulada;
- días de calor;
- las siete variables climáticas anteriores tanto para la ventana pasada como para la futura histórica/pronosticada.

Para reproducir el análisis del modelo base:

```bash
python -m modelo_final.backend.ml.modelo evaluar modelo_final/backend/datos/evaluacion_2024.csv
python -m modelo_final.backend.ml.modelo evaluar modelo_final/backend/datos/evaluacion_2026_sintetica.csv
```

El comando `entrenar` del módulo conserva únicamente la reproducción histórica del modelo base. El flujo multiempresa recomendado es el de la interfaz y PostgreSQL.

## Entidades principales de PostgreSQL

- `bodegas`: organizaciones aisladas dentro de la plataforma;
- `usuarios`: acceso y rol de cada persona;
- `fincas`: ubicación geográfica para obtener clima;
- `muestras_uva`: mediciones históricas y operativas;
- `seguimientos_uva`: evolución de un lote hasta su cosecha;
- `predicciones_uva`: historial completo de inferencias;
- `modelos_bodega`: modelos base, candidatos y activos de cada organización.

## Roles

- **Usuario de bodega:** trabaja con muestras, seguimientos, predicciones y análisis.
- **Administrador de bodega:** además administra usuarios y fincas de su organización.
- **Administrador de plataforma:** incorpora bodegas, cambia de organización y controla el ciclo de modelos.

## Desarrollo

Después de cambiar el frontend:

```bash
cd modelo_final/frontend
npm run build
```

FastAPI sirve la compilación de `frontend/dist`, por lo que el uso normal requiere un solo proceso. Para comprobar el backend y el frontend:

```bash
python -m py_compile modelo_final/backend/api.py modelo_final/backend/core/*.py modelo_final/backend/ml/*.py modelo_final/backend/services/*.py
cd modelo_final/frontend && npm run build
```

`render.yaml` pertenece a la configuración de despliegue del proyecto inicial y no representa todavía la arquitectura actual de GrapeSense. Debe adaptarse antes de publicar esta versión.

## Criterio de validación

Las métricas deben interpretarse siempre junto con:

- cantidad de lotes independientes evaluados;
- vendimias incluidas;
- error por anticipación;
- porcentaje dentro de ±3 y ±4 días;
- sesgo, para distinguir adelantos de atrasos;
- procedencia real o sintética de las muestras.

La validación comercial debe realizarse con cosechas reales de cada bodega y con seguimiento del error durante nuevas vendimias. GrapeSense es una herramienta de apoyo: la decisión final continúa en manos del enólogo.
