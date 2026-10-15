import { useState } from "react";
import { useParams } from "react-router-dom";

import { StationUnlockForm } from "../kiosk/StationUnlockForm";
import { KioskLayout } from "../../components/layouts";
import { useStationConnection } from "../kiosk/useStationConnection";
import {
  downloadStationRoster,
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
    catch { setError("The station credential is invalid or outside its event window."); }
    finally { setPending(false); }
  }

  async function exit() {
    try {
      await wipeOfflineState(scope);
      try { await endStationSession(stationToken); } catch { /* cookie still expires server-bound */ }
      setActive(false); setPendingCount(null);
    } catch { setPendingCount(null); setError("Couldn't wipe local check-ins. Keep this station open and try again."); }
  }

  async function requestExit() {
    try {
      const stored = await loadOfflineState(scope);
      if (stored?.operations.length) setPendingCount(stored.operations.length);
      else await exit();
    } catch { setError("Couldn't read local check-ins. Keep this station open and try again."); }
  }

  return <KioskLayout context={{ title: active ? "Event check-in station" : "Enter the station PIN", subtitle: "Door check-in · Station" }}
    connection={{ online }} state={{ status: "ready" }} mode="work"
    headerActions={active ? [{ label: "Lock station", onClick: () => { void requestExit(); } }] : []}
    confirmLock={pendingCount !== null ? { pendingCount, onDiscard: () => { void exit(); }, onKeep: () => setPendingCount(null) } : undefined}
    work={{ capture: !active ? <StationUnlockForm helper="Ask an organiser for the 8-digit PIN. It unlocks check-in on this device only." pending={pending} error={error ?? undefined} disabledReason={!online ? "Reconnect to unlock this station." : undefined} onSubmit={pin => { void submit(pin); }} /> : <OfflineCheckInOperator scope={scope} autoDownload download={() => downloadStationRoster(stationToken)} synchronize={(roster, operations) => syncStationRoster(stationToken, roster, operations)} />,
      panel: <div className="rounded-xl border border-line bg-panel p-6"><h2 className="title-panel">Welcome them in</h2>{active && error ? <p role="alert" className="mt-3 text-danger">{error}</p> : null}<p className="mt-3 text-muted">Find a guest by name, email or ticket code. Check-ins saved on this device sync when you reconnect.</p></div> }} />;
}
