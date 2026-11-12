import { t } from "@lingui/core/macro";
import { toneSurfaceClasses } from "../../components/ui/tones";
import type { PresenceSession } from "./api";
import { clockTime, minutesLeft, presetLongLabel } from "./presenceCopy";
import { RENEW_WINDOW_MINUTES, type RenewPhase } from "./renewReminder";
import { BoxArt } from "../../components/BoxSpinner";

export type PresenceRenewPromptProps = { session: PresenceSession; phase: RenewPhase; now: number; presets: number[];
  pending: boolean; onRenew: (minutes: number) => void };

/** The in-app prompt as the session nears or passes expiry. Renewing always extends from now. */
export function PresenceRenewPrompt({ session, phase, now, presets, pending, onRenew }: PresenceRenewPromptProps) {
  if (phase !== "soon" && phase !== "expired") return null;
  const left = Math.max(1, minutesLeft(session, now));
  const lead = phase === "soon" ? `Your check-in ends in ${left} min.` : `Your check-in ended at ${clockTime(session.expires_at)}.`;
  const body = phase === "soon" ? "Still here? Renew from now." : `Still here? You can renew for ${RENEW_WINDOW_MINUTES} minutes after it ends.`;
  return <div role="alert" className={`grid gap-3 rounded-xl border p-4 ${toneSurfaceClasses[phase === "soon" ? "warn" : "danger"]}`}>
    <p className="text-sm"><strong>{lead}</strong> {body}</p>
    <div className="flex flex-wrap gap-2" role="group" aria-label={t`Renew for`}>
      {presets.map((minutes) => <button key={minutes} type="button" className="desk-button-brand" disabled={pending} onClick={() => onRenew(minutes)}>
        {pending ? <><BoxArt size={16} mono />{t`Renewing…`}</> : t`Renew ${presetLongLabel(minutes)}`}</button>)}
    </div>
  </div>;
}
