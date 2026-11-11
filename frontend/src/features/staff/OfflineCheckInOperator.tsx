import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { Trans } from "@lingui/react/macro";
import { offlineAccountScope } from "../../lib/api/sessionTokens";
import { useCallback, useEffect, useRef, useState } from "react";

import { usePrintReceipts } from "../../components/card-print";
import { DangerZone, ScanWorkbench } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { DeskPrintSheet } from "./eventBadges/DeskPrintSheet";
import type { BadgeReceipt } from "./eventBadges/deskBadgeApi";
import { offlineSyncOutcomeLabel, waiverStateLabel } from "./checkInLabels";
import type {
  OfflineRoster,
  OfflineRosterRegistration,
  QueuedCheckIn,
  SyncResponse,
} from "./eventCheckInOfflineApi";
import {
  applySyncResults,
  loadOfflineState,
  pruneExpiredOfflineStates,
  queueBadgeReceipt,
  queueOfflineCheckIn,
  saveOfflineRoster,
  wipeOfflineState,
  type OfflineCheckInState,
} from "./eventCheckInOfflineStore";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function OfflineCheckInOperator({
  scope: resourceScope,
  download,
  synchronize,
  onSynchronized,
  autoDownload = false,
}: {
  scope: string;
  download: () => Promise<OfflineRoster>;
  synchronize: (roster: OfflineRoster, operations: QueuedCheckIn[], receipts: BadgeReceipt[]) => Promise<SyncResponse>;
  onSynchronized?: () => void | Promise<void>;
  autoDownload?: boolean;
}) {
  const scope = resourceScope.startsWith("staff:") ? offlineAccountScope(resourceScope) : resourceScope;
  const [state, setState] = useState<OfflineCheckInState | null>(null);
  const [resolved, setResolved] = useState<OfflineRosterRegistration | null>(null);
  const [printing, setPrinting] = useState<OfflineRosterRegistration | null>(null);
  const station = resourceScope.startsWith("station:");
  const receipts = usePrintReceipts<{ registration_id: number; method: "offline" | "station"; stock?: string; role?: string }>({
    queue: async (receipt) => setState(await queueBadgeReceipt(scope, receipt as BadgeReceipt)) });
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [autoAttempted, setAutoAttempted] = useState(false);
  const resolvedRef = useRef<HTMLDivElement>(null);
  const workbenchRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (resolved) resolvedRef.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" }); }, [resolved]);
  useEffect(() => { if (scanning) workbenchRef.current?.scrollIntoView?.({ block: "start", behavior: "smooth" }); }, [scanning]);

  const refresh = useCallback(async () => {
    await pruneExpiredOfflineStates();
    setState(await loadOfflineState(scope));
  }, [scope]);

  const downloadNow = useCallback(async () => {
    setBusy(true); setError(null);
    try { setState(await saveOfflineRoster(scope, await download())); }
    catch (cause) {
      if (cause instanceof StructuredApiError && [400, 403, 410].includes(cause.status)) {
        await wipeOfflineState(scope); setState(null);
      }
      setError(cause instanceof Error ? cause.message : t`Could not download roster.`);
    }
    finally { setBusy(false); }
  }, [download, scope]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const visibility = () => { if (!document.hidden) void refresh(); };
    const connection = () => setOnline(navigator.onLine);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("online", connection);
    window.addEventListener("offline", connection);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("online", connection);
      window.removeEventListener("offline", connection);
    };
  }, [refresh]);
  useEffect(() => {
    if (autoDownload && !state && !busy && !autoAttempted) {
      setAutoAttempted(true);
      void downloadNow();
    }
  }, [autoAttempted, autoDownload, busy, downloadNow, state]);

  function handleScan(value: string) {
    setScanning(false); setError(null);
    if (!state || Date.now() > Date.parse(state.roster.expires_at)) {
      setError(t`The offline roster expired. Download it again.`); return;
    }
    const match = state.roster.registrations.find(
      (row) => row.checkin_token.toLowerCase() === value.trim().toLowerCase(),
    );
    if (!match) { setError(t`That is not a check-in code for this event.`); return; }
    setResolved(match);
  }

  async function confirm() {
    if (!resolved || !state) return;
    const now = new Date();
    if (now > new Date(state.roster.scan_closes_at)) {
      setError(t`The event check-in window has closed.`); return;
    }
    const operation: QueuedCheckIn = {
      operation_id: crypto.randomUUID(),
      checkin_token: resolved.checkin_token,
      reported_occurred_at: now.toISOString(),
    };
    try {
      setState(await queueOfflineCheckIn(scope, operation));
      // The roster carries the badge and the designs when the badge desk is on: print offline.
      if (resolved.badge && state.roster.badges) setPrinting(resolved);
      setResolved(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t`Could not queue attendance.`);
    }
  }

  async function syncNow() {
    const queuedReceipts = state?.badgeReceipts ?? [];
    if (!state || (!state.operations.length && !queuedReceipts.length)) return;
    setBusy(true); setError(null);
    try {
      const response = await synchronize(state.roster, state.operations, queuedReceipts);
      setState(await applySyncResults(scope, response.results, response.recorded_at, queuedReceipts));
      await onSynchronized?.();
    } catch (cause) {
      if (cause instanceof StructuredApiError && [400, 403, 410].includes(cause.status)) {
        await wipeOfflineState(scope); setState(null);
      }
      setError(cause instanceof Error ? cause.message : t`Could not synchronize check-ins.`);
    } finally { setBusy(false); }
  }

  async function wipe() {
    await wipeOfflineState(scope);
    setState(null); setResolved(null); setScanning(false); setError(null);
  }

  return <section className="mt-3 rounded-lg border border-line bg-panel p-3" aria-labelledby={`${scope}-offline-title`}>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><h4 id={`${scope}-offline-title`} className="font-semibold text-ink">{t`Offline-ready check-in`}</h4><p className="text-xs text-muted">{online ? t`Online · attendee names are encrypted on this device.` : t`Offline · attendee names are encrypted on this device.`}</p></div>
      <button type="button" className={`desk-button ${FOCUS}`} disabled={busy} onClick={downloadNow}>{state ? t`Refresh roster` : t`Download roster`}</button>
    </div>
    {state ? <div className="mt-3 grid gap-2 text-sm">
      <RosterStatus expiresAt={state.roster.expires_at} queued={state.operations.length} lastSyncedAt={state.lastSyncedAt} />
      <p className="text-xs text-muted">{t`Keep this page open while disconnected. Closing or reloading cannot reopen it offline in this release.`}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={`desk-button-primary ${FOCUS}`} onClick={() => setScanning(true)}>{t`Scan offline`}</button>
        <button type="button" className={`desk-button ${FOCUS}`} disabled={!online || busy || !(state.operations.length || state.badgeReceipts?.length)} onClick={syncNow}>{t`Synchronize`}</button>
      </div>
      <p aria-live="polite" className="sr-only">{state.operations.length} queued check-ins. {state.conflicts.length} conflicts.</p>
      {state.conflicts.length ? <div role="alert" className="rounded-md border border-warn bg-warn-soft p-2 text-warn-ink"><strong>{t`${state.conflicts.length} synchronization conflicts`}</strong><ul className="mt-1 list-disc pl-5">{state.conflicts.map((item) => <li key={item.operation_id}>{offlineSyncOutcomeLabel(item.outcome)}</li>)}</ul></div> : null}
    </div> : <p className="mt-3 text-sm text-muted">{t`No attendee data is stored on this device.`}</p>}
    {/* The guest is standing at the door: name large, Confirm full-width on a phone, and the card
        scrolled into view because the scan happens further down the page. */}
    {resolved ? <div ref={resolvedRef} className="mt-3 scroll-mb-[calc(var(--shell-bottom-tabs,0px)+env(safe-area-inset-bottom)+1rem)] rounded-md border border-line p-3"><p className="break-words text-lg font-semibold text-ink">{resolved.name}</p><p className="text-sm text-muted">{t`Waiver: ${waiverStateLabel(resolved.host_waiver_state)}`}</p><div className="mt-3 grid gap-2 sm:flex sm:flex-wrap"><button className={`desk-button-primary min-h-12 ${FOCUS}`} type="button" onClick={confirm}>{t`Confirm attendance`}</button><button className={`desk-button ${FOCUS}`} type="button" onClick={() => setResolved(null)}>{t`Cancel`}</button></div></div> : null}
    {printing?.badge && state?.roster.badges ? <DeskPrintSheet badge={printing.badge} bundle={state.roster.badges} onSkip={() => setPrinting(null)}
      onPrinted={(info) => receipts.record({ registration_id: printing.registration_id, method: station ? "station" : "offline", ...info })} /> : null}
    {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}
    {scanning ? <div ref={workbenchRef} className="mt-3"><ScanWorkbench onFind={handleScan} onScan={handleScan} searchLabel="Find an offline check-in code" controls={<button className="desk-button" type="button" onClick={() => setScanning(false)}>{t`Done`}</button>} /></div> : null}
    {state ? <DangerZone title={t`Remove offline attendee data`} consequence="The roster and unsynchronized attendance on this device will be removed." action={{ label: t`Wipe attendee data`, onClick: wipe, confirm: { title: t`Wipe attendee data from this device?`, message: t`The roster and any check-ins not yet synced are removed from this device. This can't be undone.` } }} /> : null}
  </section>;
}

/** Roster expiry, queued count (bold) and last sync, each as one whole message. */
function RosterStatus({ expiresAt, queued, lastSyncedAt }: { expiresAt: string; queued: number; lastSyncedAt: string | null }) {
  const expires = new Date(expiresAt).toLocaleString(formatLocale());
  if (!lastSyncedAt) return <p className="text-muted"><Trans>Expires {expires} · <strong className="text-ink">{queued}</strong> queued · Last sync never</Trans></p>;
  const lastSync = new Date(lastSyncedAt).toLocaleString(formatLocale());
  return <p className="text-muted"><Trans>Expires {expires} · <strong className="text-ink">{queued}</strong> queued · Last sync {lastSync}</Trans></p>;
}
