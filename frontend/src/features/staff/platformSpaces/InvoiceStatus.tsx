import { StatusPill } from "../../../components/ui";
import type { HostingInvoice } from "./plansApi";

export function InvoiceStatus({ invoice }: { invoice: Pick<HostingInvoice, "status" | "overdue"> }) {
  if (invoice.status === "paid") return <StatusPill label="Paid" tone="success" />;
  if (invoice.status === "void") return <StatusPill label="Void" />;
  return invoice.overdue ? <StatusPill label="Overdue" tone="danger" /> : <StatusPill label="Open" tone="warn" />;
}
