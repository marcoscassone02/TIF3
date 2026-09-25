import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, BarChart3, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight,
  Building2, CloudSun, Database, Download, Eye, FileDown, FlaskConical, Grape, History, Info,
  Layers3, LoaderCircle, MapPin, MapPinned, Microscope, Pencil, Plus,
  ShieldCheck, Sparkles, Trash2, TrendingUp, Upload, Users, X,
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, session } from './api'
import { Sidebar } from './components/Sidebar'
import { ChartPanel, DetailSection, EmptyData, Field, PanelHeading, Recent, SearchBox, Stat, Value } from './components/ui'
import { downloadRows, formatDate, roleLabel, today } from './lib/format'
import type {
  AppOptions, Followup, ModelAnalysis, ModelReadiness, Organization, Prediction, PredictionInput,
  PredictionResult, Sample, SampleFilters, SampleImportResult, SampleSummary, Summary, User, View,
} from './types'

const initialForm: PredictionInput = {
  fecha_medicion: today, variedad: 'Malbec', finca_id: 0, cuartel_id: null, brix: 18,
  ph: 3.2, acidez_total_g_l: 8, lote_id: '', muestra_id: '', notas: '',
}
const palette = ['#255c42', '#c6953e', '#5b7f70', '#8b6545']

function AccessPage({ bootstrapRequired, onAccess }: { bootstrapRequired: boolean; onAccess: (user: User) => void }) {
  const [form, setForm] = useState({ bodega_nombre: '', nombre: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const response = bootstrapRequired
        ? await api.bootstrap(form)
        : await api.login({ email: form.email, password: form.password })
      session.save(response.access_token)
      onAccess(response.user)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo iniciar la sesión')
    } finally { setBusy(false) }
  }
  return <div className="access-page"><section className="access-brand"><span><Grape size={35} /></span><h1>GrapeSense</h1><p>Seguimiento y predicción de cosecha para múltiples bodegas.</p><ul><li>Datos separados por organización</li><li>Fincas con ubicación climática propia</li><li>Usuarios y modelos administrados por bodega</li></ul></section><section className="access-form"><div><p className="eyebrow">{bootstrapRequired ? 'CONFIGURACIÓN INICIAL' : 'ACCESO SEGURO'}</p><h2>{bootstrapRequired ? 'Crear la primera organización' : 'Ingresar a GrapeSense'}</h2><p>{bootstrapRequired ? 'Los datos existentes quedarán asociados a esta bodega.' : 'Usa el acceso asignado por el administrador de tu bodega.'}</p></div>{error && <div className="alert error">{error}</div>}<form onSubmit={submit}>{bootstrapRequired && <><Field label="Nombre de la bodega"><input required value={form.bodega_nombre} onChange={(e) => setForm({ ...form, bodega_nombre: e.target.value })} /></Field><Field label="Nombre del administrador"><input required value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Field></>}<Field label="Correo electrónico"><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field><Field label="Contraseña" hint={bootstrapRequired ? 'Mínimo 10 caracteres' : undefined}><input type="password" minLength={bootstrapRequired ? 10 : 8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field><button className="primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <ShieldCheck size={19} />}{bootstrapRequired ? 'Configurar plataforma' : 'Iniciar sesión'}</button></form></section></div>
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [bootstrapRequired, setBootstrapRequired] = useState(false)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    async function start() {
      try {
        const status = await api.authStatus()
        setBootstrapRequired(status.bootstrap_required)
        if (!status.bootstrap_required && session.token()) setUser(await api.me())
      } catch { session.clear() }
      finally { setLoading(false) }
    }
    void start()
  }, [])
  if (loading) return <div className="auth-shell"><LoaderCircle className="spin" /><p>Iniciando GrapeSense...</p></div>
  if (!user) return <AccessPage bootstrapRequired={bootstrapRequired} onAccess={(loggedUser) => { setUser(loggedUser); setBootstrapRequired(false) }} />
  return <PlatformApp user={user} logout={() => { session.clear(); setUser(null) }} />
}

function PlatformApp({ user, logout }: { user: User; logout: () => void }) {
  const [view, setView] = useState<View>('prediction')
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [sampleSummary, setSampleSummary] = useState<SampleSummary | null>(null)
  const [analysis, setAnalysis] = useState<ModelAnalysis | null>(null)
  const [options, setOptions] = useState<AppOptions | null>(null)
  const [globalError, setGlobalError] = useState('')
  const [initialLoading, setInitialLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [history, stats, samples, appOptions] = await Promise.all([
        api.getPredictions(), api.getSummary(), api.getSampleSummary(), api.getOptions(),
      ])
      setPredictions(history.items)
      setSummary(stats)
      setSampleSummary(samples)
      setOptions(appOptions)
      setGlobalError('')
    } catch (error) {
      setGlobalError(error instanceof Error ? error.message : 'No se pudieron cargar los datos')
    } finally {
      setInitialLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (view === 'model' && !analysis) {
      api.getModelAnalysis().then(setAnalysis).catch((error) => setGlobalError(error.message))
    }
  }, [view, analysis])

  const titles: Record<View, [string, string]> = {
    prediction: ['Predicción de cosecha', 'Registra una muestra y estima el momento de cosecha con contexto climático.'],
    predictions: ['Predicciones realizadas', 'Consulta el resultado, sus entradas químicas y el clima utilizado.'],
    samples: ['Base de muestras', 'Explora las mediciones históricas usadas para entrenar y evaluar el modelo.'],
    model: ['Análisis del modelo', 'Revisa rendimiento, variables influyentes y límites antes de interpretar una predicción.'],
    admin: ['Administración de la bodega', 'Gestiona fincas, usuarios y modelos de tu organización.'],
  }

  return (
    <div className="app-shell">
      <Sidebar view={view} setView={setView} user={user} logout={logout} />
      <main>
        <header>
          <div>
            <p className="eyebrow">APOYO A LA DECISIÓN ENOLÓGICA</p>
            <h1>{titles[view][0]}</h1>
            <p>{titles[view][1]}</p>
          </div>
          <div className="date-chip"><CalendarDays size={18} /> {formatDate(today)}</div>
        </header>
        {globalError && <div className="alert error"><strong>No pudimos completar una consulta.</strong><span>{globalError}</span></div>}
        {view === 'prediction' && <PredictionPage predictions={predictions} summary={summary} options={options} loading={initialLoading} refresh={refresh} goHistory={() => setView('predictions')} />}
        {view === 'predictions' && <PredictionsPage predictions={predictions} loading={initialLoading} />}
        {view === 'samples' && <SamplesPage summary={sampleSummary} user={user} options={options} refreshSummary={refresh} />}
        {view === 'model' && <ModelPage analysis={analysis} />}
        {view === 'admin' && <AdminPage user={user} refreshOptions={refresh} onModelChanged={() => setAnalysis(null)} />}
      </main>
    </div>
  )
}

function PredictionPage({ predictions, summary, options, loading, refresh, goHistory }: {
  predictions: Prediction[]; summary: Summary | null; options: AppOptions | null; loading: boolean; refresh: () => Promise<void>; goHistory: () => void
}) {
  const [form, setForm] = useState(initialForm)
  const [result, setResult] = useState<PredictionResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (options?.fincas.length && form.finca_id === 0) setForm((current) => ({ ...current, finca_id: options.fincas[0].finca_id }))
  }, [options, form.finca_id])
  const availableBlocks = options?.cuarteles.filter((block) => block.finca_id === form.finca_id) ?? []

  async function submit(event: FormEvent) {
    event.preventDefault(); setSubmitting(true); setError(''); setResult(null)
    try {
      const response = await api.createPrediction(form)
      setResult(response)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo realizar la predicción')
    } finally { setSubmitting(false) }
  }

  return <>
    <section className="stats-grid">
      <Stat icon={<Database />} label="Predicciones guardadas" value={summary?.total_predicciones ?? 0} />
      <Stat icon={<MapPin />} label="Lotes evaluados" value={summary?.lotes_evaluados ?? 0} />
      <Stat icon={<TrendingUp />} label="Promedio estimado" value={summary?.promedio_dias == null ? '—' : `${summary.promedio_dias} días`} />
      <Stat icon={<History />} label="Última actividad" value={summary?.ultima_prediccion ? formatDate(summary.ultima_prediccion) : 'Sin datos'} />
    </section>
    {error && <div className="alert error"><strong>No se pudo calcular.</strong><span>{error}</span></div>}
    <div className="content-grid">
      <section className="panel form-panel">
        <PanelHeading icon={<FlaskConical size={20} />} title="Nueva muestra" subtitle="Datos medidos en bodega" aside="* Campos obligatorios" />
        <form onSubmit={submit}>
          <div className="form-grid">
            <Field label="Fecha de medición *"><input type="date" max={today} required value={form.fecha_medicion} onChange={(e) => setForm({ ...form, fecha_medicion: e.target.value })} /></Field>
            <Field label="Lote *"><input required maxLength={80} placeholder="Ej. LOTE-07" value={form.lote_id} onChange={(e) => setForm({ ...form, lote_id: e.target.value })} /></Field>
            <Field label="Variedad *"><select value={form.variedad} onChange={(e) => setForm({ ...form, variedad: e.target.value })}><option>Malbec</option><option>Syrah</option><option>Cabernet</option></select></Field>
            <Field label="Finca *"><select required value={form.finca_id || ''} onChange={(e) => setForm({ ...form, finca_id: Number(e.target.value), cuartel_id: null })}>{options?.fincas.map((farm) => <option key={farm.finca_id} value={farm.finca_id}>{farm.nombre}</option>)}</select></Field>
            <Field label="Cuartel" hint="Opcional"><select value={form.cuartel_id ?? ''} onChange={(e) => setForm({ ...form, cuartel_id: e.target.value ? Number(e.target.value) : null })}><option value="">Sin seleccionar</option>{availableBlocks.map((block) => <option key={block.cuartel_id} value={block.cuartel_id}>{block.nombre}{block.variedad ? ` · ${block.variedad}` : ''}</option>)}</select></Field>
            <Field label="Brix *" hint="Grados"><input type="number" min="10" max="30" step="0.1" required value={form.brix} onChange={(e) => setForm({ ...form, brix: Number(e.target.value) })} /></Field>
            <Field label="pH *"><input type="number" min="2.5" max="4.5" step="0.01" required value={form.ph} onChange={(e) => setForm({ ...form, ph: Number(e.target.value) })} /></Field>
            <Field label="Acidez total *" hint="g/L ácido tartárico"><input type="number" min="2" max="15" step="0.1" required value={form.acidez_total_g_l} onChange={(e) => setForm({ ...form, acidez_total_g_l: Number(e.target.value) })} /></Field>
            <Field label="ID de muestra" hint="Opcional"><input maxLength={100} placeholder="Ej. M-2026-014" value={form.muestra_id} onChange={(e) => setForm({ ...form, muestra_id: e.target.value })} /></Field>
          </div>
          <Field label="Observaciones" hint="Opcional"><textarea rows={3} maxLength={1000} placeholder="Estado sanitario, color, notas del recorrido..." value={form.notas} onChange={(e) => setForm({ ...form, notas: e.target.value })} /></Field>
          <div className="climate-note"><CloudSun size={21} /><span><strong>Clima automático</strong>Se consultarán 7 días anteriores y 7 días futuros desde la fecha indicada.</span></div>
          <button className="primary-button" disabled={submitting} type="submit">{submitting ? <LoaderCircle className="spin" size={20} /> : <Sparkles size={20} />}{submitting ? 'Consultando clima y calculando...' : 'Calcular y guardar predicción'}</button>
        </form>
      </section>
      <aside className="right-column">
        {result ? <ResultCard result={result} /> : <section className="empty-result"><span><Grape size={36} /></span><h3>El resultado aparecerá aquí</h3><p>Completa la muestra para obtener los días restantes y la fecha estimada de cosecha.</p></section>}
        <section className="recent-card"><div className="section-title"><h3>Predicciones recientes</h3><button onClick={goHistory}>Ver todas</button></div>{loading ? <p>Cargando...</p> : predictions.slice(0, 4).map((item) => <Recent key={item.prediccion_id} item={item} />)}{!loading && predictions.length === 0 && <p className="muted">Todavía no hay predicciones registradas.</p>}</section>
      </aside>
    </div>
  </>
}

function ResultCard({ result }: { result: PredictionResult }) {
  return <section className="result-card">
    <div className="success-title"><CheckCircle2 size={23} /><span>Predicción guardada</span></div>
    <p className="result-label">Días estimados hasta cosecha</p><div className="big-number">{result.dias_predichos.toFixed(1)} <small>días</small></div>
    <div className="harvest-date"><CalendarDays /><span><small>Fecha estimada</small><strong>{formatDate(result.fecha_cosecha_estimada)}</strong></span></div>
    <div className="weather-windows"><div><small>Clima pasado</small><strong>{result.clima_pasado}</strong></div><div><small>Clima futuro</small><strong>{result.clima_futuro}</strong></div></div>
    <p className="source">Fuente: {result.origen_clima}</p>
  </section>
}

function PredictionsPage({ predictions, loading }: { predictions: Prediction[]; loading: boolean }) {
  const [search, setSearch] = useState('')
  const [detail, setDetail] = useState<Prediction | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return term ? predictions.filter((item) => [item.lote_id, item.muestra_id, item.variedad, item.vinedo].some((value) => String(value ?? '').toLowerCase().includes(term))) : predictions
  }, [predictions, search])
  async function openDetail(id: number) {
    setDetailLoading(true)
    try { setDetail(await api.getPrediction(id)) } finally { setDetailLoading(false) }
  }
  const columns: (keyof Prediction)[] = ['prediccion_id', 'fecha_medicion', 'lote_id', 'muestra_id', 'variedad', 'vinedo', 'Brix', 'pH', 'acidez_total_g_l', 'dias_predichos', 'fecha_cosecha_estimada', 'origen_clima', 'modelo_version', 'notas']
  return <section className="panel history-panel">
    <div className="history-toolbar"><SearchBox value={search} setValue={setSearch} placeholder="Buscar por lote, muestra, variedad o viñedo" /><button className="secondary-button" onClick={() => downloadRows(filtered, columns, 'predicciones_uva.csv')} disabled={!filtered.length}><Download size={18} /> Exportar CSV</button></div>
    <div className="table-wrap"><table><thead><tr><th>Fecha</th><th>Lote</th><th>Variedad / Viñedo</th><th>Química</th><th>Predicción</th><th>Cosecha estimada</th><th></th></tr></thead><tbody>{filtered.map((item) => <tr key={item.prediccion_id}><td>{formatDate(item.fecha_medicion)}</td><td><strong>{item.lote_id}</strong><small>{item.muestra_id || 'Sin ID de muestra'}</small></td><td><strong>{item.variedad}</strong><small>{item.vinedo}</small></td><td><span>{item.Brix.toFixed(1)} Brix</span><small>pH {item.pH.toFixed(2)} · {item.acidez_total_g_l.toFixed(1)} g/L</small></td><td><span className="days-pill">{item.dias_predichos.toFixed(1)} días</span></td><td>{formatDate(item.fecha_cosecha_estimada)}</td><td><button className="icon-button" aria-label="Ver detalle" onClick={() => void openDetail(item.prediccion_id)}><Eye size={18} /></button></td></tr>)}</tbody></table>{!loading && !filtered.length && <EmptyData text="No hay predicciones para mostrar." />}</div>
    {detailLoading && <div className="sheet-overlay"><div className="sheet loading-sheet"><LoaderCircle className="spin" /> Cargando detalle...</div></div>}
    {detail && <PredictionDetail item={detail} close={() => setDetail(null)} />}
  </section>
}

function PredictionDetail({ item, close }: { item: Prediction; close: () => void }) {
  const past = [['Temperatura media', 'pasado_tavg_7d', '°C'], ['Temperatura mínima', 'pasado_tmin_7d', '°C'], ['Temperatura máxima', 'pasado_tmax_7d', '°C'], ['Lluvia acumulada', 'pasado_prcp_sum_7d', 'mm'], ['Viento medio', 'pasado_wspd_7d', 'km/h'], ['Radiación', 'pasado_radiacion_sum_7d', 'MJ/m²'], ['Días > 35 °C', 'pasado_dias_calor_7d', '']]
  const future = [['Temperatura media', 'futuro_historico_tavg_7d', '°C'], ['Temperatura mínima', 'futuro_historico_tmin_7d', '°C'], ['Temperatura máxima', 'futuro_historico_tmax_7d', '°C'], ['Lluvia acumulada', 'futuro_historico_prcp_sum_7d', 'mm'], ['Viento medio', 'futuro_historico_wspd_7d', 'km/h'], ['Radiación', 'futuro_historico_radiacion_sum_7d', 'MJ/m²'], ['Días > 35 °C', 'futuro_historico_dias_calor_7d', '']]
  return <div className="sheet-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) close() }}><aside className="sheet"><div className="sheet-header"><div><small>PREDICCIÓN #{item.prediccion_id}</small><h2>{item.lote_id} · {item.variedad}</h2><p>{item.vinedo} · medición del {formatDate(item.fecha_medicion)}</p></div><button className="icon-button" onClick={close}><X /></button></div><div className="detail-result"><span><small>Resultado</small><strong>{item.dias_predichos.toFixed(1)} días</strong></span><span><small>Cosecha estimada</small><strong>{formatDate(item.fecha_cosecha_estimada)}</strong></span></div><DetailSection title="Química medida"><div className="detail-grid"><Value label="Brix" value={item.Brix.toFixed(1)} /><Value label="pH" value={item.pH.toFixed(2)} /><Value label="Acidez total" value={`${item.acidez_total_g_l.toFixed(1)} g/L`} /></div></DetailSection><ClimateSection title="7 días anteriores" dates={`${formatDate(item.clima_pasado_desde)} – ${formatDate(item.clima_pasado_hasta)}`} rows={past} item={item} /><ClimateSection title="7 días futuros" dates={`${formatDate(item.clima_futuro_desde)} – ${formatDate(item.clima_futuro_hasta)}`} rows={future} item={item} /><DetailSection title="Trazabilidad"><p className="detail-copy"><strong>Fuente:</strong> {item.origen_clima}</p><p className="detail-copy"><strong>Versión:</strong> {item.modelo_version}</p><p className="detail-copy"><strong>Notas:</strong> {item.notas || 'Sin observaciones'}</p></DetailSection></aside></div>
}

function ClimateSection({ title, dates, rows, item }: { title: string; dates: string; rows: string[][]; item: Prediction }) {
  return <DetailSection title={title} aside={dates}><div className="climate-grid">{rows.map(([label, key, unit]) => <Value key={key} label={label} value={`${Number(item[key]).toFixed(key.includes('dias_calor') ? 0 : 1)} ${unit}`} />)}</div></DetailSection>
}

function FollowupsPanel({ options, onChanged }: { options: AppOptions | null; onChanged: () => Promise<void> }) {
  const [items, setItems] = useState<Followup[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [action, setAction] = useState<{ type: 'sample' | 'close'; item: Followup } | null>(null)
  const [create, setCreate] = useState({ finca_id: 0, cuartel_id: null as number | null, variedad: 'Malbec', vendimia: Number(today.slice(0, 4)), fecha_inicio: today, lote_referencia: '' })
  const [measurement, setMeasurement] = useState({ fecha_medicion: today, brix: 17, ph: 3.15, acidez_total_g_l: 8.5 })
  const [harvest, setHarvest] = useState({ fecha_cosecha: today, brix: 24, ph: 3.45, acidez_total_g_l: 6 })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const load = useCallback(async () => { try { setItems((await api.getFollowups('pendiente')).items) } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudieron cargar los seguimientos') } }, [])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!create.finca_id && options?.fincas.length) setCreate((value) => ({ ...value, finca_id: options.fincas[0].finca_id }))
  }, [options, create.finca_id])
  const createBlocks = options?.cuarteles.filter((item) => item.finca_id === create.finca_id) ?? []

  async function run(operation: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setNotice('')
    try { await operation(); setNotice(success); setAction(null); setShowCreate(false); setEditingId(null); await Promise.all([load(), onChanged()]) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo completar la operación') }
    finally { setBusy(false) }
  }
  async function removeFollowup(item: Followup) {
    if (!window.confirm(`¿Eliminar el seguimiento ${item.codigo} y sus ${item.muestras} muestras?\n\nEsta acción no se puede deshacer.`)) return
    await run(
      () => api.deleteFollowup(item.seguimiento_id),
      `Se eliminó ${item.codigo} junto con ${item.muestras} muestras.`,
    )
  }
  return <section className="panel followups-panel">
    <div className="followups-heading"><div><span className="icon-box"><History size={20} /></span><div><h2>Seguimientos pendientes</h2><p>Cada lote recibe un código automático y conserva sus mediciones semanales.</p></div></div><button className="primary-button compact" onClick={() => { setShowCreate(!showCreate); setEditingId(null); setCreate({ finca_id: options?.fincas[0]?.finca_id ?? 0, cuartel_id: null, variedad: 'Malbec', vendimia: Number(today.slice(0, 4)), fecha_inicio: today, lote_referencia: '' }); setAction(null); setError(''); setNotice('') }}><Plus size={17} /> Nuevo seguimiento</button></div>
    {notice && <div className="alert success followup-alert"><CheckCircle2 size={18} /><span>{notice}</span></div>}
    {error && <div className="alert error followup-alert"><AlertTriangle size={18} /><span>{error}</span></div>}
    {showCreate && <form className="followup-form" onSubmit={(event) => { event.preventDefault(); void run(() => editingId ? api.updateFollowup(editingId, create) : api.createFollowup(create), editingId ? 'Seguimiento actualizado correctamente.' : 'Seguimiento creado. El lote y los nombres de sus muestras se asignarán automáticamente con el formato histórico.') }}>
      {editingId && <div className="edit-warning"><Pencil size={18} /><span>Estás editando un seguimiento existente. Si cambiás la finca, GrapeSense recalculará el clima de todas sus muestras.</span></div>}
      <div className="form-grid"><Field label="Fecha de inicio *"><input type="date" max={today} required value={create.fecha_inicio} onChange={(e) => setCreate({ ...create, fecha_inicio: e.target.value, vendimia: Number(e.target.value.slice(0, 4)) })} /></Field><Field label="Vendimia *"><input type="number" min="2000" max="2100" required value={create.vendimia} onChange={(e) => setCreate({ ...create, vendimia: Number(e.target.value) })} /></Field><Field label="Finca *"><select required value={create.finca_id || ''} onChange={(e) => setCreate({ ...create, finca_id: Number(e.target.value), cuartel_id: null })}>{options?.fincas.map((item) => <option key={item.finca_id} value={item.finca_id}>{item.nombre}</option>)}</select></Field><Field label="Cuartel" hint="Opcional"><select value={create.cuartel_id ?? ''} onChange={(e) => setCreate({ ...create, cuartel_id: e.target.value ? Number(e.target.value) : null })}><option value="">Sin seleccionar</option>{createBlocks.map((item) => <option key={item.cuartel_id} value={item.cuartel_id}>{item.nombre}</option>)}</select></Field><Field label="Variedad *"><select value={create.variedad} onChange={(e) => setCreate({ ...create, variedad: e.target.value })}><option>Malbec</option><option>Syrah</option><option>Cabernet</option></select></Field><Field label="Referencia propia" hint="Opcional"><input placeholder="Ej. Cuartel Norte" value={create.lote_referencia} onChange={(e) => setCreate({ ...create, lote_referencia: e.target.value })} /></Field></div><button className="primary-button" disabled={busy || !create.finca_id}>{busy ? <LoaderCircle className="spin" /> : editingId ? <Pencil size={18} /> : <Plus size={18} />} {editingId ? 'Guardar cambios' : 'Crear seguimiento'}</button>
    </form>}
    <div className="followups-list">{items.map((item) => <div className="followup-row" key={item.seguimiento_id}><div className="followup-code"><strong>{item.codigo}</strong><small>{item.lote_referencia || 'Sin referencia adicional'}</small></div><div><strong>{item.variedad} · {item.finca}</strong><small>{item.cuartel ? `${item.cuartel} · ` : ''}inicio {formatDate(item.fecha_inicio)}</small></div><div><strong>{item.muestras} muestras</strong><small>{item.ultima_medicion ? `Última: ${formatDate(item.ultima_medicion)}` : 'Todavía sin mediciones'}</small></div><div className="followup-actions"><button className="secondary-button" onClick={() => { setAction({ type: 'sample', item }); setShowCreate(false); setEditingId(null); setError(''); setNotice('') }}><Plus size={16} /> Agregar muestra</button><button className="harvest-button" onClick={() => { setAction({ type: 'close', item }); setShowCreate(false); setEditingId(null); setError(''); setNotice('') }}><CheckCircle2 size={16} /> Registrar cosecha</button><button className="icon-button" title="Editar seguimiento" onClick={() => { setCreate({ finca_id: item.finca_id, cuartel_id: item.cuartel_id, variedad: item.variedad, vendimia: item.vendimia, fecha_inicio: item.fecha_inicio, lote_referencia: item.lote_referencia ?? '' }); setEditingId(item.seguimiento_id); setShowCreate(true); setAction(null); setError(''); setNotice('') }}><Pencil size={16} /></button><button className="icon-button danger-button" title="Eliminar seguimiento" disabled={busy} onClick={() => void removeFollowup(item)}><Trash2 size={16} /></button></div></div>)}{!items.length && <div className="pending-empty"><History size={26} /><span><strong>No hay seguimientos pendientes</strong><small>Creá uno para comenzar a registrar las mediciones semanales sin administrar IDs manualmente.</small></span></div>}</div>
    {action && <form className="followup-action-form" onSubmit={(event) => { event.preventDefault(); void (action.type === 'sample' ? run(() => api.addFollowupSample(action.item.seguimiento_id, measurement), `Muestra agregada a ${action.item.codigo}. Los días hasta cosecha quedan pendientes.`) : run(() => api.closeFollowup(action.item.seguimiento_id, harvest), `Cosecha registrada. Se completaron los días restantes de todo ${action.item.codigo}.`)) }}><div className="action-title"><div><strong>{action.type === 'sample' ? 'Nueva medición semanal' : 'Cierre con cosecha efectiva'}</strong><small>{action.item.codigo} · {action.item.variedad} · {action.item.finca}</small></div><button type="button" className="icon-button" onClick={() => setAction(null)}><X size={18} /></button></div>{action.type === 'sample' ? <div className="action-fields"><Field label="Fecha de medición"><input type="date" max={today} required value={measurement.fecha_medicion} onChange={(e) => setMeasurement({ ...measurement, fecha_medicion: e.target.value })} /></Field><ChemistryFields value={measurement} setValue={setMeasurement} /></div> : <><div className="close-note"><Info size={18} /> Al cerrar, GrapeSense calcula los días hasta cosecha de todas las mediciones anteriores y actualiza su clima con los datos disponibles.</div><div className="action-fields"><Field label="Fecha efectiva de cosecha"><input type="date" max={today} required value={harvest.fecha_cosecha} onChange={(e) => setHarvest({ ...harvest, fecha_cosecha: e.target.value })} /></Field><ChemistryFields value={harvest} setValue={setHarvest} /></div></>}<button className="primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : action.type === 'sample' ? <Plus size={18} /> : <CheckCircle2 size={18} />}{busy ? 'Consultando clima...' : action.type === 'sample' ? 'Guardar muestra pendiente' : 'Registrar cosecha y completar seguimiento'}</button></form>}
  </section>
}

function ChemistryFields<T extends { brix: number; ph: number; acidez_total_g_l: number }>({ value, setValue }: { value: T; setValue: (value: T) => void }) {
  return <><Field label="Brix"><input type="number" min="10" max="35" step="0.1" required value={value.brix} onChange={(e) => setValue({ ...value, brix: Number(e.target.value) })} /></Field><Field label="pH"><input type="number" min="2.5" max="4.5" step="0.01" required value={value.ph} onChange={(e) => setValue({ ...value, ph: Number(e.target.value) })} /></Field><Field label="Acidez total" hint="g/L ácido tartárico"><input type="number" min="2" max="20" step="0.1" required value={value.acidez_total_g_l} onChange={(e) => setValue({ ...value, acidez_total_g_l: Number(e.target.value) })} /></Field></>
}

function ImportSamples({ options, onImported }: { options: AppOptions | null; onImported: () => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [fincaId, setFincaId] = useState(0)
  const [cuartelId, setCuartelId] = useState<number | null>(null)
  const [csvText, setCsvText] = useState('')
  const [filename, setFilename] = useState('')
  const [overwrite, setOverwrite] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SampleImportResult | null>(null)
  useEffect(() => {
    if (!fincaId && options?.fincas.length) setFincaId(options.fincas[0].finca_id)
  }, [options, fincaId])
  const blocks = options?.cuarteles.filter((item) => item.finca_id === fincaId) ?? []
  const rowCount = csvText.trim() ? Math.max(0, csvText.trim().split(/\r?\n/).length - 1) : 0

  function downloadTemplate() {
    const header = ['muestra_id', 'lote_id', 'vendimia', 'fecha_medicion', 'tipo_muestra', 'numero_muestra', 'variedad', 'Brix', 'pH', 'acidez_total_g_l', 'fecha_cosecha_efectiva', 'dias_hasta_cosecha']
    const example = ['M-2026-001', 'LOTE-01', '2026', '2026-02-05', 'seguimiento', '1', 'Malbec', '17.4', '3.18', '8.2', '2026-03-03', '26']
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([`${header.join(',')}\n${example.join(',')}\n`], { type: 'text/csv;charset=utf-8' }))
    link.download = 'plantilla_muestras_grapesense.csv'; link.click(); URL.revokeObjectURL(link.href)
  }
  async function chooseFile(file?: File) {
    setError(''); setResult(null)
    if (!file) return
    if (file.size > 2_000_000) { setError('El archivo supera el límite de 2 MB.'); return }
    setFilename(file.name); setCsvText(await file.text())
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setResult(null)
    try {
      const response = await api.importSamples({ finca_id: fincaId, cuartel_id: cuartelId, csv_text: csvText, sobrescribir: overwrite })
      setResult(response); await onImported()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudieron importar las muestras') }
    finally { setBusy(false) }
  }
  return <section className={`panel import-panel ${open ? 'open' : ''}`}>
    <div className="import-heading"><div><span className="icon-box"><Upload size={20} /></span><div><h2>Cargar nuevas muestras</h2><p>Guarda datos propios de la bodega y completa automáticamente el clima histórico.</p></div></div><div><button className="secondary-button" onClick={downloadTemplate}><FileDown size={17} /> Descargar plantilla</button><button className="primary-button compact" onClick={() => setOpen(!open)}><Upload size={17} /> {open ? 'Cerrar' : 'Importar CSV'}</button></div></div>
    {open && <form className="import-form" onSubmit={submit}>
      <div className="import-instructions"><Info size={18} /><p><strong>Una fila por medición.</strong> La muestra final debe usar <code>tipo_muestra=cosecha</code>. Podés informar la fecha efectiva de cosecha para calcular automáticamente los días restantes. El modelo no se reentrena al importar.</p></div>
      <div className="import-fields"><Field label="Finca *"><select required value={fincaId || ''} onChange={(e) => { setFincaId(Number(e.target.value)); setCuartelId(null) }}>{options?.fincas.map((item) => <option key={item.finca_id} value={item.finca_id}>{item.nombre}</option>)}</select></Field><Field label="Cuartel" hint="Opcional"><select value={cuartelId ?? ''} onChange={(e) => setCuartelId(e.target.value ? Number(e.target.value) : null)}><option value="">Sin seleccionar</option>{blocks.map((item) => <option key={item.cuartel_id} value={item.cuartel_id}>{item.nombre}</option>)}</select></Field><Field label="Archivo CSV *"><input type="file" accept=".csv,text/csv" required={!csvText} onChange={(e) => void chooseFile(e.target.files?.[0])} /></Field></div>
      {filename && <div className="file-ready"><CheckCircle2 size={18} /><span><strong>{filename}</strong>{rowCount} filas detectadas · máximo 250 por carga</span></div>}
      <label className="check-row"><input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} /><span><strong>Actualizar coincidencias existentes</strong><small>Busca por ID de muestra o por lote, vendimia y fecha. Si no se activa, las coincidencias se omiten.</small></span></label>
      {error && <div className="alert error import-error"><AlertTriangle size={18} /><span>{error}</span></div>}
      {result && <div className="import-result"><CheckCircle2 /><div><strong>Importación completada</strong><p>{result.insertadas} insertadas · {result.actualizadas} actualizadas · {result.omitidas} omitidas.</p>{result.fechas_con_pronostico > 0 && <small>{result.fechas_con_pronostico} fechas recientes usaron pronóstico operativo; conviene actualizarlas cuando el período sea histórico.</small>}</div></div>}
      <button className="primary-button" type="submit" disabled={busy || !csvText || !fincaId}>{busy ? <LoaderCircle className="spin" /> : <Upload size={18} />}{busy ? 'Validando y consultando clima...' : `Importar ${rowCount || ''} muestras`}</button>
    </form>}
  </section>
}

function SamplesPage({ summary, user, options, refreshSummary }: { summary: SampleSummary | null; user: User; options: AppOptions | null; refreshSummary: () => Promise<void> }) {
  const [filters, setFilters] = useState<SampleFilters>({})
  const [samples, setSamples] = useState<Sample[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<Sample | null>(null)
  const [deleting, setDeleting] = useState('')
  const limit = 100
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { const result = await api.getSamples(filters, limit, offset); setSamples(result.items); setTotal(result.total) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudieron consultar las muestras') }
    finally { setLoading(false) }
  }, [filters, offset])
  useEffect(() => { void load() }, [load])
  function update(key: keyof SampleFilters, value: string) { setOffset(0); setFilters((current) => ({ ...current, [key]: value })) }
  async function exportSamples() { const result = await api.exportSamples(filters); const columns = Object.keys(result.items[0] ?? {}) as (keyof Sample)[]; downloadRows(result.items, columns, 'muestras_uva_entrenamiento.csv') }
  async function imported() { await refreshSummary(); if (offset === 0) await load(); else setOffset(0) }
  async function remove(item: Sample) {
    if (!window.confirm(`¿Eliminar definitivamente la muestra ${item.muestra_id}?\n\nEsta acción no se puede deshacer.`)) return
    setDeleting(item.muestra_id); setError(''); setNotice('')
    try {
      const result = await api.deleteSample(item.muestra_id)
      setNotice(result.seguimiento_reabierto
        ? `Se eliminó ${result.eliminada}. Como era la cosecha final, el seguimiento volvió a quedar pendiente.`
        : `Se eliminó ${result.eliminada} correctamente.`)
      await imported()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo eliminar la muestra') }
    finally { setDeleting('') }
  }
  async function saved() {
    setEditing(null); setNotice('La muestra fue actualizada correctamente.'); await imported()
  }
  const canManage = true
  return <>
    <FollowupsPanel options={options} onChanged={imported} />
    <ImportSamples options={options} onImported={imported} />
    <section className="stats-grid sample-stats"><Stat icon={<Database />} label="Muestras registradas" value={summary?.total_muestras ?? '—'} /><Stat icon={<Layers3 />} label="Lotes" value={summary?.total_lotes ?? '—'} /><Stat icon={<CheckCircle2 />} label="Muestras de cosecha" value={summary?.muestras_cosecha ?? '—'} /><Stat icon={<CalendarDays />} label="Vendimias disponibles" value={summary?.por_vendimia.map((row) => row.vendimia).join(', ') || '—'} /></section>
    <section className="panel samples-panel">
      <PanelHeading icon={<Database size={20} />} title="Muestras de uva" subtitle={`${total} registros coinciden con los filtros`} aside="Base de evidencia de la bodega" />
      <div className="filter-grid"><SearchBox value={filters.search ?? ''} setValue={(value) => update('search', value)} placeholder="Buscar lote o ID de muestra" /><select value={filters.vendimia ?? ''} onChange={(e) => update('vendimia', e.target.value)}><option value="">Todas las vendimias</option>{summary?.por_vendimia.map((row) => <option key={row.vendimia}>{row.vendimia}</option>)}</select><select value={filters.variedad ?? ''} onChange={(e) => update('variedad', e.target.value)}><option value="">Todas las variedades</option>{summary?.variedades.map((value) => <option key={value}>{value}</option>)}</select><select value={filters.vinedo ?? ''} onChange={(e) => update('vinedo', e.target.value)}><option value="">Todos los viñedos</option>{summary?.vinedos.map((value) => <option key={value}>{value}</option>)}</select><select value={filters.tipo_muestra ?? ''} onChange={(e) => update('tipo_muestra', e.target.value)}><option value="">Todos los tipos</option><option value="seguimiento">Seguimiento</option><option value="cosecha">Cosecha</option></select><button className="secondary-button" onClick={() => void exportSamples()} disabled={!total}><Download size={18} /> Exportar filtradas</button></div>
      {notice && <div className="alert success sample-message"><CheckCircle2 size={18} /><span>{notice}</span></div>}
      {error && <div className="alert error sample-message"><AlertTriangle size={18} /><span>{error}</span></div>}
      <div className="table-wrap samples-table"><table><thead><tr><th>Fecha</th><th>Muestra / Lote</th><th>Origen</th><th>Etapa</th><th>Química</th><th>Clima pasado</th><th>Días a cosecha</th>{canManage && <th>Acciones</th>}</tr></thead><tbody>{samples.map((item) => <tr key={item.muestra_id}><td>{formatDate(item.fecha_medicion)}</td><td><strong>{item.muestra_id}</strong><small>{item.lote_id}</small></td><td><strong>{item.variedad}</strong><small>{item.vinedo} · {item.vendimia}</small></td><td><span className={`type-pill ${item.tipo_muestra}`}>{item.tipo_muestra}</span><small>Muestra {item.numero_muestra}</small></td><td><span>{item.Brix.toFixed(1)} Brix · pH {item.pH.toFixed(2)}</span><small>Acidez {item.acidez_total_g_l.toFixed(1)} g/L</small></td><td><span>{item.pasado_tavg_7d.toFixed(1)} °C · {item.pasado_prcp_sum_7d.toFixed(1)} mm</span><small>Radiación {item.pasado_radiacion_sum_7d.toFixed(1)} MJ/m²</small></td><td><strong>{item.dias_hasta_cosecha ?? '—'}</strong></td>{canManage && <td><div className="row-actions"><button className="icon-button" title="Editar muestra" onClick={() => { setEditing(item); setNotice(''); setError('') }}><Pencil size={16} /></button><button className="icon-button danger-button" title="Eliminar muestra" disabled={deleting === item.muestra_id} onClick={() => void remove(item)}>{deleting === item.muestra_id ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />}</button></div></td>}</tr>)}</tbody></table>{loading && <div className="table-loading"><LoaderCircle className="spin" /> Cargando muestras...</div>}{!loading && !samples.length && <EmptyData text="No hay muestras que coincidan con los filtros." />}</div>
      <div className="pagination"><span>Mostrando {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} de {total}</span><div><button className="icon-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}><ChevronLeft /></button><button className="icon-button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}><ChevronRight /></button></div></div>
    </section>
    {editing && <SampleEditSheet key={editing.muestra_id} item={editing} close={() => setEditing(null)} saved={saved} />}
  </>
}

function SampleEditSheet({ item, close, saved }: { item: Sample; close: () => void; saved: () => Promise<void> }) {
  const [form, setForm] = useState({ fecha_medicion: item.fecha_medicion, brix: item.Brix, ph: item.pH, acidez_total_g_l: item.acidez_total_g_l })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { await api.updateSample(item.muestra_id, form); await saved() }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo editar la muestra') }
    finally { setBusy(false) }
  }
  return <div className="sheet-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) close() }}><aside className="sheet sample-edit-sheet"><div className="sheet-header"><div><small>EDITAR MUESTRA</small><h2>{item.muestra_id}</h2><p>{item.lote_id} · {item.variedad} · {item.vinedo}</p></div><button className="icon-button" disabled={busy} onClick={close}><X /></button></div><form onSubmit={submit}><div className="edit-warning"><Info size={18} /><span>Si corregís la fecha, GrapeSense vuelve a consultar el clima. En un seguimiento también actualizará automáticamente el nombre de la muestra.</span></div><Field label="Fecha de medición"><input type="date" max={today} required value={form.fecha_medicion} onChange={(e) => setForm({ ...form, fecha_medicion: e.target.value })} /></Field><ChemistryFields value={form} setValue={setForm} />{error && <div className="alert error"><AlertTriangle size={18} /><span>{error}</span></div>}<button className="primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <CheckCircle2 size={18} />}{busy ? 'Guardando...' : 'Guardar cambios'}</button></form></aside></div>
}

function ModelPage({ analysis }: { analysis: ModelAnalysis | null }) {
  if (!analysis) return <section className="panel model-loading"><LoaderCircle className="spin" /><h2>Preparando el análisis del modelo</h2><p>Cargando el modelo activo y su evaluación para esta bodega.</p></section>
  const metrics = analysis.evaluacion
  const topVariables = analysis.importancia_variables.slice(0, 10)
  return <div className="model-page">
    <section className="model-hero"><div><span className="model-badge"><Microscope size={17} /> MODELO ACTIVO · {analysis.modelo.bodega}</span><h2>{analysis.modelo.nombre}</h2><p><strong>Objetivo:</strong> {analysis.modelo.objetivo}. Entrenado con vendimias {analysis.modelo.vendimias_entrenamiento.join(' y ')}.</p></div><div className="model-meta"><span><small>Variables</small><strong>{analysis.modelo.variables}</strong></span><span><small>Entrenamiento</small><strong>{analysis.datos.entrenamiento_muestras}</strong></span><span><small>Evaluación</small><strong>{analysis.datos.evaluacion_muestras}</strong></span></div></section>
    <section className="stats-grid model-stats"><Stat icon={<TrendingUp />} label={`Error medio · ${analysis.datos.evaluacion_etiqueta}`} value={`${metrics.mae_dias} días`} /><Stat icon={<CheckCircle2 />} label="Dentro de ±3 días" value={`${metrics.dentro_3_dias_porcentaje}%`} /><Stat icon={<CheckCircle2 />} label="Dentro de ±4 días" value={`${metrics.dentro_4_dias_porcentaje}%`} /><Stat icon={<BarChart3 />} label="Sesgo promedio" value={`${metrics.sesgo_dias > 0 ? '+' : ''}${metrics.sesgo_dias} días`} /></section>
    <section className="panel interpretation-panel">
      <div className="interpretation-heading"><span><Grape size={22} /></span><div><h3>Química y clima cumplen funciones diferentes</h3><p>Cómo interpretar correctamente la importancia de las variables.</p></div></div>
      <div className="interpretation-grid">
        <div><strong>La química representa el estado actual</strong><p>Brix, pH y acidez resumen hasta dónde llegó la maduración de la uva al momento de tomar la muestra. Parte del efecto del clima pasado ya quedó reflejado en esas mediciones.</p></div>
        <div><strong>El clima representa la velocidad esperada de evolución</strong><p>Temperatura, lluvia y radiación ayudan a estimar cómo puede continuar la maduración durante los días siguientes, especialmente al actualizar la predicción cada semana.</p></div>
      </div>
      <p className="interpretation-note"><Info size={17} /> Una importancia climática baja no significa que el clima no afecte la uva. Significa que, con el objetivo y los datos actuales, gran parte de esa información llega al modelo indirectamente a través de Brix, pH y acidez.</p>
    </section>
    <div className="model-grid">
      <ChartPanel title="Importancia por grupo" subtitle="Cuánto utiliza el modelo cada familia de información"><ResponsiveContainer width="100%" height={300}><BarChart data={analysis.importancia_grupos} layout="vertical" margin={{ left: 15, right: 25 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" unit="%" /><YAxis type="category" dataKey="grupo" width={155} tick={{ fontSize: 12 }} /><Tooltip formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Importancia']} /><Bar dataKey="importancia_porcentaje" radius={[0, 5, 5, 0]}>{analysis.importancia_grupos.map((_, index) => <Cell key={index} fill={palette[index % palette.length]} />)}</Bar></BarChart></ResponsiveContainer></ChartPanel>
      <ChartPanel title="Error según anticipación" subtitle={`MAE en ${analysis.datos.evaluacion_etiqueta}, separado por días reales restantes`}><ResponsiveContainer width="100%" height={300}><BarChart data={analysis.rendimiento_por_anticipacion}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="rango" tick={{ fontSize: 12 }} /><YAxis unit=" d" /><Tooltip formatter={(value) => [`${value} días`, 'MAE']} /><Bar dataKey="mae_dias" fill="#c6953e" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></ChartPanel>
      <ChartPanel title="Variables más utilizadas" subtitle="Importancia interna del Gradient Boosting"><ResponsiveContainer width="100%" height={380}><BarChart data={topVariables} layout="vertical" margin={{ left: 20, right: 25 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" unit="%" /><YAxis type="category" dataKey="etiqueta" width={170} tick={{ fontSize: 12 }} /><Tooltip formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Importancia']} /><Bar dataKey="importancia_porcentaje" fill="#255c42" radius={[0, 5, 5, 0]} /></BarChart></ResponsiveContainer></ChartPanel>
      <ChartPanel title="Días reales frente a predichos" subtitle={`Cada punto pertenece a ${analysis.datos.evaluacion_etiqueta}`}><ResponsiveContainer width="100%" height={380}><ScatterChart margin={{ top: 15, right: 20, bottom: 15, left: 5 }}><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" dataKey="real" name="Real" unit=" d" domain={[0, 'auto']} /><YAxis type="number" dataKey="predicho" name="Predicho" unit=" d" domain={[0, 'auto']} /><Tooltip cursor={{ strokeDasharray: '3 3' }} /><Legend /><ReferenceLine segment={[{ x: 0, y: 0 }, { x: 35, y: 35 }]} stroke="#c6953e" strokeDasharray="5 5" /><Scatter name={analysis.datos.evaluacion_etiqueta} data={analysis.comparacion} fill="#255c42" fillOpacity={0.68} /></ScatterChart></ResponsiveContainer></ChartPanel>
    </div>
    <section className="panel horizon-panel"><PanelHeading icon={<TrendingUp size={20} />} title="Rendimiento por anticipación" subtitle="Permite ver en qué etapa es más confiable la estimación" /><div className="table-wrap"><table><thead><tr><th>Días reales restantes</th><th>Muestras</th><th>Error medio</th><th>Dentro de ±3 días</th><th>Dentro de ±4 días</th><th>Sesgo</th></tr></thead><tbody>{analysis.rendimiento_por_anticipacion.map((row) => <tr key={row.rango}><td><strong>{row.rango}</strong></td><td>{row.muestras}</td><td>{row.mae_dias} días</td><td>{row.dentro_3_dias_porcentaje}%</td><td>{row.dentro_4_dias_porcentaje}%</td><td>{row.sesgo_dias > 0 ? '+' : ''}{row.sesgo_dias} días</td></tr>)}</tbody></table></div></section>
    <section className="evidence-grid"><div className="panel info-panel"><Info /><div><h3>Cómo leer la importancia</h3><p>Una importancia alta significa que el modelo recurre mucho a esa variable para dividir casos. No indica que esa variable cause por sí sola la fecha de cosecha. Las variables correlacionadas pueden repartirse la importancia.</p></div></div><div className="panel data-panel"><Database /><div><h3>Origen de la evidencia</h3><p>{analysis.datos.entrenamiento_muestras} muestras de entrenamiento y {analysis.datos.evaluacion_muestras} mediciones de {analysis.datos.evaluacion_lotes} lotes reservados. Uva: {analysis.datos.origen_uva.toLowerCase()}. Clima: {analysis.datos.origen_clima.toLowerCase()}.</p></div></div></section>
    <section className="panel warning-panel"><div className="warning-title"><AlertTriangle /><div><h3>Límites que debe conocer el enólogo</h3><p>El modelo es apoyo a la decisión, no una orden automática de cosecha.</p></div></div><ul>{analysis.advertencias.map((warning) => <li key={warning}>{warning}</li>)}</ul></section>
  </div>
}

function AdminPage({ user, refreshOptions, onModelChanged }: { user: User; refreshOptions: () => Promise<void>; onModelChanged: () => void }) {
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [modelReadiness, setModelReadiness] = useState<ModelReadiness | null>(null)
  const [wineries, setWineries] = useState<{ bodega_id: number; nombre: string; slug: string; activa: boolean; usuarios: number; fincas: number }[]>([])
  const [farm, setFarm] = useState({ nombre: '', latitud: -33.0, longitud: -68.85 })
  const [member, setMember] = useState({ nombre: '', email: '', password: '', rol: 'usuario' })
  const [editingFarm, setEditingFarm] = useState<number | null>(null)
  const [editingUser, setEditingUser] = useState<number | null>(null)
  const [winery, setWinery] = useState({ nombre: '', admin_nombre: '', admin_email: '', admin_password: '' })
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const [current, readiness] = await Promise.all([api.getOrganization(), api.getModelReadiness()])
      setOrganization(current)
      setModelReadiness(readiness)
      if (user.rol === 'superadmin') setWineries((await api.getWineries()).items)
      setError('')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo cargar la administración') }
  }, [user.rol])

  useEffect(() => { void load() }, [load])

  async function run(name: string, action: () => Promise<unknown>, success: string) {
    setBusy(name); setError(''); setNotice('')
    try { await action(); setNotice(success); await Promise.all([load(), refreshOptions()]); return true }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo guardar'); return false }
    finally { setBusy('') }
  }

  async function removeFarm(item: Organization['fincas'][number]) {
    if (!window.confirm(`¿Eliminar la finca ${item.nombre}?\n\nDejará de estar disponible para nuevas operaciones. Si tiene datos históricos, esos registros se conservarán.`)) return
    await run('delete-farm', () => api.deleteFarm(item.finca_id), `Se eliminó la finca ${item.nombre}.`)
  }

  async function removeMember(item: Organization['usuarios'][number]) {
    if (!window.confirm(`¿Eliminar el acceso de ${item.nombre}?\n\nLa persona ya no podrá ingresar a GrapeSense.`)) return
    await run('delete-user', () => api.deleteUser(item.usuario_id), `Se eliminó el usuario ${item.nombre}.`)
  }

  async function submitFarm() {
    const ok = await run(
      'farm',
      () => editingFarm ? api.updateFarm(editingFarm, farm) : api.createFarm(farm),
      editingFarm ? 'Finca actualizada correctamente.' : 'Finca agregada correctamente.',
    )
    if (ok) { setFarm({ nombre: '', latitud: -33.0, longitud: -68.85 }); setEditingFarm(null) }
  }

  async function submitMember() {
    const role = member.rol === 'superadmin' ? 'admin' : member.rol
    const ok = await run(
      'user',
      () => editingUser
        ? api.updateUser(editingUser, { ...member, rol: role, password: member.password || null })
        : api.createUser({ ...member, rol: role }),
      editingUser ? 'Usuario actualizado correctamente.' : 'Usuario creado correctamente.',
    )
    if (ok) {
      const editedSelf = editingUser === user.usuario_id
      setMember({ nombre: '', email: '', password: '', rol: 'usuario' }); setEditingUser(null)
      if (editedSelf) window.location.reload()
    }
  }

  async function trainModel() {
    if (!window.confirm(`¿Entrenar un nuevo modelo candidato para ${organization?.bodega.nombre ?? user.bodega_nombre}?\n\nGrapeSense dividirá automáticamente los lotes y no reemplazará el modelo activo.`)) return
    const ok = await run('train-model', () => api.trainModel(), 'El nuevo modelo candidato fue entrenado y quedó pendiente de revisión.')
    if (ok) onModelChanged()
  }

  async function activateModel(item: Organization['modelos'][number]) {
    if (!window.confirm(`¿Activar ${item.nombre}?\n\nLas nuevas predicciones y el análisis de esta bodega utilizarán esta versión.`)) return
    const ok = await run('activate-model', () => api.activateModel(item.modelo_bodega_id), `Se activó ${item.nombre}.`)
    if (ok) onModelChanged()
  }

  return <div className="admin-page">
    <section className="admin-overview">
      <div><span className="model-badge"><ShieldCheck size={17} /> ESPACIO AISLADO</span><h2>{organization?.bodega.nombre ?? user.bodega_nombre}</h2><p>Los usuarios sólo acceden a las muestras, predicciones y fincas de esta organización.</p></div>
      <div className="admin-counts"><span><small>Fincas</small><strong>{organization?.fincas.length ?? '—'}</strong></span><span><small>Usuarios</small><strong>{organization?.usuarios.length ?? '—'}</strong></span><span><small>Modelos</small><strong>{organization?.modelos.length ?? '—'}</strong></span></div>
    </section>
    {notice && <div className="alert success"><CheckCircle2 size={18} /><span>{notice}</span></div>}
    {error && <div className="alert error"><AlertTriangle size={18} /><span>{error}</span></div>}
    <div className="admin-grid">
      <section className="panel admin-panel"><PanelHeading icon={<MapPinned size={20} />} title="Fincas" subtitle="La ubicación determina el clima consultado" />
        <form onSubmit={(event) => { event.preventDefault(); void submitFarm() }}>
          {editingFarm && <div className="editing-label"><Pencil size={15} /> Editando finca</div>}<Field label="Nombre"><input required value={farm.nombre} onChange={(e) => setFarm({ ...farm, nombre: e.target.value })} /></Field><div className="inline-fields"><Field label="Latitud"><input type="number" step="0.000001" required value={farm.latitud} onChange={(e) => setFarm({ ...farm, latitud: Number(e.target.value) })} /></Field><Field label="Longitud"><input type="number" step="0.000001" required value={farm.longitud} onChange={(e) => setFarm({ ...farm, longitud: Number(e.target.value) })} /></Field></div><div className="form-actions"><button className="secondary-button" disabled={busy === 'farm'}>{busy === 'farm' ? <LoaderCircle className="spin" /> : editingFarm ? <Pencil size={17} /> : <Plus size={17} />}{editingFarm ? 'Guardar finca' : 'Agregar finca'}</button>{editingFarm && <button type="button" className="text-button" onClick={() => { setEditingFarm(null); setFarm({ nombre: '', latitud: -33.0, longitud: -68.85 }) }}>Cancelar</button>}</div>
        </form><div className="compact-list">{organization?.fincas.map((item) => <div key={item.finca_id}><MapPin size={17} /><span><strong>{item.nombre}</strong><small>{item.latitud.toFixed(5)}, {item.longitud.toFixed(5)}</small></span><div className="compact-actions"><button className="icon-button" title="Editar finca" onClick={() => { setEditingFarm(item.finca_id); setFarm({ nombre: item.nombre, latitud: item.latitud, longitud: item.longitud }); setNotice(''); setError('') }}><Pencil size={15} /></button><button className="icon-button danger-button" title="Eliminar finca" onClick={() => void removeFarm(item)}><Trash2 size={15} /></button></div></div>)}</div><p className="admin-help"><Info size={17} /> Al eliminar una finca deja de estar disponible para nuevas operaciones. Si tiene historial, GrapeSense lo conserva para mantener la trazabilidad.</p>
      </section>
      <section className="panel admin-panel"><PanelHeading icon={<Users size={20} />} title="Equipo" subtitle="Accesos y permisos dentro de la bodega" />
        <form onSubmit={(event) => { event.preventDefault(); void submitMember() }}>
          {editingUser && <div className="editing-label"><Pencil size={15} /> Editando usuario</div>}<div className="inline-fields"><Field label="Nombre"><input required value={member.nombre} onChange={(e) => setMember({ ...member, nombre: e.target.value })} /></Field><Field label="Rol"><select disabled={member.rol === 'superadmin'} value={member.rol} onChange={(e) => setMember({ ...member, rol: e.target.value })}>{member.rol === 'superadmin' && <option value="superadmin">Administrador de plataforma</option>}<option value="admin">Administrador de bodega</option><option value="usuario">Usuario de bodega</option></select></Field></div><Field label="Correo"><input type="email" required value={member.email} onChange={(e) => setMember({ ...member, email: e.target.value })} /></Field><Field label="Contraseña" hint={editingUser ? 'Dejar vacía para conservarla' : 'Mínimo 10 caracteres'}><input type="password" minLength={10} required={!editingUser} value={member.password} onChange={(e) => setMember({ ...member, password: e.target.value })} /></Field><div className="form-actions"><button className="secondary-button" disabled={busy === 'user'}>{busy === 'user' ? <LoaderCircle className="spin" /> : editingUser ? <Pencil size={17} /> : <Plus size={17} />}{editingUser ? 'Guardar usuario' : 'Crear usuario'}</button>{editingUser && <button type="button" className="text-button" onClick={() => { setEditingUser(null); setMember({ nombre: '', email: '', password: '', rol: 'usuario' }) }}>Cancelar</button>}</div>
        </form><div className="compact-list">{organization?.usuarios.map((item) => <div key={item.usuario_id}><Users size={17} /><span><strong>{item.nombre} · {roleLabel(item.rol)}</strong><small>{item.email}</small></span><div className="compact-actions"><button className="icon-button" title="Editar usuario" onClick={() => { setEditingUser(item.usuario_id); setMember({ nombre: item.nombre, email: item.email, password: '', rol: item.rol }); setNotice(''); setError('') }}><Pencil size={15} /></button><button className="icon-button danger-button" title="Eliminar usuario" disabled={item.usuario_id === user.usuario_id || item.rol === 'superadmin'} onClick={() => void removeMember(item)}><Trash2 size={15} /></button></div></div>)}</div><p className="admin-help"><Info size={17} /> El administrador gestiona su bodega y sus usuarios. El usuario de bodega trabaja con muestras, seguimientos, predicciones y análisis. La cuenta del administrador de plataforma está protegida contra eliminación.</p>
      </section>
      <section className="panel admin-panel model-management"><PanelHeading icon={<Microscope size={20} />} title="Modelos de la bodega" subtitle="Entrenamiento automático desde PostgreSQL" />
        {modelReadiness && <div className="training-summary"><div><small>Muestras utilizables</small><strong>{modelReadiness.muestras}</strong></div><div><small>Lotes completos</small><strong>{modelReadiness.lotes}</strong></div><div><small>Vendimias</small><strong>{modelReadiness.vendimias.join(', ') || '—'}</strong></div></div>}
        {modelReadiness?.puede_entrenar ? <div className="split-preview"><strong>División automática</strong><p>{modelReadiness.politica}.</p><small>{modelReadiness.entrenamiento_muestras} mediciones para entrenar · {modelReadiness.evaluacion_muestras} para evaluar · sin compartir lotes.</small></div> : <div className="split-preview unavailable"><strong>Entrenamiento no disponible</strong><p>{modelReadiness?.motivo ?? 'Revisando los datos disponibles.'}</p></div>}
        {user.rol === 'superadmin' && <button className="secondary-button train-button" disabled={busy === 'train-model' || !modelReadiness?.puede_entrenar} onClick={() => void trainModel()}>{busy === 'train-model' ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}{busy === 'train-model' ? 'Entrenando...' : 'Entrenar nuevo candidato'}</button>}
        <div className="compact-list model-list">{organization?.modelos.map((item) => <div key={item.modelo_bodega_id}><Microscope size={17} /><span><strong>{item.nombre}</strong><small>Versión {item.version} · vendimias {item.vendimias_entrenamiento || 'sin registrar'}</small>{item.metricas && <small>MAE {Number(item.metricas.mae_dias).toFixed(2)} días · ±4 días {Number(item.metricas.dentro_4_dias_porcentaje).toFixed(1)}%</small>}</span><div className="model-actions"><b className={item.activo ? 'active-model' : ''}>{item.activo ? 'Activo' : 'Candidato'}</b>{user.rol === 'superadmin' && !item.activo && <button className="text-button" disabled={busy === 'activate-model'} onClick={() => void activateModel(item)}>Activar</button>}</div></div>)}</div><p className="admin-help"><Info size={17} /> El entrenamiento usa las muestras con cosecha efectiva de esta bodega. Sólo el administrador de plataforma puede crear o activar modelos; el administrador de bodega puede revisar los resultados.</p>
      </section>
    </div>
    {user.rol === 'superadmin' && <section className="panel platform-admin"><PanelHeading icon={<Building2 size={20} />} title="Organizaciones de la plataforma" subtitle="Cada organización representa una bodega independiente dentro de GrapeSense" />
      <form className="winery-form" onSubmit={(event) => { event.preventDefault(); void run('winery', () => api.createWinery(winery), 'Nueva bodega creada correctamente.').then(() => setWinery({ nombre: '', admin_nombre: '', admin_email: '', admin_password: '' })) }}><Field label="Bodega"><input required value={winery.nombre} onChange={(e) => setWinery({ ...winery, nombre: e.target.value })} /></Field><Field label="Administrador"><input required value={winery.admin_nombre} onChange={(e) => setWinery({ ...winery, admin_nombre: e.target.value })} /></Field><Field label="Correo"><input type="email" required value={winery.admin_email} onChange={(e) => setWinery({ ...winery, admin_email: e.target.value })} /></Field><Field label="Contraseña"><input type="password" minLength={10} required value={winery.admin_password} onChange={(e) => setWinery({ ...winery, admin_password: e.target.value })} /></Field><button className="primary-button" disabled={busy === 'winery'}><Plus size={18} /> Crear bodega</button></form>
      <p className="platform-help"><Info size={17} /> Este apartado sólo aparece para el administrador de plataforma. Permite incorporar otra bodega y crear su primer administrador; sus muestras, fincas, usuarios y predicciones quedan separadas de las demás.</p><div className="table-wrap"><table><thead><tr><th>Organización</th><th>Identificador</th><th>Usuarios</th><th>Fincas</th><th>Estado</th></tr></thead><tbody>{wineries.map((item) => <tr key={item.bodega_id}><td><strong>{item.nombre}</strong></td><td>{item.slug}</td><td>{item.usuarios}</td><td>{item.fincas}</td><td>{item.activa ? 'Activa' : 'Inactiva'}</td></tr>)}</tbody></table></div>
    </section>}
  </div>
}
