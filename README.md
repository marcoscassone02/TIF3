# 🍇 Predicción de Fecha Óptima de Cosecha de Uvas

Proyecto de tesis orientado a la **predicción de la fecha óptima de cosecha de uvas** mediante **Machine Learning**, integrando variables **químicas** y **climáticas** para apoyar la toma de decisiones en viñedos de Mendoza.

## 📌 Descripción
El sistema utiliza un modelo de **Random Forest** entrenado con datos históricos de cosecha, incorporando:
- Variables químicas de la uva (Brix, pH, acidez total)
- Variables climáticas obtenidas desde la API de **Open-Meteo**
- Promedios móviles de clima en ventanas de 7 días

La aplicación permite realizar predicciones, almacenar resultados y visualizar el historial de cosechas a través de una interfaz web.

## 🧠 Modelo
- Algoritmo: **Random Forest Regressor**
- Optimización: **GridSearchCV**
- Métricas: MAE ≈ 2 días, R² > 0.95
- Variables climáticas: temperatura, precipitación, viento y presión

## 🖥️ Arquitectura
- **Frontend**: Streamlit  
- **Backend**: Python (predicción y persistencia de datos)  
- **Base de datos**: almacenamiento de observaciones y resultados  
- **API externa**: Open-Meteo para datos climáticos

## 🚀 Funcionalidades
- Carga manual de datos de la uva y del viñedo
- Obtención automática de datos climáticos
- Predicción de fecha de cosecha
- Guardado de resultados en base de datos
- Visualización de historial y estadísticas

## 🔮 Trabajo futuro
- Incorporación de **visión por computadora** (imágenes de racimos)
- Uso de datos fenológicos adicionales
- Despliegue en entorno productivo

## 👤 Autor
**Marcos Cassone**  
Ingeniería en Informática – Universidad de Mendoza
