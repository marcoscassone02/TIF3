import type {
  AppOptions,
  Block,
  Farm,
  Followup,
  ModelAnalysis,
  ModelReadiness,
  Organization,
  Prediction,
  PredictionInput,
  PredictionResult,
  Sample,
  SampleFilters,
  SampleImportResult,
  SampleSummary,
  Summary,
  User,
} from './types'

const TOKEN_KEY = 'grapesense_token'
const WINERY_KEY = 'grapesense_winery'
export const session = {
  token: () => localStorage.getItem(TOKEN_KEY),
  save: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  winery: () => localStorage.getItem(WINERY_KEY),
  selectWinery: (id: number) => localStorage.setItem(WINERY_KEY, String(id)),
  clear: () => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(WINERY_KEY) },
}

const BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = session.token()
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(session.winery() ? { 'X-Bodega-ID': session.winery() as string } : {}),
      ...options?.headers,
    },
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
  authStatus: () => request<{ bootstrap_required: boolean }>('/api/auth/status'),
  bootstrap: (data: { bodega_nombre: string; nombre: string; email: string; password: string }) =>
    request<{ access_token: string; user: User }>('/api/auth/bootstrap', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; user: User }>('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request<User>('/api/auth/me'),
  getOptions: () => request<AppOptions>('/api/options'),
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
  exportSamples: (filters: SampleFilters = {}) =>
    request<{ items: Sample[]; total: number }>(`/api/samples/export?${queryString(filters)}`),
  importSamples: (data: { finca_id: number; cuartel_id: number | null; csv_text: string; sobrescribir: boolean }) =>
    request<SampleImportResult>('/api/samples/import', { method: 'POST', body: JSON.stringify(data) }),
  updateSample: (id: string, data: { fecha_medicion: string; brix: number; ph: number; acidez_total_g_l: number }) =>
    request<{ muestra_id: string; fecha_medicion: string; clima_recalculado: boolean }>(`/api/samples/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSample: (id: string) =>
    request<{ eliminada: string; seguimiento_reabierto: boolean }>(`/api/samples/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getFollowups: (estado?: 'pendiente' | 'cosechado') =>
    request<{ items: Followup[] }>(`/api/followups${estado ? `?estado=${estado}` : ''}`),
  createFollowup: (data: { finca_id: number; cuartel_id: number | null; variedad: string; vendimia: number; fecha_inicio: string; lote_referencia: string }) =>
    request<Followup>('/api/followups', { method: 'POST', body: JSON.stringify(data) }),
  updateFollowup: (id: number, data: { finca_id: number; cuartel_id: number | null; variedad: string; vendimia: number; fecha_inicio: string; lote_referencia: string }) =>
    request<Followup>(`/api/followups/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteFollowup: (id: number) =>
    request<{ eliminado: string; muestras_eliminadas: number }>(`/api/followups/${id}`, { method: 'DELETE' }),
  addFollowupSample: (id: number, data: { fecha_medicion: string; brix: number; ph: number; acidez_total_g_l: number }) =>
    request<{ muestra_id: string; numero_muestra: number; origen_clima: string }>(`/api/followups/${id}/samples`, { method: 'POST', body: JSON.stringify(data) }),
  closeFollowup: (id: number, data: { fecha_cosecha: string; brix: number; ph: number; acidez_total_g_l: number }) =>
    request<{ seguimiento_id: number; codigo: string; muestras_actualizadas: number; muestra_final: string; ventanas_con_pronostico: number }>(`/api/followups/${id}/close`, { method: 'POST', body: JSON.stringify(data) }),
  getModelAnalysis: () => request<ModelAnalysis>('/api/model/analysis'),
  getOrganization: () => request<Organization>('/api/admin/organization'),
  getModelReadiness: () => request<ModelReadiness>('/api/admin/models/readiness'),
  trainModel: () => request('/api/admin/models/train', { method: 'POST' }),
  activateModel: (id: number) => request(`/api/admin/models/${id}/activate`, { method: 'POST' }),
  createFarm: (data: { nombre: string; latitud: number; longitud: number }) =>
    request<Farm>('/api/admin/farms', { method: 'POST', body: JSON.stringify(data) }),
  updateFarm: (id: number, data: { nombre: string; latitud: number; longitud: number }) =>
    request<Farm>(`/api/admin/farms/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteFarm: (id: number) =>
    request<{ eliminada: string }>(`/api/admin/farms/${id}`, { method: 'DELETE' }),
  createBlock: (data: { finca_id: number; nombre: string; variedad: string | null; hectareas: number | null }) =>
    request<Block>('/api/admin/blocks', { method: 'POST', body: JSON.stringify(data) }),
  createUser: (data: { nombre: string; email: string; password: string; rol: string }) =>
    request('/api/admin/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id: number, data: { nombre: string; email: string; password: string | null; rol: string }) =>
    request(`/api/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteUser: (id: number) =>
    request<{ eliminado: string }>(`/api/admin/users/${id}`, { method: 'DELETE' }),
  getWineries: () => request<{ items: { bodega_id: number; nombre: string; slug: string; activa: boolean; usuarios: number; fincas: number }[] }>('/api/admin/wineries'),
  createWinery: (data: { nombre: string; admin_nombre: string; admin_email: string; admin_password: string }) =>
    request('/api/admin/wineries', { method: 'POST', body: JSON.stringify(data) }),
}
