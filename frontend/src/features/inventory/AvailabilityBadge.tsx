import type { Availability } from "../../types/inventory";

type AvailabilityBadgeProps = {
  availability: Availability;
};

type Tone = "success" | "emphasis" | "danger" | "neutral";

// Filled status-box styling (theme-token fills plus readable ink labels) so the availability
// pill matches the rest of the status boxes and stays legible in BOTH light and dark
// modes — the old tinted success text washed out in dark "Available".
const TONE_CLASS: Record<Tone, string> = {
  success:
    "border-success bg-success text-on-success dark:bg-success-soft dark:text-success-ink",
  emphasis: "border-transparent bg-emphasis text-on-emphasis",
  danger: "border-danger bg-danger text-on-danger",
  neutral: "border-line bg-surface text-ink",
};

function toneForAvailability(
  label: NonNullable<Availability>["label"],
): Tone {
  if (label === "Limited") {
    return "emphasis";
  }

  if (label === "Unavailable") {
    return "neutral";
  }

  if (label === "Available") {
    return "success";
  }

  return "neutral";
}

function textForAvailability(availability: NonNullable<Availability>): string {
  const label = availability.label;

  if (availability.mode === "exact_count" && availability.count != null) {
    if (label === "Unavailable") {
      return "Unavailable";
    }

    if (label === "Limited") {
      return `${availability.count} limited`;
    }

    return `${availability.count} available`;
  }

  return label ?? "Available";
}

export function AvailabilityBadge({ availability }: AvailabilityBadgeProps) {
  if (availability === null) {
    return null;
  }

  return (
    <span
      className={`inline-flex min-h-6 items-center rounded-full border px-2 py-0.5 text-xs font-semibold tracking-tight ${TONE_CLASS[toneForAvailability(availability.label)]}`}
    >
      {textForAvailability(availability)}
    </span>
  );
}
