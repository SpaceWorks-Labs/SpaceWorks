import { useEffect, useState } from "react";
import type { EventWebsite, WebsiteSession, WebsiteTarget } from "../events/websiteTypes";
import { useWebsiteDelay } from "./eventWebsiteApi";
import { eventErrorText } from "./eventUi";
import { programmeWarnings } from "../events/websiteProgramme";
import { websiteCard, websiteCheck, websiteInput, websiteLabel, websiteLegend } from "./eventWebsiteFormStyles";

function localInput(value: string) {
  if (!value || Number.isNaN(Date.parse(value))) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function SessionDelay({ target, slug, minutes, disabled }: { target: WebsiteTarget; slug: string; minutes: number; disabled: boolean }) {
  const [value, setValue] = useState(minutes);
  useEffect(() => setValue(minutes), [minutes]);
  const delay = useWebsiteDelay(target);
  return <div className="grid gap-2 rounded-xl border border-line bg-surface p-3 sm:col-span-2">
    <div className="flex flex-wrap items-end gap-2">
      <label className={`${websiteLabel} flex-1 basis-40`}>Delay in minutes<input className={websiteInput} type="number" min={0} max={1440} value={value} onChange={(e) => setValue(Number(e.target.value))} disabled={disabled} /></label>
      <button className="desk-button" type="button" disabled={disabled || delay.isPending} onClick={() => delay.mutate({ slug, minutes: value })}>{delay.isPending ? "Updating…" : "Update live delay"}</button>
    </div>
    {delay.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(delay.error)}</p> : null}
  </div>;
}

export function EventWebsiteSchedule({ page, target, onChange, disabled, saved }: {
  page: EventWebsite; target: WebsiteTarget; onChange: (page: EventWebsite) => void; disabled: boolean; saved: boolean;
}) {
  function update(index: number, values: Partial<WebsiteSession>) {
    onChange({ ...page, sessions: page.sessions.map((row, n) => n === index ? { ...row, ...values } : row) });
  }
  const warnings = programmeWarnings(page.sessions);
  const speakers = page.sections.filter((section) => section.kind === "speaker");
  return <section aria-label="Programme editor" className="grid min-w-0 gap-4">
    <div><h3 className="title-section">Programme</h3>
      <p className="mt-1 text-sm text-muted">Enter times in your browser's local timezone, inside the event window. A delay shifts this and later sessions in the same track by the largest delay so far.</p></div>
    {warnings.length ? <div role="status" className="grid gap-2 rounded-xl border border-warn bg-warn-soft p-4 text-sm text-warn-ink">
      <h4 className="font-semibold">Programme overlap warnings</h4>
      <ul className="list-inside list-disc">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
    </div> : null}
    {page.sessions.map((row, index) => <fieldset disabled={disabled} key={index} className={`${websiteCard} ${row.visibility === "draft" ? "border-dashed" : ""}`}>
      <legend className={websiteLegend}>Session {index + 1}</legend>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={websiteLabel}>Session slug<input className={`${websiteInput} code-text`} value={row.slug} required pattern="[a-zA-Z0-9_-]+" maxLength={80} onChange={(e) => update(index, { slug: e.target.value })} /></label>
        <label className={websiteLabel}>Session title<input className={websiteInput} required maxLength={200} value={row.title} onChange={(e) => update(index, { title: e.target.value })} /></label>
        <label className={`${websiteLabel} sm:col-span-2`}>Description<textarea className={websiteInput} maxLength={10000} value={row.body} onChange={(e) => update(index, { body: e.target.value })} /></label>
        {(["starts_at", "ends_at"] as const).map((key) => <label key={key} className={websiteLabel}>{key === "starts_at" ? "Start" : "End"}<input className={websiteInput} required type="datetime-local" value={localInput(row[key])} onChange={(e) => update(index, { [key]: e.target.value ? new Date(e.target.value).toISOString() : "" })} /></label>)}
        {(["track", "room"] as const).map((kind) => <label key={kind} className={websiteLabel}>{kind === "track" ? "Track" : "Room"}<select className={websiteInput} value={row[kind] ?? ""} onChange={(e) => update(index, { [kind]: e.target.value || null })}><option value="">None</option>{page.sections.filter((section) => section.kind === kind).map((section) => <option key={section.slug} value={section.slug}>{section.title || section.slug}</option>)}</select></label>)}
        <fieldset className="grid min-w-0 gap-x-4 sm:col-span-2 sm:grid-cols-2"><legend className="mb-1 text-sm font-semibold text-ink">Speakers</legend>
          {speakers.length ? speakers.map((speaker) => <label key={speaker.slug} className={websiteCheck}><input type="checkbox" checked={row.speakers.includes(speaker.slug)} onChange={(e) => update(index, { speakers: e.target.checked ? [...row.speakers, speaker.slug] : row.speakers.filter((slug) => slug !== speaker.slug) })} />{speaker.title || speaker.slug}</label>)
            : <p className="text-sm text-muted">Add a speaker section to assign speakers.</p>}
        </fieldset>
        <label className={websiteLabel}>Session visibility<select className={websiteInput} value={row.visibility} onChange={(e) => update(index, { visibility: e.target.value as WebsiteSession["visibility"] })}><option value="draft">Draft</option><option value="published">Published</option></select></label>
        <SessionDelay target={target} slug={row.slug} minutes={row.delay_minutes ?? 0} disabled={!saved || disabled || page.inherited} />
      </div>
      <button className="desk-button-danger-outline justify-self-start" type="button" onClick={() => onChange({ ...page, sessions: page.sessions.filter((_, n) => n !== index) })}>Remove session {index + 1}</button>
    </fieldset>)}
    {!page.sessions.length ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">No sessions yet. Add your first session.</p> : null}
    <button className="desk-button justify-self-start" type="button" disabled={disabled || page.sessions.length >= 200} onClick={() => onChange({ ...page, sessions: [...page.sessions, { slug: `session-${page.sessions.length + 1}`, title: "", body: "", starts_at: "", ends_at: "", track: null, room: null, speakers: [], visibility: "draft" }] })}>Add session</button>
  </section>;
}
