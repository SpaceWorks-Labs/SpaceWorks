import { t } from "@lingui/core/macro";
import type { EventWebsite, WebsiteSession, WebsiteTarget } from "../events/websiteTypes";
import { EventWebsiteDelays } from "./EventWebsiteDelays";
import { programmeWarnings } from "../events/websiteProgramme";
import { websiteCard, websiteCheck, websiteInput, websiteLabel, websiteLegend } from "./eventWebsiteFormStyles";

function localInput(value: string) {
  if (!value || Number.isNaN(Date.parse(value))) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function EventWebsiteSchedule({ page, target, onChange, disabled, saved }: {
  page: EventWebsite; target: WebsiteTarget; onChange: (page: EventWebsite) => void; disabled: boolean; saved: boolean;
}) {
  function update(index: number, values: Partial<WebsiteSession>) {
    onChange({ ...page, sessions: page.sessions.map((row, n) => n === index ? { ...row, ...values } : row) });
  }
  const warnings = programmeWarnings(page.sessions);
  const speakers = page.sections.filter((section) => section.kind === "speaker");
  return <section aria-label={t`Programme editor`} className="grid min-w-0 gap-4">
    <div><h3 className="title-section">{t`Programme`}</h3>
      <p className="mt-1 text-sm text-muted">{t`Enter times in your browser's local timezone, inside the event window. A delay shifts this and later sessions in the same track by the largest delay so far.`}</p></div>
    {warnings.length ? <div role="status" className="grid gap-2 rounded-xl border border-warn bg-warn-soft p-4 text-sm text-warn-ink">
      <h4 className="font-semibold">{t`Programme overlap warnings`}</h4>
      <ul className="list-inside list-disc">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
    </div> : null}
    {page.sessions.map((row, index) => <fieldset disabled={disabled} key={row.session_id ?? index} className={`${websiteCard} ${row.visibility === "draft" ? "border-dashed" : ""}`}>
      <legend className={websiteLegend}>{t`Session ${index + 1}`}</legend>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={websiteLabel}>{t`Session slug`}<input className={`${websiteInput} code-text`} value={row.slug} required pattern="[a-zA-Z0-9_-]+" maxLength={80} onChange={(e) => update(index, { slug: e.target.value })} /></label>
        <label className={websiteLabel}>{t`Session title`}<input className={websiteInput} required maxLength={200} value={row.title} onChange={(e) => update(index, { title: e.target.value })} /></label>
        <label className={`${websiteLabel} sm:col-span-2`}>{t`Description`}<textarea className={websiteInput} maxLength={10000} value={row.body} onChange={(e) => update(index, { body: e.target.value })} /></label>
        {(["starts_at", "ends_at"] as const).map((key) => <label key={key} className={websiteLabel}>{key === "starts_at" ? t`Start` : t`End`}<input className={websiteInput} required type="datetime-local" value={localInput(row[key])} onChange={(e) => update(index, { [key]: e.target.value ? new Date(e.target.value).toISOString() : "" })} /></label>)}
        {(["track", "room"] as const).map((kind) => <label key={kind} className={websiteLabel}>{kind === "track" ? t`Track` : t`Room`}<select className={websiteInput} value={row[kind] ?? ""} onChange={(e) => update(index, { [kind]: e.target.value || null })}><option value="">{t`None`}</option>{page.sections.filter((section) => section.kind === kind).map((section) => <option key={section.slug} value={section.slug}>{section.title || section.slug}</option>)}</select></label>)}
        <fieldset className="grid min-w-0 gap-x-4 sm:col-span-2 sm:grid-cols-2"><legend className="mb-1 text-sm font-semibold text-ink">{t`Speakers`}</legend>
          {speakers.length ? speakers.map((speaker) => <label key={speaker.slug} className={websiteCheck}><input type="checkbox" checked={(row.speakers ?? []).includes(speaker.slug)} onChange={(e) => update(index, { speakers: e.target.checked ? [...(row.speakers ?? []), speaker.slug] : (row.speakers ?? []).filter((slug) => slug !== speaker.slug) })} />{speaker.title || speaker.slug}</label>)
            : <p className="text-sm text-muted">{t`Add a speaker section to assign speakers.`}</p>}
        </fieldset>
        <label className={websiteLabel}>{t`Session visibility`}<select className={websiteInput} value={row.visibility} onChange={(e) => update(index, { visibility: e.target.value as WebsiteSession["visibility"] })}><option value="draft">{t`Draft`}</option><option value="published">{t`Published`}</option></select></label>
      </div>
      <button className="desk-button-danger-outline justify-self-start" type="button" onClick={() => onChange({ ...page, sessions: page.sessions.filter((_, n) => n !== index) })}>{t`Remove session ${index + 1}`}</button>
    </fieldset>)}
    <EventWebsiteDelays page={page} target={target} disabled={!saved || disabled} />
    {!page.sessions.length ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">{t`No sessions yet. Add your first session.`}</p> : null}
    <button className="desk-button justify-self-start" type="button" disabled={disabled || page.sessions.length >= 200} onClick={() => onChange({ ...page, sessions: [...page.sessions, { slug: `session-${page.sessions.length + 1}`, title: "", body: "", starts_at: "", ends_at: "", track: null, room: null, speakers: [], visibility: "draft" }] })}>{t`Add session`}</button>
  </section>;
}
