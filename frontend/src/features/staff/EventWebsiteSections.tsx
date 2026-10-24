import type { EventWebsite, WebsiteSection, WebsiteTarget } from "../events/websiteTypes";
import { sponsorTiers } from "../events/websiteTypes";
import { websiteCard, websiteInput, websiteLabel, websiteLegend } from "./eventWebsiteFormStyles";

const kinds: WebsiteSection["kind"][] = ["intro", "logo", "highlight", "speaker", "track", "room", "sponsor", "faq", "resource", "prizes", "judges", "mentors", "project_gallery", "results"];

export function EventWebsiteSections({ page, target, onChange, disabled }: {
  page: EventWebsite; target: WebsiteTarget; onChange: (page: EventWebsite) => void; disabled: boolean;
}) {
  function update(index: number, values: Partial<WebsiteSection>) {
    onChange({ ...page, sections: page.sections.map((section, n) => n === index ? { ...section, ...values } : section) });
  }
  function selectAsset(index: number, id: string) {
    const asset = page.assets?.find((row) => row.id === Number(id));
    update(index, { asset_id: asset?.id ?? null,
      image_url: asset ? `/api/v1/admin/${target.kind}/${target.id}/website/assets/${asset.id}` : null,
      image_alt_text: asset?.alt_text ?? "" });
  }
  return <section aria-label="Website sections" className="grid min-w-0 gap-4">
    <div><h3 className="title-section">Sections</h3>
      <p className="mt-1 text-sm text-muted">Markdown supports paragraphs, lists, bold and HTTP links. HTML displays as text. Publish only content intended for everyone.</p></div>
    {page.sections.map((row, index) => <fieldset key={index} disabled={disabled} className={`${websiteCard} ${row.visibility === "draft" ? "border-dashed" : ""}`}>
      <legend className={websiteLegend}>Section {index + 1}</legend>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={websiteLabel}>Type<select className={websiteInput} value={row.kind} onChange={(e) => update(index, { kind: e.target.value as WebsiteSection["kind"], options: {} })}>{kinds.map((kind) => <option key={kind}>{kind}</option>)}</select></label>
        <label className={websiteLabel}>Slug<input className={`${websiteInput} code-text`} required pattern="[a-zA-Z0-9_-]+" maxLength={80} value={row.slug} onChange={(e) => update(index, { slug: e.target.value })} /></label>
        <label className={websiteLabel}>Title<input className={websiteInput} required maxLength={200} value={row.title} onChange={(e) => update(index, { title: e.target.value })} /></label>
        <label className={`${websiteLabel} sm:col-span-2`}>Text<textarea className={websiteInput} maxLength={10000} rows={4} value={row.body} onChange={(e) => update(index, { body: e.target.value })} /></label>
        <label className={`${websiteLabel} sm:col-span-2`}>Link<input className={websiteInput} type="url" pattern="[Hh][Tt][Tt][Pp][Ss]?://.*" maxLength={500} value={row.url} onChange={(e) => update(index, { url: e.target.value })} /></label>
        {row.kind === "speaker" ? <>
          {([['headline', 'Headline'], ['organization', 'Organization']] as const).map(([key, label]) => <label key={key} className={websiteLabel}>{label}<input className={websiteInput} maxLength={200} value={row[key] ?? ""} onChange={(e) => update(index, { [key]: e.target.value })} /></label>)}
          {([['website_url', 'Website'], ['linkedin_url', 'LinkedIn'], ['x_url', 'X profile']] as const).map(([key, label]) => <label key={key} className={websiteLabel}>{label}<input className={websiteInput} type="url" pattern="[Hh][Tt][Tt][Pp][Ss]?://.*" maxLength={500} value={row[key] ?? ""} onChange={(e) => update(index, { [key]: e.target.value })} /></label>)}
        </> : null}
        {row.kind === "sponsor" ? <label className={websiteLabel}>Sponsor tier<select className={websiteInput} value={row.sponsor_tier ?? "community_partner"} onChange={(e) => update(index, { sponsor_tier: e.target.value as WebsiteSection["sponsor_tier"] })}>{sponsorTiers.map((tier) => <option key={tier} value={tier}>{tier.replace(/_/g, " ")}</option>)}</select></label> : null}
        {row.kind === "highlight" ? <label className={websiteLabel}>Icon (text or emoji)<input className={websiteInput} maxLength={40} value={row.icon ?? ""} onChange={(e) => update(index, { icon: e.target.value })} /></label> : null}
        <label className={websiteLabel}>{row.kind === "speaker" ? "Photo" : row.kind === "sponsor" ? "Sponsor logo" : "Image"}<select className={websiteInput} value={row.asset_id ?? ""} onChange={(e) => selectAsset(index, e.target.value)}>
          <option value="">No image</option>{page.assets?.map((asset) => <option key={asset.id} value={asset.id}>{asset.alt_text}</option>)}
        </select></label>
        {["prizes", "judges", "mentors", "project_gallery", "results"].includes(row.kind) ? <>
          <label className={websiteLabel}>Layout<select className={websiteInput} value={row.options?.layout ?? "grid"} onChange={(e) => update(index, { options: { ...row.options, layout: e.target.value as "grid" | "list" } })}><option value="grid">Grid</option><option value="list">List</option></select></label>
          <label className={websiteLabel}>Maximum items<input className={websiteInput} type="number" min={1} max={100} value={row.options?.limit ?? 12} onChange={(e) => update(index, { options: { ...row.options, limit: Number(e.target.value) } })} /></label>
        </> : null}
        <label className={websiteLabel}>Visibility<select className={websiteInput} value={row.visibility} onChange={(e) => update(index, { visibility: e.target.value as WebsiteSection["visibility"] })}><option value="draft">Draft</option><option value="published">Published</option></select></label>
      </div>
      <button className="desk-button-danger-outline justify-self-start" type="button" onClick={() => onChange({ ...page, sections: page.sections.filter((_, n) => n !== index) })}>Remove section {index + 1}</button>
    </fieldset>)}
    {!page.sections.length ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">No sections yet. Add your first section.</p> : null}
    <button className="desk-button justify-self-start" type="button" disabled={disabled || page.sections.length >= 100} onClick={() => onChange({ ...page, sections: [...page.sections, {
      kind: "intro", slug: `section-${page.sections.length + 1}`, title: "", body: "", url: "", asset_id: null, visibility: "draft", position: page.sections.length,
      headline: "", organization: "", website_url: "", linkedin_url: "", x_url: "", sponsor_tier: "community_partner", icon: "",
    }] })}>Add section</button>
  </section>;
}
