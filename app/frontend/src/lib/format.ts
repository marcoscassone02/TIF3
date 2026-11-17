import type { User } from '../types'

export const today = new Date().toLocaleDateString('en-CA', {
  timeZone: 'America/Argentina/Mendoza',
})

export function formatDate(value: string | null, withTime = false) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(
    'es-AR',
    withTime
      ? { dateStyle: 'medium', timeStyle: 'short' }
      : { day: '2-digit', month: 'short', year: 'numeric' },
  ).format(new Date(value.includes('T') ? value : `${value}T12:00:00`))
}

export function roleLabel(role: User['rol'] | string) {
  if (role === 'superadmin') return 'Administrador de plataforma'
  if (role === 'admin') return 'Administrador de bodega'
  return 'Usuario de bodega'
}

export function downloadRows<T extends Record<string, unknown>>(
  rows: T[],
  columns: (keyof T)[],
  filename: string,
) {
  const escape = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const csv = [
    columns.join(','),
    ...rows.map((row) => columns.map((key) => escape(row[key])).join(',')),
  ].join('\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }))
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}
