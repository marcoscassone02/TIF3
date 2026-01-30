import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd
from predictor import predecir
from clima import obtener_promedios_clima_pasado, obtener_promedios_clima_futuro
from base import insertar_prediccion, insertar_prediccion_modelo, obtener_ultimas_predicciones, obtener_todas_predicciones, actualizar_notas_prediccion, actualizar_lote_prediccion

# Configuración de la página
st.set_page_config(
    page_title="GrapeSense - Predicción de Cosecha",
    page_icon="🍇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #2E8B57, #228B22);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2E8B57;
        margin: 0.5rem 0;
    }
    .prediction-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .weather-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Navegación
st.sidebar.title("🍇 GrapeSense")

# Sidebar de navegación
sidebar_options = ["🏠 Inicio", "🔮 Nueva Predicción", "📊 Historial de Predicciones", "🌤️ Pronóstico del Clima"]
if 'page' not in st.session_state:
    st.session_state['page'] = sidebar_options[0]
page = st.sidebar.selectbox(
    "Navegación",
    sidebar_options,
    index=sidebar_options.index(st.session_state['page'])
)
# Si el usuario cambia el selectbox, actualiza session_state['page']
if page != st.session_state['page']:
    st.session_state['page'] = page
    st.rerun()

# Página de Inicio
if st.session_state['page'] == "🏠 Inicio":
    st.markdown('<div class="main-header"><h1>🍇 GrapeSense</h1><h3>Sistema de Predicción de Cosecha de Uvas</h3></div>', unsafe_allow_html=True)
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        ultimas_pred = obtener_ultimas_predicciones(1)
        if ultimas_pred:
            ultima_pred = ultimas_pred[0]
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>Última Predicción</h4>
                    <h3>{ultima_pred['dias_restantes']} días</h3>
                    <p>{ultima_pred['variedad']} - {ultima_pred['viñedo']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            with col1:
                st.markdown("""
                <div class="metric-card">
                    <h4>Última Predicción</h4>
                    <h3>Sin datos</h3>
                    <p>Realiza tu primera predicción</p>
                </div>
                """, unsafe_allow_html=True)
    except:
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h4>Última Predicción</h4>
                <h3>Error DB</h3>
                <p>Verifica conexión</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h4>Variedades</h4>
            <h3>3</h3>
            <p>Cabernet, Syrah, Malbec</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h4>Viñedos</h4>
            <h3>3</h3>
            <p>Agrelo, Drummond, San Carlos</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <h4>Margen de Error</h4>
            <h3>±3 días</h3>
            <p>Rango de precisión</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Secciones principales
    st.markdown("## 🚀 Acciones Rápidas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔮 Realizar Nueva Predicción", use_container_width=True):
            st.session_state['page'] = "🔮 Nueva Predicción"
            st.rerun()
    
    with col2:
        if st.button("🌤️ Ver Pronóstico del Clima", use_container_width=True):
            st.session_state['page'] = "🌤️ Pronóstico del Clima"
            st.rerun()
    
    # Últimas predicciones
    st.markdown("## 📊 Últimas Predicciones")
    try:
        ultimas_pred = obtener_ultimas_predicciones(5)
        if ultimas_pred:
            for pred in ultimas_pred:
                st.markdown(f"""
                <div class="prediction-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4>{pred['variedad']} - {pred['viñedo']}</h4>
                            <p><strong>Días restantes:</strong> {pred['dias_restantes']} | 
                               <strong>Fecha objetivo:</strong> {pred['fecha_objetivo']}</p>
                            <p><strong>Brix:</strong> {pred['brix']} | 
                               <strong>pH:</strong> {pred['ph']} | 
                               <strong>Acidez:</strong> {pred['acidez']}</p>
                        </div>
                                                 <div style="text-align: right;">
                             <small>{pred['fecha_creacion'] if pred['fecha_creacion'] else 'Sin fecha'}</small>
                         </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay predicciones registradas. ¡Realiza tu primera predicción!")
    except Exception as e:
        st.error(f"Error al cargar predicciones: {e}")

# Página de Nueva Predicción
elif st.session_state['page'] == "🔮 Nueva Predicción":
    st.markdown('<div class="main-header"><h1>🔮 Nueva Predicción</h1></div>', unsafe_allow_html=True)
    
    with st.form("prediccion_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            variedad = st.selectbox("Variedad", ["Cabernet", "Syrah", "Malbec"])
            viñedo = st.selectbox("Viñedo", ["Agrelo", "Drummond", "San Carlos"])
            brix = st.number_input("Brix", min_value=10.0, max_value=30.0, value=14.5)
        
        with col2:
            ph = st.number_input("pH", min_value=2.5, max_value=4.5, value=3.3)
            acidez = st.number_input("Acidez Total", min_value=4.0, max_value=15.0, value=10.0)
            modo = st.radio("Modo de consulta", ["Actualidad", "Pasado"])
        
        col3, col4 = st.columns(2)
        with col3:
            dia = st.number_input("Día de cosecha", min_value=1, max_value=31, value=14)
        with col4:
            mes = st.number_input("Mes de cosecha", min_value=1, max_value=12, value=5)
        
        notas = st.text_area("Notas sobre la predicción (opcional)", "")
        
        submitted = st.form_submit_button("🔮 Predecir días restantes")
        
        if submitted:
            fecha_cosecha = date(datetime.now().year, mes, dia)
            
            # Clima para predicción (7 días hacia adelante)
            inicio_pred = fecha_cosecha
            fin_pred = fecha_cosecha + timedelta(days=6)
            clima_pred = obtener_promedios_clima_pasado if modo == "Pasado" else obtener_promedios_clima_futuro
            clima_pred_data = clima_pred(viñedo, inicio_pred.isoformat(), fin_pred.isoformat())
            
            # Clima para base de datos (7 días hacia atrás)
            inicio_db = fecha_cosecha - timedelta(days=6)
            fin_db = fecha_cosecha
            clima_db_data = clima_pred(viñedo, inicio_db.isoformat(), fin_db.isoformat())
            
            # Predicción
            dias_restantes = predecir(
                variedad, viñedo, brix, ph, acidez,
                clima_pred_data["tavg_7d"], clima_pred_data["tmin_7d"], clima_pred_data["tmax_7d"],
                clima_pred_data["prcp_7d"], clima_pred_data["wspd_7d"], clima_pred_data["pres_7d"]
            )
            
            st.success(f"Faltan aproximadamente **{dias_restantes} días** para la cosecha.")
            
            # Insertar en base de datos
            try:
                insertar_prediccion(
                    variedad=variedad, viñedo=viñedo, fecha_cosecha=fecha_cosecha,
                    brix=brix, ph=ph, acidez=acidez,
                    tavg_7d=clima_db_data["tavg_7d"], tmin_7d=clima_db_data["tmin_7d"],
                    tmax_7d=clima_db_data["tmax_7d"], prcp_7d=clima_db_data["prcp_7d"],
                    wspd_7d=clima_db_data["wspd_7d"], pres_7d=clima_db_data["pres_7d"]
                )
                
                insertar_prediccion_modelo(
                    variedad=variedad, viñedo=viñedo, fecha_cosecha=fecha_cosecha,
                    brix=brix, ph=ph, acidez=acidez,
                    tavg_7d=clima_pred_data["tavg_7d"], tmin_7d=clima_pred_data["tmin_7d"],
                    tmax_7d=clima_pred_data["tmax_7d"], prcp_7d=clima_pred_data["prcp_7d"],
                    wspd_7d=clima_pred_data["wspd_7d"], pres_7d=clima_pred_data["pres_7d"],
                    dias_restantes=dias_restantes, notas=notas
                )
                
                st.success("Datos almacenados correctamente en la base de datos.")
            except Exception as e:
                st.error(f"Error al guardar en base de datos: {e}")

# Página de Historial
elif st.session_state['page'] == "📊 Historial de Predicciones":
    st.markdown('<div class="main-header"><h1>📊 Historial de Predicciones</h1></div>', unsafe_allow_html=True)
    
    try:
        todas_pred = obtener_todas_predicciones()
        
        if todas_pred:
            # Convertir a DataFrame para mejor visualización
            df = pd.DataFrame(todas_pred)
            df['fecha_cosecha'] = pd.to_datetime(df['fecha_cosecha']).dt.date
            df['fecha_objetivo'] = pd.to_datetime(df['fecha_objetivo']).dt.date
            # Manejar fecha_creacion que puede ser None y formatear solo fecha
            df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion'], errors='coerce').dt.date
            
            # Sección Próxima a Cosechar 
            st.markdown("## Próxima a Cosechar")
            hoy = pd.to_datetime(pd.Timestamp.today().date())
            df_validas = df[pd.notna(df['fecha_objetivo'])].copy()
            if not df_validas.empty:
                df_validas['fecha_objetivo'] = pd.to_datetime(df_validas['fecha_objetivo'], errors='coerce')
                df_validas = df_validas[pd.notna(df_validas['fecha_objetivo'])]
                df_validas['dias_a_cosecha'] = (df_validas['fecha_objetivo'] - hoy).dt.days
                df_validas = df_validas[df_validas['dias_a_cosecha'] >= 0]
                if not df_validas.empty:
                    idx_min = df_validas['dias_a_cosecha'].idxmin()
                    pred_proxima = df_validas.loc[idx_min]
                    st.success(f"**{pred_proxima['variedad']} - {pred_proxima['viñedo']}**\n\nFecha objetivo: {pred_proxima['fecha_objetivo']}\n\nFaltan: **{pred_proxima['dias_a_cosecha']} días**")
                else:
                    st.info("Sin predicciones futuras")
            else:
                st.info("Sin datos")
            
            st.markdown("---")  # Separador visual
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                variedad_filtro = st.selectbox("Filtrar por variedad", ["Todas"] + list(df['variedad'].unique()))
            with col2:
                viñedo_filtro = st.selectbox("Filtrar por viñedo", ["Todos"] + list(df['viñedo'].unique()))
            with col3:
                mostrar_todas = st.checkbox("Mostrar todas las predicciones", value=False)
            
            # Aplicar filtros
            if variedad_filtro != "Todas":
                df = df[df['variedad'] == variedad_filtro]
            if viñedo_filtro != "Todos":
                df = df[df['viñedo'] == viñedo_filtro]
            
            # Mostrar datos
            columnas_mostrar = ['id', 'variedad', 'viñedo', 'fecha_cosecha', 'brix', 'ph', 'acidez', 'dias_restantes', 'fecha_objetivo', 'lote', 'notas', 'fecha_creacion']
            columnas_presentes = [col for col in columnas_mostrar if col in df.columns]
            if mostrar_todas:
                st.dataframe(df[columnas_presentes], use_container_width=True)
            else:
                st.dataframe(df.head(10)[columnas_presentes], use_container_width=True)
                if len(df) > 10:
                    st.info(f"Mostrando las primeras 10 de {len(df)} predicciones. Marca la casilla para ver todas.")
            
            # Sección para editar notas y lote
            st.markdown("## 📝 Editar Notas y Lote")
            if not df.empty:
                opciones_predicciones = []
                for idx, row in df.iterrows():
                    opcion = f"ID {row['id']} - {row['variedad']} ({row['viñedo']}) - {row['fecha_cosecha']}"
                    opciones_predicciones.append(opcion)
                prediccion_seleccionada = st.selectbox(
                    "Seleccionar predicción para editar:",
                    opciones_predicciones,
                    index=0
                )
                if prediccion_seleccionada:
                    id_prediccion = int(prediccion_seleccionada.split(" - ")[0].replace("ID ", ""))
                    prediccion_actual = df[df['id'] == id_prediccion].iloc[0]
                    notas_actuales = prediccion_actual['notas'] if pd.notna(prediccion_actual['notas']) else ""
                    lote_actual = int(prediccion_actual['lote']) if pd.notna(prediccion_actual['lote']) else ""
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Variedad:** {prediccion_actual['variedad']}")
                        st.write(f"**Viñedo:** {prediccion_actual['viñedo']}")
                        st.write(f"**Días restantes:** {prediccion_actual['dias_restantes']}")
                        nuevo_lote = st.text_input("Lote:", value=str(lote_actual), key=f"lote_{id_prediccion}")
                    with col2:
                        st.write(f"**Fecha cosecha:** {prediccion_actual['fecha_cosecha']}")
                        st.write(f"**Fecha objetivo:** {prediccion_actual['fecha_objetivo']}")
                        st.write(f"**Brix:** {prediccion_actual['brix']}")
                    nuevas_notas = st.text_area(
                        "Notas de la predicción:",
                        value=notas_actuales,
                        height=100,
                        placeholder="Agrega o modifica las notas de esta predicción...",
                        key=f"notas_{id_prediccion}"
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Guardar Notas y Lote", type="primary", key=f"guardar_{id_prediccion}"):
                            try:
                                ok_notas = actualizar_notas_prediccion(id_prediccion, nuevas_notas)
                                ok_lote = actualizar_lote_prediccion(id_prediccion, int(nuevo_lote) if nuevo_lote != '' else None)
                                if ok_notas or ok_lote:
                                    st.success("Cambios guardados correctamente!")
                                    st.rerun()
                                else:
                                    st.error("No se pudo guardar los cambios. Verifica que la predicción existe.")
                            except Exception as e:
                                st.error(f"Error al guardar los cambios: {e}")
                    with col2:
                        if st.button("🔄 Recargar Datos", key=f"recargar_{id_prediccion}"):
                            st.rerun()
            else:
                st.warning("No hay predicciones para editar.")
            
            # Estadísticas
            st.markdown("## 📈 Estadísticas")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Predicciones", len(df))
            with col2:
                st.metric("Variedad Más Predicha", df['variedad'].mode().iloc[0] if not df.empty else "N/A")
            with col3:
                st.metric("Viñedo Más Predicho", df['viñedo'].mode().iloc[0] if not df.empty else "N/A")
            
        else:
            st.info("No hay predicciones registradas en la base de datos.")
            
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")

# Página de Clima
elif st.session_state['page'] == "🌤️ Pronóstico del Clima":
    st.markdown('<div class="main-header"><h1>🌤️ Pronóstico del Clima</h1></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        viñedo_clima = st.selectbox("Seleccionar Viñedo", ["Agrelo", "Drummond", "San Carlos"])
    
    with col2:
        dias_pronostico = st.slider("Días de pronóstico", 1, 14, 7)
    
    if st.button("🌤️ Obtener Pronóstico"):
        try:
            fecha_inicio = date.today()
            fecha_fin = fecha_inicio + timedelta(days=dias_pronostico-1)
            
            clima_data = obtener_promedios_clima_futuro(
                viñedo_clima, 
                fecha_inicio.isoformat(), 
                fecha_fin.isoformat()
            )
            
            st.markdown(f"""
            <div class="weather-card">
                <h3>🌤️ Pronóstico para {viñedo_clima}</h3>
                <p><strong>Período:</strong> {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🌡️ Temperatura Promedio", f"{clima_data['tavg_7d']}°C")
                st.metric("❄️ Temperatura Mínima", f"{clima_data['tmin_7d']}°C")
            
            with col2:
                st.metric("🔥 Temperatura Máxima", f"{clima_data['tmax_7d']}°C")
                st.metric("💧 Precipitación", f"{clima_data['prcp_7d']} mm")
            
            with col3:
                st.metric("💨 Velocidad del Viento", f"{clima_data['wspd_7d']} km/h")
                st.metric("🌪️ Presión Atmosférica", f"{clima_data['pres_7d']} hPa")
                
        except Exception as e:
            st.error(f"Error al obtener el pronóstico del clima: {e}") 