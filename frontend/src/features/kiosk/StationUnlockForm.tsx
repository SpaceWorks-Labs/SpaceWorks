import { KioskPin } from "../../components/layouts/KioskPin";

/** Compatibility wrapper for callers that only need the station unlock form. */
export function StationUnlockForm({ helper, pending, error, disabledReason, onSubmit }: {
  helper: string; pending: boolean; error?: string; disabledReason?: string; onSubmit: (pin: string) => void;
}) {
  return <KioskPin title="Enter the station PIN" helper={helper} pending={pending} error={error}
    disabledReason={disabledReason} onSubmit={onSubmit} submitLabel="Unlock station" pendingLabel="Unlocking…" />;
}
