import { t } from "@lingui/core/macro";
import { useState } from "react";

import { StatusPill as Badge, ListRow, OverflowMenu } from "../../../components/ui";
import { type NotificationDestination } from "../notificationDestinationTypes";
import { CHANNELS } from "./channels";
import { DestinationForm } from "./DestinationForm";
import { RotateSigningSecret } from "./RotateSigningSecret";
import { type ScopeOptions } from "./scopeOptions";

export function DestinationRow({
  basePath,
  destination,
  makerspaceId,
  onDelete,
  options,
}: {
  basePath: string;
  destination: NotificationDestination;
  makerspaceId: number;
  onDelete: () => void;
  options: ScopeOptions;
}) {
  const [editing, setEditing] = useState(false);
  const [rotating, setRotating] = useState(false);
  const scopeCount =
    destination.scope.machine_ids.length +
    destination.scope.machine_type_ids.length +
    destination.scope.category_ids.length;

  if (editing) {
    return (
      <DestinationForm
        basePath={basePath}
        channels={CHANNELS.filter((channel) => channel.key === destination.channel)}
        destination={destination}
        makerspaceId={makerspaceId}
        onDone={() => setEditing(false)}
        options={options}
      />
    );
  }

  // Parity A10: a signed webhook's secret is rotated here, never re-shown.
  const rotatable = destination.channel === "webhook";
  const row = <ListRow title={destination.label} meta={<span className="flex flex-wrap items-center gap-2">
    <Badge label={destination.channel} />
    <Badge label={destination.credential_set ? t`Configured` : t`No credential`} tone={destination.credential_set ? "success" : "danger"} />
    {destination.is_active ? null : <Badge label={t`Paused`} tone="warn" />}
    <span>{scopeCount === 0 ? t`Everything` : `${scopeCount} scoped`}</span>
  </span>} right={<div className="flex flex-wrap gap-2">
    <button className="desk-button" onClick={() => setEditing(true)} type="button">{t`Edit`}</button>
    <OverflowMenu label={t`Actions for ${destination.label}`} actions={[
      ...(rotatable ? [{ label: t`Rotate signing secret`, confirms: true, onClick: () => setRotating(true) }] : []),
      { label: t`Remove`, tone: "danger" as const, onClick: onDelete,
        confirm: { title: t`Remove room?`, message: t`Alerts stop reaching ${destination.label}. Its saved webhook URL is discarded and can't be shown again.`, confirmLabel: t`Remove room` } }]} />
  </div>} />;
  return rotating ? <div className="grid gap-2">{row}
    <RotateSigningSecret basePath={basePath} destination={destination} makerspaceId={makerspaceId} onClose={() => setRotating(false)} /></div> : row;
}
