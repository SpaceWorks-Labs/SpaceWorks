import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fingerprint } from "lucide-react";
import { clearAccessToken, setAccessToken } from "../../../lib/api";
import { authErrorMessage } from "../../../lib/api/authErrorCopy";
import { ConfirmDialog, EmptyState, ErrorText } from "../../../components/ui";
import { invalidateAccountSecurity, passkeysKey } from "../securityQueries";
import { listPasskeys, registerPasskey, removePasskey, renamePasskey } from "./passkeyApi";
import { PasskeyRow } from "./PasskeyRow";
import { isPasskeyCancelled, passkeysSupported } from "./webauthn";

/**
 * The person's passkeys (S-A): add (recent re-authentication, asked for by the shared client),
 * rename, remove. Adding or removing one ends the person's other sessions; this browser keeps a
 * fresh session unless the removed passkey was its only proof (`onSignedOut`).
 */
export function PasskeyList({ onRecoveryCodes, onSignedOut }: {
  onRecoveryCodes: (codes: string[]) => void; onSignedOut: () => void;
}) {
  const client = useQueryClient();
  const [removing, setRemoving] = useState<{ id: number; name: string }>();
  const [notice, setNotice] = useState("");
  const query = useQuery({ queryKey: passkeysKey, queryFn: listPasskeys, retry: false });
  const settle = () => { void invalidateAccountSecurity(client); };
  const add = useMutation({ mutationFn: () => registerPasskey(""), onSuccess: result => {
    setAccessToken(result.access);
    setNotice(t`Passkey added. You're still signed in here; other devices were signed out.`);
    if (result.recovery_codes?.length) onRecoveryCodes(result.recovery_codes);
    settle();
  } });
  const rename = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => renamePasskey(id, name),
    onSuccess: () => { setNotice(t`Passkey renamed.`); settle(); } });
  const remove = useMutation({ mutationFn: (id: number) => removePasskey(id), onSuccess: result => {
    setRemoving(undefined);
    if (result.signed_out || !result.access) { clearAccessToken(); onSignedOut(); return; }
    setAccessToken(result.access);
    setNotice(t`Passkey removed. Other devices were signed out.`);
    settle();
  } });
  const supported = passkeysSupported();
  const allowed = query.data?.passkeys_allowed !== false;
  const busy = add.isPending || rename.isPending || remove.isPending;
  const failure = add.error && !isPasskeyCancelled(add.error) ? add.error : rename.error ?? remove.error;
  if (query.isLoading) return <p role="status" className="text-sm text-muted">{t`Loading passkeys…`}</p>;
  if (query.error) return <ErrorText message={authErrorMessage(query.error, "Couldn't load your passkeys. Try again.")} onRetry={() => void query.refetch()} />;
  const rows = query.data?.passkeys ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`A passkey signs you in with your fingerprint, face or device PIN instead of a password. It never leaves your device, and it only works on this website.`}</p>
    {!allowed ? <p className="text-sm text-ink">{t`Passkeys are turned off for your account. Saved passkeys stay listed; use your authenticator app to sign in.`}</p> : null}
    {rows.length ? <ul className="grid gap-3">{rows.map(passkey => <li key={passkey.id}><PasskeyRow passkey={passkey} busy={busy}
      onRename={name => rename.mutate({ id: passkey.id, name })} onRemove={() => setRemoving({ id: passkey.id, name: passkey.name || "this passkey" })} /></li>)}</ul>
      : <EmptyState message={t`No passkeys yet. Add one to sign in without typing a password.`} />}
    {allowed ? supported ? <div><button type="button" className="desk-button-primary min-h-11 gap-2" disabled={busy} onClick={() => add.mutate()}>
      <Fingerprint aria-hidden="true" size={20} />{add.isPending ? t`Waiting for your device…` : t`Add a passkey`}</button></div>
      : <p className="text-sm text-muted">{t`This browser can't create passkeys. Try a recent version of Chrome, Edge, Firefox or Safari.`}</p> : null}
    <p role="status" className="text-sm text-ink empty:hidden">{notice}</p>
    {failure ? <ErrorText message={authErrorMessage(failure, "Couldn't change your passkeys. Try again.")} /> : null}
    <ConfirmDialog open={Boolean(removing)} title={t`Remove this passkey?`} tone="danger" confirmLabel={t`Remove passkey`} pending={remove.isPending}
      message={removing?.name ? t`${removing.name} will stop working, and your other devices will be signed out. Remove it from your device's password manager too.` : t`This passkey will stop working, and your other devices will be signed out. Remove it from your device's password manager too.`}
      onCancel={() => setRemoving(undefined)} onConfirm={() => { if (removing) remove.mutate(removing.id); }} />
  </div>;
}
