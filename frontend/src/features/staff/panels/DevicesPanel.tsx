import { t } from "@lingui/core/macro";
import { machineStatusLabel } from "./machine/machineStatusLabel";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { devicesApi, type EnrollmentGrant } from "../devicesApi";
import { deviceQueryKeys } from "../deviceQueryKeys";
import { DeviceCreateForm, DeviceIdentitySection } from "./DeviceIdentitySection";
import { DeviceEnrollmentModal } from "./DeviceEnrollmentModal";
import { ListLayout, DetailLayout, FlowLayout } from "../../../components/layouts";
import { ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { opsQueryState } from "../opsPresentation";
import { deviceKindLabel } from "./operationsLabels";

export function DevicesPanel({ makerspaceId }: { makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [grant, setGrant] = useState<EnrollmentGrant | null>(null);
  const devices = useQuery({
    queryKey: deviceQueryKeys.list(makerspaceId, page),
    queryFn: () => devicesApi.list(makerspaceId, page),
    refetchInterval: 60_000,
  });
  const detail = useQuery({
    queryKey: deviceQueryKeys.detail(makerspaceId, selectedId ?? ""),
    queryFn: () => devicesApi.detail(selectedId!),
    enabled: selectedId !== null,
    refetchInterval: 60_000,
  });
  const rows = devices.data?.results ?? [];
  const isOnline = (device: typeof rows[number]) => device.status === "active" && !device.offline_since;
  return <ListLayout header={{ title: t`Devices`, subtitle: t`Printers and other hardware that talk to Space Works.`,
      primary: { label: t`Add device`, icon: "Plus", onClick: () => setCreating(true) } }}
      state={opsQueryState(devices, "devices")} isEmpty={rows.length === 0}
      empty={{ message: t`No devices yet. Add your first device.`, action: { label: t`Add device`, onClick: () => setCreating(true) } }}
      stats={[{ label: t`Online on this page`, value: rows.filter(isOnline).length },
        { label: t`Offline on this page`, value: rows.filter(device => device.status === "active" && !!device.offline_since).length },
        { label: t`Revoked on this page`, value: rows.filter(device => device.status === "revoked").length }]}
      body={{ kind: "rows", rows: rows.map(device => <ListRow key={device.id} title={device.name} onClick={() => setSelectedId(device.id)}
        identity={{ kind: "icon", icon: "Settings", tone: "accent" }}
        meta={<>{deviceKindLabel(device.kind)} · {device.last_seen_at ? <>{t`Last seen `}<RelativeTime date={device.last_seen_at} /></> : t`No heartbeat yet`}</>}
        right={<StatusPill label={device.status === "active" ? device.offline_since ? t`Offline` : t`Online` : machineStatusLabel(device.status)}
          tone={isOnline(device) ? "success" : device.status === "revoked" ? "danger" : "warn"} />} />) }}
      pagination={{ page, pageSize: 24, count: devices.data?.count ?? 0, onChange: next => { setSelectedId(null); setPage(next); } }}
      detail={<>
    {selectedId ? <DetailLayout presentation="drawer" open onClose={() => setSelectedId(null)} title={detail.data?.name ?? t`Device details`}
      state={opsQueryState(detail, "device details")} main={detail.data ? <DeviceIdentitySection key={`${detail.data.id}:${detail.data.name}:${detail.data.offline_threshold_seconds}`} device={detail.data} onGrant={setGrant} /> : null} /> : null}
    {creating ? <FlowLayout presentation="dialog" open title={t`Add device`} steps={[]} current="create" state={{ status: "ready" }}
      onCancel={() => setCreating(false)} work={<DeviceCreateForm makerspaceId={makerspaceId} onGrant={value => { setCreating(false); setGrant(value); }} />}
      footer={{ next: { label: t`Create device`, onClick: () => document.querySelector<HTMLFormElement>("#device-create-form")?.requestSubmit() } }} /> : null}
    {grant ? <DeviceEnrollmentModal key={grant.enrollment_id} grant={grant} onClose={() => setGrant(null)} /> : null}
      </>} />
;
}
