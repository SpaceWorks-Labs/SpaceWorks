import { CenteredCardLayout } from "../../components/layouts";
import { RelativeTime, StatusPill } from "../../components/ui";
import type { Tone } from "../../components/ui";
import { StructuredApiError } from "../../lib/api/errors";
import { useOpenHostingRequest, type HostingRequestStatus } from "./hostingApi";
import { useFragmentToken, useTokenCall } from "./useFragmentToken";

const STATUS: Record<HostingRequestStatus, { label: string; tone: Tone; copy: string }> = {
  submitted: { label: "Waiting for review", tone: "info", copy: "Your email is confirmed and your request is waiting for review." },
  pending_verification: { label: "Email not confirmed", tone: "warn", copy: "We're still waiting for you to confirm your email." },
  accepted: { label: "Accepted", tone: "success", copy: "Accepted — the platform team will set up your space and be in touch." },
  rejected: { label: "Not accepted", tone: "danger", copy: "Not accepted." },
  withdrawn: { label: "Withdrawn", tone: "neutral", copy: "This invitation was withdrawn." },
  invited: { label: "Invited", tone: "neutral", copy: "This request hasn't been sent yet. Use the invitation link from your email to send it." },
};
const UNAVAILABLE = "This link has expired or is no longer available.";
const home = { label: "Go to home", href: "/" };

/** Read-only: the applicant can see where the request stands, never change it from here. */
export function HostingRequestStatusPage() {
  const token = useFragmentToken();
  // The first open of a fresh link confirms the email, so it runs once even under StrictMode.
  const open = useTokenCall(token, useOpenHostingRequest().mutateAsync);
  if (!token || (open.error instanceof StructuredApiError && open.error.status === 404)) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Compass", tone: "warn" }} title="Request unavailable"
      body={<p role="alert">{UNAVAILABLE}</p>} primary={home} />;
  }
  const request = open.data;
  if (!request) {
    return <CenteredCardLayout width={480} title="Opening your request" body="" primary={home}
      state={open.error ? { status: "error", error: open.error instanceof Error ? open.error.message : "Couldn't open this request. Try again.", onRetry: open.retry } : { status: "loading" }} />;
  }
  const status = STATUS[request.status] ?? STATUS.invited;
  return <CenteredCardLayout width={480} state={{ status: "ready" }} media={{ icon: "Building2", tone: status.tone }}
    eyebrow="Hosting request" title={request.space_name}
    body={<div role="status" className="grid gap-3">
      <span><StatusPill label={status.label} tone={status.tone} /></span>
      <p className="text-ink">{status.copy}</p>
      {request.status === "rejected" && request.rejection_reason ? <p><span className="font-semibold text-ink">Reason: </span>{request.rejection_reason}</p> : null}
    </div>}
    content={<dl className="grid gap-2 text-sm">
      <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">Sent</dt><dd><RelativeTime date={request.created_at} exact /></dd></div>
      {request.verified_at ? <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">Email confirmed</dt><dd><RelativeTime date={request.verified_at} exact /></dd></div> : null}
      {request.decided_at ? <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">Decided</dt><dd><RelativeTime date={request.decided_at} exact /></dd></div> : null}
    </dl>}
    primary={home} />;
}
