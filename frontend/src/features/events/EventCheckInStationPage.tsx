import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { KioskLayout } from "../../components/layouts";
import { useStationConnection } from "../kiosk/useStationConnection";
import {
  downloadStationRoster,
  fetchStationBadge,
  endStationSession,
  startStationSession,
  syncStationRoster,
} from "../staff/eventCheckInOfflineApi";
import { loadOfflineState, wipeOfflineState } from "../staff/eventCheckInOfflineStore";
import { OfflineCheckInOperator } from "../staff/OfflineCheckInOperator";

export function EventCheckInStationPage() {
  const { stationToken = "" } = useParams();
  const scope = `station:${stationToken}`;
  const online = useStationConnection();
  const [active, setActive] = useState(false);
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(pin: string) { setPending(true); setError(null);
    try { await startStationSession(stationToken, pin); setActive(true); }
    catch { setError(t`The station credential is invalid or outside its event window.`); }
    finally { setPending(false); }
  }

  async function exit() {
    try {
      await wipeOfflineState(scope);
      try { await endStationSession(stationToken); } catch { /* cookie still expires server-bound */ }
      setActive(false); setPendingCount(null);
    } catch { setPendingCount(null); setError(t`Couldn't wipe local check-ins. Keep this station open and try again.`); }
  }

  async function requestExit() {
    try {
      const stored = await loadOfflineState(scope);
      if (stored?.operations.length) setPendingCount(stored.operations.length);
      else await exit();
    } catch { setError(t`Couldn't read local check-ins. Keep this station open and try again.`); }
  }

  return <KioskLayout context={{ title: active ? t`Event check-in station` : t`Enter the station PIN`, subtitle: t`Door check-in · Station` }}
    connection={{ online }} state={{ status: "ready" }} mode={active ? "work" : "lock"}
    lock={{ title: t`Enter the station PIN`, helper: t`Ask an organiser for the 8-digit PIN. It unlocks check-in on this device only.`,
      pending, error: error ?? undefined, disabledReason: !online ? "Reconnect to unlock this station." : undefined,
      submitLabel: t`Unlock station`, pendingLabel: "Unlocking…", onSubmit: pin => { void submit(pin); } }}
    headerActions={active ? [{ label: t`Lock station`, onClick: () => { void requestExit(); } }] : []}
    confirmLock={pendingCount !== null ? { pendingCount, title: t`Discard check-ins and lock?`,
      consequence: `${pendingCount} unsynced check-ins will be permanently removed from this device before they reach the server.`, onDiscard: () => { void exit(); }, onKeep: () => setPendingCount(null) } : undefined}
    work={{ capture: <OfflineCheckInOperator scope={scope} autoDownload fetchBadge={(registrationId) => fetchStationBadge(stationToken, registrationId)} download={() => downloadStationRoster(stationToken)} synchronize={(roster, operations, receipts) => syncStationRoster(stationToken, roster, operations, receipts)} />,
      panel: <div className="rounded-xl border border-line bg-panel p-6"><h2 className="title-panel">{t`Welcome them in`}</h2>{active && error ? <p role="alert" className="mt-3 text-danger">{error}</p> : null}<p className="mt-3 text-muted">{t`Find a guest by name, email or ticket code. Check-ins saved on this device sync when you reconnect.`}</p></div> }} />;
}
