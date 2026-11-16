import { t } from "@lingui/core/macro";
import type { ReactNode } from 'react'
import { Field } from '../../../components/ui'

export function SetupText({ label, value, onChange, type = 'text', required = false }: {
  label: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean
}) {
  return <Field label={label}><input className="desk-input min-h-11" type={type} required={required}
    value={value} onChange={event => onChange(event.target.value)} /></Field>
}
export function Toggle({ children, checked, onChange }: { children: ReactNode; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />{children}</label>
}
export function ids(value: string) {
  if (!value.trim()) return []
  const result = value.split(',').map(x => Number(x.trim()))
  if (result.some(x => !Number.isSafeInteger(x) || x < 1) || new Set(result).size !== result.length) throw new Error(t`Use distinct positive IDs separated by commas.`)
  return result
}
export function tags(value: string) { return value.split(',').map(x => x.trim()).filter(Boolean) }
export function iso(value: string) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) throw new Error(t`Choose a valid date and time.`)
  return date.toISOString()
}
export function localDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function edited(initial: object | undefined, fields: Record<string, unknown>) {
  if (!initial) return fields
  const canonical = (value: unknown): unknown => {
    if (typeof value === 'string' && /^\d{4}-\d\d-\d\dT/.test(value) && Number.isFinite(Date.parse(value))) return new Date(value).toISOString()
    if (Array.isArray(value)) return value.map(canonical)
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)]))
    return value
  }
  const source = initial as Record<string, unknown>
  return Object.fromEntries(Object.entries(fields).filter(([key, value]) => JSON.stringify(canonical(value)) !== JSON.stringify(canonical(source[key]))))
}
