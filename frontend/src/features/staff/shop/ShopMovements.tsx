import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { Modal } from "../../../components/ui";
import { listMovements, staffShopError, staffShopKeys } from "./staffShopApi";

const KIND = (): Record<string, string> => ({ restock: t`Restocked`, count: t`Shelf count`, damage: t`Damaged`, internal_use: t`Used in the space`,
  sale: t`Sold`, returned: t`Returned`, written_off: t`Written off` });

/** Every change to one variant's count, newest first, with who made it and why. */
export function ShopMovements({ makerspaceId, variantId, label, onClose }: { makerspaceId: number; variantId: number; label: string; onClose: () => void }) {
  const query = useQuery({ queryKey: staffShopKeys.movements(makerspaceId, variantId), queryFn: () => listMovements(makerspaceId, variantId) });
  const rows = query.data?.results ?? [];
  return <Modal open onClose={onClose} title={t`Stock history: ${label}`} size="xl"
    footer={<button type="button" className="desk-button min-h-11" onClick={onClose}>{t`Close`}</button>}>
    {query.isPending ? <p role="status" className="text-sm text-muted">{t`Loading history…`}</p>
      : query.error ? <p role="alert" className="text-sm text-danger">{staffShopError(query.error)}</p>
      : !rows.length ? <p className="text-sm text-muted">{t`No stock changes yet.`}</p>
      : <div className="overflow-x-auto"><table className="w-full min-w-[32rem] text-sm">
        <caption className="sr-only">{t`Stock history for ${label}`}</caption>
        <thead><tr className="border-b border-line text-left text-muted">
          <th scope="col" className="py-2 pr-3">{t`When`}</th><th scope="col" className="py-2 pr-3">{t`Change`}</th>
          <th scope="col" className="py-2 pr-3 text-right">{t`Quantity`}</th><th scope="col" className="py-2 pr-3 text-right">{t`After`}</th>
          <th scope="col" className="py-2">{t`By and why`}</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.id} className="border-b border-line align-top">
          <td className="py-2 pr-3">{new Date(row.created_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" })}</td>
          <td className="py-2 pr-3">{KIND()[row.kind] ?? row.kind}{row.order ? t` · order #${row.order}` : ""}</td>
          <td className="py-2 pr-3 text-right tabular-nums">{row.quantity > 0 ? `+${row.quantity}` : row.quantity}</td>
          <td className="py-2 pr-3 text-right tabular-nums">{row.balance_after}</td>
          <td className="py-2">{row.actor_name}{row.reason ? <span className="block text-muted">{row.reason}</span> : null}</td>
        </tr>)}</tbody>
      </table>{query.data && query.data.count > rows.length ? <p className="mt-2 text-sm text-muted">{t`Showing the latest ${rows.length} of ${query.data.count} changes.`}</p> : null}</div>}
  </Modal>;
}
