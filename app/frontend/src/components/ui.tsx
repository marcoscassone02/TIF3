import type { ReactNode } from 'react'
import { Database, Grape, Search } from 'lucide-react'
import type { Prediction } from '../types'
import { formatDate } from '../lib/format'

export function PanelHeading({ icon, title, subtitle, aside }: { icon: ReactNode; title: string; subtitle: string; aside?: string }) {
  return <div className="panel-heading"><div><span className="icon-box">{icon}</span><div><h2>{title}</h2><p>{subtitle}</p></div></div>{aside && <span className="required-note">{aside}</span>}</div>
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field"><span>{label}{hint && <small>{hint}</small>}</span>{children}</label>
}

export function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return <div className="stat-card"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div>
}

export function Recent({ item }: { item: Prediction }) {
  return <div className="recent-row"><span className="grape-dot"><Grape size={17} /></span><div><strong>{item.lote_id} · {item.variedad}</strong><small>{formatDate(item.fecha_medicion)} · {item.vinedo}</small></div><b>{item.dias_predichos.toFixed(1)} d</b></div>
}

export function SearchBox({ value, setValue, placeholder }: { value: string; setValue: (value: string) => void; placeholder: string }) {
  return <div className="search"><Search size={18} /><input aria-label={placeholder} placeholder={placeholder} value={value} onChange={(event) => setValue(event.target.value)} /></div>
}

export function EmptyData({ text }: { text: string }) {
  return <div className="no-data"><Database size={30} /><p>{text}</p></div>
}

export function DetailSection({ title, aside, children }: { title: string; aside?: string; children: ReactNode }) {
  return <section className="detail-section"><div className="detail-title"><h3>{title}</h3>{aside && <small>{aside}</small>}</div>{children}</section>
}

export function Value({ label, value }: { label: string; value: string }) {
  return <div className="value-pair"><small>{label}</small><strong>{value}</strong></div>
}

export function ChartPanel({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return <section className="panel chart-panel"><div><h3>{title}</h3><p>{subtitle}</p></div>{children}</section>
}
