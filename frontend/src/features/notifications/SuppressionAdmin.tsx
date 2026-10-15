import { ListLayout } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { ConfirmDialog, ErrorBlock, ListRow, Modal, Pagination, RelativeTime, StatusPill } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import type { Page } from "./PersonalInbox";
type Suppression = { id: number; address_hash: string; reason: string; created_at: string };

export function SuppressionAdmin({ makerspaceId, embedded = false, dialogOpen, onDialogClose }: { makerspaceId: number; embedded?: boolean; dialogOpen?: boolean; onDialogClose?: () => void }) {
  const [removing, setRemoving] = useState<number | null>(null);
  const client = useQueryClient();
  const [address, setAddress] = useState("");
  const [reason, setReason] = useState("bounce");
  const [page, setPage] = useState(1);
  const key = ["notification-suppressions", makerspaceId];
  const path = `/integrations/makerspace/${makerspaceId}/email-suppressions`;
  const rows = useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Page<Suppression>>(`${path}?page=${page}`) });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const add = useMutation({ mutationFn: () => staffRequest(path, { method: "POST", body: JSON.stringify({ address, reason }) }),
    onSuccess: () => { setAddress(""); onDialogClose?.(); refresh(); } });
  const remove = useMutation({ mutationFn: (id: number) => staffRequest(`${path}/${id}`, { method: "DELETE" }), onSuccess: refresh });
  const error = remove.error;
  const state = { status: rows.isLoading ? "loading" as const : rows.error ? "error" as const : "ready" as const,
    error: "Couldn't load suppressions. Try again.", onRetry: () => { void rows.refetch(); } };
  const form = (<>
    <form className="my-3 flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); add.mutate(); }}>
      <label className="grid gap-1 text-sm">Email address<input className="desk-input" type="email" maxLength={254} required value={address} onChange={(e) => setAddress(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">Reason<select className="desk-input" value={reason} onChange={(e) => setReason(e.target.value)}><option value="bounce">Hard bounce</option><option value="complaint">Spam complaint</option></select></label>
      <button className="desk-button-primary" disabled={add.isPending}>{add.isPending ? "Suppressing…" : "Suppress email"}</button>
      {add.error ? <ErrorBlock error={add.error} /> : null}
    </form>
  </>);
  const content = <div className="grid gap-4">
    <p className="text-sm text-muted">Suppress addresses after hard bounces or spam complaints. This stops all space mail, including queued retries. Addresses stay private as keyed hashes.</p>
    {dialogOpen === undefined ? form : null}

    {error && !rows.error ? <ErrorBlock error={error} /> : null}
    <QueryContent state={state} isEmpty={rows.data?.results.length === 0} empty={{ message: "No suppressed addresses. Bounced or blocked addresses appear here." }}>
      <div className="grid gap-3">{rows.data?.results.map(row => <ListRow key={row.id} title={row.reason === "bounce" ? "Hard bounce" : "Spam complaint"}
        meta={<span className="grid gap-1"><span className="break-all tabular-nums">{row.address_hash}</span><RelativeTime date={row.created_at} /></span>}
        right={<div className="flex items-center gap-3"><StatusPill label="Suppressed" tone="warn" />
          <button className="desk-button" disabled={remove.isPending} onClick={() => setRemoving(row.id)}>Remove suppression</button></div>} />)}</div>
      <Pagination page={page} totalPages={Math.ceil((rows.data?.count ?? 0) / 24)} onChange={setPage} />
    </QueryContent>
    <Modal open={Boolean(dialogOpen)} title="Suppress an address" onClose={() => { if (!add.isPending) onDialogClose?.(); }}>
      {form}
    </Modal>
    <ConfirmDialog open={removing !== null} title="Remove suppression?" message="Mail to this address can resume. Continue only after resolving the delivery problem."
      confirmLabel="Remove suppression" onCancel={() => setRemoving(null)} onConfirm={() => { if (removing !== null) remove.mutate(removing); setRemoving(null); }} />
  </div>;
  return embedded ? content : <ListLayout header={{ title: "Email suppression", subtitle: "Keep confirmed delivery problems out of the queue." }}
    state={{ status: "ready" }} empty={{ message: "No suppressed addresses." }} body={{ kind: "rows", rows: content }} />;
}
