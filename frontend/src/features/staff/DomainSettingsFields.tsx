import { t } from "@lingui/core/macro";
import { useId, useState, type ReactNode } from "react";

import { SettingsRow } from "../../components/ui";
import { SettingsEditorActions } from "./SettingsEditorActions";
import type { DomainSettingValues } from "./domainSettingsApi";

type Field = keyof DomainSettingValues;
type Draft = Partial<Record<Field, string | boolean>>;

const COPY: Record<Field, { label: string; helper: string }> = {
  event_default_registration_audience: {
    label: t`Default registration audience`,
    helper: t`New events and recurring series start with this audience. Existing events keep theirs.`,
  },
  event_reminder_lead_hours: {
    label: t`Event reminder lead hours`,
    helper: t`Hours before a confirmed event to email members, for example: 24, 2. Leave blank to disable.`,
  },
  booking_requester_notifications_enabled: {
    label: t`Email booking requesters`,
    helper: t`Default for booking submitted, confirmed and rejected emails. Each space may override it.`,
  },
  booking_reminder_lead_hours: {
    label: t`Booking reminder lead hours`,
    helper: t`Hours before a confirmed booking to email the booker, for example: 24, 2. Leave blank to disable.`,
  },
  filament_low_stock_threshold_grams: {
    label: t`Filament low-stock threshold (grams)`,
    helper: t`Spools at or below this weight can suggest a reorder. 0 turns it off.`,
  },
};

const AUDIENCES = [
  ["members", "Members"], ["accounts", "Authenticated accounts"], ["invite", "Invited accounts"],
  ["participating_organizations", "Participating organizations"],
] as const;
const HOURS_ERROR = "Enter unique whole hours from 1 to 8760, separated by commas, or leave blank to disable.";

function toDraft(values: DomainSettingValues): Draft {
  return Object.fromEntries(Object.entries(values).map(([key, value]) =>
    [key, Array.isArray(value) ? value.join(", ") : typeof value === "boolean" ? value : String(value)]));
}

function parseHours(text: string): number[] | null {
  const parts = text.trim() ? text.split(",").map((part) => part.trim()) : [];
  const hours = parts.map(Number);
  const valid = parts.every((part) => /^\d+$/.test(part)) && hours.length <= 100
    && hours.every((hour) => hour >= 1 && hour <= 8760) && new Set(hours).size === hours.length;
  return valid ? hours : null;
}

/** The changed fields, parsed back to the API's types, or the first client-side error. */
function changes(values: DomainSettingValues, initial: Draft, draft: Draft): { patch?: DomainSettingValues; error?: string } {
  const patch: Record<string, unknown> = {};
  for (const field of Object.keys(draft) as Field[]) {
    const value = draft[field];
    if (value === initial[field]) continue;
    if (Array.isArray(values[field])) {
      const hours = parseHours(String(value));
      if (!hours) return { error: HOURS_ERROR };
      patch[field] = hours;
    } else if (field === "filament_low_stock_threshold_grams") {
      if (!/^\d+(\.\d{1,2})?$/.test(String(value).trim())) return { error: "Enter a weight of 0 or more grams." };
      patch[field] = String(value).trim();
    } else {
      patch[field] = value;
    }
  }
  return { patch: patch as DomainSettingValues };
}

export function DomainSettingsFields({ values, disabled, pending, error, onSave, lockedFields, renderLock }: {
  values: DomainSettingValues;
  disabled: boolean;
  pending: boolean;
  error?: string;
  onSave: (patch: DomainSettingValues) => void;
  /** Fields this caller may not change because the Space Manager locked them (#101). */
  lockedFields?: ReadonlySet<string>;
  /** The lock control or lock notice shown under a field. */
  renderLock?: (field: string) => ReactNode;
}) {
  const id = useId();
  const [initial] = useState(() => toDraft(values));
  const [draft, setDraft] = useState(initial);
  const [problem, setProblem] = useState("");
  const dirty = (Object.keys(initial) as Field[]).some((field) => initial[field] !== draft[field]);
  const set = (field: Field, value: string | boolean) => { setDraft((current) => ({ ...current, [field]: value })); setProblem(""); };

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const result = changes(values, initial, draft);
    if (result.error) { setProblem(result.error); return; }
    onSave(result.patch ?? {});
  }

  return <form className="grid min-w-0" onSubmit={submit}>
    {(Object.keys(initial) as Field[]).map((field) => {
      const inputId = `${id}-${field}`;
      const value = draft[field];
      const fieldDisabled = disabled || (lockedFields?.has(field) ?? false);
      return <SettingsRow key={field} label={COPY[field].label} helper={COPY[field].helper} htmlFor={inputId}>
        <div className="grid min-w-0 gap-2">
        {typeof value === "boolean" ? (
          <label className="min-h-11 flex items-start gap-3 text-sm text-ink">
            <input id={inputId} className="mt-1 h-4 w-4" type="checkbox" checked={value} disabled={fieldDisabled}
              onChange={(event) => set(field, event.target.checked)} />
            <span>{value ? t`On` : t`Off`}</span>
          </label>
        ) : field === "event_default_registration_audience" ? (
          <select id={inputId} className="desk-input w-full min-w-0" value={String(value)} disabled={fieldDisabled}
            onChange={(event) => set(field, event.target.value)}>
            {AUDIENCES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        ) : (
          <input id={inputId} className="desk-input w-full min-w-0" value={String(value ?? "")} disabled={fieldDisabled}
            inputMode={field === "filament_low_stock_threshold_grams" ? "decimal" : "numeric"}
            onChange={(event) => set(field, event.target.value)} />
        )}
        {renderLock?.(field)}
        </div>
      </SettingsRow>;
    })}
    {problem || error ? <p role="alert" className="text-sm text-danger">{problem || error}</p> : null}
    <SettingsEditorActions dirty={dirty} pending={pending} disabled={disabled || !dirty}
      onDiscard={() => { setDraft(initial); setProblem(""); }} />
  </form>;
}
