import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { Crown, LogOut, UserMinus } from 'lucide-react';
import { ConfirmDialog, Modal } from '../../../components/ui';
import type { Team } from './types';

type Member = Team['members'][number];
const nameOf = (member: Member) => member.profile?.display_name || t`Team member`;

/**
 * C3 roster: everyone sees who is on the team and who leads it; the leader can hand the team over or remove a member
 * (`events.team_moderation`; the server offers `handover` / `remove_member` in `allowed_actions`).
 */
export function TeamRoster({ team, pending, onHandover, onRemove }: { team: Team; pending: boolean;
  onHandover: (memberId: number) => void; onRemove: (memberId: number) => void }) {
  const [confirm, setConfirm] = useState<{ kind: 'handover' | 'remove'; member: Member } | null>(null);
  const canHandover = team.allowed_actions.includes('handover'), canRemove = team.allowed_actions.includes('remove_member');
  return <>
    <h2 className="title-section">{t`Team roster`}</h2>
    <ul className="grid gap-2">{team.members.map(member => { const leader = member.member_id === team.leader_member_id;
      return <li key={member.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-3 text-sm text-ink">
        <span className="flex min-w-0 items-center gap-2">
          {member.profile?.url ? <a className="truncate underline" href={member.profile.url}>{member.profile.display_name || t`Public member profile`}</a> : <span className="truncate">{t`Team member`}</span>}
          {leader ? <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs font-semibold"><Crown aria-hidden="true" className="size-3" />{t`Leader`}</span> : null}
        </span>
        {!leader && (canHandover || canRemove) ? <span className="flex flex-wrap gap-2">
          {canHandover ? <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" disabled={pending}
            onClick={() => setConfirm({ kind: 'handover', member })}><Crown aria-hidden="true" className="size-4" />{t`Make leader…`}</button> : null}
          {canRemove ? <button type="button" className="desk-button-danger-outline inline-flex min-h-11 items-center gap-2" disabled={pending}
            onClick={() => setConfirm({ kind: 'remove', member })}><UserMinus aria-hidden="true" className="size-4" />{t`Remove…`}</button> : null}
        </span> : null}
      </li>; })}</ul>
    <ConfirmDialog open={!!confirm} pending={pending} onCancel={() => setConfirm(null)}
      tone={confirm?.kind === 'remove' ? 'danger' : 'default'}
      title={confirm?.kind === 'remove' ? t`Remove ${confirm ? nameOf(confirm.member) : ''} from the team?` : t`Make ${confirm ? nameOf(confirm.member) : ''} the leader?`}
      message={confirm?.kind === 'remove' ? t`They leave the team but keep their place at the event, and can join another team.`
        : t`They take over the team's invitations, roster and submission. You stay on the team as a member. They are notified.`}
      confirmLabel={confirm?.kind === 'remove' ? t`Remove member` : t`Hand over`}
      onConfirm={() => { if (!confirm) return; (confirm.kind === 'remove' ? onRemove : onHandover)(confirm.member.member_id); setConfirm(null); }} />
  </>;
}

/** C4: leaving can also cancel the leaver's own registration (offered while `events.team_moderation` is on). */
export function LeaveTeamButton({ team, pending, onLeave }: { team: Team; pending: boolean; onLeave: (cancelRegistration: boolean) => void }) {
  const [open, setOpen] = useState(false); const [cancel, setCancel] = useState(false);
  if (!team.allowed_actions.includes('cancel_registration')) {
    return <button className="desk-button-danger-outline" type="button" disabled={pending} onClick={() => onLeave(false)}>{t`Leave team`}</button>;
  }
  const leader = team.allowed_actions.includes('handover');
  return <>
    <button className="desk-button-danger-outline inline-flex items-center gap-2" type="button" disabled={pending} onClick={() => setOpen(true)}>
      <LogOut aria-hidden="true" className="size-4" />{t`Leave team…`}</button>
    <Modal open={open} onClose={() => !pending && setOpen(false)} title={t`Leave ${team.name}?`} footer={<div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={() => setOpen(false)}>{t`Stay on the team`}</button>
      <button type="button" className="desk-button-danger w-full sm:w-auto" disabled={pending} onClick={() => { onLeave(cancel); setOpen(false); }}>
        {cancel ? t`Leave and cancel my registration` : t`Leave team`}</button></div>}>
      <div className="grid gap-3 text-sm">
        <p className="text-muted">{leader ? t`The longest-standing member becomes leader and is notified. If you are the last member, the team closes.`
          : t`The team keeps going without you.`}</p>
        <label className="flex min-h-11 items-start gap-3 text-ink"><input type="checkbox" className="mt-1" checked={cancel} onChange={e => setCancel(e.target.checked)} />
          <span>{t`Also cancel my registration for this event`}<span className="block text-xs text-muted">{t`Your place is released for someone else. This cannot be undone here.`}</span></span></label>
      </div>
    </Modal>
  </>;
}
