import { t } from "@lingui/core/macro";
import { pageInput, pageLabel } from "./documentDefaults";
import { SectionEntryForms } from "./SectionEntryForms";
import { ScreenHelp } from "../help/HelpLink";
import type { PageAsset, PageOwner, PageSection } from "./pageTypes";
import { useId } from "react";

export function PageSectionForm({ section, assets, kind, onChange }: {
  section: PageSection; assets: PageAsset[]; kind: PageOwner["kind"] | "event"; onChange: (section: PageSection) => void;
}) {
  const helpId = useId();
  if (section.type === "functional_content") return <p className="text-sm text-muted">{t`The existing catalogue and enabled activities stay available here. Their visibility comes from the public APIs.`}</p>;
  return <div className="grid gap-4">
    <label className={pageLabel}>{t`Section title`}<input className={pageInput} maxLength={200} value={section.payload.title} onChange={e => onChange({ ...section, payload: { ...section.payload, title: e.target.value } } as PageSection)} /></label>
    {section.type === "about" ? <div className="grid gap-1"><label className={pageLabel}>{t`Story`}<textarea className={pageInput} aria-describedby={helpId} rows={7} maxLength={10000} value={section.payload.markdown} onChange={e => onChange({ ...section, payload: { ...section.payload, markdown: e.target.value } })} /></label><p id={helpId} className="text-sm text-muted">{t`Paragraphs, - lists, **bold**, and [links](https://example.com). No HTML, embedded images or video.`}</p></div> : null}
    {section.type === "gallery" || section.type === "team" || section.type === "testimonials" || section.type === "links" ? <SectionEntryForms section={section} assets={assets} onChange={onChange} /> : null}
    {section.type === "stats" ? <div className="grid gap-2">{(["show_public_inventory_units", "show_published_event_count", "publish_public_member_count"] as const).filter(key => kind === "makerspace" || key === "show_published_event_count").map(key => <label key={key} className="flex min-h-11 items-center gap-2 text-sm">
      <input type="checkbox" checked={section.payload[key]} onChange={e => onChange({ ...section, payload: { ...section.payload, [key]: e.target.checked } })} />
      {{ show_public_inventory_units: "Publish the exact-count inventory subset", show_published_event_count: "Publish public event count", publish_public_member_count: "Consent to publish the active public member aggregate" }[key]}
    </label>)}<p className="text-sm text-muted">{t`Only metrics supported for this owner are accepted by the server. No private activity or hidden stock totals are published.`}</p></div> : null}
    {section.type === "location" ? <div className="grid gap-3">
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={section.payload.enabled_publicly} onChange={e => onChange({ ...section, payload: { ...section.payload, enabled_publicly: e.target.checked } })} />{t`Publish this location`}</label>
      <label className={pageLabel}>{t`Location source`}<select className={pageInput} value={section.payload.source} onChange={e => onChange({ ...section, payload: { title: section.payload.title, enabled_publicly: section.payload.enabled_publicly, source: e.target.value as "entered" | "makerspace_public" } })}>
        <option value="entered">{t`Enter a public address`}</option>{kind === "makerspace" ? <option value="makerspace_public">{t`Existing public makerspace location`}</option> : null}</select></label>
      {section.payload.source === "entered" ? <>
        <label className={pageLabel}>{t`Public address`}<textarea className={pageInput} maxLength={500} value={section.payload.address ?? ""} onChange={e => onChange({ ...section, payload: { ...section.payload, address: e.target.value } })} /></label>
        <label className={pageLabel}>{t`HTTPS map link`}<input className={pageInput} type="url" pattern="https://.*" maxLength={500} value={section.payload.map_url ?? ""} onChange={e => onChange({ ...section, payload: { ...section.payload, map_url: e.target.value } })} /></label>
        {(["latitude", "longitude"] as const).map(key => <label className={pageLabel} key={key}>{key === "latitude" ? t`Public latitude` : t`Public longitude`}<input className={pageInput} type="number" step="any" min={key === "latitude" ? -90 : -180} max={key === "latitude" ? 90 : 180} value={section.payload[key] ?? ""} onChange={e => onChange({ ...section, payload: { ...section.payload, [key]: e.target.value === "" ? null : Number(e.target.value) } })} /></label>)}
        <label className={pageLabel}>{t`Directions`}<textarea className={pageInput} maxLength={2000} value={section.payload.directions ?? ""} onChange={e => onChange({ ...section, payload: { ...section.payload, directions: e.target.value } })} /></label>
      </> : null}<p className="text-sm text-muted">{t`This is public location consent. Check-in geofence coordinates are never copied into it.`}</p>
    </div> : null}
    {section.type === "sponsors" ? <ScreenHelp screen="pages.sponsors" className="flex justify-start" /> : null}
    {section.type === "crew" ? <p className="text-sm text-muted">{t`Shows approved crew who chose to appear publicly and keep a public profile: their name, handle and crew role only.`}</p> : null}
    {["upcoming_events", "linked_makerspaces", "organization_events", "membership_plans", "sponsors", "crew"].includes(section.type) ? <p className="text-sm text-muted">{t`This collection is refreshed from eligible public records on every read. No names, counts or event lists are saved in this section.`}</p> : null}
    {section.type === "shop" ? <p className="text-sm text-muted">{t`Shows a few public products from your shop, linking to the full shop. Products, prices and stock come live from the shop on every read.`}</p> : null}
  </div>;
}
