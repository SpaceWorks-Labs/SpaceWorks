import { t } from "@lingui/core/macro";
import type { Tone } from "../../components/ui/types";
import { formatDate, formatDateTime } from "../../lib/format";
import type { BorrowMode, Entitlements, MachineMode, PassKind, PassStatus } from "./api";

export const passKindLabel = (kind: string) =>
  ({ event: t`Event guest`, sponsored: t`Member's guest`, day: t`Day pass` } as Record<string, string>)[kind] ?? kind;

export const passStatusLabel = (status: string) => ({
  issued: t`Issued`, active: t`Active`, expired: t`Expired`, revoked: t`Withdrawn`, converted: t`Joined as member`,
} as Record<string, string>)[status] ?? status;

export const passStatusTone = (status: PassStatus | string): Tone =>
  status === "active" || status === "issued" ? "success" : status === "revoked" ? "danger" : status === "converted" ? "info" : "neutral";

export const BORROW_MODES: BorrowMode[] = ["none", "on_site", "full_with_deposit"];
export const MACHINE_MODES: MachineMode[] = ["none", "supervised", "after_induction_cert"];

export const borrowModeLabel = (mode: string) => ({
  none: t`No borrowing`, on_site: t`On site only, due back by the end of the pass`, full_with_deposit: t`Full borrowing with a deposit`,
} as Record<string, string>)[mode] ?? mode;

export const machineModeLabel = (mode: string) => ({
  none: t`No machine use`, supervised: t`Supervised use in an instructor's session`,
  after_induction_cert: t`After a certification from an induction event`,
} as Record<string, string>)[mode] ?? mode;

/** What a pass allows, in one line for a card or a row. */
export function entitlementSummary(value: Entitlements | undefined): string {
  const borrow = value?.borrow ? borrowModeLabel(value.borrow) : t`No borrowing`;
  const machines = value?.machines ? machineModeLabel(value.machines) : t`No machine use`;
  return `${borrow} · ${machines}`;
}

export const passWindow = (from: string, until: string) =>
  formatDate(from) === formatDate(until) ? `${formatDate(from)}` : `${formatDateTime(from)} – ${formatDateTime(until)}`;

export const paymentStatusLabel = (status: string | null) => status === null ? "" : ({
  pending: t`Payment due`, paid: t`Paid`, waived: t`Waived`, cancelled: t`Cancelled`, refunded: t`Refunded`, failed: t`Payment failed`,
} as Record<string, string>)[status] ?? status;

export const scanReasonLabel = (reason: string) => ({
  expired: t`This pass has ended.`, revoked: t`This pass was withdrawn.`, converted: t`This guest has joined as a member.`,
  not_yet_valid: t`This pass hasn't started yet.`, unknown: t`This code isn't a pass from this space.`,
  unavailable: t`This pass isn't usable right now (for example, an unpaid day pass).`,
  off: t`Guest passes are switched off in this space.`, issued: t`This pass is issued but not live.`,
} as Record<string, string>)[reason] ?? t`This pass can't be used.`;

export type { PassKind };
