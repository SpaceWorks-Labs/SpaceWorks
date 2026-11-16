import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { formatDateTime } from "../../../lib/format";
import type { StaffEvent } from "../eventsApiTypes";

export type CloseRule = "open" | "before" | "at";
/** The fourth publishing question (parity E-F3, B2): spots, when sign-ups close, the public count and approval. */
export type SignupAnswers = {
  capacity: number; close: CloseRule; lead_minutes: number; closes_at: string;
  show_registration_count: boolean; registration_requires_approval: boolean;
};

const localInput = (value: string) => { const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16); };

export function signupAnswersFor(event: StaffEvent): SignupAnswers {
  return { capacity: event.capacity, show_registration_count: event.show_registration_count ?? true,
    registration_requires_approval: event.registration_requires_approval,
    close: event.registration_cutoff_at ? "at" : event.registration_cutoff_lead_minutes !== null ? "before" : "open",
    lead_minutes: event.registration_cutoff_lead_minutes ?? 120, closes_at: event.registration_cutoff_at ? localInput(event.registration_cutoff_at) : "" };
}

/** Only the event fields that changed, ready for the event PATCH (no change answers an empty object). */
export function signupPatch(before: SignupAnswers, after: SignupAnswers) {
  const patch: Record<string, unknown> = {};
  if (before.capacity !== after.capacity) patch.capacity = after.capacity;
  if (before.show_registration_count !== after.show_registration_count) patch.show_registration_count = after.show_registration_count;
  if (before.registration_requires_approval !== after.registration_requires_approval) patch.registration_requires_approval = after.registration_requires_approval;
  const cutoff = (value: SignupAnswers) => ({
    registration_cutoff_at: value.close === "at" && value.closes_at ? new Date(value.closes_at).toISOString() : null,
    registration_cutoff_lead_minutes: value.close === "before" ? value.lead_minutes : null });
  if (JSON.stringify(cutoff(before)) !== JSON.stringify(cutoff(after))) Object.assign(patch, cutoff(after));
  return patch;
}

export function leadText(minutes: number) {
  if (minutes && minutes % 1440 === 0) return plural(minutes / 1440, { one: "# day", other: "# days" });
  if (minutes && minutes % 60 === 0) return plural(minutes / 60, { one: "# hour", other: "# hours" });
  return plural(minutes, { one: "# minute", other: "# minutes" });
}

/** "40 spots · closes 2 hours before · you approve each sign-up": the sign-up half of the summary line. */
export function signupSummary(answers: SignupAnswers) {
  const spots = answers.capacity ? plural(answers.capacity, { one: "# spot", other: "# spots" }) : t`unlimited spots`;
  const closing = answers.close === "before" ? (answers.lead_minutes ? t`closes ${leadText(answers.lead_minutes)} before the start` : t`closes when it starts`)
    : answers.close === "at" && answers.closes_at ? t`closes ${formatDateTime(answers.closes_at)}` : t`no closing time`;
  const approval = answers.registration_requires_approval ? t`you approve each sign-up` : t`places are confirmed straight away`;
  return [spots, closing, approval].join(" · ");
}

const UNITS = [[1, () => t`minutes`], [60, () => t`hours`], [1440, () => t`days`]] as const;

export function SignupsQuestion({ answers, onChange, approvalLocked, idPrefix }: {
  answers: SignupAnswers; onChange: (patch: Partial<SignupAnswers>) => void; approvalLocked: boolean; idPrefix: string;
}) {
  const [unit, setUnit] = useState(() => UNITS.slice().reverse().find(([size]) => answers.lead_minutes % size === 0)?.[0] ?? 1);
  const row = "grid gap-2 p-4";
  return <fieldset className="grid gap-2"><legend className="mb-1 text-sm font-semibold">{t`4. How do sign-ups work?`}</legend>
    <div className="grid divide-y divide-line rounded-control border border-line">
      <div className={row}>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" className="h-5 w-5 accent-accent" checked={answers.capacity > 0}
          onChange={event => onChange({ capacity: event.target.checked ? 50 : 0 })} />{t`Limit the number of spots`}</label>
        {answers.capacity > 0 ? <label className="flex flex-wrap items-center gap-2 text-sm"><span className="sr-only">{t`Number of spots`}</span>
          <input className="desk-input w-28 tabular-nums" type="number" min={1} inputMode="numeric" value={answers.capacity}
            onChange={event => onChange({ capacity: Math.max(1, Number(event.target.value) || 1) })} />
          <span className="text-muted">{t`spots. When it is full, new sign-ups join the waitlist.`}</span></label>
          : <p className="text-sm text-muted">{t`Unlimited: everyone who signs up gets a place.`}</p>}
      </div>
      <div className={row} role="group" aria-labelledby={`${idPrefix}-close`}>
        <p id={`${idPrefix}-close`} className="text-sm font-semibold">{t`Close sign-ups`}</p>
        <div className="flex flex-wrap gap-2">{([["open", t`Keep open`], ["before", t`Before the start`], ["at", t`At a set time`]] as const).map(([value, label]) =>
          <label key={value} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-control border border-line px-3 text-sm has-checked:border-brand-boundary has-checked:bg-brand-soft">
            <input type="radio" name={`${idPrefix}-close-rule`} checked={answers.close === value} onChange={() => onChange({ close: value })} />{label}</label>)}</div>
        {answers.close === "before" ? <div className="flex flex-wrap items-center gap-2 text-sm">
          <input className="desk-input w-24 tabular-nums" type="number" min={0} aria-label={t`How long before the start`} value={answers.lead_minutes / unit}
            onChange={event => onChange({ lead_minutes: Math.max(0, Math.round(Number(event.target.value) || 0)) * unit })} />
          <select className="desk-input" aria-label={t`Unit`} value={unit} onChange={event => { const next = Number(event.target.value); onChange({ lead_minutes: Math.round(answers.lead_minutes / unit) * next }); setUnit(next as typeof unit); }}>
            {UNITS.map(([size, label]) => <option key={size} value={size}>{label()}</option>)}</select>
          <span className="text-muted">{t`before the start. Moves with the start time.`}</span></div> : null}
        {answers.close === "at" ? <input className="desk-input sm:max-w-xs" type="datetime-local" aria-label={t`Sign-ups close at`} required value={answers.closes_at}
          onChange={event => onChange({ closes_at: event.target.value })} /> : null}
      </div>
      <label className={`${row} flex min-h-11 items-center gap-3 text-sm`}><input type="checkbox" className="h-5 w-5 accent-accent" checked={answers.show_registration_count}
        onChange={event => onChange({ show_registration_count: event.target.checked })} />
        <span><span className="font-semibold">{t`Show how many are going`}</span><span className="block text-muted">{t`Guests see the number of sign-ups on the event page.`}</span></span></label>
      <label className={`${row} flex min-h-11 items-center gap-3 text-sm`}><input type="checkbox" className="h-5 w-5 accent-accent" checked={answers.registration_requires_approval}
        disabled={approvalLocked} onChange={event => onChange({ registration_requires_approval: event.target.checked })} />
        <span><span className="font-semibold">{t`Approve each sign-up`}</span><span className="block text-muted">{approvalLocked
          ? t`Approval is set before the event is published and cannot change after.` : t`People wait for your decision before their place is confirmed.`}</span></span></label>
    </div>
  </fieldset>;
}
