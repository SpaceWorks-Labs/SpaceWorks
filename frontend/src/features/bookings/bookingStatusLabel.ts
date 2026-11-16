import { t } from "@lingui/core/macro";

/** Translated wording for a `Booking.Status` value. */
export function bookingStatusLabel(status: string): string {
  switch (status) {
    case "pending": return t`Pending`;
    case "confirmed": return t`Confirmed`;
    case "rejected": return t`Rejected`;
    case "cancelled": return t`Cancelled`;
    case "completed": return t`Completed`;
    case "no_show": return t`No-show`;
    default: return status.replace(/_/g, " ");
  }
}

/** Translated wording for a `BookableSpace.kind` value. */
export function spaceKindLabel(kind: string): string {
  switch (kind) {
    case "dev_room": return t`Development room`;
    case "bench": return t`Bench`;
    case "meeting": return t`Meeting room`;
    case "other": return t`Other`;
    case "machine": return t`Machine time`;
    default: return kind.replace(/_/g, " ");
  }
}
