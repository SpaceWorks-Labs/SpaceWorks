import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, SettingsSection, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { guestErrorText } from "../guestPasses/api";
import { eraserErrorText, providerApi, providerKeys, type ProviderInput, type ProviderScope } from "./api";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

const sourceNote = (effective: "space" | "platform" | null | undefined) => effective === "space" ? t`Using this space's own service.`
  : effective === "platform" ? t`Using the platform's service.` : t`Background removal stays hidden until a service is set here or by the platform.`;

/**
 * Background eraser service (decision 314 c): any HTTPS service that implements the image adapter contract.
 * Per space (Space Manager) or for the whole platform (superadmin). The shared secret is write-only.
 */
export function EraserProviderCard({ scope }: { scope: ProviderScope }) {
  const client = useQueryClient();
  const key = providerKeys.scope(scope);
  const query = useQuery({ queryKey: key, queryFn: () => providerApi.read(scope), retry: false });
  const [form, setForm] = useState({ url: "", secret: "" });
  const [editing, setEditing] = useState(false);
  const save = useMutation({
    mutationFn: (input: ProviderInput) => providerApi.save(scope, input),
    onSuccess: (data) => { client.setQueryData(key, data); setEditing(false); setForm({ url: "", secret: "" }); void client.invalidateQueries({ queryKey: ["audit"] }); },
  });
  const test = useMutation({
    mutationFn: () => providerApi.test(scope),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  const data = query.data;
  const space = scope.kind === "space";
  const ready = form.url.trim() !== "" && (form.secret.length >= 16 || (data?.configured && form.secret === ""));
  return <SettingsSection title={t`Background eraser`} description={space
    ? t`Connect your own background-removal service for card photos. Photos are sent to it only when staff or a member asks. The secret is never shown again after saving.`
    : t`The background-removal service every space uses unless it sets its own. Photos are sent to it only when someone asks. The secret is never shown again after saving.`}>
    {query.isLoading ? <LogoLoader label={t`Loading eraser settings…`} size={48} className="min-h-16 py-3" /> : null}
    {query.isError ? <p role="alert" className="py-4 text-sm text-danger">{guestErrorText(query.error)}</p> : null}
    {data ? <div className="grid gap-3 rounded-2xl border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="title-section">{t`Eraser service`}</h3>
        <StatusPill tone={data.configured ? "success" : "neutral"} label={data.configured ? t`Set up` : t`Not set up`} />
      </div>
      {data.configured ? <p className="text-sm text-muted [overflow-wrap:anywhere]">{data.provider_url} · {t`Fingerprint ${data.fingerprint}`}</p> : null}
      {space ? <p className="text-sm text-muted">{sourceNote(data.effective)}</p> : null}
      {data.last_test_at ? <p role="status" className={data.last_test_ok ? "text-sm text-success-ink" : "text-sm text-danger"}>
        {data.last_test_ok ? t`Last test passed on ${formatDate(data.last_test_at)}.` : t`Last test failed on ${formatDate(data.last_test_at)}: ${eraserErrorText(data.last_test_error)}`}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button min-h-11" aria-expanded={editing} onClick={() => { save.reset(); setEditing(!editing); }}>
          {data.configured ? t`Replace service` : t`Add service`}</button>
        {data.configured ? <button type="button" className="desk-button min-h-11" disabled={test.isPending} onClick={() => test.mutate()}>
          {test.isPending ? <><BoxArt size={16} mono />{t`Testing…`}</> : t`Test connection`}</button> : null}
        {data.configured ? <button type="button" className="desk-button-ghost min-h-11" disabled={save.isPending} onClick={() => save.mutate({ clear: true })}>{t`Remove`}</button> : null}
      </div>
      {test.data && !test.data.ok ? <p role="alert" className="text-sm text-danger">{eraserErrorText(test.data.error)}</p> : null}
      {test.data?.ok ? <p role="status" className="text-sm text-success-ink">{t`The service answered correctly.`}</p> : null}
      {editing ? <form className="grid gap-3" aria-label={t`Eraser service`} onSubmit={(event) => {
        event.preventDefault();
        if (ready) save.mutate({ provider_url: form.url.trim(), ...(form.secret ? { secret: form.secret } : {}) });
      }}>
        <Field label={t`Service address`} hint={space ? t`A public https address, like https://eraser.example.org.` : t`Like https://eraser.example.org or http://bg-eraser:8080.`}>
          <input className="desk-input" type="url" autoComplete="off" value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} /></Field>
        <Field label={t`Shared secret`} hint={t`At least 16 characters. The service verifies every request with it.`}>
          <input className="desk-input" type="password" autoComplete="new-password" value={form.secret} onChange={(event) => setForm({ ...form, secret: event.target.value })} /></Field>
        <div><button type="submit" className="desk-button-primary min-h-11" disabled={!ready || save.isPending}>{save.isPending ? t`Saving…` : t`Save service`}</button></div>
      </form> : null}
      {space && data.platform_available ? <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5" checked={data.use_platform_provider ?? true} disabled={save.isPending}
          onChange={(event) => save.mutate({ use_platform_provider: event.target.checked })} />
        {t`Use the platform's service when this space has none of its own`}</label> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(save.error)}</p> : null}
    </div> : null}
  </SettingsSection>;
}
