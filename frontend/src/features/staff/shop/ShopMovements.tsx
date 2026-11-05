import { useQuery } from "@tanstack/react-query";

import { Modal } from "../../../components/ui";
import { listMovements, staffShopError, staffShopKeys } from "./staffShopApi";

const KIND: Record<string, string> = { restock: "Restocked", count: "Shelf count", damage: "Damaged", internal_use: "Used in the space",
  sale: "Sold", returned: "Returned", written_off: "Written off" };

/** Every change to one variant's count, newest first, with who made it and why. */
export function ShopMovements({ makerspaceId, variantId, label, onClose }: { makerspaceId: number; variantId: number; label: string; onClose: () => void }) {
  const query = useQuery({ queryKey: staffShopKeys.movements(makerspaceId, variantId), queryFn: () => listMovements(makerspaceId, variantId) });
  const rows = query.data?.results ?? [];
  return <Modal open onClose={onClose} title={`Stock history: ${label}`} size="xl"
    footer={<button type="button" className="desk-button min-h-11" onClick={onClose}>Close</button>}>
    {query.isPending ? <p role="status" className="text-sm text-muted">Loading history…</p>
      : query.error ? <p role="alert" className="text-sm text-danger">{staffShopError(query.error)}</p>
      : !rows.length ? <p className="text-sm text-muted">No stock changes yet.</p>
      : <div className="overflow-x-auto"><table className="w-full min-w-[32rem] text-sm">
        <caption className="sr-only">Stock history for {label}</caption>
        <thead><tr className="border-b border-line text-left text-muted">
          <th scope="col" className="py-2 pr-3">When</th><th scope="col" className="py-2 pr-3">Change</th>
          <th scope="col" className="py-2 pr-3 text-right">Quantity</th><th scope="col" className="py-2 pr-3 text-right">After</th>
          <th scope="col" className="py-2">By and why</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.id} className="border-b border-line align-top">
          <td className="py-2 pr-3">{new Date(row.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</td>
          <td className="py-2 pr-3">{KIND[row.kind] ?? row.kind}{row.order ? ` · order #${row.order}` : ""}</td>
          <td className="py-2 pr-3 text-right tabular-nums">{row.quantity > 0 ? `+${row.quantity}` : row.quantity}</td>
          <td className="py-2 pr-3 text-right tabular-nums">{row.balance_after}</td>
          <td className="py-2">{row.actor_name}{row.reason ? <span className="block text-muted">{row.reason}</span> : null}</td>
        </tr>)}</tbody>
      </table>{query.data && query.data.count > rows.length ? <p className="mt-2 text-sm text-muted">Showing the latest {rows.length} of {query.data.count} changes.</p> : null}</div>}
  </Modal>;
}
