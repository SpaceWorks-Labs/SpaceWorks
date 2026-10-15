import { useState } from "react";

import { StatusPill as Badge, ListRow, OverflowMenu } from "../../../components/ui";
import { type NotificationDestination } from "../notificationDestinationTypes";
import { CHANNELS } from "./channels";
import { DestinationForm } from "./DestinationForm";
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

  return <ListRow title={destination.label} meta={<span className="flex flex-wrap items-center gap-2">
    <Badge label={destination.channel} />
    <Badge label={destination.credential_set ? "Configured" : "No credential"} tone={destination.credential_set ? "success" : "danger"} />
    {destination.is_active ? null : <Badge label="Paused" tone="warn" />}
    <span>{scopeCount === 0 ? "Everything" : `${scopeCount} scoped`}</span>
  </span>} right={<div className="flex gap-2">
    <button className="desk-button" onClick={() => setEditing(true)} type="button">Edit</button>
    <OverflowMenu label={`Actions for ${destination.label}`} actions={[{ label: "Remove", tone: "danger", onClick: onDelete,
      confirm: { title: "Remove room?", message: `Alerts stop reaching ${destination.label}. Its saved webhook URL is discarded and can't be shown again.`, confirmLabel: "Remove room" } }]} />
  </div>} />;
}
