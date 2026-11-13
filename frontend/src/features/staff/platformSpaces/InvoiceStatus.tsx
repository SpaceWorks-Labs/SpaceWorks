import { t } from "@lingui/core/macro";
import { StatusPill } from "../../../components/ui";
import type { HostingInvoice } from "./plansApi";

export function InvoiceStatus({ invoice }: { invoice: Pick<HostingInvoice, "status" | "overdue"> }) {
  if (invoice.status === "paid") return <StatusPill label={t`Paid`} tone="success" />;
  if (invoice.status === "void") return <StatusPill label={t`Void`} />;
  return invoice.overdue ? <StatusPill label={t`Overdue`} tone="danger" /> : <StatusPill label={t`Open`} tone="warn" />;
}
