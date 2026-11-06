import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow, StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { listPlans, membershipPlanKeys } from "../membershipPlansApi";
import { lifecycleApi, lifecycleKeys, type InviteLink } from "../membershipLifecycleApi";
import { Panel } from "../panels/shared";

const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`That did not work.`);

/** X11: multi-use invite links with a use limit, expiry and revoke. The code is shown once. */
export function InviteLinksManager({ makerspaceId, slug }: { makerspaceId: number; slug: string }) {
  const client = useQueryClient();
  const links = useQuery({ queryKey: lifecycleKeys.invites(makerspaceId), queryFn: () => lifecycleApi.invites(makerspaceId) });
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const [label, setLabel] = useState("");
  const [planId, setPlanId] = useState("");
  const [maxUses, setMaxUses] = useState("25");
  const [created, setCreated] = useState<InviteLink | null>(null);
  const refresh = () => client.invalidateQueries({ queryKey: lifecycleKeys.invites(makerspaceId) });
  const create = useMutation({
    mutationFn: () => lifecycleApi.createInvite(makerspaceId, { label: label.trim(), plan_id: planId ? Number(planId) : null,
      max_uses: Number(maxUses), expires_at: null }),
    onSuccess: (link) => { setCreated(link); setLabel(""); void refresh(); },
  });
  const revoke = useMutation({ mutationFn: (id: number) => lifecycleApi.revokeInvite(id), onSuccess: () => { void refresh(); } });
  const shareUrl = created?.code ? `${window.location.origin}/m/${slug}/join?invite=${encodeURIComponent(created.code)}` : "";
  const failure = create.error ?? revoke.error;
  return <Panel title={t`Invite links`}>
    <p className="mb-3 text-sm text-muted">{t`A link lets people join even when the space or plan is invite-only. Each use is counted; revoke a link at any time.`}</p>
    {created?.code ? <div role="status" className="mb-3 grid gap-1 rounded-xl border border-line p-3 text-sm">
      <span>{t`Copy this link now; it is not shown again.`}</span>
      <input className="desk-input" readOnly value={shareUrl} aria-label={t`New invite link`} onFocus={(event) => event.target.select()} />
    </div> : null}
    {links.isSuccess && !links.data.length ? <EmptyState message={t`No invite links yet.`} /> : null}
    {links.data?.map((link) => <ListRow key={link.id} title={link.label || t`Link #${link.id}`} identity={{ kind: "icon", icon: "Mail", tone: "accent" }}
      meta={<>{link.plan_name || t`Default plan`} · {link.uses}/{link.max_uses} used</>}
      right={<div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={link.live ? "success" : "neutral"} label={link.live ? t`Live` : link.revoked_at ? t`Revoked` : t`Used up or expired`} />
        {link.live ? <button className="desk-button" type="button" disabled={revoke.isPending} onClick={() => revoke.mutate(link.id)}>{t`Revoke`}</button> : null}
      </div>} />)}
    <form className="mt-4 grid gap-2 sm:grid-cols-4" aria-label={t`New invite link`} onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
      <Field label={t`Label`}><input className="desk-input" maxLength={120} value={label} onChange={(event) => setLabel(event.target.value)} /></Field>
      <Field label={t`Plan`}><select className="desk-input max-w-full" value={planId} onChange={(event) => setPlanId(event.target.value)}>
        <option value="">{t`Space default`}</option>
        {(plans.data ?? []).filter((plan) => plan.is_active).map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}</select></Field>
      <Field label={t`Uses`}><input className="desk-input" inputMode="numeric" value={maxUses} onChange={(event) => setMaxUses(event.target.value)} /></Field>
      <div className="flex items-end"><button className="desk-button-primary" type="submit"
        disabled={create.isPending || !/^[1-9]\d{0,4}$/.test(maxUses)}>{t`Create link`}</button></div>
    </form>
    {failure ? <p role="alert" className="mt-2 text-sm text-danger">{errorText(failure)}</p> : null}
  </Panel>;
}
