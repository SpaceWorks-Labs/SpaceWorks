import { useEffect, useState } from "react";
import type { EventWebsite, WebsiteSession, WebsiteTarget } from "../events/websiteTypes";
import { useWebsiteDelay } from "./eventWebsiteApi";
import { eventErrorText } from "./eventUi";
import { programmeWarnings } from "../events/websiteProgramme";

function localInput(value: string) {
  if (!value || Number.isNaN(Date.parse(value))) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function SessionDelay({ target, slug, minutes, disabled }: { target: WebsiteTarget; slug: string; minutes: number; disabled: boolean }) {
  const [value, setValue] = useState(minutes);
  useEffect(() => setValue(minutes), [minutes]);
  const delay = useWebsiteDelay(target);
  return <div className="grid gap-2"><label>Delay in minutes<input className="desk-input" type="number" min={0} max={1440} value={value} onChange={(e) => setValue(Number(e.target.value))} disabled={disabled} /></label>
    <button className="desk-button w-fit" type="button" disabled={disabled || delay.isPending} onClick={() => delay.mutate({ slug, minutes: value })}>{delay.isPending ? "Updating…" : "Update live delay"}</button>
    {delay.error ? <p role="alert">{eventErrorText(delay.error)}</p> : null}
  </div>;
}

export function EventWebsiteSchedule({ page, target, onChange, disabled, saved }: {
  page: EventWebsite; target: WebsiteTarget; onChange: (page: EventWebsite) => void; disabled: boolean; saved: boolean;
}) {
  function update(index: number, values: Partial<WebsiteSession>) {
    onChange({ ...page, sessions: page.sessions.map((row, n) => n === index ? { ...row, ...values } : row) });
  }
  return <section aria-label="Programme editor" className="grid gap-3"><h4 className="font-semibold">Programme</h4>
    <p className="text-sm text-muted">Enter times in your browser's local timezone, inside the event window. A delay shifts this and later sessions in the same track by the largest delay so far.</p>
    {programmeWarnings(page.sessions).length ? <div role="status" className="rounded-lg border border-border p-3"><h5 className="font-semibold">Programme overlap warnings</h5><ul className="list-inside list-disc">{programmeWarnings(page.sessions).map((warning) => <li key={warning}>{warning}</li>)}</ul></div> : null}
    {page.sessions.map((row, index) => <fieldset disabled={disabled} key={index} className="grid gap-2 rounded-lg border border-border p-3">
      <legend className="px-1">Session {index + 1}</legend>
      <label>Session slug<input className="desk-input" value={row.slug} required pattern="[a-zA-Z0-9_-]+" maxLength={80} onChange={(e) => update(index, { slug: e.target.value })} /></label>
      <label>Session title<input className="desk-input" required maxLength={200} value={row.title} onChange={(e) => update(index, { title: e.target.value })} /></label>
      <label>Description<textarea className="desk-input" maxLength={10000} value={row.body} onChange={(e) => update(index, { body: e.target.value })} /></label>
      {(["starts_at", "ends_at"] as const).map((key) => <label key={key}>{key === "starts_at" ? "Start" : "End"}<input className="desk-input" required type="datetime-local" value={localInput(row[key])} onChange={(e) => update(index, { [key]: e.target.value ? new Date(e.target.value).toISOString() : "" })} /></label>)}
      {(["track", "room"] as const).map((kind) => <label key={kind}>{kind === "track" ? "Track" : "Room"}<select className="desk-input" value={row[kind] ?? ""} onChange={(e) => update(index, { [kind]: e.target.value || null })}><option value="">None</option>{page.sections.filter((section) => section.kind === kind).map((section) => <option key={section.slug} value={section.slug}>{section.title || section.slug}</option>)}</select></label>)}
      <fieldset><legend>Speakers</legend>{page.sections.filter((section) => section.kind === "speaker").map((speaker) => <label key={speaker.slug} className="mr-3 inline-flex gap-2"><input type="checkbox" checked={row.speakers.includes(speaker.slug)} onChange={(e) => update(index, { speakers: e.target.checked ? [...row.speakers, speaker.slug] : row.speakers.filter((slug) => slug !== speaker.slug) })} />{speaker.title || speaker.slug}</label>)}</fieldset>
      <label>Session visibility<select className="desk-input" value={row.visibility} onChange={(e) => update(index, { visibility: e.target.value as WebsiteSession["visibility"] })}><option value="draft">Draft</option><option value="published">Published</option></select></label>
      <SessionDelay target={target} slug={row.slug} minutes={row.delay_minutes ?? 0} disabled={!saved || disabled || page.inherited} />
      <button className="desk-button-danger w-fit" type="button" onClick={() => onChange({ ...page, sessions: page.sessions.filter((_, n) => n !== index) })}>Remove session {index + 1}</button>
    </fieldset>)}
    <button className="desk-button w-fit" type="button" disabled={disabled || page.sessions.length >= 200} onClick={() => onChange({ ...page, sessions: [...page.sessions, { slug: `session-${page.sessions.length + 1}`, title: "", body: "", starts_at: "", ends_at: "", track: null, room: null, speakers: [], visibility: "draft" }] })}>Add session</button>
  </section>;
}
