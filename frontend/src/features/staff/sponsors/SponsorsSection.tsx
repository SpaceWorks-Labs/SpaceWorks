import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailDrawer, EmptyState, ListRow, StatusPill, Tabs } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { ImageUploader } from "../ImageUploader";
import { SponsorCharges, SponsorEventLinks } from "./SponsorMoneyAndEvents";
import { SponsorForm } from "./SponsorForm";
import { SponsorPerks } from "./SponsorPerks";
import { sponsorApi, sponsorKeys, type Sponsor } from "./staffSponsorsApi";
import { TiersEditor } from "./TiersEditor";

function SponsorDrawer({ makerspaceId, sponsor, canRecord, onEdit, onClose }: {
  makerspaceId: number; sponsor: Sponsor; canRecord: boolean; onEdit: () => void; onClose: () => void;
}) {
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: ["staff-sponsors", makerspaceId] });
  const archive = useMutation({ mutationFn: () => sponsorApi.archive(makerspaceId, sponsor.id, !sponsor.archived_at),
    onSuccess: () => { refresh(); onClose(); } });
  return <DetailDrawer open title={sponsor.name} onClose={onClose}><div className="grid gap-6">
    <dl className="grid gap-2 text-sm">
      {sponsor.tier_name ? <div><dt className="text-muted">{t`Tier`}</dt><dd>{sponsor.tier_name}</dd></div> : null}
      {sponsor.contact_name || sponsor.contact_email ? <div><dt className="text-muted">{t`Contact (private)`}</dt>
        <dd>{[sponsor.contact_name, sponsor.contact_email, sponsor.contact_phone].filter(Boolean).join(" · ")}</dd></div> : null}
      <div><dt className="text-muted">{t`Sponsor wall`}</dt><dd>{sponsor.show_on_wall ? t`Shown` : t`Hidden`}</dd></div>
    </dl>
    {canRecord ? <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button" onClick={onEdit}>{t`Edit`}</button>
      <button type="button" className="desk-button-ghost" disabled={archive.isPending} onClick={() => archive.mutate()}>
        {sponsor.archived_at ? t`Restore` : t`Archive`}</button></div> : null}
    {archive.error ? <p role="alert" className="text-sm text-danger">{financeError(archive.error)}</p> : null}
    {canRecord ? <ImageUploader endpoint={sponsorApi.logoEndpoint(makerspaceId, sponsor.id)} currentUrl={sponsor.logo_url || null}
      label={t`Logo (public, on the sponsor wall)`} fit="contain" onChanged={refresh} /> : null}
    <SponsorPerks makerspaceId={makerspaceId} sponsorId={sponsor.id} canRecord={canRecord} />
    <SponsorCharges makerspaceId={makerspaceId} sponsorId={sponsor.id} canRecord={canRecord} />
    <SponsorEventLinks makerspaceId={makerspaceId} sponsorId={sponsor.id} canRecord={canRecord} />
  </div></DetailDrawer>;
}

function SponsorsList({ makerspaceId, canRecord }: { makerspaceId: number; canRecord: boolean }) {
  const [archived, setArchived] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Sponsor | "new" | null>(null);
  const sponsors = useQuery({ queryKey: sponsorKeys.list(makerspaceId, archived), queryFn: () => sponsorApi.list(makerspaceId, archived) });
  const tiers = useQuery({ queryKey: sponsorKeys.tiers(makerspaceId), queryFn: () => sponsorApi.tiers(makerspaceId) });
  const open = sponsors.data?.find(row => row.id === openId);
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={archived}
        onChange={event => setArchived(event.target.checked)} />{t`Include archived`}</label>
      {canRecord ? <button type="button" className="desk-button ml-auto" onClick={() => setEditing("new")}>{t`Add a sponsor`}</button> : null}
    </div>
    {sponsors.error ? <p role="alert" className="text-sm text-danger">{financeError(sponsors.error)}</p> : null}
    {sponsors.data && !sponsors.data.length ? <EmptyState message={t`No sponsors yet.`} /> : null}
    {sponsors.data?.map(row => <ListRow key={row.id} title={row.name} onClick={() => setOpenId(row.id)}
      identity={row.logo_url ? { kind: "image", src: row.logo_url } : { kind: "avatar", name: row.name, seed: String(row.id) }}
      meta={[row.tier_name, row.ends_on ? `Until ${new Date(row.ends_on).toLocaleDateString(formatLocale())}` : ""].filter(Boolean).join(" · ")}
      right={<div className="flex flex-wrap gap-2">{row.perks_open ? <StatusPill label={t`${row.perks_open} perks open`} tone="warn" /> : null}
        {row.archived_at ? <StatusPill label={t`Archived`} tone="neutral" /> : null}</div>} />)}
    {open ? <SponsorDrawer makerspaceId={makerspaceId} sponsor={open} canRecord={canRecord} onClose={() => setOpenId(null)}
      onEdit={() => setEditing(open)} /> : null}
    {editing ? <SponsorForm makerspaceId={makerspaceId} sponsor={editing === "new" ? undefined : editing} tiers={tiers.data ?? []}
      onClose={() => setEditing(null)} /> : null}
  </div>;
}

/** Sponsors (`finance.sponsors`): sponsors, perk checklists, sponsorship money, event links and tiers. */
export function SponsorsSection({ makerspaceId, canRecordPayment }: { makerspaceId: number; canRecordPayment: boolean }) {
  const [tab, setTab] = useState("sponsors");
  return <section className="grid gap-4" aria-label={t`Sponsors`}>
    <Tabs tabs={[{ key: "sponsors", label: t`Sponsors` }, { key: "tiers", label: t`Tiers and perks` }]} activeKey={tab}
      label={t`Sponsor sections`} onChange={setTab} />
    {tab === "sponsors" ? <SponsorsList makerspaceId={makerspaceId} canRecord={canRecordPayment} />
      : <TiersEditor makerspaceId={makerspaceId} canRecord={canRecordPayment} />}
  </section>;
}
