export type View = 'prediction' | 'predictions' | 'samples' | 'model' | 'admin'

export type Prediction = {
  prediccion_id: number
  fecha_medicion: string
  fecha_creacion: string
  muestra_id: string | null
  lote_id: string
  vendimia: number
  variedad: string
  vinedo: string
  Brix: number
  pH: number
  acidez_total_g_l: number
  dias_predichos: number
  fecha_cosecha_estimada: string
  clima_pasado_desde: string
  clima_pasado_hasta: string
  clima_futuro_desde: string
  clima_futuro_hasta: string
  origen_clima: string
  modelo_version: string
  notas: string | null
  [key: string]: string | number | null
}

export type PredictionInput = {
  fecha_medicion: string
  variedad: string
  finca_id: number
  cuartel_id: number | null
  brix: number
  ph: number
  acidez_total_g_l: number
  lote_id: string
  muestra_id: string
  notas: string
}

export type PredictionResult = {
  prediccion_id: number
  fecha_medicion: string
  dias_predichos: number
  fecha_cosecha_estimada: string
  origen_clima: string
  clima_pasado: string
  clima_futuro: string
  tabla: string
}

export type Summary = {
  total_predicciones: number
  lotes_evaluados: number
  promedio_dias: number | null
  ultima_prediccion: string | null
}

export type Sample = {
  muestra_id: string
  lote_id: string
  vendimia: number
  fecha_medicion: string
  tipo_muestra: string
  numero_muestra: number
  variedad: string
  vinedo: string
  Brix: number
  pH: number
  acidez_total_g_l: number
  dias_hasta_cosecha: number | null
  pasado_tavg_7d: number
  pasado_prcp_sum_7d: number
  pasado_radiacion_sum_7d: number
  futuro_historico_tavg_7d: number
  futuro_historico_prcp_sum_7d: number
  futuro_historico_radiacion_sum_7d: number
  [key: string]: string | number | null
}

export type SampleSummary = {
  total_muestras: number
  total_lotes: number
  muestras_cosecha: number
  por_vendimia: { vendimia: number; muestras: number; lotes: number; primera_medicion: string; ultima_medicion: string }[]
  variedades: string[]
  vinedos: string[]
}

export type Metrics = {
  muestras: number
  mae_dias: number
  rmse_dias: number
  sesgo_dias: number
  dentro_3_dias_porcentaje: number
  dentro_4_dias_porcentaje: number
  r2: number
}

export type ModelAnalysis = {
  modelo: { nombre: string; algoritmo: string; version: string; bodega: string; objetivo: string; variables: number; vendimias_entrenamiento: number[] }
  datos: { entrenamiento_muestras: number; evaluacion_muestras: number; evaluacion_lotes: number; evaluacion_etiqueta: string; origen_uva: string; origen_clima: string }
  evaluacion: Metrics
  evaluacion_2024: Metrics
  rendimiento_por_anticipacion: ({ rango: string } & Metrics)[]
  importancia_variables: { variable: string; etiqueta: string; grupo: string; importancia_porcentaje: number }[]
  importancia_grupos: { grupo: string; importancia_porcentaje: number }[]
  comparacion: { real: number; predicho: number; error_absoluto: number }[]
  comparacion_2024: { real: number; predicho: number; error_absoluto: number }[]
  advertencias: string[]
}

export type ModelReadiness = {
  puede_entrenar: boolean
  muestras: number
  lotes: number
  vendimias: number[]
  motivo: string | null
  politica?: string
  entrenamiento_muestras?: number
  entrenamiento_lotes?: number
  evaluacion_muestras?: number
  evaluacion_lotes?: number
  vendimias_entrenamiento?: number[]
  vendimias_evaluacion?: number[]
}

export type SampleFilters = {
  vendimia?: string
  variedad?: string
  vinedo?: string
  tipo_muestra?: string
  search?: string
}

export type User = {
  usuario_id: number
  bodega_id: number
  nombre: string
  email: string
  rol: 'superadmin' | 'admin' | 'usuario'
  bodega_nombre: string
}

export type Farm = { finca_id: number; nombre: string; latitud: number; longitud: number; activa: boolean }
export type Block = { cuartel_id: number; finca_id: number; finca?: string; nombre: string; variedad: string | null; hectareas: number | null; activo: boolean }
export type AppOptions = { variedades: string[]; fincas: Farm[]; cuarteles: Block[]; fecha_maxima: string }

export type SampleImportResult = {
  filas_recibidas: number
  insertadas: number
  actualizadas: number
  omitidas: number
  fechas_climaticas_consultadas: number
  fechas_con_pronostico: number
}

export type Followup = {
  seguimiento_id: number
  codigo: string
  lote_referencia: string | null
  variedad: string
  vendimia: number
  estado: 'pendiente' | 'cosechado'
  fecha_inicio: string
  fecha_cosecha_efectiva: string | null
  finca_id: number
  finca: string
  cuartel_id: number | null
  cuartel: string | null
  muestras: number
  ultima_medicion: string | null
  ultima_muestra: number | null
}

export type Organization = {
  bodega: { bodega_id: number; nombre: string; slug: string; activa: boolean; fecha_creacion: string }
  fincas: Farm[]
  cuarteles: Block[]
  usuarios: { usuario_id: number; nombre: string; email: string; rol: string; activo: boolean; fecha_creacion: string }[]
  modelos: { modelo_bodega_id: number; nombre: string; version: string; vendimias_entrenamiento: string | null; metricas: Metrics & { politica?: string } | null; activo: boolean; fecha_entrenamiento: string | null }[]
}
