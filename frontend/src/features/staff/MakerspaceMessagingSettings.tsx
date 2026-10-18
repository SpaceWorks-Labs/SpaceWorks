import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { CopyMessagingValue, MessagingError } from "../messaging/MessagingFeedback";
import { messagingLabels, messagingSettingsKey, messagingSettingsPath, useMessagingSettings,
  type MessagingChannel, type MessagingSettings, type MessagingSettingsWrite } from "../messaging/messagingApi";
import { SettingsQueryState } from "./SettingsQueryState";
import { MessagingTestSend } from "./MessagingTestSend";

const fields = {
  sms: [["sms_account_sid", "Twilio account SID"], ["sms_from_number", "SMS from number (E.164)"], ["sms_auth_token", "Twilio auth token"]],
  whatsapp: [["whatsapp_phone_number_id", "WhatsApp phone number ID"], ["whatsapp_business_account_id", "WhatsApp business account ID"],
    ["whatsapp_access_token", "WhatsApp access token"], ["whatsapp_app_secret", "WhatsApp app secret"]],
} as const;
type TextField = typeof fields[MessagingChannel][number][0];
const secrets = new Set<TextField>(["sms_auth_token", "whatsapp_access_token", "whatsapp_app_secret"]);

export function MakerspaceMessagingSettings({ makerspaceId, modules }: { makerspaceId: number; modules: string[] }) {
  const settings = useMessagingSettings(makerspaceId);
  return <SettingsQueryState query={settings} resource="messaging settings">
    {settings.data ? <MessagingEditor key={makerspaceId} makerspaceId={makerspaceId} settings={settings.data} modules={modules} /> : null}
  </SettingsQueryState>;
}

function MessagingEditor({ makerspaceId, settings, modules }: { makerspaceId: number; settings: MessagingSettings; modules: string[] }) {
  const client = useQueryClient();
  // Only edits enter the PATCH. Read payloads are never spread into secret inputs.
  const [draft, setDraft] = useState<MessagingSettingsWrite>({});
  const save = useMutation({
    mutationFn: (payload: MessagingSettingsWrite) => staffRequest<MessagingSettings>(messagingSettingsPath(makerspaceId), {
      method: "PATCH", body: JSON.stringify(payload),
    }),
    onSuccess: (_data, payload) => {
      setDraft(current => {
        const next = { ...current };
        for (const name of Object.keys(payload) as (keyof MessagingSettingsWrite)[]) delete next[name];
        for (const name of secrets) if (next[name] === "") delete next[name];
        return next;
      });
      return client.invalidateQueries({ queryKey: messagingSettingsKey(makerspaceId), exact: true });
    },
  });
  const value = (name: TextField) => draft[name] ?? (secrets.has(name) ? "" : settings[name as keyof MessagingSettings] as string);
  return <SettingsRow label="SMS & WhatsApp" helper="Own credentials take precedence. An incomplete or broken own sender does not fall back to the platform. Enable delivery separately in the notification rules matrix.">
    <div className="grid min-w-0 gap-5">
      <fieldset disabled={save.isPending} className="grid min-w-0 gap-5">
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" checked={draft.use_platform_sender ?? settings.use_platform_sender}
            onChange={event => setDraft({ ...draft, use_platform_sender: event.target.checked })} />Use platform sender when no own sender is configured
        </label>
        {(["sms", "whatsapp"] as const).filter(channel => modules.includes(channel)).map(channel => <section key={channel} className="grid min-w-0 gap-3 rounded-md border border-line p-4">
          <div className="flex flex-wrap items-center gap-3"><h3 className="title-section">{messagingLabels[channel]}</h3>
            <StatusPill label={`${messagingLabels[channel]} source: ${settings.effective_source[channel]}`} tone={settings.effective_source[channel] === "none" ? "neutral" : "success"} />
          </div>
          <p className="text-sm text-muted">Platform {messagingLabels[channel]}: {settings.platform_available[channel] ? "available" : "unavailable"}</p>
          {fields[channel].map(([name, label]) => {
            const secret = secrets.has(name);
            const configured = secret && Boolean(settings[`${name}_set` as keyof MessagingSettings]);
            return <div key={name} className="grid gap-2">
              <label className="grid gap-1 text-sm font-semibold">{label}
                <input className="desk-input w-full" type={secret ? "password" : name === "sms_from_number" ? "tel" : "text"}
                  autoComplete={secret ? "new-password" : "off"} value={value(name)} maxLength={name === "whatsapp_access_token" ? 8192 : secret ? 4096 : 64}
                  onChange={event => setDraft({ ...draft, [name]: event.target.value })} />
              </label>
              {secret ? <><p className="text-sm text-muted">{label}: {configured ? "set" : "not set"}. Leave blank to keep the saved value.</p>
                <button type="button" className="desk-button w-fit" disabled={!configured} onClick={() => save.mutate({ [name]: "" })}>Clear {label}</button></> : null}
            </div>;
          })}
          {channel === "sms" ? <p className="text-sm text-muted">Use a notification number separate from OTP, in a separate Messaging Service. Configure inbound POST with Advanced Opt-Out in Twilio.</p>
            : <p className="text-sm text-muted">In Meta, use one app per sender, verify and register the Cloud API number with its two-step PIN, subscribe the WABA to the app and the messages field, and grant the system-user token whatsapp_business_messaging and whatsapp_business_management.</p>}
          {Object.entries(settings.webhook_urls[channel]).map(([kind, url]) => <CopyMessagingValue key={kind} label={`${messagingLabels[channel]} ${kind} URL`} value={url} />)}
          {channel === "whatsapp" ? <CopyMessagingValue label="Meta verify token" value={settings.whatsapp_webhook_verify_token} /> : null}
        </section>)}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button-primary" disabled={!Object.keys(draft).length} onClick={() => {
            const payload = { ...draft };
            for (const name of secrets) if (payload[name] === "") delete payload[name];
            save.mutate(payload);
          }}>{save.isPending ? "Saving…" : "Save messaging settings"}</button>
          <button type="button" className="desk-button" onClick={() => { setDraft({}); save.reset(); }}>Discard changes</button>
        </div>
      </fieldset>
      <MessagingError error={save.error} />
      {save.isSuccess ? <p role="status" className="text-sm text-success-ink">Messaging settings saved.</p> : null}
      <MessagingTestSend makerspaceId={makerspaceId} modules={modules} />
    </div>
  </SettingsRow>;
}
