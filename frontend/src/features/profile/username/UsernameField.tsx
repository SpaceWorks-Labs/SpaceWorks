import { t } from "@lingui/core/macro";
import { useEffect, useRef } from "react";

import { useUsernameAvailability, useUsernameSuggestion, type UsernameStatus } from "./usernameApi";

export const usernameStatusText = (status: UsernameStatus) => ({
  idle: "", checking: t`Checking…`, available: t`That username is free.`, taken: t`That username is taken.`,
  reserved: t`That username is reserved. Try another.`, error: t`Couldn't check it just now. You can still continue.`,
  invalid: t`Use 3–30 lowercase letters, numbers, dots, underscores or hyphens; start and end with a letter or number.`,
}[status]);

/** A username is usable unless the server or the grammar says no; a failed check never blocks. */
export const usernameUsable = (status: UsernameStatus) => status === "available" || status === "error";

/**
 * Sign-up username: pre-filled with a suggestion (until the person types), checked live against the
 * grammar, reserved list and existing handles. The parent owns the value and reads `status` to gate submit.
 */
export function UsernameField({ id, value, onChange, onStatus, seed = {}, autoFocus = false, prefill = true }: {
  id: string; value: string; onChange: (next: string) => void; onStatus?: (status: UsernameStatus) => void;
  seed?: { displayName?: string; email?: string; known?: string | null }; autoFocus?: boolean; prefill?: boolean;
}) {
  const touched = useRef(false);
  const suggestion = useUsernameSuggestion(seed, true);
  const status = useUsernameAvailability(value);
  useEffect(() => { onStatus?.(status); }, [status, onStatus]);
  useEffect(() => {
    if (prefill && !touched.current && suggestion.data) onChange(suggestion.data);
  }, [prefill, suggestion.data, onChange]);
  const bad = status === "invalid" || status === "taken" || status === "reserved";
  return <div className="grid gap-1">
    <label className="text-sm font-semibold" htmlFor={id}>{t`Username`}</label>
    <span className="flex min-w-0 items-center rounded-control border border-line bg-panel focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
      <span aria-hidden="true" className="pl-3 text-muted">@</span>
      <input id={id} className="min-h-11 w-full min-w-0 bg-transparent px-1 text-ink outline-none" value={value} maxLength={30} required
        autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} autoFocus={autoFocus}
        aria-invalid={bad || undefined} aria-describedby={`${id}-status`}
        onChange={event => { touched.current = true; onChange(event.target.value); }} />
    </span>
    <p id={`${id}-status`} role="status" className={`text-sm ${bad ? "text-danger" : status === "available" ? "text-success-ink" : "text-muted"}`}>
      {usernameStatusText(status)}</p>
  </div>;
}
