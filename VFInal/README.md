# 🍇 GrapeSense - Sistema de Predicción de Cosecha

## Descripción
GrapeSense es una aplicación web desarrollada con Streamlit que permite predecir los días restantes para la cosecha de uvas basándose en parámetros vitivinícolas y datos climáticos.

## Características

### 🏠 Página de Inicio
- Dashboard con métricas principales
- Acceso rápido a las funcionalidades
- Vista de las últimas predicciones realizadas

### 🔮 Nueva Predicción
- Formulario completo para ingresar parámetros
- Predicción en tiempo real
- Almacenamiento automático en base de datos

### 📊 Historial de Predicciones
- Visualización de todas las predicciones realizadas
- Filtros por variedad y viñedo
- Estadísticas descriptivas

### 🌤️ Pronóstico del Clima
- Consulta de datos climáticos para los próximos 7 días
- Información de temperatura, precipitación, viento y presión
- Datos específicos por viñedo

## Instalación

1. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

2. **Configurar base de datos:**
   - Copia `env_example.txt` a `.env`
   - Completa con tus credenciales de PostgreSQL

3. **Ejecutar la aplicación:**
```bash
# Aplicación original
streamlit run app.py

# Nueva aplicación con múltiples páginas
streamlit run app_main.py
```

## Estructura de Archivos

- `app_main.py` - Nueva aplicación principal con navegación
- `app.py` - Aplicación original
- `base.py` - Funciones de base de datos
- `clima.py` - Funciones para obtener datos climáticos
- `predictor.py` - Modelo de predicción
- `modelo_entrenado.pkl` - Modelo entrenado

## Uso

1. **Realizar una predicción:**
   - Selecciona variedad y viñedo
   - Ingresa parámetros (Brix, pH, Acidez)
   - Define fecha de cosecha
   - Obtén la predicción de días restantes

2. **Consultar historial:**
   - Ve a "Historial de Predicciones"
   - Filtra por variedad o viñedo
   - Visualiza estadísticas

3. **Ver pronóstico del clima:**
   - Selecciona viñedo
   - Define días de pronóstico
   - Consulta datos climáticos

## Tecnologías Utilizadas

- **Streamlit** - Framework web
- **PostgreSQL** - Base de datos
- **Scikit-learn** - Modelo de machine learning
- **Pandas** - Manipulación de datos
- **Open-Meteo API** - Datos climáticos

## Viñedos Soportados

- **Agrelo** (Mendoza, Argentina)
- **Drummond** (Mendoza, Argentina)
- **San Carlos** (Mendoza, Argentina)

## Variedades Soportadas

- **Cabernet Sauvignon**
- **Syrah**
- **Malbec** 