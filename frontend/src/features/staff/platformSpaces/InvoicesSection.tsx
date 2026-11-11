import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, Field, ListRow, Pagination, Skeleton } from "../../../components/ui";
import { InvoiceStatus } from "./InvoiceStatus";
import { CreateInvoiceDialog, RecordPaymentDialog, VoidInvoiceDialog } from "./InvoiceDialogs";
import { formatMoney, useInvoices, type HostingInvoice } from "./plansApi";
import { PAGE_SIZE } from "./spacesApi";

/** Hosting invoices across every space: raise one, record an offline payment, or void it. */
export function InvoicesSection() {
  const [status, setStatus] = useState("open");
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<{ kind: "create" } | { kind: "pay" | "void"; invoice: HostingInvoice } | null>(null);
  const list = useInvoices(status, page);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-end gap-3">
      <Field label={t`Status`} className="min-w-48">
        <select className="desk-input" value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}>
          <option value="">{t`Every status`}</option><option value="open">{t`Open`}</option><option value="paid">{t`Paid`}</option><option value="void">{t`Void`}</option>
        </select>
      </Field>
      <button type="button" className="desk-button-primary" onClick={() => setDialog({ kind: "create" })}>{t`New invoice`}</button>
    </div>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource={t`invoices`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No invoices with this status.`} />
      : <div className="grid gap-3">{rows.map(invoice => <ListRow key={invoice.id} title={`${invoice.number} · ${invoice.makerspace_name}`}
        meta={`${formatMoney(invoice.amount_minor, invoice.currency)} · due ${invoice.due_on}${invoice.description ? ` · ${invoice.description}` : ""}`}
        right={<div className="flex flex-wrap items-center gap-2"><InvoiceStatus invoice={invoice} />
          {invoice.status === "open" ? <>
            <button type="button" className="desk-button" aria-label={t`Record payment for ${invoice.number}`} onClick={() => setDialog({ kind: "pay", invoice })}>{t`Record payment…`}</button>
            <button type="button" className="desk-button-danger-outline" aria-label={t`Void ${invoice.number}`} onClick={() => setDialog({ kind: "void", invoice })}>{t`Void…`}</button>
          </> : null}</div>} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {dialog?.kind === "create" ? <CreateInvoiceDialog onClose={() => setDialog(null)} /> : null}
    {dialog?.kind === "pay" ? <RecordPaymentDialog invoice={dialog.invoice} onClose={() => setDialog(null)} /> : null}
    {dialog?.kind === "void" ? <VoidInvoiceDialog invoice={dialog.invoice} onClose={() => setDialog(null)} /> : null}
  </div>;
}
