import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Smartphone } from "lucide-react";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { ConfirmDialog, EmptyState, ErrorText, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { forgetKnownDevice, listKnownDevices, type KnownDevice } from "./knownDevicesApi";
import { invalidateAccountSecurity, knownDevicesKey } from "./securityQueries";

/**
 * Devices that passed the unusual-sign-in check (S-B). Forgetting one means its next sign-in
 * asks for the extra check again; it does not sign that device out.
 */
export function KnownDevicesList() {
  const client = useQueryClient();
  const [forgetting, setForgetting] = useState<KnownDevice>();
  const [notice, setNotice] = useState("");
  const query = useQuery({ queryKey: knownDevicesKey, queryFn: listKnownDevices, retry: false });
  const forget = useMutation({ mutationFn: (id: number) => forgetKnownDevice(id), onSuccess: () => {
    setForgetting(undefined);
    setNotice("Device forgotten. Its next sign-in will ask for the extra check.");
    void invalidateAccountSecurity(client);
  } });
  if (query.isLoading) return <p role="status" className="text-sm text-muted">Loading devices…</p>;
  if (query.error) return <ErrorText message={authErrorMessage(query.error, "Couldn't load your devices. Try again.")} onRetry={() => void query.refetch()} />;
  const devices = query.data?.devices ?? [];
  const days = query.data?.remembered_days;
  const label = (device: KnownDevice) => device.label || "Unknown device";
  return <div className="grid gap-4">
    <p className="text-sm text-muted">After a sign-in passes the extra check, we remember that browser so it isn't asked every time{days ? ` (for ${days} ${days === 1 ? "day" : "days"} after its last sign-in)` : ""}. A remembered device never skips two-step sign-in. Forget any you don't recognise.</p>
    {devices.length ? <ul className="grid gap-3">{devices.map(device => <li key={device.id}><ListRow title={label(device)}
      identityContent={<span aria-hidden="true" className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-line bg-surface text-accent-ink"><Smartphone size={20} /></span>}
      meta={<>Last checked <RelativeTime date={device.last_verified_at} /></>}
      right={<div className="flex flex-wrap items-center gap-2">
        {device.current ? <StatusPill tone="info" label="This device" /> : null}
        <button type="button" className="desk-button min-h-11" disabled={forget.isPending} aria-label={`Forget ${label(device)}`}
          onClick={() => setForgetting(device)}>Forget</button>
      </div>} /></li>)}</ul>
      : <EmptyState message="No remembered devices yet." />}
    <p role="status" className="text-sm text-ink empty:hidden">{notice}</p>
    {forget.error ? <ErrorText message={authErrorMessage(forget.error, "Couldn't forget that device. Try again.")} /> : null}
    <ConfirmDialog open={Boolean(forgetting)} title="Forget this device?" confirmLabel="Forget device" pending={forget.isPending}
      message={`${forgetting ? label(forgetting) : "This device"} will need the extra check at its next sign-in. It stays signed in until then.`}
      onCancel={() => setForgetting(undefined)} onConfirm={() => { if (forgetting) forget.mutate(forgetting.id); }} />
  </div>;
}
