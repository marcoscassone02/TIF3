import { useEffect, useState, type ReactNode } from 'react'
import { BarChart3, Building2, Database, Grape, History, LogOut, Plus, ShieldCheck } from 'lucide-react'
import { api, session } from '../api'
import { roleLabel } from '../lib/format'
import type { User, View } from '../types'

type SidebarProps = {
  view: View
  setView: (view: View) => void
  user: User
  logout: () => void
}

export function Sidebar({ view, setView, user, logout }: SidebarProps) {
  const [wineries, setWineries] = useState<{ bodega_id: number; nombre: string }[]>([])

  useEffect(() => {
    if (user.rol === 'superadmin') {
      api.getWineries().then((result) => setWineries(result.items)).catch(() => undefined)
    }
  }, [user.rol])

  const items: { id: View; label: string; icon: ReactNode }[] = [
    { id: 'prediction', label: 'Nueva predicción', icon: <Plus size={19} /> },
    { id: 'predictions', label: 'Predicciones', icon: <History size={19} /> },
    { id: 'samples', label: 'Base de muestras', icon: <Database size={19} /> },
    { id: 'model', label: 'Análisis del modelo', icon: <BarChart3 size={19} /> },
  ]
  if (user.rol === 'superadmin' || user.rol === 'admin') {
    items.push({ id: 'admin', label: 'Administración', icon: <ShieldCheck size={19} /> })
  }

  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark"><Grape size={25} /></span><span><strong>GrapeSense</strong><small>Apoyo enológico</small></span></div>
    <nav>{items.map((item) => <button key={item.id} className={view === item.id ? 'active' : ''} onClick={() => setView(item.id)}>{item.icon}{item.label}</button>)}</nav>
    {user.rol === 'superadmin' && wineries.length > 0 && <label className="tenant-switch"><span>Bodega administrada</span><select value={user.bodega_id} onChange={(event) => { session.selectWinery(Number(event.target.value)); window.location.reload() }}>{wineries.map((item) => <option key={item.bodega_id} value={item.bodega_id}>{item.nombre}</option>)}</select></label>}
    <div className="tenant-card">
      <div className="tenant-profile">
        <span className="tenant-icon"><Building2 size={18} /></span>
        <div className="tenant-details">
          <strong title={user.bodega_nombre}>{user.bodega_nombre}</strong>
          <span className="tenant-user" title={user.nombre}>{user.nombre}</span>
          <small>{roleLabel(user.rol)}</small>
        </div>
      </div>
      <button className="logout-button" onClick={logout}><LogOut size={16} /><span>Cerrar sesión</span></button>
    </div>
  </aside>
}
