import { useState } from "react";

import { Callout, Field } from "../../components/ui";
import { CHANNEL_LABELS, defaultChannel, providerSpec, type ChannelSpec } from "./channelCatalog";
import { useSaveChannel, type Channel, type ChannelWrite, type ProviderKey, type Quotas, type WhatsAppTemplate } from "./channelsApi";
import { WhatsAppTemplatesEditor } from "./WhatsAppTemplatesEditor";
import { SlackInstallation } from "./SlackInstallation";
import { WhatsAppApprovalRefresh } from "./WhatsAppApprovalRefresh";

type Props = { makerspaceId: number; spec: ChannelSpec; row?: Channel; moduleInstalled: boolean };

const sameQuotas = (a: Quotas, b: Quotas) => a.daily_limit === b.daily_limit && a.recipient_daily_limit === b.recipient_daily_limit;
const sameTemplates = (a: WhatsAppTemplate[], b: WhatsAppTemplate[]) => JSON.stringify(a.map(strip)) === JSON.stringify(b.map(strip));
const strip = ({ feature, event, audience, locale, template_name, variables }: WhatsAppTemplate) => ({ ...(feature ? { feature } : {}), event, audience, locale, template_name, variables });

/**
 * One channel's settings, saved together with an explicit Save. The PATCH sends only what
 * changed: provider, identity and credentials advance the installation generation, which
 * disconnects every personal connection, so an unrelated toggle must never resend them.
 */
export function ChannelSetupForm({ makerspaceId, spec, row, moduleInstalled }: Props) {
  const initial = row ?? defaultChannel(spec);
  const [draft, setDraft] = useState<Channel>(initial);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState("");
  const [clearCredentials, setClearCredentials] = useState(false);
  const save = useSaveChannel(makerspaceId, spec.key);
  const provider = providerSpec(spec, draft.provider);
  const set = (patch: Partial<Channel>) => { setDraft(current => ({ ...current, ...patch })); setProblem(""); };
  const typed = Object.values(secrets).some(Boolean);
  const addressed = spec.key === "sms" || spec.key === "whatsapp";
  const rotates = draft.provider !== initial.provider || draft.integration_identity !== initial.integration_identity || typed
    || clearCredentials || Boolean(draft.use_platform_sender) !== Boolean(initial.use_platform_sender);
  const chat = spec.providers.some(item => item.identityLabel || item.derivedIdentity || item.installation);

  function submit() {
    const missing = provider.credentials.filter(field => !field.optional && !secrets[field.key]?.trim());
    if (typed && provider.identityCredential && !draft.integration_identity.trim()) missing.push({ key: provider.identityCredential, label: provider.identityLabel ?? "Identity" });
    if (typed && missing.length) return setProblem(`Enter every required credential to replace them: ${missing.map(field => field.label).join(", ")}.`);
    if (draft.personal_enabled && chat && !draft.integration_identity.trim() && !(typed && provider.derivedIdentity) && !draft.use_platform_sender)
      return setProblem(provider.installation ? "Install the Slack app before turning on personal messages."
        : provider.derivedIdentity ? "Enter every required credential before turning on personal messages."
        : `Enter the ${provider.identityLabel?.toLowerCase()} before turning on personal messages.`);
    const body: ChannelWrite = { enabled: draft.enabled, personal_enabled: draft.personal_enabled };
    if (addressed && Boolean(draft.use_platform_sender) !== Boolean(initial.use_platform_sender)) body.use_platform_sender = Boolean(draft.use_platform_sender);
    if (addressed && Boolean(draft.activation_hold) !== Boolean(initial.activation_hold)) body.activation_hold = Boolean(draft.activation_hold);
    if (clearCredentials && !typed) body.credentials = {};
    if (spec.rooms) body.room_enabled = draft.room_enabled;
    if (spec.key === "email") body.email_fallback = draft.email_fallback;
    // A new row is created with the server's default provider, so a non-default choice is sent.
    if (draft.provider !== initial.provider || (!row && draft.provider !== spec.providers[0].key)) body.provider = draft.provider;
    if (draft.integration_identity !== initial.integration_identity) body.integration_identity = draft.integration_identity.trim();
    if (typed) {
      // Replacing app credentials starts a new installation, with personal delivery off.
      if (provider.installation) body.personal_enabled = false;
      body.credentials = Object.fromEntries(Object.entries(secrets).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()]));
      if (provider.identityCredential) body.credentials[provider.identityCredential] = draft.integration_identity.trim();
      if (provider.derivedIdentity === "mattermost") body.integration_identity = body.credentials.server_url.replace(/\/+$/, "");
      if (provider.derivedIdentity === "discord") body.integration_identity = `${body.credentials.application_id}:${body.credentials.guild_id}`;
    }
    if (!sameQuotas(draft.quotas, initial.quotas)) body.quotas = Object.fromEntries(Object.entries(draft.quotas).filter(([, value]) => value)) as Quotas;
    if (spec.key === "whatsapp" && !sameTemplates(draft.templates, initial.templates)) body.templates = draft.templates.map(strip);
    save.mutate(body, { onSuccess: saved => { setDraft(saved); setSecrets({}); setClearCredentials(false); } });
  }

  const toggle = (key: "enabled" | "room_enabled" | "personal_enabled" | "email_fallback", label: string, helper: string) =>
    <label className="flex min-h-11 items-start gap-3 text-sm">
      <input className="mt-1 h-4 w-4" type="checkbox" checked={draft[key]} disabled={save.isPending || (key !== "enabled" && !draft.enabled)}
        onChange={event => set({ [key]: event.target.checked })} />
      <span className="grid gap-0.5"><span className="font-semibold text-ink">{label}</span><span className="text-muted">{helper}</span></span>
    </label>;

  return <form className="grid min-w-0 gap-4" aria-label={`${spec.label} settings`} onSubmit={event => { event.preventDefault(); submit(); }}>
    {!moduleInstalled ? <Callout size="inline" tone="warn" lead={`The ${spec.label} module is not installed here.`}
      body="You can prepare these settings, but nothing is sent until the platform administrator installs it." /> : null}
    {!row ? <p role="note" className="text-sm text-muted">Not set up yet. Until you save, existing rooms and email keep working exactly as today.</p> : null}
    <fieldset className="grid gap-1"><legend className="sr-only">{spec.label} delivery</legend>
      {toggle("enabled", `Use ${spec.label}`, "Turn the whole channel on or off for this space.")}
      {spec.rooms ? toggle("room_enabled", "Staff rooms", "Post alerts into the group rooms listed under Rooms.") : null}
      {toggle("personal_enabled", "Personal messages", spec.key === "email" ? "Send people their own messages by email." : `Let staff and members receive their own messages on ${spec.label}.`)}
      {spec.key === "email" ? toggle("email_fallback", "Email fallback", "Email a person when none of the channels they chose could deliver.") : null}
    </fieldset>
    {addressed ? <fieldset className="grid gap-2 rounded-lg border border-line p-3"><legend className="px-1 text-sm font-semibold">Sender</legend>
      <p className="text-sm text-muted">Saved own credentials take precedence. Incomplete own settings refuse delivery; they never fall back to a platform sender.</p>
      {spec.key === "sms" || draft.provider === "meta" ? <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={Boolean(draft.use_platform_sender)} disabled={save.isPending}
          onChange={event => set({ use_platform_sender: event.target.checked })} />Allow the operator's platform sender
      </label> : null}
      {initial.credentials_set ? <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={clearCredentials} disabled={save.isPending || typed}
        onChange={event => setClearCredentials(event.target.checked)} />Remove saved own credentials on save</label> : null}
      {initial.activation_hold ? <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={!draft.activation_hold} disabled={save.isPending}
        onChange={event => set({ activation_hold: !event.target.checked })} />I reviewed the imported sender configuration; release its hold on save</label> : null}
    </fieldset> : null}
    {spec.providers.length > 1 ? <Field label="Provider"><select className="desk-input" value={draft.provider} disabled={save.isPending}
      onChange={event => { set({ provider: event.target.value as ProviderKey }); setSecrets({}); }}>
      {spec.providers.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></Field> : null}
    {provider.identityLabel ? <Field label={provider.identityLabel} hint={provider.identityHint}>
      <input className="desk-input" value={draft.integration_identity} maxLength={255} disabled={save.isPending}
        onChange={event => set({ integration_identity: event.target.value })} /></Field> : null}
    {provider.credentials.length ? <fieldset className="grid gap-3 rounded-lg border border-line p-3">
      <legend className="px-1 text-sm font-semibold text-ink">Credentials</legend>
      <p className="text-sm text-muted">{draft.credentials_set && draft.provider === initial.provider
        ? "Credentials are saved and never shown again. Fill in every field below only to replace them."
        : "Stored encrypted. They are never shown again after you save."}</p>
      {provider.credentials.map(field => <Field key={field.key} label={`${field.label}${field.optional ? " (optional)" : ""}`} hint={field.hint}>
        <input className="desk-input" type={field.secret ? "password" : "text"} autoComplete="off" value={secrets[field.key] ?? ""}
          disabled={save.isPending} onChange={event => { setSecrets(current => ({ ...current, [field.key]: event.target.value })); setProblem(""); }} />
      </Field>)}
    </fieldset> : null}
    {provider.installation ? <SlackInstallation makerspaceId={makerspaceId} configured={draft.credentials_set} /> : null}
    {spec.key !== "email" && spec.key !== "native_push" ? <div className="grid gap-3 sm:grid-cols-2">
      {(["daily_limit", "recipient_daily_limit"] as const).map(key => <Field key={key} label={key === "daily_limit" ? "Messages per day (optional)" : "Messages per person per day (optional)"}>
        <input className="desk-input" type="number" min={1} value={draft.quotas[key] ?? ""} disabled={save.isPending}
          onChange={event => set({ quotas: { ...draft.quotas, [key]: event.target.value ? Number(event.target.value) : undefined } })} />
      </Field>)}
    </div> : null}
    {spec.key === "whatsapp" ? <WhatsAppTemplatesEditor templates={draft.templates} disabled={save.isPending} onChange={templates => set({ templates })} /> : null}
    {spec.key === "whatsapp" && draft.provider === "twilio" ? <WhatsAppApprovalRefresh makerspaceId={makerspaceId}
      disabled={save.isPending || !row?.credentials_set || rotates || !sameTemplates(draft.templates, initial.templates)}
      onRefresh={templates => set({ templates })} /> : null}
    {rotates && row ? <Callout size="inline" tone="warn" lead="Saving reconnects this channel."
      body={`Changing the provider, ${provider.identityLabel?.toLowerCase() ?? "identity"} or credentials disconnects everyone's personal ${CHANNEL_LABELS[spec.key]} connection. They will need to connect again.`} /> : null}
    {problem ? <p role="alert" className="text-sm text-danger">{problem}</p> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    {save.isSuccess && !save.isPending ? <p role="status" className="text-sm text-muted">{spec.label} settings saved.</p> : null}
    <div><button className="desk-button" type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : `Save ${spec.label}`}</button></div>
  </form>;
}
