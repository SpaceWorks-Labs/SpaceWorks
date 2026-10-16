import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { Field, StatusPill } from "../../components/ui";
import { sectionKinds, type BookingWebsite } from "../bookings/bookingWebsiteTypes";
import { PrivateWebsiteImage } from "./PrivateWebsiteImage";

type Section = BookingWebsite["sections"][number];

/** One website section: its private preview, or its edit fields. Draft state stays with the editor. */
export function BookingWebsiteSectionCard({ section, assets, spaceId, preview, edit, onChange, onRemove }: {
  section: Section; assets: BookingWebsite["assets"]; spaceId: number; preview: boolean; edit: boolean;
  onChange: (values: Partial<Section>) => void; onRemove: () => void;
}) {
  if (preview) return <article className="grid min-w-0 gap-3 rounded-xl border border-line bg-panel p-5">
    <div className="flex flex-wrap items-center gap-2"><h3 className="title-section">{section.title}</h3>
      <StatusPill label={section.visibility === "published" ? "Published" : "Draft"} tone={section.visibility === "published" ? "success" : "neutral"} /></div>
    <RestrictedMarkdown text={section.body} />
    {edit && section.asset_id ? <PrivateWebsiteImage url={`/api/v1/admin/spaces/${spaceId}/website/assets/${section.asset_id}/`} alt={assets?.find((asset) => asset.id === section.asset_id)?.alt_text || section.title} /> : null}
  </article>;
  return <article className="grid min-w-0 gap-4 rounded-xl border border-line bg-panel p-5">
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Section title"><input className="desk-input w-full" disabled={!edit} maxLength={200} value={section.title} onChange={(e) => onChange({ title: e.target.value })} /></Field>
      <Field label="Section slug"><input className="desk-input w-full" disabled={!edit} maxLength={80} value={section.slug} onChange={(e) => onChange({ slug: e.target.value })} /></Field>
      <Field label="Section kind"><select className="desk-input w-full" disabled={!edit} value={section.kind} onChange={(e) => onChange({ kind: e.target.value as Section["kind"] })}>{sectionKinds.map((kind) => <option key={kind}>{kind}</option>)}</select></Field>
      <Field label="Section visibility"><select className="desk-input w-full" disabled={!edit} value={section.visibility} onChange={(e) => onChange({ visibility: e.target.value as Section["visibility"] })}><option value="draft">Draft</option><option value="published">Published</option></select></Field>
    </div>
    <Field label="Text (restricted Markdown)"><textarea className="desk-input w-full" disabled={!edit} rows={4} maxLength={10000} value={section.body} onChange={(e) => onChange({ body: e.target.value })} /></Field>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="HTTP(S) link"><input className="desk-input w-full" disabled={!edit} type="url" maxLength={500} value={section.url} onChange={(e) => onChange({ url: e.target.value })} /></Field>
      <Field label="Gallery image"><select className="desk-input w-full" disabled={!edit} value={section.asset_id ?? ""} onChange={(e) => onChange({ asset_id: Number(e.target.value) || null })}><option value="">None</option>{assets?.map((asset) => <option value={asset.id} key={asset.id}>{asset.alt_text}</option>)}</select></Field>
      <Field label="Position"><input type="number" min={0} max={1000} className="desk-input w-full" disabled={!edit} value={section.position} onChange={(e) => onChange({ position: Number(e.target.value) })} /></Field>
    </div>
    {edit ? <button className="desk-button-danger-outline w-fit" type="button" onClick={onRemove}>Remove section</button> : null}
  </article>;
}
