import { t } from "@lingui/core/macro";
import { EmptyState, ErrorText, ListRow, Skeleton } from "../../../components/ui";
import { authErrorMessage } from "../../../lib/api/authErrorCopy";
import { InvoiceStatus } from "../platformSpaces/InvoiceStatus";
import { StructuredApiError } from "../../../lib/api/errors";
import { formatMoney } from "../platformSpaces/plansApi";
import { paymentMethodLabel } from "../../../lib/money";
import { useInvoiceCheckout, useSpaceInvoices } from "./spacePlanApi";

/** The space's hosting invoices; an open one can be paid online when the platform takes online payments. */
export function SpaceInvoices({ makerspaceId }: { makerspaceId: number }) {
  const invoices = useSpaceInvoices(makerspaceId, true);
  const checkout = useInvoiceCheckout(makerspaceId);
  if (invoices.isLoading) return <Skeleton className="h-24 w-full" />;
  if (invoices.isError) return <ErrorText resource={t`invoices`} onRetry={() => { void invoices.refetch(); }} />;
  const rows = invoices.data ?? [];
  if (!rows.length) return <EmptyState message={t`No hosting invoices yet.`} />;
  return <div className="grid gap-3">
    {checkout.error ? <p role="alert" className="text-sm text-danger">{checkout.error instanceof StructuredApiError && checkout.error.code === "invoice_not_open"
      ? t`This invoice is no longer open. Refresh to see its current state.` : authErrorMessage(checkout.error, "Couldn't start the payment. Try again.")}</p> : null}
    {rows.map(invoice => <ListRow key={invoice.id} title={`${invoice.number} · ${formatMoney(invoice.amount_minor, invoice.currency)}`}
      meta={[t`Due ${invoice.due_on}`, invoice.description, invoice.receipts.length ? t`Paid by ${paymentMethodLabel(invoice.receipts[0].method)}` : ""].filter(Boolean).join(" · ")}
      right={<div className="flex flex-wrap items-center gap-2"><InvoiceStatus invoice={invoice} />
        {invoice.status === "open" && invoice.online_payable ? <button type="button" className="desk-button-primary"
          disabled={checkout.isPending} onClick={() => checkout.mutate(invoice.id)}>{checkout.isPending && checkout.variables === invoice.id ? t`Opening…` : t`Pay online`}{" "}<span className="sr-only">{invoice.number}</span></button> : null}
      </div>} />)}
  </div>;
}
