import { t } from "@lingui/core/macro";
import { useState } from "react";
import { organizationRelationshipLabel } from "./lifecycleLabels";
import { ConfirmDialog, ListRow, OverflowMenu, StatusPill, PagePager } from "../../components/ui";
import { FlowLayout } from "../../components/layouts/FlowLayout";
import type { Makerspace } from "./panels/shared";
import { useChangeOrganizationLink, useCreateOrganization, useOrganizationLinks, type OrganizationLink } from "./organizationsApi";

export function OrganizationCreate({ onCreated, onClose = () => {} }: { onCreated: (id: number) => void; onClose?: () => void }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const create = useCreateOrganization();
  return <FlowLayout title={t`Create organization`} state={{ status: "ready" }} steps={[{ key: "profile", label: t`Organization profile`, state: "current" }]} current="profile" onCancel={onClose}
    footer={{ next: { label: t`Create organization`, pending: create.isPending, disabled: !name.trim() || !slug.trim(), disabledReason: t`Enter a name and public slug.`, onClick: () => (document.getElementById("create-organization") as HTMLFormElement)?.requestSubmit() } }}
    work={<div className="grid gap-6 md:grid-cols-2"><form id="create-organization" className="grid gap-3" onSubmit={event => { event.preventDefault(); create.mutate({ name: name.trim(), slug: slug.trim() }, { onSuccess: row => { onCreated(row.id); setName(""); setSlug(""); } }); }}>
    <h3 className="title-section">{t`Create organization`}</h3>
    <label>{t`Name`}<input className="desk-input block w-full" required maxLength={200} value={name} onChange={event => setName(event.target.value)} /></label>
    <label>{t`Slug`}<input className="desk-input block w-full" required pattern="[-a-zA-Z0-9_]+" maxLength={50} value={slug} onChange={event => setSlug(event.target.value)} /></label>
    {create.error ? <p role="alert" className="text-danger">{create.error.message}</p> : null}
  </form><aside aria-label={t`Public page preview`} className="rounded-xl border border-dashed border-line bg-surface p-5"><p className="eyebrow">{t`Public page preview`}</p><h2 className="title-panel mt-3">{name || t`Your organization`}</h2><p className="mt-2 break-all text-sm text-muted">/o/{slug || "your-organization"}</p><p className="mt-5 text-sm text-muted">{t`Your public profile will appear here.`}</p></aside></div>} />;
}

export function OrganizationLinks({ id, makerspaces }: { id: number; makerspaces: Makerspace[] }) {
  const [page, setPage] = useState(1);
  const links = useOrganizationLinks(id, true, page);
  const change = useChangeOrganizationLink(id);
  const [space, setSpace] = useState("");
  const [relationship, setRelationship] = useState<OrganizationLink["relationship"]>("affiliate");
  const [pending, setPending] = useState<{ makerspace_id: number; relationship?: OrganizationLink["relationship"] } | null>(null);
  return <section className="grid gap-3 rounded border border-line p-4">
    <h3 className="title-section">{t`Linked makerspaces`}</h3>
    <p className="text-sm text-muted">{t`Linking a space extends the organization's granted actions to it. Relationship labels describe the connection; all three can confer those actions.`}</p>
    <label>{t`Makerspace`}<select className="desk-input block w-full" value={space} onChange={event => setSpace(event.target.value)}><option value="">{t`Choose space`}</option>{makerspaces.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
    <label>{t`Relationship`}<select className="desk-input block max-w-full" value={relationship} onChange={event => setRelationship(event.target.value as OrganizationLink["relationship"])}>{["affiliate", "manager", "owner"].map(value => <option key={value}>{value}</option>)}</select></label>
    <button className="desk-button" disabled={!space || change.isPending} onClick={() => setPending({ makerspace_id: Number(space), relationship })}>{t`Link or update relationship`}</button>
    {links.isLoading ? <p role="status">{t`Loading links…`}</p> : null}
    {links.error || change.error ? <p role="alert" className="text-danger">{(links.error ?? change.error)?.message}</p> : null}
    <div className="grid gap-3">{links.data?.results.map(row => <ListRow key={row.id} title={row.makerspace_name} identity={{ kind: "icon", icon: "Settings", tone: "accent" }} right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={organizationRelationshipLabel(row.relationship)} /><OverflowMenu actions={[{ label: t`Unlink`, tone: "danger", disabled: change.isPending, disabledReason: t`Wait while the relationship is updated.`, onClick: () => setPending({ makerspace_id: row.makerspace_id }) }]} /></div>} />)}</div>
    <PagePager page={page} setPage={setPage} next={links.data?.next} />
    <ConfirmDialog open={Boolean(pending)} title={pending?.relationship ? t`Change organization reach?` : t`Unlink makerspace?`} message={t`This changes which spaces organization members can act in.`} confirmLabel={t`Confirm`} onCancel={() => setPending(null)} onConfirm={() => { if (pending) change.mutate(pending, { onSuccess: () => setPending(null) }); }} pending={change.isPending} />
  </section>;
}
