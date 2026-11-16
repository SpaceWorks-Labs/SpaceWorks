import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../components/ui";
import type { CallbackURLs } from "./channelsApi";

const labels: Record<keyof CallbackURLs, string> = {
  inbound_url: "Inbound callback URL", status_url: "Status callback URL",
  status_url_template: "Status callback URL template", webhook_url: "Meta webhook URL",
};

export function ChannelCallbackURLs({ urls }: { urls?: CallbackURLs }) {
  const [message, setMessage] = useState("");
  if (!urls || !Object.values(urls).some(Boolean)) return null;
  async function copy(label: string, url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setMessage(`${label} copied.`);
    } catch {
      setMessage(t`Copy failed. Select the URL and copy it manually.`);
    }
  }
  return <fieldset className="grid min-w-0 gap-3 rounded-lg border border-line p-3">
    <legend className="px-1 text-sm font-semibold">{t`Provider callbacks`}</legend>
    <p className="text-sm text-muted">{t`These URLs match the saved settings. Save changes to refresh them.`}</p>
    {(Object.keys(labels) as (keyof CallbackURLs)[]).map(key => urls[key] ? <div key={key} className="flex min-w-0 items-start gap-2">
      <Field label={labels[key]} className="min-w-0 flex-1"
        hint={key === "status_url_template" ? t`The sender replaces {delivery_id} for each message automatically.` : undefined}>
        <input className="desk-input min-w-0" readOnly value={urls[key]} />
      </Field>
        <button type="button" className="desk-button" aria-label={t`Copy ${labels[key]}`}
          onClick={() => { void copy(labels[key], urls[key]!); }}>{t`Copy`}</button>
    </div> : null)}
    {message ? <p role="status" className="text-sm text-muted">{message}</p> : null}
  </fieldset>;
}
