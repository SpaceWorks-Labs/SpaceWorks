import type { EventWebsite, WebsiteSection, WebsiteTarget } from "../events/websiteTypes";
import { sponsorTiers } from "../events/websiteTypes";

const kinds: WebsiteSection["kind"][] = ["intro", "logo", "highlight", "speaker", "track", "room", "sponsor", "faq", "resource"];

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
  return <section aria-label="Website sections" className="grid gap-3">
    <h4 className="font-semibold">Sections</h4>
    <p className="text-sm text-muted">Markdown supports paragraphs, lists, bold and HTTP links. HTML displays as text. Publish only content intended for everyone.</p>
    {page.sections.map((row, index) => <fieldset key={index} disabled={disabled} className="grid gap-2 rounded-lg border border-border p-3">
      <legend className="px-1">Section {index + 1}</legend>
      <label>Type<select className="desk-input" value={row.kind} onChange={(e) => update(index, { kind: e.target.value as WebsiteSection["kind"] })}>{kinds.map((kind) => <option key={kind}>{kind}</option>)}</select></label>
      <label>Slug<input className="desk-input" required pattern="[a-zA-Z0-9_-]+" maxLength={80} value={row.slug} onChange={(e) => update(index, { slug: e.target.value })} /></label>
      <label>Title<input className="desk-input" required maxLength={200} value={row.title} onChange={(e) => update(index, { title: e.target.value })} /></label>
      <label>Text<textarea className="desk-input" maxLength={10000} rows={4} value={row.body} onChange={(e) => update(index, { body: e.target.value })} /></label>
      <label>Link<input className="desk-input" type="url" pattern="[Hh][Tt][Tt][Pp][Ss]?://.*" maxLength={500} value={row.url} onChange={(e) => update(index, { url: e.target.value })} /></label>
      {row.kind === "speaker" ? <>
        {([['headline', 'Headline'], ['organization', 'Organization']] as const).map(([key, label]) => <label key={key}>{label}<input className="desk-input" maxLength={200} value={row[key] ?? ""} onChange={(e) => update(index, { [key]: e.target.value })} /></label>)}
        {([['website_url', 'Website'], ['linkedin_url', 'LinkedIn'], ['x_url', 'X profile']] as const).map(([key, label]) => <label key={key}>{label}<input className="desk-input" type="url" pattern="[Hh][Tt][Tt][Pp][Ss]?://.*" maxLength={500} value={row[key] ?? ""} onChange={(e) => update(index, { [key]: e.target.value })} /></label>)}
      </> : null}
      {row.kind === "sponsor" ? <label>Sponsor tier<select className="desk-input" value={row.sponsor_tier ?? "community_partner"} onChange={(e) => update(index, { sponsor_tier: e.target.value as WebsiteSection["sponsor_tier"] })}>{sponsorTiers.map((tier) => <option key={tier} value={tier}>{tier.replace(/_/g, " ")}</option>)}</select></label> : null}
      {row.kind === "highlight" ? <label>Icon (text or emoji)<input className="desk-input" maxLength={40} value={row.icon ?? ""} onChange={(e) => update(index, { icon: e.target.value })} /></label> : null}
      <label>{row.kind === "speaker" ? "Photo" : row.kind === "sponsor" ? "Sponsor logo" : "Image"}<select className="desk-input" value={row.asset_id ?? ""} onChange={(e) => selectAsset(index, e.target.value)}>
        <option value="">No image</option>{page.assets?.map((asset) => <option key={asset.id} value={asset.id}>{asset.alt_text}</option>)}
      </select></label>
      <label>Visibility<select className="desk-input" value={row.visibility} onChange={(e) => update(index, { visibility: e.target.value as WebsiteSection["visibility"] })}><option value="draft">Draft</option><option value="published">Published</option></select></label>
      <button className="desk-button-danger w-fit" type="button" onClick={() => onChange({ ...page, sections: page.sections.filter((_, n) => n !== index) })}>Remove section {index + 1}</button>
    </fieldset>)}
    <button className="desk-button w-fit" type="button" disabled={disabled || page.sections.length >= 100} onClick={() => onChange({ ...page, sections: [...page.sections, {
      kind: "intro", slug: `section-${page.sections.length + 1}`, title: "", body: "", url: "", asset_id: null, visibility: "draft", position: page.sections.length,
      headline: "", organization: "", website_url: "", linkedin_url: "", x_url: "", sponsor_tier: "community_partner", icon: "",
    }] })}>Add section</button>
  </section>;
}
