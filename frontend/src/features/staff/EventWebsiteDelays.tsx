import { useEffect, useState } from "react";
import type { EventWebsite, WebsiteDelayTarget, WebsiteTarget } from "../events/websiteTypes";
import { useWebsiteDelay } from "./eventWebsiteApi";
import { eventErrorText } from "./eventUi";
import { websiteInput, websiteLabel } from "./eventWebsiteFormStyles";

function DelayControl({ target, row, revision, disabled }: {
  target: WebsiteTarget; row: WebsiteDelayTarget; revision: number; disabled: boolean;
}) {
  const minutes = row.working_delay_minutes ?? row.public_delay_minutes ?? 0;
  const [value, setValue] = useState(minutes);
  useEffect(() => setValue(minutes), [minutes]);
  const delay = useWebsiteDelay(target);
  const slug = row.working_slug ?? row.public_slug;
  return <fieldset disabled={disabled || delay.isPending || !slug} className="grid gap-3 rounded-xl border border-line bg-surface p-4">
    <legend className="px-1 text-sm font-semibold">{slug}</legend>
    <p className="text-sm text-muted">{row.working_present && row.public_present ? "Changes this session in both the saved draft and released programme."
      : row.public_present ? "Changes the released programme only. This session was removed from the draft; it will stay removed."
      : "Changes the draft only. The public programme stays unchanged."}</p>
    {row.working_slug && row.public_slug && row.working_slug !== row.public_slug ? <p className="text-sm text-muted">Public slug: {row.public_slug}. Draft slug: {row.working_slug}.</p> : null}
    <label className={websiteLabel}>Delay in minutes<input className={websiteInput} type="number" min={0} max={1440} step={1} value={value} onChange={e => setValue(Number(e.target.value))} /></label>
    <button className="desk-button justify-self-start" type="button" disabled={!Number.isInteger(value) || value < 0 || value > 1440} onClick={() => { if (slug) delay.mutate({ slug, minutes: value, revision, session_id: row.session_id }); }}>Update {row.public_present ? "live" : "draft"} delay</button>
    {delay.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(delay.error)}</p> : null}
  </fieldset>;
}
export function EventWebsiteDelays({ page, target, disabled }: { page: EventWebsite; target: WebsiteTarget; disabled: boolean }) {
  if (!page.delay_targets?.length) return null;
  return <section aria-label="Operational session delays" className="grid gap-3"><h3 className="title-section">Operational delays</h3>
    <p className="text-sm text-muted">Save pending edits first. Changing a delay never releases editorial changes.</p>
    {page.delay_targets.map(row => <DelayControl key={row.session_id} row={row} target={target} revision={page.revision} disabled={disabled || page.inherited} />)}
  </section>;
}
