import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { SettingsActions, SettingsRow, SettingsSection } from "../../../components/ui";
import { guestErrorText, guestKeys, guestStaffApi, type GuestPassPolicy } from "../../guestPasses/api";
import { LogoLoader } from "../../../components/LogoLoader";

type Waiver = Pick<GuestPassPolicy, "waiver_required_on_site" | "waiver_gate_without_passes">;
const pick = (policy: GuestPassPolicy): Waiver =>
  ({ waiver_required_on_site: policy.waiver_required_on_site, waiver_gate_without_passes: policy.waiver_gate_without_passes });

/**
 * EV-25 (decision 226(a), open item B12): the non-member waiver gate lives outside the Guest passes
 * section, so a space can keep (or set) it while guest passes are off. It shares the guest-pass policy
 * row and sends a partial PATCH with only the two waiver switches.
 */
export function GuestWaiverSettings({ makerspaceId, passesOn }: { makerspaceId: number; passesOn: boolean }) {
  const client = useQueryClient();
  const key = guestKeys.policy(makerspaceId);
  const policy = useQuery({ queryKey: key, queryFn: () => guestStaffApi.policy(makerspaceId) });
  const [draft, setDraft] = useState<Waiver | null>(null);
  useEffect(() => { if (policy.data) setDraft(pick(policy.data)); }, [policy.data]);
  const save = useMutation({
    mutationFn: (next: Waiver) => guestStaffApi.savePolicy(makerspaceId, next),
    onSuccess: (data) => { client.setQueryData(key, data); setDraft(pick(data)); },
  });
  const dirty = Boolean(draft && policy.data && JSON.stringify(draft) !== JSON.stringify(pick(policy.data)));
  const toggle = (field: keyof Waiver, label: string) =>
    <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" role="switch" className="h-5 w-5 accent-accent"
      checked={Boolean(draft?.[field])} onChange={(event) => draft && setDraft({ ...draft, [field]: event.target.checked })} />{label}</label>;

  return <SettingsSection title={t`Visitor waiver`} description={t`Whether a non-member must accept the current waiver before checking in.`}>
    {policy.isLoading ? <LogoLoader label={t`Loading the waiver rule…`} size={48} className="min-h-16 py-3" /> : null}
    {policy.isError ? <div role="alert" className="flex flex-wrap items-center gap-3 py-4 text-sm text-danger">
      {guestErrorText(policy.error)}
      <button type="button" className="desk-button" onClick={() => void policy.refetch()}>{t`Try again`}</button></div> : null}
    {draft ? <form onSubmit={(event) => { event.preventDefault(); save.mutate(draft); }}>
      <SettingsRow label={t`Waiver before a guest is on site`} helper={t`Guests accept the current waiver on their phone or at the desk before checking in.`}>
        <div className="grid gap-3">
          {toggle("waiver_required_on_site", t`Require the waiver`)}
          {draft.waiver_required_on_site ? toggle("waiver_gate_without_passes", passesOn
            ? t`Keep asking for the waiver if guest passes are switched off`
            : t`Ask for the waiver while guest passes are off`) : null}
        </div>
      </SettingsRow>
      {save.error ? <p role="alert" className="py-3 text-sm text-danger">{guestErrorText(save.error)}</p> : null}
      {dirty ? <SettingsActions pending={save.isPending} onDiscard={() => setDraft(policy.data ? pick(policy.data) : null)} /> : null}
    </form> : null}
  </SettingsSection>;
}
