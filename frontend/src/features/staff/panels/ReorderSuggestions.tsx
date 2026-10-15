import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { Callout, ErrorText, ListRow, Pagination } from "../../../components/ui";
import { DetailLayout } from "../../../components/layouts";
import { inventoryQueryState } from "./inventoryPresentation";

type Suggestion = { id: number; name: string; available_quantity: number; reorder_point: number; reorder_quantity: number; supplier: string; sku: string };

export function ReorderSuggestions({ makerspaceId, canProcure }: { makerspaceId: number; canProcure: boolean }) {
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  const suggestions = useQuery({ queryKey: ["reorder-suggestions", makerspaceId, page],
    queryFn: () => staffRequest<{ count: number; results: Suggestion[] }>(`/admin/makerspace/${makerspaceId}/inventory/reorder-suggestions?page=${page}`) });
  const create = useMutation({ mutationFn: (productId: number) => staffRequest<{ id: number }>(
    `/admin/makerspace/${makerspaceId}/inventory/reorder-draft`, { method: "POST", body: JSON.stringify({ product_id: productId }) }),
    onSuccess: (result) => { setMessage(`Procurement draft #${result.id} is ready in To Buy.`);
      client.invalidateQueries({ queryKey: ["procurement", makerspaceId] }); },
  });
  if (!open && suggestions.isSuccess && !suggestions.data.count) return null;
  return <>
    {suggestions.data?.count ? <div className="mb-6"><Callout size="banner" tone="warn" lead={`${suggestions.data.count} ${suggestions.data.count === 1 ? "item is" : "items are"} running low.`}
      body="Review their reorder points before your next project." action={{ label: "Review suggestions", onClick: () => setOpen(true) }} /></div> : null}
    {suggestions.error ? <ErrorText resource="reorder suggestions" onRetry={() => { void suggestions.refetch(); }} message="Couldn't load reorder suggestions. Try again." /> : null}
    <DetailLayout presentation="drawer" open={open} onClose={() => setOpen(false)} title="Reorder suggestions"
      state={inventoryQueryState(suggestions, "reorder suggestions")} isEmpty={!suggestions.data?.results.length}
      empty={{ message: "No products are at their reorder points. Check back as stock changes." }}
      main={<div className="grid gap-3">{suggestions.data?.results.map(row => <ListRow key={row.id} title={row.name}
        meta={`${row.available_quantity} available · reorder at ${row.reorder_point}${row.supplier ? ` · ${row.supplier}` : ""}`}
        right={canProcure ? <button className="desk-button-ghost" disabled={create.isPending || row.reorder_quantity < 1} onClick={() => create.mutate(row.id)}>
          {create.isPending ? "Drafting…" : `Draft order for ${row.reorder_quantity}`}</button> : null} />)}
        <p role="status" className="text-sm text-muted">{message}</p><ErrorText message={create.error?.message} />
        <Pagination page={page} totalPages={Math.max(1, Math.ceil((suggestions.data?.count ?? 0) / 24))} count={suggestions.data?.count ?? 0} pageSize={24} onChange={setPage} />
      </div>} />
  </>;
}
