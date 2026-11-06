import { t } from "@lingui/core/macro";
import { ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import type { Transfer } from "./StockTransferPanel";
export function TransferTable({ transfers, makerspaceNames, sourceContainerNames, destinationContainerNames }: {
 transfers: Transfer[]; makerspaceNames: Map<number, string>; sourceContainerNames: Map<number, string>; destinationContainerNames: Map<number, string>;
}) {
 return <div className="grid gap-3">{transfers.map(transfer => <ListRow key={transfer.id}
   title={t`${transfer.lines.reduce((sum, line) => sum + line.quantity, 0)} units transferred`}
   identity={{ kind: "icon", icon: "ArrowRight", tone: "accent" }}
   meta={<>#{transfer.id} · {transfer.lines.length === 1 ? t`1 line` : `${transfer.lines.length} lines`} · {endpointLabel(transfer.source_makerspace ?? transfer.makerspace, transfer.source_container, makerspaceNames, sourceContainerNames)} → {endpointLabel(transfer.destination_makerspace ?? transfer.makerspace, transfer.destination_container, makerspaceNames, destinationContainerNames)} · {transfer.reason}</>}
   right={<div className="grid justify-items-end gap-2"><RelativeTime date={transfer.created_at} exact /><StatusPill label={transfer.status.replace(/_/g, " ")} /></div>} />)}</div>;
}
function endpointLabel(spaceId: number, containerId: number | null, spaceNames: Map<number, string>, containerNames: Map<number, string>) {
 const space = spaceNames.get(spaceId) ?? `Makerspace ${spaceId}`;
 return containerId ? `${space} / ${containerNames.get(containerId) ?? `Container ${containerId}`}` : space;
}
