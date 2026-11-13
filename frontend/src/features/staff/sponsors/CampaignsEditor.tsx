import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow, Modal, StatusPill } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { donationStaffApi, donationStaffKeys, type CampaignInput, type StaffCampaign } from "./staffDonationsApi";

const blank: CampaignInput = { kind: "campaign", name: "", slug: "", description: "", goal_amount: null, starts_at: null,
  ends_at: null, is_active: true, is_public: true };
const slugify = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);
const local = (value: string | null) => value ? value.slice(0, 16) : "";
const iso = (value: string) => value ? new Date(value).toISOString() : null;

function CampaignForm({ makerspaceId, campaign, onClose }: { makerspaceId: number; campaign?: StaffCampaign; onClose: () => void }) {
  const client = useQueryClient();
  const [form, setForm] = useState<CampaignInput>(campaign ? { ...campaign } : blank);
  const save = useMutation({
    mutationFn: () => campaign ? donationStaffApi.updateCampaign(makerspaceId, campaign.id, form)
      : donationStaffApi.createCampaign(makerspaceId, { ...form, slug: form.slug || slugify(form.name) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: donationStaffKeys.campaigns(makerspaceId) }); onClose(); },
  });
  const set = (patch: Partial<CampaignInput>) => setForm(current => ({ ...current, ...patch }));
  return <Modal open onClose={onClose} title={campaign ? t`Edit campaign` : t`New campaign or fund`}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      <Field label={t`Kind`}><select className="desk-input" value={form.kind} onChange={event => set({ kind: event.target.value as CampaignInput["kind"] })}>
        <option value="campaign">{t`Campaign (a goal and a window)`}</option><option value="fund">{t`Fund (always open)`}</option></select></Field>
      <Field label={t`Name`}><input className="desk-input" required maxLength={120} value={form.name}
        onChange={event => set({ name: event.target.value })} /></Field>
      <Field label={t`Description`}><textarea className="desk-input" rows={3} value={form.description}
        onChange={event => set({ description: event.target.value })} /></Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t`Goal (optional)`}><input className="desk-input tabular-nums" inputMode="decimal" value={form.goal_amount ?? ""}
          onChange={event => set({ goal_amount: event.target.value || null })} /></Field>
        <Field label={t`Opens`}><input className="desk-input" type="datetime-local" value={local(form.starts_at)}
          onChange={event => set({ starts_at: iso(event.target.value) })} /></Field>
        <Field label={t`Closes`}><input className="desk-input" type="datetime-local" value={local(form.ends_at)}
          onChange={event => set({ ends_at: iso(event.target.value) })} /></Field>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active}
        onChange={event => set({ is_active: event.target.checked })} />{t`Taking gifts`}</label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.is_public}
        onChange={event => set({ is_public: event.target.checked })} />{t`Shown on the donation page`}</label>
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
      <div className="flex justify-end gap-2"><button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button" disabled={save.isPending}>{t`Save`}</button></div>
    </form>
  </Modal>;
}

/** Campaigns (a goal and a window) and funds (always open) a gift can go to. */
export function CampaignsEditor({ makerspaceId, campaigns, canRecord }: {
  makerspaceId: number; campaigns: StaffCampaign[]; canRecord: boolean;
}) {
  const [editing, setEditing] = useState<StaffCampaign | "new" | null>(null);
  return <div className="grid gap-4">
    {canRecord ? <button type="button" className="desk-button justify-self-start" onClick={() => setEditing("new")}>{t`New campaign`}</button> : null}
    {!campaigns.length ? <EmptyState message={t`No campaigns yet. Gifts go to the space in general.`} /> : null}
    {campaigns.map(row => <ListRow key={row.id} title={row.name} identity={{ kind: "icon", icon: "Info", tone: "neutral" }}
      meta={[row.kind === "fund" ? "Fund" : "Campaign", row.goal_amount ? `Goal ${row.currency.toUpperCase()} ${row.goal_amount}` : "",
        row.ends_at ? `Closes ${new Date(row.ends_at).toLocaleDateString(formatLocale())}` : ""].filter(Boolean).join(" · ")}
      right={<div className="flex items-center gap-2"><StatusPill label={row.is_active ? t`Open` : t`Closed`} tone={row.is_active ? "success" : "neutral"} />
        {canRecord ? <button type="button" className="desk-button-ghost" onClick={() => setEditing(row)}>{t`Edit`}</button> : null}</div>} />)}
    {editing ? <CampaignForm makerspaceId={makerspaceId} campaign={editing === "new" ? undefined : editing}
      onClose={() => setEditing(null)} /> : null}
  </div>;
}
