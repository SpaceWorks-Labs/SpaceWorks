import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { staffRequest, StructuredApiError } from "../../../lib/api";
import { TELEMETRY_DOCS_URL } from "./TelemetryProviderHelp";

type FirebasePublic = { api_key: string; auth_domain: string; project_id: string; app_id: string; messaging_sender_id: string; measurement_id: string; vapid_public_key: string };
type State = { configured: boolean; config: FirebasePublic | null };
const empty = (): FirebasePublic => ({ api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" });
const path = "/admin/platform/firebase-web-settings";

/** Public web SDK identifiers only. FCM service credentials remain in platform push settings. */
export function PublicFirebaseSettings() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["platform-firebase-web-settings"], queryFn: () => staffRequest<State>(path), retry: false });
  const save = useMutation({ mutationFn: (config: FirebasePublic | null) => staffRequest<State>(path, { method: "PATCH", body: JSON.stringify({ config }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["platform-firebase-web-settings"] }); void client.invalidateQueries({ queryKey: ["audit"] }); } });
  const [draft, setDraft] = useState<FirebasePublic | null>(null);
  useEffect(() => { if (query.data) setDraft(query.data.config ?? empty()); }, [query.data]);
  if (query.isPending) return <p role="status">{t`Loading Firebase web settings…`}</p>;
  if (query.error || !draft) return <p role="alert">{t`Firebase web settings could not load.`}</p>;
  const fields: { key: keyof FirebasePublic; label: string; required?: boolean }[] = [
    { key: "api_key", label: t`Web API key`, required: true }, { key: "auth_domain", label: t`Auth domain` },
    { key: "project_id", label: t`Firebase project ID`, required: true }, { key: "app_id", label: t`Web app ID`, required: true },
    { key: "messaging_sender_id", label: t`Messaging sender ID`, required: true }, { key: "measurement_id", label: t`Measurement ID` },
    { key: "vapid_public_key", label: t`VAPID public key`, required: true },
  ];
  const incomplete = fields.some(field => field.required && !draft[field.key].trim());
  return <section className="grid gap-3 rounded-xl border border-line p-4" aria-labelledby="firebase-web-title">
    <h2 id="firebase-web-title" className="title-section">{t`Firebase web notifications`}</h2>
    <p>{t`These public web identifiers must match the platform push project. Service-account credentials are managed separately.`}</p>
    <p className="text-sm text-muted">{t`Firebase Analytics and Performance also read this configuration; Firebase's origins must be in the operator's allow-list (WEB_TELEMETRY_ALLOWED_ORIGINS).`}{" "}
      <a className="desk-link" href={TELEMETRY_DOCS_URL} target="_blank" rel="noreferrer">{t`Provider guide ↗`}</a></p>
    <p>{query.data?.configured ? t`Configured` : t`Not configured`}</p>
    {fields.map(field => <label key={field.key} className="grid gap-1 text-sm font-semibold">{field.label}
      <input className="desk-input" value={draft[field.key]} required={field.required} onChange={event => setDraft({ ...draft, [field.key]: event.target.value })} />
    </label>)}
    <div className="flex flex-wrap gap-2"><button type="button" className="desk-button-primary" disabled={save.isPending || incomplete} onClick={() => save.mutate(draft)}>{t`Save Firebase web settings`}</button>
      <button type="button" className="desk-button" disabled={save.isPending || !query.data?.configured} onClick={() => save.mutate(null)}>{t`Clear Firebase web settings`}</button></div>
    {save.error ? <p role="alert">{save.error instanceof StructuredApiError ? save.error.message : t`Could not save Firebase web settings.`}</p> : null}
    {save.isSuccess ? <p role="status">{t`Firebase web settings saved.`}</p> : null}
  </section>;
}
