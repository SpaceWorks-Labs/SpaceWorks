import { StatusPill } from "../../components/ui";
import type { Availability } from "../../types/inventory";

export function AvailabilityBadge({ availability }: { availability: Availability }) {
  if (availability === null) return null;
  const label = availability.label ?? "Available";
  const count = availability.mode === "exact_count" ? availability.count : null;
  return <StatusPill label={count != null && label !== "Unavailable" ? `${count} ${label.toLowerCase()}` : label}
    tone={label === "Available" ? "success" : label === "Limited" ? "warn" : "neutral"} />;
}
