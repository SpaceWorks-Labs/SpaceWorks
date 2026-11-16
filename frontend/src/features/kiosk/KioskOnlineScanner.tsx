import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ScanWorkbench } from "../../components/ui";
import { runOnlineCommand, type KioskLease } from "./kioskApi";

// All QR lookup still goes through the station-scoped, lease-checked command.
export function KioskOnlineScanner({ token, lease }: { token: string; lease: KioskLease }) {
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const allowed = lease.permitted_operations.includes("resolve_qr");
  async function resolvePayload(value: string) {
    if (pending || !value.trim() || !lease.permitted_operations.includes("resolve_qr")) return;
    setPending(true);
    setError(null); setResult(null);
    try {
      const response = await runOnlineCommand<{ target: { label?: string; name?: string } }>(
        token, lease.lease_token, "resolve_qr", { payload: value.trim() },
      );
      setResult(response.result.target.label ?? response.result.target.name ?? "Resolved");

    } catch { setError(t`That QR code is not known here, or your lease no longer allows it.`); }
    finally { setPending(false); }
  }


  return <ScanWorkbench searchLabel="Scan or type a QR code" helper={t`Only labels available to this operator shift can be resolved.`}
    onFind={value => { void resolvePayload(value); }} onScan={value => { void resolvePayload(value); }} findPending={pending}
    state={allowed ? { status: "ready" } : { status: "error", error: t`Your operator shift doesn't allow QR lookup.` }}
    result={error ? { tone: "danger", title: t`Couldn't resolve this label`, summary: error, next: { label: t`Try another code`, onClick: () => setError(null) } }
      : result ? { tone: "success", title: result, summary: t`This label belongs to your station's makerspace.`, next: { label: t`Next`, onClick: () => setResult(null) } } : undefined} />;
}
