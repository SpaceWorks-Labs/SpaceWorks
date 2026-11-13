import { t } from "@lingui/core/macro";
import { useCallback, useState } from "react";
import { UsernameField, usernameUsable } from "../username/UsernameField";
import type { UsernameStatus } from "../username/usernameApi";
import { fieldError, useClaimHandle } from "./profileEditApi";
import { BoxArt } from "../../../components/BoxSpinner";

/**
 * Choose or change the account's handle (its username). With none yet it is a clear call to action with live
 * availability; with one, a change is allowed once every 30 days and the old address keeps redirecting for 30 days.
 * The server stays the authority on reserved names, collisions and the cooldown.
 */
export function HandleField({ handle }: { handle: string | null }) {
  const claim = useClaimHandle();
  const [editing, setEditing] = useState(!handle);
  const [value, setValue] = useState(handle ?? "");
  const [status, setStatus] = useState<UsernameStatus>("idle");
  const onStatus = useCallback((next: UsernameStatus) => setStatus(next), []);
  const normalized = value.trim().toLowerCase();
  const unchanged = normalized === handle;
  const submit = () => { if (normalized && !unchanged && usernameUsable(status)) claim.mutate(normalized, { onSuccess: () => setEditing(false) }); };
  if (handle && !editing) return <div className="flex flex-wrap items-center gap-2">
    <span className="chip text-sm">@{handle}</span>
    <button type="button" className="desk-button" onClick={() => { setValue(handle); claim.reset(); setEditing(true); }}>{t`Change handle`}</button>
  </div>;
  return <form className="grid gap-2" onSubmit={event => { event.preventDefault(); submit(); }}>
    {handle ? null : <p className="text-sm font-semibold text-ink">{t`Choose your handle`}</p>}
    <UsernameField id="profile-handle" value={value} onChange={next => { setValue(next); claim.reset(); }} onStatus={onStatus} prefill={!handle} />
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary" disabled={!normalized || unchanged || !usernameUsable(status) || claim.isPending}>
        {claim.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : handle ? t`Save handle` : t`Choose handle`}</button>
      {handle ? <button type="button" className="desk-button" onClick={() => { setEditing(false); claim.reset(); }}>{t`Cancel`}</button> : null}
    </div>
    {claim.error ? <p role="alert" className="text-sm text-danger">{fieldError(claim.error, "handle")}</p> : null}
    <p className="text-sm text-muted">{handle
      ? t`You can change your handle once every 30 days. Your old link keeps redirecting to the new one for 30 days.`
      : t`Your handle is your profile address. Members can also reach you by account link without one.`}</p>
  </form>;
}
