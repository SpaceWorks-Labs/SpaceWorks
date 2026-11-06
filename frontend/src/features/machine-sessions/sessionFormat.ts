import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { money } from "../payments/usePriceQuote";
import type { ChargeState, SessionRate, SessionSource } from "./api";

/** "45 min", "1 h", "2 h 05 min". */
export function duration(minutes: number) {
  const whole = Math.max(0, Math.floor(minutes));
  const hours = Math.floor(whole / 60);
  const rest = whole % 60;
  if (!hours) return `${rest} min`;
  return rest ? `${hours} h ${String(rest).padStart(2, "0")} min` : `${hours} h`;
}

/** "1:05:09" for a running timer. */
export function clock(seconds: number) {
  const whole = Math.max(0, Math.floor(seconds));
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${Math.floor(whole / 3600)}:${pad(Math.floor(whole / 60) % 60)}:${pad(whole % 60)}`;
}

/** The frozen rate in words: price per hour, then the increment and minimum when set. */
export function rateLine(rate: SessionRate) {
  const parts = [`${money(rate.unit_amount, rate.currency)} an hour`];
  if (rate.increment > 1) parts.push(`billed per ${rate.increment} min`);
  if (rate.minimum > 0) parts.push(`${rate.minimum} min minimum`);
  return parts.join(" · ");
}

export function when(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleString(formatLocale(), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
}

export const STOP_REASONS: Record<string, string> = {
  member: "Stopped by you", staff: "Stopped by staff", max_length: "Reached the maximum length",
  check_out: "Stopped at check-out", closing: "Stopped at closing time", device: "Ended by the machine",
};

export const SOURCES: Record<SessionSource, string> = { member_qr: "Machine QR", staff: "Staff", device: "Machine report" };

export const CHARGE_LABELS: Record<ChargeState, { text: string; tone: "neutral" | "info" | "warn" | "success" }> = {
  job: { text: t`Billed with the job`, tone: "neutral" },
  none: { text: t`Not charged`, tone: "neutral" },
  running: { text: t`Running`, tone: "info" },
  raised: { text: t`Charge raised`, tone: "success" },
  held: { text: t`Waiting for staff check`, tone: "warn" },
  free: { text: t`Nothing to pay`, tone: "neutral" },
};
