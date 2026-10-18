import { memberRequest, staffRequest } from '../../../lib/api'

export function apiPath(url: string) {
  if (!url.startsWith('/api/v1/') || /[\\\s?#%]/.test(url) || /\/(?:\.{1,2})(?:\/|$)/.test(url) || url.includes('://')) {
    throw new Error('Invalid event action URL.')
  }
  return url.slice('/api/v1'.length)
}
export function readMember<T>(url: string) { return memberRequest<T>(apiPath(url)) }
export function readStaff<T>(url: string) { return staffRequest<T>(apiPath(url)) }
function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']'
  if (value && typeof value === 'object') return '{' + Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
    .map(([key, val]) => JSON.stringify(key) + ':' + canonical(val)).join(',') + '}'
  return JSON.stringify(value)
}
/** Memory only: retry the same command UUID after a lost response. */
export class CommandSession {
  private operations = new Map<string, string>()
  async send<T>(url: string, method: 'POST' | 'PATCH', body: Record<string, unknown>, staff = false) {
    const key = method + url + canonical(body)
    let operation = this.operations.get(key)
    if (!operation) { operation = crypto.randomUUID(); this.operations.set(key, operation) }
    const request = staff ? staffRequest : memberRequest
    const result = await request<T>(apiPath(url), { method,
      headers: { 'Idempotency-Key': operation }, body: JSON.stringify({ ...body, operation_id: operation }) })
    this.operations.delete(key)
    return result
  }
}
