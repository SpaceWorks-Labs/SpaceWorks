import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SettingsActions, SettingsRow, SettingsSection } from "../../../components/ui";
import { guestErrorText } from "../../guestPasses/api";
import { communityKeys, communityStaffApi, type CommunityPolicy } from "../api";
import { LogoLoader } from "../../../components/LogoLoader";

type Flags = { minors: boolean; volunteer: boolean; joinFunnel: boolean };

/**
 * Settings › Community (decision 223 k): minors, volunteer credit and the join follow-up. Each
 * group shows only while its capability is on; the server refuses a change to a switched-off one.
 */
export function CommunityPolicySettings({ makerspaceId, flags }: { makerspaceId: number; flags: Flags }) {
  const client = useQueryClient();
  const key = communityKeys.policy(makerspaceId);
  const policy = useQuery({ queryKey: key, queryFn: () => communityStaffApi.policy(makerspaceId) });
  const [draft, setDraft] = useState<CommunityPolicy | null>(null);
  useEffect(() => { if (policy.data) setDraft(policy.data); }, [policy.data]);
  const save = useMutation({
    mutationFn: (next: Partial<CommunityPolicy>) => communityStaffApi.savePolicy(makerspaceId, next),
    onSuccess: (data) => { client.setQueryData(key, data); setDraft(data); },
  });
  const changed = draft && policy.data
    ? (Object.keys(draft) as (keyof CommunityPolicy)[]).filter((field) => draft[field] !== policy.data[field]) : [];
  const set = <K extends keyof CommunityPolicy>(field: K, value: CommunityPolicy[K]) => draft && setDraft({ ...draft, [field]: value });
  const check = (field: keyof CommunityPolicy, label: string) => <label className="flex min-h-11 items-center gap-3 text-sm">
    <input type="checkbox" role="switch" className="h-5 w-5 accent-accent" checked={Boolean(draft?.[field])} onChange={(event) => set(field, event.target.checked as never)} />{label}</label>;
  const num = (field: keyof CommunityPolicy, label: string, suffix: string, max?: number) => <label className="flex flex-wrap items-center gap-3 text-sm">
    <input className="desk-input w-28" type="number" min={0} max={max} aria-label={label} value={String(draft?.[field] ?? "")}
      onChange={(event) => set(field, Math.max(0, Math.floor(Number(event.target.value) || 0)) as never)} />{suffix}</label>;
  return <SettingsSection title={t`Community`} description={t`Minors and guardian consent, volunteer credit and the join follow-up.`}>
    {policy.isLoading ? <LogoLoader label={t`Loading community settings…`} size={48} className="min-h-16 py-3" /> : null}
    {policy.isError ? <p role="alert" className="py-4 text-sm text-danger">{guestErrorText(policy.error)}</p> : null}
    {draft ? <form onSubmit={(event) => { event.preventDefault(); save.mutate(Object.fromEntries(changed.map((field) => [field, draft[field]]))); }}>
      {flags.minors ? <>
        <SettingsRow label={t`Minors`} helper={t`People under the adult age need a guardian's signed consent before they join, register, visit, borrow or use machines.`}>
          <div className="grid gap-3">
            {check("minors_admitted", t`Admit people under the adult age`)}
            {num("minors_minimum_age", t`Minimum age`, t`minimum age`, 17)}
            {num("adult_age", t`Adult age`, t`adult age (age of majority)`, 21)}
          </div>
        </SettingsRow>
        <SettingsRow label={t`What minors may do`} helper={t`Consent is valid for the number of days set here, then the guardian signs again.`}>
          <div className="grid gap-3">
            {check("guardian_must_be_present", t`A guardian must be checked in with them`)}
            {check("minors_may_borrow", t`Minors may borrow items`)}
            {check("minors_may_use_machines", t`Minors may use machines`)}
            {num("consent_valid_days", t`Consent valid for`, t`days a consent stays valid`)}
          </div>
        </SettingsRow>
      </> : null}
      {flags.volunteer ? <SettingsRow label={t`Volunteer credit`} helper={t`Approved volunteer minutes turn into a credit on the member's next membership charge. 0 minutes turns conversion off.`}>
        <div className="grid gap-3">
          {num("volunteer_minutes_per_credit", t`Minutes per credit`, t`volunteer minutes earn one credit`)}
          <label className="grid gap-1 text-sm">{t`Each credit is`}
            <select className="desk-input w-full" value={draft.volunteer_credit_kind} onChange={(event) => set("volunteer_credit_kind", event.target.value as CommunityPolicy["volunteer_credit_kind"])}>
              <option value="discount">{t`A discount amount`}</option><option value="free_days">{t`Free days on the next term`}</option></select></label>
          {draft.volunteer_credit_kind === "discount"
            ? <label className="grid gap-1 text-sm">{t`Discount per credit (in the space's currency)`}
              <input className="desk-input w-32" inputMode="decimal" value={draft.volunteer_credit_amount} onChange={(event) => set("volunteer_credit_amount", event.target.value.replace(/[^\d.]/g, ""))} /></label>
            : num("volunteer_credit_days", t`Free days per credit`, t`free days per credit`, 366)}
        </div>
      </SettingsRow> : null}
      {flags.joinFunnel ? <SettingsRow label={t`Join follow-up`} helper={t`After an event, attendees who are not members get one opt-in invitation to join.`}>
        <div className="grid gap-3">
          {check("join_followup_enabled", t`Send the follow-up`)}
          {num("join_followup_delay_hours", t`Hours after the event`, t`hours after the event ends`)}
        </div>
      </SettingsRow> : null}
      {save.error ? <p role="alert" className="py-3 text-sm text-danger">{guestErrorText(save.error)}</p> : null}
      {changed.length ? <SettingsActions pending={save.isPending} onDiscard={() => setDraft(policy.data ?? null)} /> : null}
    </form> : null}
  </SettingsSection>;
}
