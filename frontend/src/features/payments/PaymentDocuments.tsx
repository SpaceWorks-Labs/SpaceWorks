import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ListRow, RelativeTime } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";

import { memberRequest, memberRequestBlob, staffRequest, staffRequestBlob } from "../../lib/api";

export type PaymentDocument = {
  id: number; payment: number; number: string; kind: "receipt" | "credit_note" | "bill";
  amount: string; currency: string; issued_at: string; money_at: string;
  status: string;
};
type DocumentPage = { count: number; next: string | null; previous: string | null; results: PaymentDocument[] };

export function PaymentDocuments({ makerspaceId, audience, initiallyExpanded = false }: { makerspaceId: number; audience: "member" | "staff"; initiallyExpanded?: boolean }) {
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState("");
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const request = audience === "member" ? memberRequest : staffRequest;
  const base = audience === "member" ? `/member/makerspaces/${makerspaceId}` : `/admin/makerspace/${makerspaceId}`;
  const documents = useQuery({
    queryKey: ["payment-documents", audience, makerspaceId, page, kind],
    queryFn: () => request<DocumentPage>(`${base}/payment-documents?page=${page}${kind ? `&kind=${kind}` : ""}`),
    enabled: expanded,
    refetchInterval: expanded ? 30_000 : false,
  });
  const download = useMutation({
    mutationFn: async (document: PaymentDocument) => {
      const grant = await request<{ url: string; expires_in: number }>(`${base}/payment-documents/${document.id}/download-url`);
      // Grants contain a server route (/api/v1/...), whereas API helpers take a
      // path relative to that prefix. Authentication is required even with the grant.
      const path = grant.url.replace(/^\/api\/v1/, "");
      const blob = await (audience === "member" ? memberRequestBlob(path) : staffRequestBlob(path));
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = `payment-document-${document.id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });
  return <section className="grid gap-4" aria-label={t`Payment documents`}>
    {!initiallyExpanded ? <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="title-panel">{t`Bills, receipts and credit notes`}</h3>
      <button className="desk-button" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? t`Hide documents` : t`Show documents`}</button>
    </div> : null}
    {expanded ? <><label className="grid gap-1 text-sm">{t`Document kind`}<select className="desk-input" value={kind} onChange={event => { setKind(event.target.value); setPage(1); }}>
        <option value="">{t`All documents`}</option><option value="bill">{t`Bills`}</option>
        <option value="receipt">{t`Receipts`}</option><option value="credit_note">{t`Credit notes`}</option>
      </select>
    </label><QueryContent state={documents.isLoading ? { status: "loading" } : documents.error
      ? { status: "error", error: "Couldn't load documents. Try again.", onRetry: () => { void documents.refetch(); } } : { status: "ready" }}
      isEmpty={documents.data?.count === 0} empty={{ message: t`No issued documents match this filter.` }}>
      <div className="grid gap-3">{documents.data?.results.map(document => <ListRow key={document.id}
        title={`${{ receipt: "Receipt", credit_note: "Credit note", bill: "Bill" }[document.kind]} ${document.number}`}
        identity={{ kind: "date", date: document.issued_at }}
        meta={<><span className="tabular-nums">{document.currency.toUpperCase()} {document.amount}</span>{document.status ? <span>{document.status}</span> : null}<span aria-hidden="true"> · </span><RelativeTime date={document.issued_at} /></>}
        right={<button className="desk-button" type="button" disabled={download.isPending} onClick={() => download.mutate(document)}>{t`Download PDF`}</button>} />)}</div>
      {documents.data && documents.data.count > 24 ? <div className="flex flex-wrap items-center gap-3">
        <button className="desk-button" type="button" disabled={!documents.data.previous} onClick={() => setPage(page - 1)}>{t`Previous`}</button>
        <span className="text-sm text-muted">{t`Page ${page}`}</span>
        <button className="desk-button" type="button" disabled={!documents.data.next} onClick={() => setPage(page + 1)}>{t`Next`}</button>
      </div> : null}
    </QueryContent></> : null}
    {download.error ? <p role="alert" className="text-sm text-danger">{download.error.message}</p> : null}
  </section>;
}
