import { t } from "@lingui/core/macro";
import { StatusPill } from "../../components/ui";
import type { Availability } from "../../types/inventory";

/** `eventsOn` false (decision 228a): an event-only item reads as plainly unavailable, not "at events". */
export function AvailabilityBadge({ availability, eventsOn = true }: { availability: Availability; eventsOn?: boolean }) {
  if (availability === null) return null;
  const label = availability.label ?? "Available";
  if (label === "Lent at events only") return eventsOn ? <StatusPill label={t`Lent at events only`} tone="info" /> : <StatusPill label={t`Unavailable`} tone="neutral" />;
  const count = availability.mode === "exact_count" ? availability.count : null;
  const text = count != null && label !== "Unavailable"
    ? label === "Limited" ? t`${count} limited` : t`${count} available`
    : label === "Limited" ? t`Limited` : label === "Unavailable" ? t`Unavailable` : t`Available`;
  return <StatusPill label={text} tone={label === "Available" ? "success" : label === "Limited" ? "warn" : "neutral"} />;
}
