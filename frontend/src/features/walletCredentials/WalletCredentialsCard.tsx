import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Callout, SettingsSection, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { guestErrorText } from "../guestPasses/api";
import { walletCredentialsApi, walletKeys, type AppleStatus, type GoogleStatus, type Source, type WalletCredentialsInput, type WalletScope } from "./api";
import { AppleCredentialForm, GoogleCredentialForm } from "./WalletCredentialForms";

const sourceNote = (source: Source | undefined) => source === "platform" ? t`Using the platform's credentials.`
  : source === "deployment" ? t`Using the deployment's credentials.` : source === "space" ? t`Using this space's credentials.`
  : t`Wallet buttons stay hidden until credentials are set here or by the platform.`;

/**
 * Wallet passes (decision 223 l): a space's own signing credentials (Space Manager, under
 * Settings › Membership) or the platform's (superadmin, recent re-authentication). A space with
 * none uses the platform's; with neither, the wallet buttons stay hidden.
 */
export function WalletCredentialsCard({ scope }: { scope: WalletScope }) {
  const client = useQueryClient();
  const key = walletKeys.scope(scope);
  const query = useQuery({ queryKey: key, queryFn: () => walletCredentialsApi.read(scope), retry: false });
  const [editing, setEditing] = useState<"apple" | "google" | null>(null);
  // Stays up for the rest of the visit once a save changed the Apple pass type (later saves do not hide it).
  const [reissueNeeded, setReissueNeeded] = useState(false);
  const save = useMutation({
    mutationFn: (input: WalletCredentialsInput) => walletCredentialsApi.save(scope, input),
    onSuccess: (data) => { if (data.reissue_needed) setReissueNeeded(true); client.setQueryData(key, data); setEditing(null); void client.invalidateQueries({ queryKey: ["audit"] }); },
  });
  const data = query.data;
  const effective = data?.effective;
  return <SettingsSection title={t`Wallet passes`} description={scope.kind === "space"
    ? t`Sign Apple Wallet and Google Wallet passes for member cards and guest passes with this space's own credentials. Secrets are never shown again after saving.`
    : t`Used by every space that has no credentials of its own, while hosting other makerspaces is on. Secrets are never shown again after saving.`}>
    {query.isLoading ? <p role="status" className="py-4 text-sm text-muted">{t`Loading wallet credentials…`}</p> : null}
    {query.isError ? <p role="alert" className="py-4 text-sm text-danger">{guestErrorText(query.error)}</p> : null}
    {data ? <div className="grid gap-4 py-3">
      {reissueNeeded ? <div role="status"><Callout size="inline" tone="warn" lead={t`Your Apple pass type changed.`}
        body={t`Passes already in members' wallets won't update; ask holders to re-add them from My passes.`} /></div> : null}
      <Platform name={t`Apple Wallet`} configured={data.apple.configured} note={effective ? sourceNote(effective.apple) : undefined}
        facts={appleFacts(data.apple)} warning={data.apple.expires_soon ? t`The certificate expires soon. Upload a renewed one.` : undefined}
        editing={editing === "apple"} onEdit={() => { save.reset(); setEditing(editing === "apple" ? null : "apple"); }}
        onClear={() => save.mutate({ clear_apple: true })} pending={save.isPending}
        form={<AppleCredentialForm pending={save.isPending} onSubmit={(input) => save.mutate(input)} />} />
      <Platform name={t`Google Wallet`} configured={data.google.configured} note={effective ? sourceNote(effective.google) : undefined}
        facts={googleFacts(data.google)} editing={editing === "google"} onEdit={() => { save.reset(); setEditing(editing === "google" ? null : "google"); }}
        onClear={() => save.mutate({ clear_google: true })} pending={save.isPending}
        form={<GoogleCredentialForm pending={save.isPending} onSubmit={(input) => save.mutate(input)} />} />
      {save.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(save.error)}</p> : null}
    </div> : null}
  </SettingsSection>;
}

function appleFacts(apple: AppleStatus): string[] {
  return [apple.pass_type_id ? t`Pass Type ID ${apple.pass_type_id}` : "", apple.team_id ? t`Team ${apple.team_id}` : "",
    apple.expires_at ? t`Expires ${formatDate(apple.expires_at)}` : "", apple.fingerprint ? t`Fingerprint ${apple.fingerprint.slice(0, 16)}…` : ""].filter(Boolean);
}

function googleFacts(google: GoogleStatus): string[] {
  return [google.issuer_id ? t`Issuer ${google.issuer_id}` : "", google.class_prefix ? t`Prefix ${google.class_prefix}` : "",
    google.fingerprint ? t`Fingerprint ${google.fingerprint.slice(0, 16)}…` : ""].filter(Boolean);
}

function Platform({ name, configured, note, facts, warning, editing, onEdit, onClear, pending, form }: {
  name: string; configured: boolean; note?: string; facts: string[]; warning?: string; editing: boolean;
  onEdit: () => void; onClear: () => void; pending: boolean; form: ReactNode;
}) {
  return <div className="grid gap-3 rounded-2xl border border-line p-4">
    <div className="flex flex-wrap items-center gap-2">
      <h3 className="title-section">{name}</h3>
      <StatusPill tone={configured ? "success" : "neutral"} label={configured ? t`Set up` : t`Not set up`} />
    </div>
    {facts.length ? <p className="text-sm text-muted [overflow-wrap:anywhere]">{facts.join(" · ")}</p> : null}
    {note ? <p className="text-sm text-muted">{note}</p> : null}
    {warning ? <p role="status" className="text-sm text-warn-ink">{warning}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button min-h-11" aria-expanded={editing} onClick={onEdit}>{configured ? t`Replace credentials` : t`Add credentials`}</button>
      {configured ? <button type="button" className="desk-button-ghost min-h-11" disabled={pending} onClick={onClear}>{t`Remove`}</button> : null}
    </div>
    {editing ? form : null}
  </div>;
}
