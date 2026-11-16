import { t } from "@lingui/core/macro";
import { useId } from "react";

import type { ActivityFamily, SectionKey } from "../accountProfileTypes";
import { fieldError, useOwnProfile, usePatchProfile } from "./profileEditApi";

/** Per-section "show" switch (default on). Saves on its own: a toggle is a consent, not a draft field. */
const DEFAULT_OFF: ActivityFamily[] = ["speaking", "machine_activity", "bookings", "loans"];

export function SectionToggle({ section, label }: { section: SectionKey | ActivityFamily; label?: string }) {
  const profile = useOwnProfile();
  const patch = usePatchProfile();
  const key = `show_${section}` as const;
  const fallback = section in (profile.data?.shown ?? {}) ? profile.data?.shown[section as SectionKey] : !DEFAULT_OFF.includes(section as ActivityFamily);
  const checked = profile.data?.toggles?.[key] ?? fallback ?? true;
  const id = `profile-show-${section}-${useId()}`;
  const pending = patch.isPending && key in (patch.variables ?? {});
  return <div className="grid gap-1">
    <label htmlFor={id} className="flex min-h-11 cursor-pointer items-center gap-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
      <input id={id} type="checkbox" role="switch" className="h-5 w-5 accent-accent" checked={checked} disabled={!profile.data || patch.isPending}
        onChange={() => patch.mutate({ [key]: !checked })} />
      <span className="text-sm font-semibold text-ink">{label ?? t`Show this section on my profile`}{pending ? t` · Saving…` : ""}</span>
    </label>
    {patch.error ? <p role="alert" className="text-sm text-danger">{fieldError(patch.error, "detail")}</p> : null}
  </div>;
}
