import type { Key } from "react";

import { Badge, DataTable, OverflowMenu, RelativeTime, type DataTableColumn } from "../../../../components/ui";
import type { CardStatus, MemberCard } from "./types";

export function CardsTable({
  cards,
  status,
  loading,
  selectedIds,
  onSelectionChange,
  printingCardId,
  onPrint,
  onReissue,
  onRevoke,
  rowActions,
}: {
  cards: MemberCard[];
  status: CardStatus;
  loading: boolean;
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
  printingCardId: number | null;
  onPrint: (card: MemberCard) => void;
  onReissue: (card: MemberCard) => void;
  onRevoke: (card: MemberCard) => void;
  /** Card-engine actions for an active card (download, email, photo request). */
  rowActions?: (card: MemberCard) => { label: string; onClick: () => void; confirms?: boolean }[];
}) {
  const columns: DataTableColumn<MemberCard>[] = [
    {
      key: "card_number",
      header: "Card number",
      sortable: true,
      render: (card) => <span className="tabular-nums text-xs">{card.number_display || card.card_number}</span>,
    },
    { key: "printed_name", header: "Name", sortable: true },
    {
      key: "valid_until",
      header: "Valid until",
      render: (card) => <span className="text-xs text-muted">{card.valid_until || "—"}</span>,
    },
    {
      key: "is_active",
      header: "Status",
      render: (card) =>
        card.is_active ? (
          <Badge tone="success">Active</Badge>
        ) : (
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone="danger">Revoked</Badge>
            {card.revoked_reason ? (
              <span className="text-xs text-muted">{card.revoked_reason}</span>
            ) : null}
          </span>
        ),
    },
    {
      key: "print_count",
      header: "Prints",
      sortable: true,
      render: (card) => (
        <span className="text-xs text-muted">
          <span className="tabular-nums text-ink">{card.print_count}</span> · last{" "}
          {card.last_printed_at ? <RelativeTime date={card.last_printed_at} /> : "never"}
        </span>
      ),
    },
    {
      key: "photo_set",
      header: "Photo",
      render: (card) =>
        card.photo_request_open ? <Badge tone="warn">update asked</Badge>
          : card.photo_set ? <Badge tone="neutral">on file</Badge> : <span className="text-xs text-muted">none</span>,
    },
    {
      key: "actions",
      header: "Actions",
      render: (card) => (
        <div className="desk-actions flex flex-wrap gap-2">
          <button
            className="desk-button-ghost"
            type="button"
            disabled={printingCardId === card.id}
            onClick={() => onPrint(card)}
          >
            {printingCardId === card.id ? "Preparing…" : "Print"}
          </button>
          {card.is_active ? (
            <>
              <OverflowMenu label={"Actions for " + card.printed_name} actions={[
                ...(rowActions ? rowActions(card) : []),
                { label: "Reissue", confirms: true, onClick: () => onReissue(card) },
                { label: "Revoke", confirms: true, tone: "danger", onClick: () => onRevoke(card) },
              ]} />
            </>
          ) : null}
        </div>
      ),
    },
  ];

  // Selection only exists on the active list: the sheet endpoint prints active cards, so
  // offering checkboxes on revoked rows would build a selection the print refuses.
  const selection =
    status === "active"
      ? { selectedIds, onSelectionChange: (ids: Key[]) => onSelectionChange(ids.map(Number)) }
      : {};

  return (
    <DataTable
      columns={columns}
      data={cards}
      loading={loading}
      skeletonCols={7}
      emptyTitle={status === "active" ? "No active cards" : "No revoked cards"}
      emptyDescription={
        status === "active"
          ? "Issue a card from the Issue tab."
          : "Revoked cards stay listed here for the audit trail."
      }
      {...selection}
    />
  );
}
