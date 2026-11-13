import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, DangerZone, SettingsRow, SettingsSection, SettingsActions } from "../../../components/ui";
import { devicesApi, type Device, type DeviceKind, type EnrollmentGrant } from "../devicesApi";
import { deviceQueryKeys } from "../deviceQueryKeys";

export function DeviceCreateForm({ makerspaceId, onGrant }: {
  makerspaceId: number; onGrant: (grant: EnrollmentGrant) => void;
}) {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<DeviceKind>("generic");
  const create = useMutation({
    // Return void: TanStack must never retain bearer material as mutation data.
    mutationFn: async () => {
      const response = await devicesApi.create(makerspaceId, { name, kind, offline_threshold_seconds: 300 });
      onGrant(response.enrollment);
    },
    onSuccess: () => {
      setName("");
      void client.invalidateQueries({ queryKey: deviceQueryKeys.root(makerspaceId) });
    },
  });
  return <form id="device-create-form" className="grid gap-4" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
    <label>{t`Device name`}<input className="desk-input block" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} /></label>
    <label>{t`Device kind`}<select className="desk-input block" value={kind} onChange={(e) => setKind(e.target.value as DeviceKind)}>
      <option value="generic">{t`Generic`}</option><option value="printer">{t`Printer`}</option><option value="label_printer">{t`Label printer`}</option>
    </select></label>
    <button hidden disabled={create.isPending || !name.trim()}>{t`Create device`}</button>
    {create.isPending ? <p role="status">{t`Creating device...`}</p> : null}
    {create.error ? <p role="alert">{t`Could not create device. Please retry.`}</p> : null}
  </form>;
}

export function DeviceIdentitySection({ device, onGrant }: { device: Device; onGrant: (grant: EnrollmentGrant) => void }) {
  const client = useQueryClient();
  const [name, setName] = useState(device.name);
  const [threshold, setThreshold] = useState(device.offline_threshold_seconds);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const action = useMutation({
    mutationFn: async (operation: "save" | "enrollment" | "revoke") => {
      if (operation === "enrollment") onGrant(await devicesApi.enrollment(device.id));
      else if (operation === "revoke") await devicesApi.revoke(device.id);
      else await devicesApi.update(device.id, { name, offline_threshold_seconds: threshold });
      // Enrollment response is consumed only by local state, never returned to TanStack.
    },
    onSuccess: () => {
      setConfirmRevoke(false);
      void client.invalidateQueries({ queryKey: deviceQueryKeys.root(device.makerspace) });
    },
  });
  const dirty = name !== device.name || threshold !== device.offline_threshold_seconds;
  return <section aria-label={t`Identity for ${device.name}`}>
    <SettingsSection title={t`Device identity`} description={t`Fingerprint: ${device.key_fingerprint ? `${device.key_fingerprint.slice(0, 12)}…` : "Not enrolled"} · Key version ${device.key_version}`}>
      <form onSubmit={e => { e.preventDefault(); action.mutate("save"); }}>
        <SettingsRow label={t`Name`} htmlFor="device-name"><input id="device-name" className="desk-input w-full" required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></SettingsRow>
        <SettingsRow label={t`Offline threshold (seconds)`} htmlFor="device-threshold" helper={t`Space Works marks the device offline when a heartbeat is late by this amount.`}>
          <input id="device-threshold" className="desk-input w-full" required type="number" min={1} max={604800} value={threshold} onChange={e => setThreshold(Number(e.target.value))} />
        </SettingsRow>
        {dirty || action.isPending ? <SettingsActions onDiscard={() => { setName(device.name); setThreshold(device.offline_threshold_seconds); }} pending={action.isPending} /> : null}
      </form>
      <SettingsRow label={t`Enrollment`} helper={t`A new enrollment replaces the device key. Copy the one-time token before closing it.`}>
        <button className="desk-button" disabled={action.isPending} onClick={() => action.mutate("enrollment")}>
          {device.status === "active" ? t`Rotate key` : device.status === "revoked" ? t`Reactivate device` : t`Issue enrollment`}
        </button>
      </SettingsRow>
    </SettingsSection>
    <p role="status">{action.isPending ? t`Saving…` : action.isSuccess ? t`Device updated.` : ""}</p>
    {action.error ? <p role="alert">{t`Device change failed. Please retry.`}</p> : null}
    <DangerZone title={t`Revoke device`} consequence="Stops signed requests immediately. Enroll the device again to reactivate it."
      action={{ label: t`Revoke device`, disabled: action.isPending || device.status === "revoked", disabledReason: device.status === "revoked" ? t`This device is already revoked.` : t`Wait for the current change to finish.`, onClick: () => setConfirmRevoke(true) }} />
    <ConfirmDialog open={confirmRevoke} onCancel={() => setConfirmRevoke(false)} title={t`Revoke device`}
      onConfirm={() => action.mutate("revoke")} pending={action.isPending} tone="danger"
      message={t`This immediately stops signed requests from this device. Re-enrollment is required to activate it again.`} />
  </section>;
}
