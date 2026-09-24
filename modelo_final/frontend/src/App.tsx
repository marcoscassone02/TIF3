import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, BarChart3, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight,
  CloudSun, Database, Download, Eye, FlaskConical, Grape, History, Info, Layers3,
  LoaderCircle, MapPin, Microscope, Plus, Search, Sparkles, TrendingUp, X,
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  api, ModelAnalysis, Prediction, PredictionInput, PredictionResult, Sample,
  SampleFilters, SampleSummary, Summary,
} from './api'

type View = 'prediction' | 'predictions' | 'samples' | 'model'

const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Argentina/Mendoza' })
const initialForm: PredictionInput = {
  fecha_medicion: today, variedad: 'Malbec', vinedo: 'Agrelo', brix: 18,
  ph: 3.2, acidez_total_g_l: 8, lote_id: '', muestra_id: '', notas: '',
}
const palette = ['#255c42', '#c6953e', '#5b7f70', '#8b6545']

function formatDate(value: string | null, withTime = false) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('es-AR', withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { day: '2-digit', month: 'short', year: 'numeric' },
  ).format(new Date(value.includes('T') ? value : `${value}T12:00:00`))
}

function downloadRows<T extends Record<string, unknown>>(rows: T[], columns: (keyof T)[], filename: string) {
  const escape = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const csv = [columns.join(','), ...rows.map((row) => columns.map((key) => escape(row[key])).join(','))].join('\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }))
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export default function App() {
  const [view, setView] = useState<View>('prediction')
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [sampleSummary, setSampleSummary] = useState<SampleSummary | null>(null)
  const [analysis, setAnalysis] = useState<ModelAnalysis | null>(null)
  const [globalError, setGlobalError] = useState('')
  const [initialLoading, setInitialLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [history, stats, samples] = await Promise.all([
        api.getPredictions(), api.getSummary(), api.getSampleSummary(),
      ])
      setPredictions(history.items)
      setSummary(stats)
      setSampleSummary(samples)
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
  }

  return (
    <div className="app-shell">
      <Sidebar view={view} setView={setView} />
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
        {view === 'prediction' && <PredictionPage predictions={predictions} summary={summary} loading={initialLoading} refresh={refresh} goHistory={() => setView('predictions')} />}
        {view === 'predictions' && <PredictionsPage predictions={predictions} loading={initialLoading} />}
        {view === 'samples' && <SamplesPage summary={sampleSummary} />}
        {view === 'model' && <ModelPage analysis={analysis} />}
      </main>
    </div>
  )
}

function Sidebar({ view, setView }: { view: View; setView: (view: View) => void }) {
  const items: { id: View; label: string; icon: ReactNode }[] = [
    { id: 'prediction', label: 'Nueva predicción', icon: <Plus size={19} /> },
    { id: 'predictions', label: 'Predicciones', icon: <History size={19} /> },
    { id: 'samples', label: 'Base de muestras', icon: <Database size={19} /> },
    { id: 'model', label: 'Análisis del modelo', icon: <BarChart3 size={19} /> },
  ]
  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark"><Grape size={25} /></span><span><strong>GrapeSense</strong><small>Apoyo enológico</small></span></div>
    <nav>{items.map((item) => <button key={item.id} className={view === item.id ? 'active' : ''} onClick={() => setView(item.id)}>{item.icon}{item.label}</button>)}</nav>
    <div className="system-card"><span className="status-dot" /><div><strong>Sistema conectado</strong><small>Modelo y PostgreSQL</small></div></div>
  </aside>
}

function PredictionPage({ predictions, summary, loading, refresh, goHistory }: {
  predictions: Prediction[]; summary: Summary | null; loading: boolean; refresh: () => Promise<void>; goHistory: () => void
}) {
  const [form, setForm] = useState(initialForm)
  const [result, setResult] = useState<PredictionResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

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
            <Field label="Viñedo *"><select value={form.vinedo} onChange={(e) => setForm({ ...form, vinedo: e.target.value })}><option>Agrelo</option><option>Drummond</option><option>San Carlos</option></select></Field>
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

function SamplesPage({ summary }: { summary: SampleSummary | null }) {
  const [filters, setFilters] = useState<SampleFilters>({})
  const [samples, setSamples] = useState<Sample[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const limit = 100
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { const result = await api.getSamples(filters, limit, offset); setSamples(result.items); setTotal(result.total) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudieron consultar las muestras') }
    finally { setLoading(false) }
  }, [filters, offset])
  useEffect(() => { void load() }, [load])
  function update(key: keyof SampleFilters, value: string) { setOffset(0); setFilters((current) => ({ ...current, [key]: value })) }
  async function exportSamples() { const result = await api.getSamples(filters, 1000, 0); const columns = Object.keys(result.items[0] ?? {}) as (keyof Sample)[]; downloadRows(result.items, columns, 'muestras_uva.csv') }
  return <>
    <section className="stats-grid sample-stats"><Stat icon={<Database />} label="Muestras registradas" value={summary?.total_muestras ?? '—'} /><Stat icon={<Layers3 />} label="Lotes" value={summary?.total_lotes ?? '—'} /><Stat icon={<CheckCircle2 />} label="Muestras de cosecha" value={summary?.muestras_cosecha ?? '—'} /><Stat icon={<CalendarDays />} label="Vendimias disponibles" value={summary?.por_vendimia.map((row) => row.vendimia).join(', ') || '—'} /></section>
    <section className="panel samples-panel"><PanelHeading icon={<Database size={20} />} title="Muestras de uva" subtitle={`${total} registros coinciden con los filtros`} aside="Consulta de solo lectura" /><div className="filter-grid"><SearchBox value={filters.search ?? ''} setValue={(value) => update('search', value)} placeholder="Buscar lote o ID de muestra" /><select value={filters.vendimia ?? ''} onChange={(e) => update('vendimia', e.target.value)}><option value="">Todas las vendimias</option>{summary?.por_vendimia.map((row) => <option key={row.vendimia}>{row.vendimia}</option>)}</select><select value={filters.variedad ?? ''} onChange={(e) => update('variedad', e.target.value)}><option value="">Todas las variedades</option>{summary?.variedades.map((value) => <option key={value}>{value}</option>)}</select><select value={filters.vinedo ?? ''} onChange={(e) => update('vinedo', e.target.value)}><option value="">Todos los viñedos</option>{summary?.vinedos.map((value) => <option key={value}>{value}</option>)}</select><select value={filters.tipo_muestra ?? ''} onChange={(e) => update('tipo_muestra', e.target.value)}><option value="">Todos los tipos</option><option value="seguimiento">Seguimiento</option><option value="cosecha">Cosecha</option></select><button className="secondary-button" onClick={() => void exportSamples()} disabled={!total}><Download size={18} /> Exportar filtradas</button></div>{error && <div className="alert error">{error}</div>}<div className="table-wrap samples-table"><table><thead><tr><th>Fecha</th><th>Muestra / Lote</th><th>Origen</th><th>Etapa</th><th>Química</th><th>Clima pasado</th><th>Días a cosecha</th></tr></thead><tbody>{samples.map((item) => <tr key={item.muestra_id}><td>{formatDate(item.fecha_medicion)}</td><td><strong>{item.muestra_id}</strong><small>{item.lote_id}</small></td><td><strong>{item.variedad}</strong><small>{item.vinedo} · {item.vendimia}</small></td><td><span className={`type-pill ${item.tipo_muestra}`}>{item.tipo_muestra}</span><small>Muestra {item.numero_muestra}</small></td><td><span>{item.Brix.toFixed(1)} Brix · pH {item.pH.toFixed(2)}</span><small>Acidez {item.acidez_total_g_l.toFixed(1)} g/L</small></td><td><span>{item.pasado_tavg_7d.toFixed(1)} °C · {item.pasado_prcp_sum_7d.toFixed(1)} mm</span><small>Radiación {item.pasado_radiacion_sum_7d.toFixed(1)} MJ/m²</small></td><td><strong>{item.dias_hasta_cosecha ?? '—'}</strong></td></tr>)}</tbody></table>{loading && <div className="table-loading"><LoaderCircle className="spin" /> Cargando muestras...</div>}{!loading && !samples.length && <EmptyData text="No hay muestras que coincidan con los filtros." />}</div><div className="pagination"><span>Mostrando {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} de {total}</span><div><button className="icon-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}><ChevronLeft /></button><button className="icon-button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}><ChevronRight /></button></div></div></section>
  </>
}

function ModelPage({ analysis }: { analysis: ModelAnalysis | null }) {
  if (!analysis) return <section className="panel model-loading"><LoaderCircle className="spin" /><h2>Preparando el análisis del modelo</h2><p>Calculando métricas sobre la evaluación temporal 2024.</p></section>
  const metrics = analysis.evaluacion_2024
  const topVariables = analysis.importancia_variables.slice(0, 10)
  return <div className="model-page">
    <section className="model-hero"><div><span className="model-badge"><Microscope size={17} /> MODELO EN USO</span><h2>{analysis.modelo.algoritmo}</h2><p><strong>Objetivo:</strong> {analysis.modelo.objetivo}. Entrenado con vendimias {analysis.modelo.vendimias_entrenamiento.join(' y ')}.</p></div><div className="model-meta"><span><small>Variables</small><strong>{analysis.modelo.variables}</strong></span><span><small>Entrenamiento</small><strong>{analysis.datos.entrenamiento_muestras}</strong></span><span><small>Evaluación 2024</small><strong>{analysis.datos.evaluacion_2024_muestras}</strong></span></div></section>
    <section className="stats-grid model-stats"><Stat icon={<TrendingUp />} label="Error medio absoluto 2024" value={`${metrics.mae_dias} días`} /><Stat icon={<CheckCircle2 />} label="Dentro de ±3 días" value={`${metrics.dentro_3_dias_porcentaje}%`} /><Stat icon={<CheckCircle2 />} label="Dentro de ±4 días" value={`${metrics.dentro_4_dias_porcentaje}%`} /><Stat icon={<BarChart3 />} label="Sesgo promedio" value={`${metrics.sesgo_dias > 0 ? '+' : ''}${metrics.sesgo_dias} días`} /></section>
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
      <ChartPanel title="Error según anticipación" subtitle="MAE en la vendimia 2024, separado por días reales restantes"><ResponsiveContainer width="100%" height={300}><BarChart data={analysis.rendimiento_por_anticipacion}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="rango" tick={{ fontSize: 12 }} /><YAxis unit=" d" /><Tooltip formatter={(value) => [`${value} días`, 'MAE']} /><Bar dataKey="mae_dias" fill="#c6953e" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></ChartPanel>
      <ChartPanel title="Variables más utilizadas" subtitle="Importancia interna del Gradient Boosting"><ResponsiveContainer width="100%" height={380}><BarChart data={topVariables} layout="vertical" margin={{ left: 20, right: 25 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" unit="%" /><YAxis type="category" dataKey="etiqueta" width={170} tick={{ fontSize: 12 }} /><Tooltip formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Importancia']} /><Bar dataKey="importancia_porcentaje" fill="#255c42" radius={[0, 5, 5, 0]} /></BarChart></ResponsiveContainer></ChartPanel>
      <ChartPanel title="Días reales frente a predichos" subtitle="Cada punto representa una muestra de evaluación 2024"><ResponsiveContainer width="100%" height={380}><ScatterChart margin={{ top: 15, right: 20, bottom: 15, left: 5 }}><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" dataKey="real" name="Real" unit=" d" domain={[0, 'auto']} /><YAxis type="number" dataKey="predicho" name="Predicho" unit=" d" domain={[0, 'auto']} /><Tooltip cursor={{ strokeDasharray: '3 3' }} /><Legend /><ReferenceLine segment={[{ x: 0, y: 0 }, { x: 35, y: 35 }]} stroke="#c6953e" strokeDasharray="5 5" /><Scatter name="Evaluación 2024" data={analysis.comparacion_2024} fill="#255c42" fillOpacity={0.68} /></ScatterChart></ResponsiveContainer></ChartPanel>
    </div>
    <section className="panel horizon-panel"><PanelHeading icon={<TrendingUp size={20} />} title="Rendimiento por anticipación" subtitle="Permite ver en qué etapa es más confiable la estimación" /><div className="table-wrap"><table><thead><tr><th>Días reales restantes</th><th>Muestras</th><th>Error medio</th><th>Dentro de ±3 días</th><th>Dentro de ±4 días</th><th>Sesgo</th></tr></thead><tbody>{analysis.rendimiento_por_anticipacion.map((row) => <tr key={row.rango}><td><strong>{row.rango}</strong></td><td>{row.muestras}</td><td>{row.mae_dias} días</td><td>{row.dentro_3_dias_porcentaje}%</td><td>{row.dentro_4_dias_porcentaje}%</td><td>{row.sesgo_dias > 0 ? '+' : ''}{row.sesgo_dias} días</td></tr>)}</tbody></table></div></section>
    <section className="evidence-grid"><div className="panel info-panel"><Info /><div><h3>Cómo leer la importancia</h3><p>Una importancia alta significa que el modelo recurre mucho a esa variable para dividir casos. No indica que esa variable cause por sí sola la fecha de cosecha. Las variables correlacionadas pueden repartirse la importancia.</p></div></div><div className="panel data-panel"><Database /><div><h3>Origen de la evidencia</h3><p>{analysis.datos.entrenamiento_muestras} muestras de entrenamiento y {analysis.datos.evaluacion_2024_muestras} de evaluación temporal. Uva: {analysis.datos.origen_uva.toLowerCase()}. Clima: {analysis.datos.origen_clima.toLowerCase()}.</p></div></div></section>
    <section className="panel warning-panel"><div className="warning-title"><AlertTriangle /><div><h3>Límites que debe conocer el enólogo</h3><p>El modelo es apoyo a la decisión, no una orden automática de cosecha.</p></div></div><ul>{analysis.advertencias.map((warning) => <li key={warning}>{warning}</li>)}</ul></section>
  </div>
}

function PanelHeading({ icon, title, subtitle, aside }: { icon: ReactNode; title: string; subtitle: string; aside?: string }) { return <div className="panel-heading"><div><span className="icon-box">{icon}</span><div><h2>{title}</h2><p>{subtitle}</p></div></div>{aside && <span className="required-note">{aside}</span>}</div> }
function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) { return <label className="field"><span>{label}{hint && <small>{hint}</small>}</span>{children}</label> }
function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) { return <div className="stat-card"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div> }
function Recent({ item }: { item: Prediction }) { return <div className="recent-row"><span className="grape-dot"><Grape size={17} /></span><div><strong>{item.lote_id} · {item.variedad}</strong><small>{formatDate(item.fecha_medicion)} · {item.vinedo}</small></div><b>{item.dias_predichos.toFixed(1)} d</b></div> }
function SearchBox({ value, setValue, placeholder }: { value: string; setValue: (value: string) => void; placeholder: string }) { return <div className="search"><Search size={18} /><input aria-label={placeholder} placeholder={placeholder} value={value} onChange={(e) => setValue(e.target.value)} /></div> }
function EmptyData({ text }: { text: string }) { return <div className="no-data"><Database size={30} /><p>{text}</p></div> }
function DetailSection({ title, aside, children }: { title: string; aside?: string; children: ReactNode }) { return <section className="detail-section"><div className="detail-title"><h3>{title}</h3>{aside && <small>{aside}</small>}</div>{children}</section> }
function Value({ label, value }: { label: string; value: string }) { return <div className="value-pair"><small>{label}</small><strong>{value}</strong></div> }
function ChartPanel({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) { return <section className="panel chart-panel"><div><h3>{title}</h3><p>{subtitle}</p></div>{children}</section> }
