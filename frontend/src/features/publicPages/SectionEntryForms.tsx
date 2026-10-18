import { pageInput, pageLabel } from "./documentDefaults";
import type { PageAsset, PageSection, SectionPayloads } from "./pageTypes";

type EntrySection = Extract<PageSection, { type: "team" | "testimonials" | "links" | "gallery" }>;
export function SectionEntryForms({ section, assets, onChange }: { section: EntrySection; assets: PageAsset[]; onChange: (section: PageSection) => void }) {
  if (section.type === "gallery") {
    const items = section.payload.items;
    return <div className="grid gap-3">{items.map((item, index) => <div key={index} className="grid gap-2 rounded-xl border border-line p-3">
      <label className={pageLabel}>Gallery image {index + 1}<select className={pageInput} required value={item.asset_id} onChange={e => onChange({ ...section, payload: { ...section.payload, items: items.map((row, n) => n === index ? { ...row, asset_id: Number(e.target.value) } : row) } })}>
        <option value="">Choose an image</option>{assets.map(asset => <option key={asset.id} value={asset.id}>{asset.alt_text}</option>)}
      </select></label>
      <label className={pageLabel}>Caption<input className={pageInput} maxLength={300} value={item.caption} onChange={e => onChange({ ...section, payload: { ...section.payload, items: items.map((row, n) => n === index ? { ...row, caption: e.target.value } : row) } })} /></label>
      <button type="button" className="desk-button" onClick={() => onChange({ ...section, payload: { ...section.payload, items: items.filter((_, n) => n !== index) } })}>Remove image {index + 1}</button>
    </div>)}<button type="button" className="desk-button justify-self-start" disabled={items.length >= 24 || !assets.length} onClick={() => onChange({ ...section, payload: { ...section.payload, items: [...items, { asset_id: assets[0].id, caption: "" }] } })}>Add gallery image</button></div>;
  }
  if (section.type === "testimonials") {
    const entries = section.payload.entries;
    const change = (index: number, patch: Partial<SectionPayloads["testimonials"]["entries"][number]>) => onChange({ ...section, payload: { ...section.payload, entries: entries.map((entry, n) => n === index ? { ...entry, ...patch } : entry) } });
    return <div className="grid gap-3">{entries.map((entry, index) => <div key={entry.id} className="grid gap-2 rounded-xl border border-line p-3">
      <label className={pageLabel}>Quote {index + 1}<textarea className={pageInput} required rows={3} maxLength={2000} value={entry.quote} onChange={e => change(index, { quote: e.target.value })} /></label>
      <label className={pageLabel}>Attribution<input className={pageInput} required maxLength={200} value={entry.attribution} onChange={e => change(index, { attribution: e.target.value })} /></label>
      <button type="button" className="desk-button" onClick={() => onChange({ ...section, payload: { ...section.payload, entries: entries.filter((_, n) => n !== index) } })}>Remove quote {index + 1}</button>
    </div>)}<button type="button" className="desk-button justify-self-start" disabled={entries.length >= 20} onClick={() => onChange({ ...section, payload: { ...section.payload, entries: [...entries, { id: crypto.randomUUID(), quote: "", attribution: "" }] } })}>Add testimonial</button></div>;
  }
  if (section.type === "links") {
    const entries = section.payload.entries;
    const change = (index: number, patch: Partial<typeof entries[number]>) => onChange({ ...section, payload: { ...section.payload, entries: entries.map((entry, n) => n === index ? { ...entry, ...patch } : entry) } });
    return <div className="grid gap-3">{entries.map((entry, index) => <div key={entry.id} className="grid gap-2 rounded-xl border border-line p-3">
      <label className={pageLabel}>Link label {index + 1}<input className={pageInput} required maxLength={80} value={entry.label} onChange={e => change(index, { label: e.target.value })} /></label>
      <label className={pageLabel}>Platform<select className={pageInput} value={entry.platform} onChange={e => change(index, { platform: e.target.value as typeof entry.platform })}>{["website", "github", "linkedin", "instagram", "youtube", "x", "other"].map(platform => <option key={platform}>{platform}</option>)}</select></label>
      <label className={pageLabel}>HTTPS URL<input className={pageInput} required type="url" pattern="https://.*" maxLength={500} value={entry.url ?? ""} onChange={e => change(index, { url: e.target.value })} /></label>
      <button type="button" className="desk-button" onClick={() => onChange({ ...section, payload: { ...section.payload, entries: entries.filter((_, n) => n !== index) } })}>Remove link {index + 1}</button>
    </div>)}<button type="button" className="desk-button justify-self-start" disabled={entries.length >= 20} onClick={() => onChange({ ...section, payload: { ...section.payload, entries: [...entries, { id: crypto.randomUUID(), label: "", platform: "website", url: "" }] } })}>Add link</button></div>;
  }
  const entries = section.payload.entries;
  const change = (index: number, entry: typeof entries[number]) => onChange({ ...section, payload: { ...section.payload, entries: entries.map((row, n) => n === index ? entry : row) } });
  return <div className="grid gap-3">
    <p className="text-sm text-muted">Linked members appear only while their public profile remains eligible. Use the stable profile ID from the member's profile, never a staff account.</p>
    {entries.map((entry, index) => <div key={entry.id} className="grid gap-2 rounded-xl border border-line p-3">
      <label className={pageLabel}>Person {index + 1}<select className={pageInput} value={entry.kind} onChange={e => change(index, e.target.value === "member" ? { id: entry.id, kind: "member", profile_id: 0, role: entry.role } : { id: entry.id, kind: "explicit", display_name: "", url: "", role: entry.role })}><option value="explicit">Entered public name</option><option value="member">Linked public member</option></select></label>
      {entry.kind === "member" ? <label className={pageLabel}>Member profile ID<input className={pageInput} type="number" required min={1} step={1} value={entry.profile_id || ""} onChange={e => change(index, { ...entry, profile_id: Number(e.target.value) })} /></label>
        : <><label className={pageLabel}>Display name<input className={pageInput} required maxLength={200} value={entry.display_name} onChange={e => change(index, { ...entry, display_name: e.target.value })} /></label>
          <label className={pageLabel}>HTTPS profile link<input className={pageInput} type="url" pattern="https://.*" maxLength={500} value={entry.url ?? ""} onChange={e => change(index, { ...entry, url: e.target.value })} /></label></>}
      <label className={pageLabel}>Role<input className={pageInput} maxLength={120} value={entry.role} onChange={e => change(index, { ...entry, role: e.target.value })} /></label>
      <button type="button" className="desk-button" onClick={() => onChange({ ...section, payload: { ...section.payload, entries: entries.filter((_, n) => n !== index) } })}>Remove person {index + 1}</button>
    </div>)}
    <button type="button" className="desk-button justify-self-start" disabled={entries.length >= 40} onClick={() => onChange({ ...section, payload: { ...section.payload, entries: [...entries, { id: crypto.randomUUID(), kind: "explicit", display_name: "", role: "", url: "" }] } })}>Add person</button>
  </div>;
}
