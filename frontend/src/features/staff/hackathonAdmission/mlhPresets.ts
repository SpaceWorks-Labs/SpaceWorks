import { useQuery } from '@tanstack/react-query'
import { staffRequest } from '../../../lib/api'
import type { ProgrammeMlhPreset } from './MlhPresetPicker'

/**
 * EP-9: the approved, age-free MLH application presets the server publishes for an event's hackathon.
 * The list is static per deployment, so it is cached for the session. A server without the route (or
 * any load error) yields no presets: the picker then explains that sharing cannot be turned on here.
 */
export const mlhPresetsPath = (eventId: number) => '/admin/events/' + eventId + '/hackathon/mlh-presets/'

const isPreset = (row: unknown): row is ProgrammeMlhPreset => {
  if (!row || typeof row !== 'object') return false
  const { id, label, schema } = row as Record<string, unknown>
  if (typeof id !== 'string' || typeof label !== 'string' || !schema || typeof schema !== 'object') return false
  const { schema_version: version, form_id: formId, revision, questions } = schema as Record<string, unknown>
  return version === 2 && typeof formId === 'string' && typeof revision === 'number' && Array.isArray(questions)
}

/** Accepts a bare list or a `{ results }` page; anything malformed is dropped rather than offered. */
export function readMlhPresets(body: unknown): ProgrammeMlhPreset[] {
  const rows = Array.isArray(body) ? body : body && typeof body === 'object' ? (body as { results?: unknown }).results : null
  return Array.isArray(rows) ? rows.filter(isPreset) : []
}

export function useMlhPresets(eventId: number, enabled: boolean): readonly ProgrammeMlhPreset[] {
  const query = useQuery({ queryKey: ['staff-event-admission', eventId, 'mlh-presets'], enabled, retry: false, staleTime: Infinity,
    queryFn: async () => readMlhPresets(await staffRequest<unknown>(mlhPresetsPath(eventId))) })
  return Array.isArray(query.data) ? query.data : []
}
