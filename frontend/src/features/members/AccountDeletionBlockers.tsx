import { t } from "@lingui/core/macro";
import type { DeletionBlocker } from "./accountDeletionApi";

const destinations: Record<string, [string, string]> = {
  unpaid_charges: ["payments", "View charges"], refund_in_progress: ["payments", "View refunds"],
  refund_under_review: ["payments", "View refunds"],
  deposit_held: ["payments", "View deposits"], active_loans: ["loans", "View borrowed hardware"],
  open_requests: ["loans", "View hardware requests"], problem_report_open: ["loans", "View problem reports"],
  upcoming_bookings: ["bookings", "Manage bookings"], upcoming_registrations: ["events", "Manage registrations"],
  open_service_jobs: ["overview", "View machine jobs"], access_restricted: ["overview", "Contact makerspace staff"],
  last_manager: ["account?section=membership", "Manage makerspace staff"],
  makerspace_gated: ["overview", "View makerspace status"],
};

export function AccountDeletionBlockers({ blockers, slug }: { blockers: DeletionBlocker[]; slug: string }) {
  return <ul className="grid gap-3">{blockers.map((row, index) => {
    const [screen, label] = destinations[row.code] || ["account-portal", "View account"];
    // Global preview returns IDs across spaces; each action must lead to that
    // space, never silently send another tenant's blocker to the current space.
    const targetSlug = row.makerspace_slug || slug;
    const base = row.makerspace_member_url || (targetSlug ? `/m/${encodeURIComponent(targetSlug)}/member` : "/member");
    const href = row.organization_id ? row.organization_url || "/admin/organizations"
      : row.code === "last_manager" ? base.replace(/\/member\/?$/, "/admin/members")
      : `${base}/${screen}`;
    return <li key={`${row.code}-${row.makerspace_id}-${index}`} className="rounded-xl border border-line p-3">
      <p>{row.detail}{row.count > 1 ? ` (${row.count})` : ""}{row.makerspace_id ? t` — Makerspace ${row.makerspace_id}` : ""}</p>
      <a className="desk-button mt-2 inline-flex" href={href}>{row.organization_id ? t`Manage organization governors` : label}</a>
    </li>;
  })}</ul>;
}
