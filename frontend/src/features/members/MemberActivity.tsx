import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";
import { useTenantPath } from "../../lib/tenant";
import { useEffect, useState } from "react";

import { EmptyState, ListRow, StatusPill, RelativeTime, Modal, TicketCard } from "../../components/ui";
import { staffRequestBlob } from "../../lib/api";
import { MemberEventFeedback } from "./MemberEventFeedback";
import { CertificateApprovals } from "./certificates/CertificateApprovals";
import { MyCertificates } from "./certificates/MyCertificates";
import { MemberLoanRenew } from "./MemberLoanRenew";
import { MemberEventCancel } from "./MemberEventCancel";
import { MemberCalendarLinks } from "./calendarFeeds/MemberCalendarLinks";
import { MemberGifts } from "../donations/MemberGifts";
import { OfflineLoansControl } from "./memberCard/OfflineLoansControl";
import { MemberServiceRequestRows, type MemberServiceRequest } from "../machine-service/MemberServiceRequestRows";
import { ReportProblem } from "../repairs/ReportProblem";

type Loan = { request_id?: number; can_renew?: boolean; renewal_count?: number; renewal_refusal?: string | null; label: string; checked_out_at: string; due_at: string | null; overdue: boolean };
type MachineServiceRequest = MemberServiceRequest;
type Booking = { space_name: string; starts_at: string; ends_at: string; status: string };
type Registration = {
  registration_id: number;
  event_title: string;
  starts_at: string;
  ends_at?: string;
  status: string;
  waitlist_position: number | null;
  cancellation_cutoff_at?: string;
  can_cancel?: boolean;
  // Non-null only for a REGISTERED row: a waitlisted registration has nothing confirmable
  // behind it, and a QR that scans and then fails is worse than no QR at all.
  checkin_token: string | null;
  feedback_available: boolean;
  feedback_path: string | null;
  certificate: { id: number; status: string; revision: number } | null;
};
type Presence = { started_at: string; expires_at: string; active: boolean };

export type MemberNotice = { level: string; event: string; title: string; body: string };
export type MemberLoanHistoryRow = {
  label: string; checked_out_at: string; returned_at: string | null;
  due_at: string | null; returned_late: boolean;
};
export type MemberRequestHistoryRow = {
  // Lane L12: present once the activity payload carries it; withdrawing a request needs it.
  id?: number;
  status: string; created_at: string; item_count: number;
  returned_quantity: number; damaged_quantity: number; missing_quantity: number;
};
export type MemberDuesSummary = {
  // `null` means the ledger could not be read, which is NOT the same as an empty map
  // for "nothing outstanding" -- rendering the two alike would tell a member they owe
  // nothing on the strength of a failed query.
  dues_amount: string; outstanding_by_currency: Record<string, string> | null;
};

export type MemberActivity = {
  active_hardware_loans: Loan[];
  machine_service_requests?: MachineServiceRequest[];
  bookings?: { upcoming: Booking[]; past: Booking[] };
  event_registrations?: Registration[];
  recent_presence_sessions: Presence[];
  currently_checked_in: boolean;
  accountability: { membership_active: boolean; waiver_acceptance_required: boolean; restriction_code: string | null };
  // The dashboard half (D8). Optional: the payload omits them for a space whose
  // `membership` module is off, and this endpoint is not reachable there at all.
  notices?: MemberNotice[];
  loan_history?: MemberLoanHistoryRow[];
  request_history?: MemberRequestHistoryRow[];
  membership_dues?: MemberDuesSummary;
  // The member's current (else latest) plan term; null when they never held one.
  membership_term?: MemberTermSummary | null;
};

export type MemberTermSummary = {
  plan_name: string; starts_at: string; ends_at: string;
  // `current` uses the borrowing rule's own predicate; `blocks_borrowing` is true only when
  // no term is current AND the space refuses lapsed members.
  current: boolean; blocks_borrowing: boolean;
};

/** The member's own check-in QR, fetched rather than linked.
 *
 * `<img src>` cannot carry an Authorization header, so the SVG is fetched through the
 * refresh-aware authenticated path and handed to the DOM as an object URL. That URL is
 * revoked on unmount and whenever it is replaced -- otherwise every open-and-close leaks a
 * blob for the lifetime of the tab.
 */
function CheckInQr({ makerspaceId, registrationId, title, startsAt, organisation }: { makerspaceId: number; registrationId: number; title: string; startsAt: string; organisation: string }) {
  const [open, setOpen] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    let url: string | null = null;
    staffRequestBlob(
      `/member/makerspaces/${makerspaceId}/event-registrations/${registrationId}/qr`,
    )
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : t`Could not load your code.`);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
      setSrc(null);
    };
  }, [open, makerspaceId, registrationId]);

  return <div className="mt-1">
    <button
      type="button"
      className="desk-button-ghost"
      aria-expanded={open}
      onClick={() => { setError(null); setOpen((value) => !value); }}
    >
      {open ? t`Hide check-in QR` : t`Show check-in QR`}
    </button>
    {/* Unmounted rather than hidden, so the blob is released and keyboard users cannot tab
        into an image that is not on screen. */}
    {open ? <Modal open title={t`Your event ticket`} onClose={() => setOpen(false)}
      footer={<button type="button" className="desk-button w-full" onClick={() => setOpen(false)}>{t`Done`}</button>}>
      {src ? <TicketCard organisation={organisation} title={title} fields={[{ label: t`When`, value: new Date(startsAt).toLocaleString(formatLocale()) }, { label: t`Registration`, value: registrationId }]} qr={<img src={src} alt={t`Your check-in QR code`} />} caption={t`Show this code at event check-in.`} /> : <p role="status">{t`Loading your ticket…`}</p>}
    </Modal> : null}
    {open && error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
  </div>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section aria-label={title} className="grid gap-3"><h2 className="title-panel">{title}</h2>{children}</section>;
}
function Empty({ children = "Nothing here yet. Check back after your next visit." }: { children?: string }) {
  return <EmptyState message={children} />;
}
const REGISTRATION_LABELS: Record<string, string> = { pending_approval: t`Awaiting approval`, registered: t`Confirmed`, waitlisted: t`Waitlisted`, rejected: t`Not approved`, cancelled: t`Cancelled`, attended: t`Attended` };
const statusTone = (status: string) => ["registered", "confirmed", "attended", "completed"].includes(status) ? "success" as const : ["cancelled", "rejected"].includes(status) ? "neutral" as const : "warn" as const;

export function MemberActivityPanel({ activity, makerspaceId, makerspaceSlug, makerspaceName, modules, section = "all", eventPeriod, features = [] }: {
  modules: string[]; features?: string[]; section?: "all" | "overview" | "loans" | "bookings" | "events"; eventPeriod?: "going" | "past";
  activity: MemberActivity; makerspaceId: number; makerspaceSlug: string;
  /** Printed on event tickets; the hosting makerspace, not the platform. */
  makerspaceName: string;
}) {
  const tenantPath = useTenantPath(makerspaceSlug);
  if (!modules.includes("membership")) return null;
  const printerRequests = (activity.machine_service_requests ?? []).filter(request => request.machine_type === "3d_printer");
  const otherServiceRequests = (activity.machine_service_requests ?? []).filter(request => request.machine_type !== "3d_printer");
  // An event counts as past once it has ENDED, so a running event (and its check-in QR) stays under "Going".
  const registrations = (activity.event_registrations ?? []).filter(row => !eventPeriod || (eventPeriod === "past") === (new Date(row.ends_at ?? row.starts_at).getTime() < Date.now()));
  const requestRows = (rows: MachineServiceRequest[]) => <MemberServiceRequestRows rows={rows} makerspaceSlug={makerspaceSlug} />;
  return <div className="grid gap-6">
    {(section === "all" || section === "loans") && modules.includes("request_workflow") ? <OfflineLoansControl key={makerspaceId} space={makerspaceSlug} loans={activity.active_hardware_loans} /> : null}
    {section === "all" || section === "overview" ? <Section title={t`My activity`}><p className="text-sm text-muted">{activity.currently_checked_in ? t`You are currently checked in.` : t`You are not currently checked in.`}</p>{activity.accountability.waiver_acceptance_required ? <p className="text-sm text-danger">{t`Accept the current waiver before making facility requests.`}</p> : null}</Section> : null}
    {(section === "all" || section === "loans") && modules.includes("request_workflow") ? <Section title={t`Active hardware loans`}>{activity.active_hardware_loans.length ? activity.active_hardware_loans.map(loan => <ListRow key={`${loan.label}-${loan.checked_out_at}`} title={loan.label}
      identity={loan.due_at ? { kind: "date", date: loan.due_at } : { kind: "icon", icon: "Wrench", tone: "info" }}
      meta={loan.due_at ? <>{t`Due `}<RelativeTime date={loan.due_at} /></> : "No due date"}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={loan.overdue ? t`Overdue` : t`On loan`} tone={loan.overdue ? "danger" : "info"} />{loan.can_renew && loan.request_id ? <MemberLoanRenew key={loan.due_at} makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} requestId={loan.request_id} /> : null}
        {loan.request_id && features.includes("inventory.issue_reporting") ? <ReportProblem source={{ makerspace_id: makerspaceId, loan_id: loan.request_id }} /> : null}</div>} />) : <EmptyState message={t`Nothing out right now. Browse the catalogue to borrow something.`} action={{ label: t`Browse inventory`, href: tenantPath("inventory") }} />}</Section> : null}
    {(section === "all" || section === "overview") && (modules.includes("machines") || modules.includes("machine_service")) && activity.machine_service_requests ? <>{modules.includes("printing") ? <Section title={t`3D print requests`}>{requestRows(printerRequests)}</Section> : null}{otherServiceRequests.length ? <Section title={t`Machine-service requests`}>{requestRows(otherServiceRequests)}</Section> : null}<div className="flex flex-wrap gap-2">{modules.includes("machine_service") ? <Link className="desk-button" to={tenantPath("member/machine-jobs")}>{t`All my machine jobs`}</Link> : null}{modules.includes("machines") && features.includes("machines.sessions") ? <Link className="desk-button" to={tenantPath("member/machine-sessions")}>{t`My machine sessions`}</Link> : null}</div></> : null}
    {(section === "all" || section === "bookings") && modules.includes("bookings") && activity.bookings ? <Section title={t`Bookings`}>{(["upcoming", "past"] as const).map(period => <div key={period} className="grid gap-3"><h3 className="title-section">{period === "upcoming" ? t`Upcoming` : t`Past`}</h3>{activity.bookings![period].length ? activity.bookings![period].map((item, index) => <ListRow key={index} title={item.space_name} identity={{ kind: "date", date: item.starts_at }} meta={`${new Date(item.starts_at).toLocaleString(formatLocale())} – ${new Date(item.ends_at).toLocaleTimeString(formatLocale())}`} right={<StatusPill label={item.status.replace(/_/g, " ")} tone={statusTone(item.status)} />} />) : <Empty />}</div>)}</Section> : null}
    {(section === "all" || section === "events") && modules.includes("events") && activity.event_registrations ? <Section title={t`Event registrations`}><MemberCalendarLinks makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} />{registrations.length ? registrations.map(item => <ListRow key={item.registration_id} title={item.event_title} identity={{ kind: "date", date: item.starts_at }}
      meta={<><span className="tabular-nums">{new Date(item.starts_at).toLocaleString(formatLocale())}</span>{item.status === "pending_approval" ? t` · No payment until confirmed` : ""}{item.waitlist_position ? t` · Waitlist ${item.waitlist_position}` : ""}</>}
      right={<div className="grid gap-2"><StatusPill label={REGISTRATION_LABELS[item.status] ?? item.status} tone={statusTone(item.status)} />
        <Link className="desk-button-ghost" to={tenantPath(`member/events/${item.registration_id}/ticket`)}>{t`Open ticket`}</Link>
        {item.checkin_token ? <CheckInQr makerspaceId={makerspaceId} registrationId={item.registration_id} title={item.event_title} startsAt={item.starts_at} organisation={makerspaceName} /> : null}
        <MemberEventCancel makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} registrationId={item.registration_id} status={item.status} canCancel={item.can_cancel} cutoffAt={item.cancellation_cutoff_at} />
        <MemberEventFeedback makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} registrationId={item.registration_id} feedbackPath={item.feedback_path} certificate={item.certificate} /></div>} />) : <EmptyState message={eventPeriod === "past" ? t`No past events yet.` : t`You’re not registered for anything yet. See what’s on.`} action={{ label: t`See events`, href: `/m/${makerspaceSlug}/events` }} />}</Section> : null}
    {(section === "all" || section === "events") && modules.includes("events") ? <Section title={t`Certificates`}><CertificateApprovals makerspaceId={makerspaceId} /><MyCertificates makerspaceId={makerspaceId} /></Section> : null}
    {section === "all" || section === "overview" ? <MemberGifts makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} /> : null}
    {(section === "all" || section === "overview") && modules.includes("presence") ? <Section title={t`Recent presence`}>{activity.recent_presence_sessions.length ? activity.recent_presence_sessions.map(item => <ListRow key={item.started_at} title={t`Makerspace visit`} identity={{ kind: "date", date: item.started_at }} meta={<><RelativeTime date={item.started_at} /> {t` · until ${new Date(item.expires_at).toLocaleString(formatLocale())}`}</>} right={<StatusPill label={item.active ? t`Active` : t`Ended`} tone={item.active ? "success" : "neutral"} />} />) : <Empty />}</Section> : null}
  </div>;
}
