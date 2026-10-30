import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare } from 'lucide-react'
import { staffRequest } from '../../../lib/api'
import { StructuredApiError } from '../../../lib/api/errors'
import { Card } from '../../../components/ui'
import type { EventScope } from '../../events/contributions/types'

type Room = { id: number; label: string; channel: 'telegram' | 'slack' | 'discord' | 'mattermost'; is_active: boolean }
type Routes = { rooms: Room[]; destination_ids: number[] }
const CHANNEL: Record<Room['channel'], string> = { telegram: 'Telegram', slack: 'Slack', discord: 'Discord', mattermost: 'Mattermost' }

/** G9: which team chat rooms hear about new help requests while mentors are on shift. */
export function MentorAlertRooms({ scope }: { scope: EventScope }) {
  const client = useQueryClient()
  const key = ['mentor-alert-routes', scope.accountId, scope.makerspaceId, scope.eventId]
  const path = `/admin/events/${scope.eventId}/mentor-alert-routes/`
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<Routes>(path), retry: false })
  const [chosen, setChosen] = useState<number[]>([])
  useEffect(() => { if (query.data) setChosen(query.data.destination_ids) }, [query.data])
  const save = useMutation({ mutationFn: (ids: number[]) => staffRequest<Routes>(path, { method: 'PUT', body: JSON.stringify({ destination_ids: ids }) }),
    onSuccess: data => client.setQueryData(key, data) })
  // 404 while events.mentor_chat_alerts is off: the setting is simply not offered.
  if (query.error instanceof StructuredApiError && query.error.status === 404) return null
  if (!query.data) return null
  const rooms = query.data.rooms
  return <Card><section aria-labelledby="mentor-alert-rooms" className="grid gap-3">
    <h4 id="mentor-alert-rooms" className="flex items-center gap-2 font-semibold"><MessageSquare aria-hidden="true" className="size-4" />Chat alerts for new help requests</h4>
    <p className="text-sm text-muted">Chosen rooms get a short message when a team asks for help and at least one mentor is on shift: the topic, the team name and a link to Mentor Desk. No buttons and no personal details. Quiet hours apply.</p>
    {rooms.length ? <fieldset className="grid gap-2"><legend className="sr-only">Rooms</legend>{rooms.map(room => <label key={room.id} className="flex min-h-11 items-center gap-3 text-sm">
      <input type="checkbox" disabled={!room.is_active && !chosen.includes(room.id)} checked={chosen.includes(room.id)}
        onChange={event => setChosen(event.target.checked ? [...chosen, room.id] : chosen.filter(id => id !== room.id))} />
      <span>{room.label} · {CHANNEL[room.channel]}{room.is_active ? '' : ' (switched off)'}</span></label>)}</fieldset>
      : <p className="text-sm">This space has no chat rooms yet. Add one in notification settings first.</p>}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error instanceof Error ? save.error.message : 'Could not save the rooms.'}</p> : null}
    {save.isSuccess ? <p role="status" className="text-sm">Rooms saved.</p> : null}
    {rooms.length ? <button type="button" className="desk-button justify-self-start" disabled={save.isPending} onClick={() => save.mutate(chosen)}>{save.isPending ? 'Saving…' : 'Save rooms'}</button> : null}
  </section></Card>
}
