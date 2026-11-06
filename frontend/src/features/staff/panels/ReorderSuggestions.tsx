import { t } from "@lingui/core/macro";
import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { Callout, ErrorText, ListRow, Pagination } from "../../../components/ui";
import type { CalloutProps } from "../../../components/ui";
import { DetailLayout } from "../../../components/layouts";
import { inventoryQueryState } from "./inventoryPresentation";

type Suggestion = { id: number; name: string; available_quantity: number; reorder_point: number; reorder_quantity: number; supplier: string; sku: string };

/** Split into a callout and its drawer so the list can show the callout above an empty or filtered-empty table. */
export function useReorderSuggestions({ makerspaceId, canProcure }: { makerspaceId: number; canProcure: boolean }): { callout?: CalloutProps; error: ReactNode; panel: ReactNode } {
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => { setPage(1); setOpen(false); setMessage(""); }, [makerspaceId]);
  const client = useQueryClient();
  const suggestions = useQuery({ queryKey: ["reorder-suggestions", makerspaceId, page],
    queryFn: () => staffRequest<{ count: number; results: Suggestion[] }>(`/admin/makerspace/${makerspaceId}/inventory/reorder-suggestions?page=${page}`) });
  const create = useMutation({ mutationFn: (productId: number) => staffRequest<{ id: number }>(
    `/admin/makerspace/${makerspaceId}/inventory/reorder-draft`, { method: "POST", body: JSON.stringify({ product_id: productId }) }),
    onSuccess: (result) => { setMessage(t`Procurement draft #${result.id} is ready in To Buy.`);
      client.invalidateQueries({ queryKey: ["procurement", makerspaceId] }); },
  });
  const count = suggestions.data?.count ?? 0;
  const callout: CalloutProps | undefined = count ? { size: "banner", tone: "warn", lead: `${count} ${count === 1 ? "item is" : "items are"} running low.`,
    body: t`Review their reorder points before your next project.`, action: { label: t`Review suggestions`, onClick: () => setOpen(true) } } : undefined;
  const error = suggestions.error ? <ErrorText resource="reorder suggestions" onRetry={() => { void suggestions.refetch(); }} message={t`Couldn't load reorder suggestions. Try again.`} /> : null;
  const panel = open ? <DetailLayout presentation="drawer" open onClose={() => setOpen(false)} title={t`Reorder suggestions`}
      state={inventoryQueryState(suggestions, "reorder suggestions")} isEmpty={!suggestions.data?.results.length}
      empty={{ message: t`No products are at their reorder points. Check back as stock changes.` }}
      main={<div className="grid gap-3">{suggestions.data?.results.map(row => <ListRow key={row.id} title={row.name}
        meta={`${row.available_quantity} available · reorder at ${row.reorder_point}${row.supplier ? ` · ${row.supplier}` : ""}`}
        right={canProcure ? <button className="desk-button-ghost" disabled={create.isPending || row.reorder_quantity < 1} onClick={() => create.mutate(row.id)}>
          {create.isPending ? t`Drafting…` : t`Draft order for ${row.reorder_quantity}`}</button> : null} />)}
        <p role="status" className="text-sm text-muted">{message}</p><ErrorText message={create.error?.message} />
        <Pagination page={page} totalPages={Math.max(1, Math.ceil(count / 24))} count={count} pageSize={24} onChange={setPage} />
      </div>} /> : null;
  return { callout, error, panel };
}

/** Standalone rendering: the callout followed by its drawer. */
export function ReorderSuggestions(props: { makerspaceId: number; canProcure: boolean }) {
  const { callout, error, panel } = useReorderSuggestions(props);
  return <>{callout ? <Callout {...callout} /> : null}{error}{panel}</>;
}
