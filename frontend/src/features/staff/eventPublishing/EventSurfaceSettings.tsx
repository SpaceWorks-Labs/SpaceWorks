import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Code2, Copy, X } from "lucide-react";
import { SettingsSection } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { eventErrorText } from "../eventUi";
import { useEmbedPolicy, useReportSwitches, useSaveEmbedPolicy, useSaveReportSwitch, type EmbedPolicy } from "./eventSurfaceApi";

const READ_ONLY = { setting_locked: "The Space Manager has locked this setting.",
  setting_not_delegated: "Ask the Space Manager to give you control of event settings." } as Record<string, string>;

/** DY-61: the event PDF and event exports switches, editable by the Event Manager with the events grant. */
export function EventReportSwitches({ makerspaceId }: { makerspaceId: number }) {
  const query = useReportSwitches(makerspaceId);
  const save = useSaveReportSwitch(makerspaceId);
  if (query.error instanceof StructuredApiError && query.error.status === 404) return null;
  return <SettingsSection title={t`Event reports`} description={t`Post-event PDF and detail exports for this space's events.`}>
    {query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    <div className="grid gap-3">{query.data?.switches.map(row => <label key={row.key} className="flex min-h-11 items-start gap-3 text-sm">
      <input type="checkbox" className="mt-1" checked={row.enabled} disabled={!row.editable || save.isPending}
        onChange={event => save.mutate({ [row.key]: event.target.checked })} />
      <span className="grid gap-0.5"><span className="font-semibold">{row.label}</span>
        <span className="text-muted">{row.description}</span>
        {!row.editable && row.code ? <span className="text-muted">{READ_ONLY[row.code] ?? t`Only the Space Manager changes this setting.`}</span> : null}
        {row.enabled && !row.effective ? <span className="text-muted">{t`Needs the Reports module installed.`}</span> : null}
      </span>
    </label>)}</div>
    {save.error ? <p role="alert" className="mt-2 text-sm text-danger">{eventErrorText(save.error)}</p> : null}
  </SettingsSection>;
}

/** G4: which partner sites may frame this space's event cards (off by default). */
export function EventEmbedPolicyCard({ makerspaceId }: { makerspaceId: number }) {
  const query = useEmbedPolicy(makerspaceId);
  const save = useSaveEmbedPolicy(makerspaceId);
  const [draft, setDraft] = useState<EmbedPolicy | null>(null);
  const [origin, setOrigin] = useState("");
  const [copied, setCopied] = useState("");
  useEffect(() => { setDraft(null); }, [query.data]);
  if (query.error instanceof StructuredApiError && query.error.status === 404) return null;
  const policy = draft ?? query.data;
  const add = () => {
    const value = origin.trim().toLowerCase().replace(/\/+$/, "");
    if (!policy || !value || policy.allowed_origins.includes(value)) return;
    setDraft({ ...policy, allowed_origins: [...policy.allowed_origins, value] }); setOrigin("");
  };
  const snippet = `<iframe src="${window.location.origin}${policy?.embed_path ?? "/embed/"}EVENT-LINK-CODE/" title="Event" width="360" height="420" style="border:0" loading="lazy"></iframe>`;
  return <SettingsSection title={t`Event embeds`} description={t`Let partner websites show an event card. Sign-up always opens here, in a new tab.`}>
    {query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    {policy ? <div className="grid gap-4">
      <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
        <input type="checkbox" checked={policy.enabled} onChange={event => setDraft({ ...policy, enabled: event.target.checked })} />{t`Allow embeds on the sites below`}</label>
      <div className="grid gap-2">
        <label htmlFor={`embed-origin-${makerspaceId}`} className="text-sm font-semibold">{t`Partner site (exact https:// origin)`}</label>
        <div className="flex flex-wrap gap-2">
          <input id={`embed-origin-${makerspaceId}`} className="desk-input min-w-0 flex-1" placeholder="https://partner.example" value={origin}
            onChange={event => setOrigin(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); add(); } }} />
          <button type="button" className="desk-button" onClick={add}>{t`Add site`}</button>
        </div>
        <ul aria-label={t`Allowed sites`} className="flex flex-wrap gap-2">{policy.allowed_origins.map(value => <li key={value}
          className="flex items-center gap-1 rounded-full border border-line bg-surface py-1 pl-3 pr-1 text-sm">{value}
          <button type="button" className="grid h-8 w-8 place-items-center rounded-full hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" aria-label={t`Remove ${value}`}
            onClick={() => setDraft({ ...policy, allowed_origins: policy.allowed_origins.filter(item => item !== value) })}><X aria-hidden="true" size={16} /></button></li>)}</ul>
      </div>
      <div className="grid gap-2"><p className="flex items-center gap-2 text-sm font-semibold"><Code2 aria-hidden="true" size={16} />{t`Snippet`}</p>
        <pre className="overflow-x-auto rounded-control bg-surface p-3 text-xs"><code>{snippet}</code></pre>
        <p className="text-xs text-muted">{t`Replace EVENT-LINK-CODE with the event's link code (the part after /events/ in its address).`}</p>
        <button type="button" className="desk-button justify-self-start" onClick={() => { void Promise.resolve().then(() => navigator.clipboard.writeText(snippet)).then(() => setCopied("Snippet copied.")).catch(() => setCopied("Couldn't copy. Select the snippet to copy it.")); }}><Copy aria-hidden="true" size={20} />{t`Copy snippet`}</button>
        <p role="status" className="text-sm text-muted">{copied}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button-primary" disabled={!draft || save.isPending} onClick={() => draft && save.mutate(draft)}>{save.isPending ? t`Saving…` : t`Save embeds`}</button>
        {draft ? <button type="button" className="desk-button" onClick={() => setDraft(null)}>{t`Discard`}</button> : null}
      </div>
      {save.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(save.error)}</p> : null}
    </div> : null}
  </SettingsSection>;
}

/** The public-surface settings shown inside the events settings dialog. */
export function EventSurfaceSettings({ makerspaceId }: { makerspaceId: number }) {
  return <div className="mt-6 grid gap-6">
    <EventReportSwitches makerspaceId={makerspaceId} />
    <EventEmbedPolicyCard makerspaceId={makerspaceId} />
  </div>;
}
