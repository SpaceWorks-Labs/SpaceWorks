import { t } from "@lingui/core/macro";
import { useState } from "react";
import { StatusPill } from "../../components/ui";
import { DEFAULT_PRESETS, usePresenceCurrent, usePresenceMutations } from "./api";
import { PresenceCheckInSheet } from "./PresenceCheckInSheet";
import { PresenceRenewPrompt } from "./PresenceRenewPrompt";
import { clockTime, displayDisclosure, minutesLeft, presenceErrorText, presetLongLabel, STATUS_LABELS, timeLeftLabel } from "./presenceCopy";
import { renewPhase, useNow, useRenewNotification } from "./renewReminder";
import { requestWebNotify, webNotifyPermission } from "./webNotify";

export type PresencePanelProps = {
  slug: string; spaceName: string;
  /** Module gate AND signed-in account. false renders nothing and sends no request. */
  enabled: boolean;
  member: boolean; claim?: boolean; selfCheckIn: boolean;
  /** Optional control so a page header action can open the same sheet. */
  sheetOpen?: boolean; onSheetOpenChange?: (open: boolean) => void;
};

/** The member's presence card: check in, the current session with time left, renew and end. */
export function PresencePanel({ enabled, ...props }: PresencePanelProps) {
  return enabled ? <PresencePanelBody {...props} /> : null;
}

function PresencePanelBody({ slug, spaceName, member, claim, selfCheckIn, sheetOpen, onSheetOpenChange }: Omit<PresencePanelProps, "enabled">) {
  const current = usePresenceCurrent(slug, true);
  const { renew, end } = usePresenceMutations(slug);
  const now = useNow();
  const [ownOpen, setOwnOpen] = useState(false);
  const open = sheetOpen ?? ownOpen;
  const setOpen = onSheetOpenChange ?? setOwnOpen;
  // The server supplies renewable history, including after reopening the page.
  // A later poll returning null also withdraws the prompt after a staff/user end.
  const reported = current.data?.active ? current.data.session : null;
  // Between polls a session can lapse locally; treat it as expired straight away.
  const live = reported && minutesLeft(reported, now) > 0 ? reported : null;
  const session = reported ?? current.data?.renewable ?? null;
  const phase = renewPhase(session, now);
  useRenewNotification(session, phase, spaceName);
  const [permission, setPermission] = useState(webNotifyPermission);
  const presets = current.data?.presets?.length ? current.data.presets : DEFAULT_PRESETS;
  const optOutAllowed = current.data?.personal_opt_out_allowed ?? session?.personal_opt_out_allowed;
  const showSession = session && (live || phase === "expired");
  const error = renew.error ?? end.error;

  return <section aria-labelledby="presence-panel-title" className={`desk-panel ${live ? "border-success" : "border-brand"} p-5`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 id="presence-panel-title" className="title-panel">{t`Presence`}</h2>
      {live ? <StatusPill label={t`Checked in`} tone="success" /> : null}
    </div>
    {current.isLoading ? <p role="status" className="mt-2 text-sm text-muted">{t`Checking your presence…`}</p> : null}
    {current.isError ? <p role="alert" className="mt-2 text-sm text-danger">{presenceErrorText(current.error).text}</p> : null}
    {current.isSuccess && showSession ? <div className="mt-3 grid gap-4">
      <div className="grid gap-1">
        <p className="text-sm text-ink"><strong>{STATUS_LABELS[session.status]}</strong>
          {session.status === "attending_event" ? <span className="text-muted"> {t` · set by your event ticket check-in`}</span> : null}</p>
        {live ? <p className="text-sm text-muted"><span className="tabular-nums">{timeLeftLabel(minutesLeft(session, now))}</span> {t` · until `}<time className="tabular-nums" dateTime={session.expires_at}>{clockTime(session.expires_at)}</time></p> : null}
        <p className="text-sm text-muted">{displayDisclosure(session)}</p>
      </div>
      <PresenceRenewPrompt session={session} phase={phase} now={now} presets={presets} pending={renew.isPending} onRenew={(minutes) => renew.mutate(minutes)} />
      {live && phase === "none" ? <div className="grid gap-2"><span className="text-sm font-semibold text-ink">{t`Extend from now`}</span>
        <div className="flex flex-wrap gap-2">{presets.map((minutes) => <button key={minutes} type="button" className="desk-button" disabled={renew.isPending}
          onClick={() => renew.mutate(minutes)}>{presetLongLabel(minutes)}</button>)}</div></div> : null}
      <div className="flex flex-wrap gap-2">
        {live ? <button type="button" className="desk-button" disabled={end.isPending} onClick={() => end.mutate()}>{end.isPending ? t`Ending…` : t`End check-in`}</button>
          : <button type="button" className="desk-button" onClick={() => setOpen(true)}>{t`Check in again`}</button>}
        {live && permission === "default" ? <button type="button" className="desk-button" onClick={() => void requestWebNotify().then(setPermission)}>{t`Notify me before it ends`}</button> : null}
      </div>
    </div> : null}
    {current.isSuccess && !showSession ? <div className="mt-2 grid gap-3">
      <p className="text-sm text-muted">{session && phase === "gone" ? t`Your last check-in has ended.` : t`You're not checked in.`}</p>
      <button type="button" className="desk-button-brand justify-self-start" onClick={() => setOpen(true)}>{t`Check in`}</button>
    </div> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-danger">{presenceErrorText(error).text}</p> : null}
    {open ? <PresenceCheckInSheet open slug={slug} onClose={() => setOpen(false)} presets={presets} member={member} claim={claim}
      selfCheckIn={selfCheckIn} optOutAllowed={optOutAllowed} /> : null}
  </section>;
}
