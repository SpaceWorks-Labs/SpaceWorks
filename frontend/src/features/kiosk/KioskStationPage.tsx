import { useCallback, useEffect, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { KioskLayout } from "../../components/layouts";
import { Callout } from "../../components/ui";
import { KioskOnlineHandover } from "./KioskOnlineHandover";
import { KioskOnlineScanner } from "./KioskOnlineScanner";
import {
  endKioskSession,
  startKioskSession,
  takeOperatorLease,
  type KioskBootstrap,
  type KioskLease,
} from "./kioskApi";
import { enterKioskMode, useIdleReset } from "./kioskSession";
import { useKioskQueue } from "./useKioskQueue";
import { KioskOfflineHandover } from "./KioskOfflineHandover";
import { KioskReplayCorrection } from "./KioskReplayCorrection";

// Only an online-obtained lease and selected package can survive an offline reload.
// Reset destroys encrypted local work; the cookie and human grant remain server-owned.
export function KioskStationPage() {
  const { slug, stationToken = "" } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const recoveryId = searchParams.get("recovery");
  const [session, setSession] = useState<KioskBootstrap | null>(() => {
    const opened = location.state?.kiosk as { token: string; session: KioskBootstrap } | undefined;
    return opened?.token === stationToken ? opened.session : null;
  });
  const [lease, setLease] = useState<KioskLease | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shiftPending, setShiftPending] = useState(false);
  const [pending, setPending] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [resetRequested, setResetRequested] = useState(false);
  const offline = useKioskQueue(stationToken, slug, recoveryId);
  const activeSession = session ?? offline.queue?.session ?? null;
  const activeLease = lease ?? offline.queue?.lease ?? null;
  const queueMode = Boolean(offline.queue && (!offline.online || offline.restored || continuing));
  const hasCommands = Boolean(offline.queue?.commands.length);
  // One account per person: the station runs in the operator's own (person) session.
  const contextReady = Boolean(slug) || Boolean(activeSession);

  useEffect(() => {
    if (offline.restored && !offline.queue) { setSession(null); setLease(null); }
  }, [offline.restored, offline.queue]);

  const lock = useCallback(async () => {
    await offline.reset();
    setSession(null); setLease(null);
    setContinuing(false); setResetRequested(false);
    try { await endKioskSession(stationToken); } catch { /* the signed cookie still expires */ }
  }, [stationToken, offline.reset]);
  const idle = useIdleReset(Boolean(activeSession), activeLease?.expires_at ?? activeSession?.session_expires_at, () => {
    // Idle never discards pending captures silently. Authority expiry is pruned by
    // the store; the UI requests an explicit destructive reset for unexpired work.
    if (hasCommands) setResetRequested(true);
    else void lock().catch(() => setError("Local reset failed. Close this kiosk and reconnect."));
  });

  async function unlock(pin: string) { setPending(true); setError(null);
    try { setSession(await startKioskSession(stationToken, pin, slug)); }
    catch { setError("The Station PIN is invalid or this kiosk is not enabled."); }
    finally { setPending(false); }
  }

  async function signIn() {
    if (shiftPending || !contextReady) return;
    setShiftPending(true); setError(null);
    try { setLease(await takeOperatorLease(stationToken)); }
    catch { setError("Sign in to the staff console with an account allowed to work this Station."); }
    finally { setShiftPending(false); }
  }

  const workPanel = !contextReady ? null : recoveryId && activeSession ? <KioskReplayCorrection key={`${stationToken}/${recoveryId}`} id={recoveryId} token={stationToken} session={activeSession} online={offline.online} onQueueChange={offline.setQueue} />
    : queueMode && offline.queue ? <KioskOfflineHandover queue={offline.queue}
      onChange={() => { void offline.refresh(); }} retry={() => { void offline.retry(); }}
      acknowledge={() => { void lock().catch(() => setError("Local reset failed.")); }} />
    : activeSession && activeLease ? <div className="grid gap-5">
      {activeSession.station.kind === "handover" && offline.online && !hasCommands ? <KioskOnlineHandover token={stationToken} lease={activeLease} makerspaceId={activeSession.makerspace.id}
        onWorkLoaded={work => offline.save(activeSession, activeLease, work)} /> : null}
      {!offline.online ? <p role="status">Reconnect to unlock and load this handover</p> : null}
      {offline.queue ? <button type="button" className="desk-button" onClick={() => setContinuing(true)}>Continue with encrypted queue</button> : null}
    </div> : null;
  return <KioskLayout context={{ title: activeSession?.station.name ?? "Enter the station PIN",
    subtitle: activeSession ? `${activeSession.makerspace.name} · ${activeSession.station.kind} station` : "Enter the station PIN to begin a handover." }}
    connection={{ online: offline.online, queued: offline.queue?.commands.filter(command => command.status !== "succeeded").length }}
    idleCountdown={idle.seconds !== null && !hasCommands ? { seconds: idle.seconds, onKeep: idle.onKeep } : undefined}
    state={activeSession && !activeLease && !recoveryId && error ? { status: "error", error, onRetry: () => { void signIn(); } } : { status: "ready" }}
    mode={!activeSession && offline.online ? "lock" : activeSession && !activeLease && !recoveryId ? "ready" : "work"}
    lock={{ title: "Enter the station PIN", helper: "Ask a manager for the 8-digit PIN. It unlocks this device only.",
      pending, error: error ?? undefined, submitLabel: "Unlock station", pendingLabel: "Unlocking…", onSubmit: pin => { void unlock(pin); } }}
    ready={{ primary: { label: "Start operator shift", pending: shiftPending, pendingLabel: "Starting…", onClick: () => { void signIn(); }, disabled: !offline.online || !contextReady,
      disabledReason: !offline.online ? "Reconnect before starting an operator shift." : !contextReady ? "Preparing the tenant staff workspace." : undefined } }}
    headerActions={activeSession ? [{ label: "Full screen", onClick: () => { void enterKioskMode(); } },
      { label: "Lock station", onClick: () => { if (hasCommands) setResetRequested(true); else void lock().catch(() => setError("Local reset failed.")); } }] : []}
    work={{ capture: !activeSession ? <Callout size="panel" tone="warn" lead="Reconnect to unlock and load this handover" /> : offline.online && activeLease && !hasCommands && !queueMode && !recoveryId ? <KioskOnlineScanner token={stationToken} lease={activeLease} /> : <div className="rounded-xl border border-dashed border-outline p-8"><p className="title-panel">{offline.online ? "Your handover workspace" : "Keep working offline"}</p><p className="mt-3 text-muted">Loaded handovers stay encrypted on this device until the server confirms them.</p></div>,
      panel: <div className="grid gap-5">{!activeSession ? <p className="text-muted">The station PIN unlocks this device. An operator must then sign in before handling hardware.</p> : workPanel}{activeSession && error ? <Callout size="inline" tone="danger" lead={error} /> : null}
        {offline.storageError ? <p role="status" className="text-muted">{offline.storageError}</p> : null}</div> }}
    confirmLock={resetRequested ? { pendingCount: offline.queue?.commands.length ?? 0, title: "Discard handovers and lock?",
      consequence: "Queued handovers and their photos will be permanently removed from this device before they reach the server.",
      onDiscard: () => { void lock().catch(() => setError("Local reset failed.")); }, onKeep: () => setResetRequested(false) } : undefined} />;
}
