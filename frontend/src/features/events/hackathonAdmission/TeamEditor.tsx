import { useState } from 'react'
import { Card } from '../../../components/ui'
import type { Team } from './types'

export function TeamEditor({ team, pending, onSave }: { team?: Team; pending: boolean
  onSave: (body: Record<string, unknown>) => void }) {
  const [name, setName] = useState(team?.name ?? '')
  const [intro, setIntro] = useState(team?.finder_intro ?? '')
  const [skills, setSkills] = useState(team?.skills.join(', ') ?? '')
  const [seeking, setSeeking] = useState(team?.seeking_members ?? false)
  return <Card><form className="grid gap-4" onSubmit={event => { event.preventDefault(); onSave({
    expected_version: team?.version ?? 0, name, finder_intro: intro,
    skills: skills.split(',').map(s => s.trim()).filter(Boolean), seeking_members: seeking }) }}>
    <label className="grid gap-1 text-sm text-ink">Team name<input required maxLength={100} className="desk-input" value={name} onChange={e => setName(e.target.value)} /></label>
    <label className="grid gap-1 text-sm text-ink">Skills (separate with commas)<input maxLength={800} className="desk-input" value={skills} onChange={e => setSkills(e.target.value)} /></label>
    <label className="grid gap-1 text-sm text-ink">Finder introduction<textarea maxLength={500} className="desk-input" value={intro} onChange={e => setIntro(e.target.value)} /></label>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={seeking} onChange={e => setSeeking(e.target.checked)} />Show this team in the team finder.</label>
    <p className="text-sm text-muted">Your introduction and chosen skills are visible to eligible participants. Keep private contact details out of your introduction.</p>
    <button className="desk-button-primary justify-self-start" disabled={pending} type="submit">{team ? 'Save team' : 'Create team'}</button>
  </form></Card>
}
