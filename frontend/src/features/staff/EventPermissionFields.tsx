import { t } from "@lingui/core/macro";
import { EVENT_PERMISSIONS, type EventPermission } from "./eventStaffPermissions";

export const ROLE_LABELS = [["speaker", "Speaker"], ["volunteer", "Volunteer"], ["check_in", "Check-in"]] as const;
export type RoleLabel = typeof ROLE_LABELS[number][0] | "";
export const roleLabelText = (value?: string | null) => ROLE_LABELS.find(([key]) => key === value)?.[1] ?? null;

export function EventPermissionFields({ value, onChange, disabled = false, legend = "Permissions", onSpeakerPreset }: {
  value: EventPermission[]; onChange: (next: EventPermission[]) => void; disabled?: boolean; legend?: string;
  /** Speakers only need the door: check-in, which also shows who has arrived. */
  onSpeakerPreset?: () => void;
}) {
  return <fieldset disabled={disabled} className="grid min-w-0 gap-x-4 sm:grid-cols-2">
    <legend className="mb-1 text-sm font-semibold text-ink">{legend}</legend>
    {onSpeakerPreset ? <div className="flex flex-wrap items-center gap-2 py-1 sm:col-span-2">
      <button type="button" className="desk-button" onClick={onSpeakerPreset}>{t`Speaker preset`}</button>
      <span className="text-sm text-muted">{t`Check in attendees only.`}</span>
    </div> : null}
    {EVENT_PERMISSIONS.map(([permission, label]) => <label key={permission} className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={value.includes(permission)} onChange={(event) => onChange(
        event.target.checked ? [...value, permission] : value.filter((entry) => entry !== permission),
      )} />{label}
    </label>)}
  </fieldset>;
}

export function RoleLabelField({ value, onChange, disabled = false, label = t`Role label` }: {
  value: string; onChange: (next: RoleLabel) => void; disabled?: boolean; label?: string;
}) {
  return <label className="grid gap-1 text-sm font-semibold text-ink">{label}
    <select className="desk-input w-full min-w-0 font-normal sm:max-w-xs" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value as RoleLabel)}>
      <option value="">{t`No label`}</option>
      {ROLE_LABELS.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
    </select>
    <span className="text-sm font-normal text-muted">{t`Shown to your team only. Permissions alone decide what they can do.`}</span>
  </label>;
}
