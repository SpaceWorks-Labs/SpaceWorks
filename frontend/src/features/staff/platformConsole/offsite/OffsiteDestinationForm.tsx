import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { actionErrorText } from "../../platformSpaces/ActionDialog";
import { fieldError } from "../../platformParity/parityRequest";
import { useSaveDestination, type Addressing, type Destination, type DestinationBody } from "./offsiteApi";
import { BoxArt } from "../../../../components/BoxSpinner";

const blank = { name: "", endpoint_url: "", bucket: "", region: "", prefix: "", addressing_style: "auto" as Addressing,
  retention_days: "90", enabled: true, access_key_id: "", secret_access_key: "" };

/**
 * Register a destination, or edit one. Credentials are write-only: an edit leaves them blank to
 * keep the stored pair. Once a destination has a journal the server refuses location changes.
 */
export function OffsiteDestinationForm({ destination, onDone }: { destination?: Destination; onDone: () => void }) {
  const save = useSaveDestination(destination?.id);
  const [form, setForm] = useState<typeof blank>(() => destination ? { ...blank, name: destination.name,
    endpoint_url: destination.endpoint_url, bucket: destination.bucket, region: destination.region, prefix: destination.prefix,
    addressing_style: destination.addressing_style, retention_days: String(destination.retention_days), enabled: destination.enabled } : blank);
  const set = <K extends keyof typeof blank>(key: K, value: (typeof blank)[K]) => setForm(current => ({ ...current, [key]: value }));
  const days = Number(form.retention_days);
  const daysOk = Number.isInteger(days) && days >= 1 && days <= 3650;
  const credentialsOk = destination ? Boolean(form.access_key_id) === Boolean(form.secret_access_key) : Boolean(form.access_key_id && form.secret_access_key);
  const valid = form.name.trim() && form.bucket.trim() && daysOk && credentialsOk;
  const error = (field: string) => fieldError(save.error, field);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || save.isPending) return;
    const body: DestinationBody = { name: form.name.trim(), endpoint_url: form.endpoint_url.trim(), bucket: form.bucket.trim(),
      region: form.region.trim(), prefix: form.prefix.trim(), addressing_style: form.addressing_style, retention_days: days, enabled: form.enabled };
    if (form.access_key_id) Object.assign(body, { access_key_id: form.access_key_id, secret_access_key: form.secret_access_key });
    save.mutate(body, { onSuccess: () => { toast(destination ? t`Destination saved.` : t`Destination added.`); onDone(); } });
  };
  const other = save.error && !["name", "endpoint_url", "bucket", "prefix", "retention_days"].some(error) ? actionErrorText(save.error) : "";
  return <form className="grid gap-4 p-3" aria-label={destination ? t`Edit ${destination.name}` : t`New offsite destination`} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Name`} hint={t`Lowercase letters, digits and hyphens, e.g. r2-offsite.`} error={error("name")}>
        <input className="desk-input" value={form.name} maxLength={64} spellCheck={false} onChange={event => set("name", event.target.value)} />
      </Field>
      <Field label={t`Bucket`} error={error("bucket")}>
        <input className="desk-input" value={form.bucket} maxLength={255} spellCheck={false} onChange={event => set("bucket", event.target.value)} />
      </Field>
      <Field label={t`Endpoint URL (blank for AWS)`} hint={t`For R2, MinIO or Supabase, the S3 API address.`} error={error("endpoint_url")}>
        <input className="desk-input" type="url" value={form.endpoint_url} maxLength={300} spellCheck={false} onChange={event => set("endpoint_url", event.target.value)} />
      </Field>
      <Field label={t`Region (optional)`}>
        <input className="desk-input" value={form.region} maxLength={64} spellCheck={false} onChange={event => set("region", event.target.value)} />
      </Field>
      <Field label={t`Folder prefix (optional)`} error={error("prefix")}>
        <input className="desk-input" value={form.prefix} maxLength={200} spellCheck={false} onChange={event => set("prefix", event.target.value)} />
      </Field>
      <Field label={t`Addressing`}>
        <select className="desk-input" value={form.addressing_style} onChange={event => set("addressing_style", event.target.value as Addressing)}>
          <option value="auto">{t`Auto`}</option><option value="path">{t`Path`}</option><option value="virtual">{t`Virtual host`}</option>
        </select>
      </Field>
      <Field label={t`Keep copies for (days)`} error={error("retention_days") ?? (daysOk ? undefined : "Use 1 to 3650 days.")}>
        <input className="desk-input" inputMode="numeric" value={form.retention_days} onChange={event => set("retention_days", event.target.value)} />
      </Field>
      <label className="flex min-h-11 items-center gap-2 text-sm font-semibold">
        <input type="checkbox" checked={form.enabled} onChange={event => set("enabled", event.target.checked)} />{t`Push new backups here`}
      </label>
      <Field label={destination ? t`New access key ID (blank keeps it)` : t`Access key ID`}>
        <input className="desk-input" value={form.access_key_id} maxLength={200} autoComplete="off" spellCheck={false} onChange={event => set("access_key_id", event.target.value)} />
      </Field>
      <Field label={destination ? t`New secret access key (blank keeps it)` : t`Secret access key`}
        error={credentialsOk ? undefined : destination ? t`Enter both keys to rotate them, or neither.` : t`Both keys are required.`}>
        <input className="desk-input" type="password" value={form.secret_access_key} maxLength={200} autoComplete="new-password" onChange={event => set("secret_access_key", event.target.value)} />
      </Field>
    </div>
    {other ? <p role="alert" className="text-sm text-danger">{other}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || save.isPending}>
      {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : destination ? t`Save destination` : t`Add destination`}
    </button>
  </form>;
}
