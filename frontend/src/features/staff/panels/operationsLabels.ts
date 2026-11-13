import { t } from "@lingui/core/macro";

const humanize = (value: string) => value.replace(/_/g, " ");

/** Translated wording for a `StocktakeSession.status` value. */
export function stocktakeStatusLabel(status: string): string {
  switch (status) {
    case "draft": return t`Draft`;
    case "counting": return t`Counting`;
    case "completed": return t`Completed`;
    case "approved": return t`Approved`;
    case "applied": return t`Applied`;
    case "cancelled": return t`Cancelled`;
    default: return humanize(status);
  }
}

/** Translated wording for a `StockTransfer.status` value. */
export function stockTransferStatusLabel(status: string): string {
  switch (status) {
    case "applied": return t`Applied`;
    case "cancelled": return t`Cancelled`;
    default: return humanize(status);
  }
}

/** Translated wording for a `Device.kind` value. */
export function deviceKindLabel(kind: string): string {
  switch (kind) {
    case "printer": return t`Printer`;
    case "label_printer": return t`Label printer`;
    case "generic": return t`Other device`;
    case "adapter": return t`Device adapter`;
    default: return humanize(kind);
  }
}

/** Translated wording for a label print's result, or its device command status while no result exists. */
export function labelPrintStatusLabel(status: string): string {
  switch (status) {
    case "pending": return t`Pending`;
    case "succeeded": return t`Printed`;
    case "retryable_failed": return t`Failed, will retry`;
    case "failed": return t`Failed`;
    case "queued": return t`Queued`;
    case "leased": return t`Sent to the device`;
    case "acknowledged": return t`Received by the device`;
    case "delivery_failed": return t`Delivery failed`;
    case "cancelled": return t`Cancelled`;
    default: return humanize(status);
  }
}
