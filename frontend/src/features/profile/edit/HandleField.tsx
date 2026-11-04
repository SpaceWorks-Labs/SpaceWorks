import { useState } from "react";
import { ConfirmDialog } from "../../../components/ui";
import { HANDLE_PATTERN } from "../publicProfileApi";
import { fieldError, useClaimHandle, useReleaseHandle } from "./profileEditApi";

const GRAMMAR = "3–30 lowercase letters, numbers, dots, underscores or hyphens; start and end with a letter or number.";

/**
 * Claim, change or release the account's public handle. The server is the authority on
 * reserved names, collisions and the 30-day cooldown; the client check only spares a round trip.
 */
export function HandleField({ makerspaceId, handle }: {
  makerspaceId: number; handle: string | null;
}) {
  const claim = useClaimHandle(makerspaceId);
  const release = useReleaseHandle(makerspaceId);
  const [editing, setEditing] = useState(!handle);
  const [value, setValue] = useState(handle ?? "");
  const [confirmRelease, setConfirmRelease] = useState(false);
  const normalized = value.trim().toLowerCase();
  const invalid = normalized !== "" && !HANDLE_PATTERN.test(normalized);
  const submit = () => {
    if (!HANDLE_PATTERN.test(normalized)) return;
    claim.mutate(normalized, { onSuccess: () => setEditing(false) });
  };
  const errorId = `profile-handle-error-${makerspaceId}`;
  const showEditor = editing || !handle;
  return <div className="grid gap-3">
    {handle && !showEditor ? <div className="flex flex-wrap items-center gap-2">
      <span className="chip text-sm">@{handle}</span>
      <button type="button" className="desk-button" onClick={() => { setValue(handle); claim.reset(); setEditing(true); }}>Change handle</button>
      <button type="button" className="desk-button-danger-outline" onClick={() => setConfirmRelease(true)}>Release handle</button>
    </div> : <form className="grid gap-2" onSubmit={event => { event.preventDefault(); submit(); }}>
      <div className="flex flex-wrap gap-2">
        <span className="flex min-w-0 grow items-center rounded-control border border-line bg-panel focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
          <span aria-hidden="true" className="pl-3 text-muted">@</span>
          <input id={`profile-handle-${makerspaceId}`} aria-label="Public handle" className="min-h-11 w-full min-w-0 bg-transparent px-1 text-ink outline-none"
            value={value} autoCapitalize="none" autoCorrect="off" spellCheck={false} maxLength={30}
            aria-invalid={invalid || Boolean(claim.error) || undefined} aria-describedby={errorId}
            onChange={event => { setValue(event.target.value); claim.reset(); }} />
        </span>
        <button type="submit" className="desk-button-primary" disabled={!normalized || invalid || claim.isPending}>
          {claim.isPending ? "Saving…" : handle ? "Save handle" : "Claim handle"}</button>
        {handle ? <button type="button" className="desk-button" onClick={() => { setEditing(false); claim.reset(); }}>Cancel</button> : null}
      </div>
      <p id={errorId} role={invalid || claim.error ? "alert" : undefined} className={`text-sm ${invalid || claim.error ? "text-danger" : "text-muted"}`}>
        {claim.error ? fieldError(claim.error, "handle") : invalid ? GRAMMAR
          : handle ? "You can change your handle once every 30 days. Your old link keeps redirecting for 30 days." : GRAMMAR}
      </p>
    </form>}
    {release.error ? <p role="alert" className="text-sm text-danger">{fieldError(release.error, "handle")}</p> : null}
    <ConfirmDialog open={confirmRelease} tone="danger" title="Release your handle?" confirmLabel="Release handle" pending={release.isPending}
      message="Your public page goes offline now. The name stays reserved for 30 days, you can't claim another handle until then, and publishing again needs your consent again."
      onCancel={() => setConfirmRelease(false)}
      onConfirm={() => release.mutate(undefined, { onSuccess: () => { setConfirmRelease(false); setEditing(true); setValue(""); }, onError: () => setConfirmRelease(false) })} />
  </div>;
}
