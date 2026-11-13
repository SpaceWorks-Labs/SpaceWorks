import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { staffPathState, staffTabPath } from "./staffTabs";
import { LogoLoader } from "../../components/LogoLoader";

/** Decision 216 item 4: the admission checks a booking would meet, read-only. Submit re-verifies. */
export type ReadinessCheck = {
  code: "room_outage" | "machine_repair" | "machine_lockout" | "machine_access";
  state: "ok" | "blocked" | "warning";
  detail: string;
  reason?: string;
};
export type BookingReadinessResult = { ready: boolean; checks: ReadinessCheck[]; maintenance_link: { machine_id: number } | null };

function label(row: ReadinessCheck) {
  switch (row.code) {
    case "room_outage":
      return row.state === "blocked" ? t`This room is out of service at that time.`
        : row.state === "warning" ? t`This room has an open outage; bookings are still allowed.` : t`No room outage.`;
    case "machine_repair":
      return row.state === "blocked" ? t`The machine is under repair at that time.` : t`The machine is in service.`;
    case "machine_lockout":
      return row.state === "warning" ? t`Overdue safety maintenance locks the machine: it cannot be started until done.`
        : t`No maintenance lockout.`;
    case "machine_access":
      return row.state === "blocked" ? (row.reason === "machine_access_expired" ? t`The member's machine access has ended.` : t`The member has not been given access to this machine.`)
        : t`The member has access to this machine.`;
    default:
      return row.detail;
  }
}

const TONES = { ok: "success", blocked: "danger", warning: "warn" } as const;

function MaintenanceLink({ machineId }: { machineId: number }) {
  const { pathname } = useLocation();
  const guest = pathname.startsWith("/guest-admin");
  const base = staffTabPath("machines", guest, staffPathState(pathname, guest).makerspaceSlug || null);
  return <Link className="desk-button w-fit" to={consoleSessionHref(`${base}?machine=${machineId}&detail_tab=Maintenance`)}>
    {t`Open machine maintenance record`}</Link>;
}

function ReadinessPanel({ path, explicit = false }: { path: string | null; explicit?: boolean }) {
  // A plain effect, not a query: the staff booking form renders outside any QueryClient.
  // Keyed by path, so an answer for an earlier room/member/window is never shown.
  const [result, setResult] = useState<{ path: string; data: BookingReadinessResult | null } | null>(null);
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    staffRequest<BookingReadinessResult>(path, { signal: controller.signal })
      .then(data => setResult({ path, data }))
      .catch(() => { if (!controller.signal.aborted) setResult({ path, data: null }); });
    return () => controller.abort();
  }, [path]);
  if (path === null) return null;
  if (result?.path !== path) return <LogoLoader label={t`Checking room and machine readiness…`} size={48} className="min-h-16 py-3" />;
  // Advisory only: the booking itself re-checks everything. Silent inside the form; a staff
  // member who asked for it explicitly gets an answer either way.
  if (!result.data) return explicit ? <p className="text-sm text-muted" role="status">{t`Readiness checks are unavailable for your access.`}</p> : null;
  const { checks, maintenance_link: link } = result.data;
  if (!checks.length) return explicit ? <p className="text-sm text-muted" role="status">{t`No readiness checks apply to this booking.`}</p> : null;
  return <section className="grid gap-2 rounded-md border border-line p-2 text-sm" aria-label={t`Booking readiness`}>
    <ul className="grid gap-1">{checks.map(row => <li key={row.code} className="flex flex-wrap items-center gap-2">
      <StatusPill tone={TONES[row.state]} label={row.state === "ok" ? t`Ready` : row.state === "blocked" ? t`Blocked` : t`Warning`} />
      <span>{label(row)}</span></li>)}</ul>
    {link ? <MaintenanceLink machineId={link.machine_id} /> : null}
  </section>;
}

function iso(value: string) {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toISOString() : null;
}

/** Before a staff booking is submitted: the chosen room, window and (optional) member. */
export function StaffBookingReadiness({ spaceId, memberId, start, end }: { spaceId: number; memberId: string; start: string; end: string }) {
  const startsAt = iso(start);
  const endsAt = iso(end);
  const params = new URLSearchParams();
  if (startsAt && endsAt && endsAt > startsAt) {
    params.set("starts_at", startsAt);
    params.set("ends_at", endsAt);
    if (Number(memberId) > 0) params.set("member_id", memberId);
  }
  return <ReadinessPanel path={params.has("starts_at") ? `/admin/spaces/${spaceId}/bookings/readiness/?${params}` : null} />;
}

/**
 * While reviewing an existing booking: its own window and member. Rendered once per row of
 * the bookings list, so it asks the server only when opened rather than once per row.
 */
export function ExistingBookingReadiness({ bookingId }: { bookingId: number }) {
  const [open, setOpen] = useState(false);
  const id = `booking-readiness-${bookingId}`;
  return <div className="grid gap-2">
    <button className="desk-button w-fit" type="button" aria-expanded={open} aria-controls={id}
      onClick={() => setOpen(value => !value)}>{open ? t`Hide readiness checks` : t`Check readiness`}</button>
    <div id={id}>{open ? <ReadinessPanel path={`/admin/bookings/${bookingId}/readiness/`} explicit /> : null}</div>
  </div>;
}
