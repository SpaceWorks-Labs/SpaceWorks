import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from 'react';
import { ErrorText, Field, Modal } from '../../../components/ui';
import { commandErrorText } from '../../events/programmeCommandErrors';
import { useOrganiserTeamMembers, type OrganiserTeam } from './organiserTeamApi';
import { LogoLoader } from '../../../components/LogoLoader';

function Footer({ pending, disabled, label, onCancel, onConfirm }: { pending: boolean; disabled: boolean; label: string; onCancel: () => void; onConfirm: () => void }) {
  return <div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
    <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={onCancel}>{t`Cancel`}</button>
    <button type="button" className="desk-button-primary w-full sm:w-auto" disabled={pending || disabled} onClick={onConfirm}>{label}</button>
  </div>;
}

function Body({ children, error }: { children: ReactNode; error: unknown }) {
  return <div className="grid gap-4">{children}{error ? <ErrorText message={commandErrorText(error)} /> : null}</div>;
}

/** Organiser rename: skips the leader and the forming rule, never the one-name-per-event rule. */
export function RenameTeamDialog({ team, pending, error, onCancel, onSave }: { team: OrganiserTeam; pending: boolean; error: unknown;
  onCancel: () => void; onSave: (name: string) => void }) {
  const [name, setName] = useState(team.name);
  const valid = name.trim() && name.trim() !== team.name;
  return <Modal open onClose={() => !pending && onCancel()} title={t`Rename ${team.name}`}
    footer={<Footer pending={pending} disabled={!valid} label={pending ? t`Saving…` : t`Rename team`} onCancel={onCancel} onConfirm={() => onSave(name.trim())} />}>
    <Body error={error}><Field label={t`Team name`} hint={t`Each team in this event needs its own name.`}>
      <input className="desk-input min-h-11" maxLength={100} value={name} onChange={e => setName(e.target.value)} autoComplete="off" /></Field></Body>
  </Modal>;
}

/** C6 move: one active member to another open team of this event; the target's maximum size still applies. */
export function MoveMemberDialog({ eventId, team, targets, pending, error, onCancel, onMove }: { eventId: number; team: OrganiserTeam;
  targets: OrganiserTeam[]; pending: boolean; error: unknown; onCancel: () => void; onMove: (memberId: number, target: OrganiserTeam) => void }) {
  const members = useOrganiserTeamMembers(eventId, team.id);
  const [member, setMember] = useState(''); const [target, setTarget] = useState('');
  const open = targets.filter(row => row.id !== team.id && row.state === 'forming');
  const chosen = open.find(row => String(row.id) === target);
  const label = (row: { member_id: number; display_name: string; is_leader: boolean }) =>
    `${row.display_name || t`Member ${row.member_id}`}${row.is_leader ? t` (leader)` : ''}`;
  return <Modal open onClose={() => !pending && onCancel()} title={t`Move a member of ${team.name}`}
    footer={<Footer pending={pending} disabled={!member || !chosen} label={pending ? t`Moving…` : t`Move member`} onCancel={onCancel}
      onConfirm={() => chosen && onMove(Number(member), chosen)} />}>
    <Body error={error ?? members.error}>
      {members.isLoading ? <LogoLoader label={t`Loading the roster…`} size={48} className="min-h-16 py-3" /> : null}
      <Field label={t`Member`}><select className="desk-input min-h-11" value={member} onChange={e => setMember(e.target.value)}>
        <option value="">{t`Choose a member`}</option>
        {(members.data?.members ?? []).map(row => <option key={row.member_id} value={row.member_id}>{label(row)}</option>)}</select></Field>
      <Field label={t`Move to`} hint={open.length ? t`Only teams still forming are listed.` : t`No other team on this page is still forming.`}>
        <select className="desk-input min-h-11" value={target} onChange={e => setTarget(e.target.value)}>
          <option value="">{t`Choose a team`}</option>
          {open.map(row => <option key={row.id} value={row.id}>{t`${row.name} · ${row.member_count} members`}</option>)}</select></Field>
      <p className="text-xs text-muted">{t`If the leader moves, the longest-standing member who stays becomes leader. The moved member is notified.`}</p>
    </Body>
  </Modal>;
}
