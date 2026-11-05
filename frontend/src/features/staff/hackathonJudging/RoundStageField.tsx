import { Field } from '../../../components/ui';
import { useStagePlan } from '../submissionStages/api';

/** #178: the submission stage a round judges. Empty means the event's last stage; frozen once the round opens. */
export function RoundStageField({ eventId, value, onChange, locked }: { eventId: number; value: string; onChange: (value: string) => void; locked: boolean }) {
  const stages = (useStagePlan(eventId).data?.stages ?? []).filter(stage => stage.id !== null);
  if (stages.length < 2 && !value) return null;
  return <Field label="Stage this round judges" hint={locked ? 'Fixed once the round opens.' : 'Judges see each team’s current submission for this stage.'}>
    <select className="desk-input min-h-11" value={value} disabled={locked} onChange={e => onChange(e.target.value)}>
      <option value="">The last stage</option>
      {stages.map(stage => <option key={stage.id} value={String(stage.id)}>{`Stage ${stage.position}: ${stage.name}`}</option>)}</select></Field>;
}
