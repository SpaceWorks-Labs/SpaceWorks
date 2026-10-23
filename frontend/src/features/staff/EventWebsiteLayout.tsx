import { AccentPresetPicker, ACCENT_PRESETS, type AccentPreset } from "./eventProgramme/AccentPresetPicker";
import { emptyVenue, orderedGroups, type EventWebsite, type WebsiteVenue } from "../events/websiteTypes";
import { websiteCard, websiteCheck, websiteInput, websiteLabel, websiteLegend } from "./eventWebsiteFormStyles";
import { useRef, useState } from "react";

export function EventWebsiteLayout({ page, onChange, disabled }: {
  page: EventWebsite; onChange: (page: EventWebsite) => void; disabled: boolean;
}) {
  const order = orderedGroups(page);
  const venue = page.venue;
  const accentPreset = (Object.entries(ACCENT_PRESETS).find(([, preset]) => preset.background.toLowerCase() === page.accent_color?.toLowerCase())?.[0] ?? null) as AccentPreset | null;
  const groupRefs = useRef(new Map<string, HTMLLIElement>());
  const [announcement, announce] = useState("");
  function move(index: number, offset: number) {
    const next = [...order];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    onChange({ ...page, section_order: next });
    announce(`${order[index]} moved to position ${index + offset + 1}.`);
    requestAnimationFrame(() => groupRefs.current.get(order[index])?.focus());
  }
  function venueChange(values: Partial<WebsiteVenue>) {
    onChange({ ...page, venue: { ...emptyVenue(), ...venue, ...values } });
  }
  return <fieldset disabled={disabled} className={websiteCard}>
    <legend className={websiteLegend}>Page layout and venue</legend>
    <div className="grid gap-4 sm:grid-cols-2">
      <label className={websiteLabel}>Tagline<input className={websiteInput} maxLength={300} value={page.tagline ?? ""} onChange={(e) => onChange({ ...page, tagline: e.target.value })} /></label>
      <AccentPresetPicker value={accentPreset} onChange={preset => onChange({ ...page, accent_color: preset ? ACCENT_PRESETS[preset].background : '' })} />
      {page.accent_color && !accentPreset ? <p className="self-center text-sm text-muted">Existing custom accent is retained. Use the public palette picker to override it, or Inherit to reveal it.</p> : null}
    </div>
    <p className="text-sm text-muted">Choose which groups appear publicly and move them into display order. Hidden groups and their detail pages are unavailable publicly.</p>
    <p role="status" aria-live="polite" className="sr-only">{announcement}</p>
    <ol className="grid gap-2" aria-label="Section order">{order.map((group, index) => <li key={group} tabIndex={-1} ref={node => { if (node) groupRefs.current.set(group, node); else groupRefs.current.delete(group); }} className="flex min-w-0 flex-wrap items-center gap-2 rounded-xl border border-line px-3 py-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <label className={`${websiteCheck} mr-auto min-w-0`}><input type="checkbox" checked={page.section_enabled?.[group] !== false} onChange={(e) => onChange({ ...page, section_enabled: { ...page.section_enabled, [group]: e.target.checked } })} />{group}</label>
      <button className="desk-button" type="button" disabled={disabled || index === 0} aria-label={`Move ${group} up`} onClick={() => move(index, -1)}>Up</button>
      <button className="desk-button" type="button" disabled={disabled || index === order.length - 1} aria-label={`Move ${group} down`} onClick={() => move(index, 1)}>Down</button>
    </li>)}</ol>
    <label className={websiteCheck}><input type="checkbox" checked={Boolean(venue)} onChange={(e) => onChange({ ...page, venue: e.target.checked ? emptyVenue() : null })} />Add venue details</label>
    {venue ? <div className="grid gap-4 sm:grid-cols-2">
      {([['name', 'Venue name', 200], ['address', 'Address', 500], ['city', 'City', 200], ['country', 'Country', 200], ['map_url', 'Map link', 500]] as const).map(([key, label, max]) => <label key={key} className={websiteLabel}>{label}<input className={websiteInput} type={key === "map_url" ? "url" : "text"} pattern={key === "map_url" ? "[Hh][Tt][Tt][Pp][Ss]?://.*" : undefined} maxLength={max} value={venue[key]} onChange={(e) => venueChange({ [key]: e.target.value })} /></label>)}
      {([['latitude', 90], ['longitude', 180]] as const).map(([key, bound]) => <label key={key} className={websiteLabel}>{key === "latitude" ? "Latitude" : "Longitude"}<input className={websiteInput} type="number" step="any" min={-bound} max={bound} value={venue[key] ?? ""} onChange={(e) => venueChange({ [key]: e.target.value === "" ? null : Number(e.target.value) })} /></label>)}
      {([['directions', 'Directions'], ['parking', 'Parking'], ['public_transport', 'Public transport'], ['accessibility_notes', 'Accessibility notes']] as const).map(([key, label]) => <label key={key} className={`${websiteLabel} sm:col-span-2`}>{label}<textarea className={websiteInput} rows={3} maxLength={2000} value={venue[key]} onChange={(e) => venueChange({ [key]: e.target.value })} /></label>)}
    </div> : null}
  </fieldset>;
}
