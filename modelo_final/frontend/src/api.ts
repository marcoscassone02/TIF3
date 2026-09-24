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
  vinedo: string
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
  modelo: { algoritmo: string; version: string; objetivo: string; variables: number; vendimias_entrenamiento: number[] }
  datos: { entrenamiento_muestras: number; evaluacion_2024_muestras: number; evaluacion_2026_muestras: number; origen_uva: string; origen_clima: string }
  evaluacion_2024: Metrics
  evaluacion_2026_sintetica: Metrics
  rendimiento_por_anticipacion: ({ rango: string } & Metrics)[]
  importancia_variables: { variable: string; etiqueta: string; grupo: string; importancia_porcentaje: number }[]
  importancia_grupos: { grupo: string; importancia_porcentaje: number }[]
  comparacion_2024: { real: number; predicho: number; error_absoluto: number }[]
  advertencias: string[]
}

export type SampleFilters = {
  vendimia?: string
  variedad?: string
  vinedo?: string
  tipo_muestra?: string
  search?: string
}

const BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail ?? 'No se pudo completar la operación')
  return body as T
}

function queryString(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.toString()
}

export const api = {
  createPrediction: (data: PredictionInput) =>
    request<PredictionResult>('/api/predictions', { method: 'POST', body: JSON.stringify(data) }),
  getPredictions: (limit = 500) => request<{ items: Prediction[] }>(`/api/predictions?limit=${limit}`),
  getPrediction: (id: number) => request<Prediction>(`/api/predictions/${id}`),
  getSummary: () => request<Summary>('/api/summary'),
  getSamples: (filters: SampleFilters = {}, limit = 100, offset = 0) =>
    request<{ items: Sample[]; total: number; limit: number; offset: number }>(
      `/api/samples?${queryString({ ...filters, limit, offset })}`,
    ),
  getSampleSummary: () => request<SampleSummary>('/api/samples/summary'),
  getModelAnalysis: () => request<ModelAnalysis>('/api/model/analysis'),
}
