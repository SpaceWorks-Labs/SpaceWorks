import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SettingsActions, SettingsRow, SettingsSection } from "../../../components/ui";
import { guestErrorText, guestKeys, guestStaffApi, type GuestPassPolicy } from "../api";
import { BORROW_MODES, MACHINE_MODES, borrowModeLabel, machineModeLabel } from "../labels";

const count = (value: string) => (value.trim() === "" ? null : Math.max(0, Math.floor(Number(value))));
/** EV-25: the waiver switches are edited in Settings › Visitor waiver (reachable with passes off), so this form never sends them. */
const WAIVER_FIELDS = new Set<string>(["waiver_required_on_site", "waiver_gate_without_passes"]);
const withoutWaiver = (policy: GuestPassPolicy): Partial<GuestPassPolicy> =>
  Object.fromEntries(Object.entries(policy).filter(([field]) => !WAIVER_FIELDS.has(field)));

/** Settings › Guest passes: how guests may borrow, use machines and be sponsored (223 c, d, f, i, j). */
export function GuestPassPolicySettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const key = guestKeys.policy(makerspaceId);
  const policy = useQuery({ queryKey: key, queryFn: () => guestStaffApi.policy(makerspaceId) });
  const [draft, setDraft] = useState<GuestPassPolicy | null>(null);
  useEffect(() => { if (policy.data) setDraft(policy.data); }, [policy.data]);
  const save = useMutation({
    mutationFn: (next: GuestPassPolicy) => guestStaffApi.savePolicy(makerspaceId, withoutWaiver(next)),
    onSuccess: (data) => { client.setQueryData(key, data); setDraft(data); },
  });
  const dirty = Boolean(draft && policy.data && JSON.stringify(withoutWaiver(draft)) !== JSON.stringify(withoutWaiver(policy.data)));
  const set = <K extends keyof GuestPassPolicy>(field: K, value: GuestPassPolicy[K]) => draft && setDraft({ ...draft, [field]: value });
  const toggle = (field: "sponsor_must_be_present", label: string) =>
    <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" role="switch" className="h-5 w-5 accent-accent"
      checked={Boolean(draft?.[field])} onChange={(event) => set(field, event.target.checked)} />{label}</label>;
  const number = (field: keyof GuestPassPolicy, label: string, optional = false) =>
    <input className="desk-input w-32" type="number" min={0} aria-label={label} value={draft?.[field] === null ? "" : String(draft?.[field] ?? "")}
      placeholder={optional ? t`No limit` : undefined}
      onChange={(event) => set(field, (optional ? count(event.target.value) : count(event.target.value) ?? 0) as never)} />;

  return <SettingsSection title={t`Guest pass rules`} description={t`Live passes keep the rules they were issued with; changes apply to new passes.`}>
    {policy.isLoading ? <p role="status" className="py-4 text-sm text-muted">{t`Loading guest pass rules…`}</p> : null}
    {policy.isError ? <p role="alert" className="py-4 text-sm text-danger">{guestErrorText(policy.error)}</p> : null}
    {draft ? <form onSubmit={(event) => { event.preventDefault(); save.mutate(draft); }}>
      <SettingsRow label={t`Guest borrowing`} helper={t`On site only: items are due back by the end of the pass. Full borrowing always takes a deposit.`}>
        <select className="desk-input w-full" aria-label={t`Guest borrowing`} value={draft.guest_borrowing_mode} onChange={(event) => set("guest_borrowing_mode", event.target.value as GuestPassPolicy["guest_borrowing_mode"])}>
          {BORROW_MODES.map((mode) => <option key={mode} value={mode}>{borrowModeLabel(mode)}</option>)}</select>
      </SettingsRow>
      <SettingsRow label={t`Guest machine use`} helper={t`Supervised: only inside a certified instructor's session. After induction: a certification granted at an induction event.`}>
        <select className="desk-input w-full" aria-label={t`Guest machine use`} value={draft.guest_machine_mode} onChange={(event) => set("guest_machine_mode", event.target.value as GuestPassPolicy["guest_machine_mode"])}>
          {MACHINE_MODES.map((mode) => <option key={mode} value={mode}>{machineModeLabel(mode)}</option>)}</select>
      </SettingsRow>
      <SettingsRow label={t`Who pays for a sponsored guest's lost or damaged items`} helper={t`Either way the sponsor is told, and an incident is noted on the sponsor's record.`}>
        <select className="desk-input w-full" aria-label={t`Liability for sponsored guests`} value={draft.sponsored_liability} onChange={(event) => set("sponsored_liability", event.target.value as GuestPassPolicy["sponsored_liability"])}>
          <option value="guest">{t`The guest, as the accountable borrower`}</option><option value="sponsor">{t`The sponsoring member`}</option></select>
      </SettingsRow>
      <SettingsRow label={t`Walk-in and door registration creates`} helper={t`A non-member registered at the door or desk gets a guest pass for the day, or a full membership as before.`}>
        <select className="desk-input w-full" aria-label={t`Walk-in registration creates`} value={draft.walk_in_registration_creates} onChange={(event) => set("walk_in_registration_creates", event.target.value as GuestPassPolicy["walk_in_registration_creates"])}>
          <option value="guest_pass">{t`A guest pass`}</option><option value="membership">{t`A full membership`}</option></select>
      </SettingsRow>
      <SettingsRow label={t`Sponsoring members`} helper={t`Who may bring a guest, and how many at once.`}>
        <div className="grid gap-3">
          {toggle("sponsor_must_be_present", t`The member must be checked in`)}
          <label className="flex flex-wrap items-center gap-3 text-sm">{number("sponsor_min_tenure_days", t`Days of membership before bringing guests`)}{t`days of membership first`}</label>
          <label className="flex flex-wrap items-center gap-3 text-sm">{number("max_concurrent_guests_per_sponsor", t`Guests per member at once`)}{t`guests per member at once`}</label>
        </div>
      </SettingsRow>
      <SettingsRow label={t`Visits and joining`} helper={t`After this many visits in 30 days a guest is invited to join. A visit limit refuses further passes until they join.`}>
        <div className="grid gap-3">
          <label className="flex flex-wrap items-center gap-3 text-sm">{number("visits_before_join_prompt", t`Visits before the join prompt`)}{t`visits before suggesting membership`}</label>
          <label className="flex flex-wrap items-center gap-3 text-sm">{number("hard_visit_cap", t`Visit limit`, true)}{t`visit limit (blank for none)`}</label>
          <label className="flex flex-wrap items-center gap-3 text-sm">{number("day_pass_daily_cap", t`Day passes per day`, true)}{t`day passes sold per day (blank for no limit)`}</label>
        </div>
      </SettingsRow>
      {save.error ? <p role="alert" className="py-3 text-sm text-danger">{guestErrorText(save.error)}</p> : null}
      {dirty ? <SettingsActions pending={save.isPending} onDiscard={() => setDraft(policy.data ?? null)} /> : null}
    </form> : null}
  </SettingsSection>;
}
