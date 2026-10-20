import { useState } from "react";

import { CenteredCardLayout } from "../../components/layouts";
import { Field } from "../../components/ui";
import { StructuredApiError } from "../../lib/api/errors";
import { useResolveHostingInvitation, useSubmitHostingInvitation, type HostingInvitationPreview } from "./hostingApi";
import { EMPTY_HOSTING_FORM, HOSTING_ACK, hostingErrorText, hostingFieldErrors, hostingRequestBody, type HostingFormKey } from "./hostingForm";
import { HostingRequestFields } from "./HostingRequestFields";
import { useFragmentToken, useTokenCall } from "./useFragmentToken";

const EXPIRED = "This invitation link has expired or was already used.";
const FORM_ID = "hosting-invite-form";
const home = { label: "Go to home", href: "/" };

export function HostingInvitePage() {
  const token = useFragmentToken();
  const resolve = useTokenCall(token, useResolveHostingInvitation().mutateAsync);
  if (!token || (resolve.error instanceof StructuredApiError && resolve.error.status === 404)) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Mail", tone: "warn" }} title="Invitation unavailable"
      body={<p role="alert">{EXPIRED}</p>} primary={home} />;
  }
  if (!resolve.data) {
    return <CenteredCardLayout width={480} title="Opening your invitation" body="" primary={home}
      state={resolve.error ? { status: "error", error: errorMessage(resolve.error), onRetry: resolve.retry } : { status: "loading" }} />;
  }
  return <HostingInviteForm token={token} invite={resolve.data} />;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Couldn't open this invitation. Try again.";
}

function HostingInviteForm({ token, invite }: { token: string; invite: HostingInvitationPreview }) {
  const submit = useSubmitHostingInvitation();
  const [form, setForm] = useState(() => ({ ...EMPTY_HOSTING_FORM, space_name: invite.space_name, applicant_email: invite.applicant_email }));
  // Joining the inviting organization is the default whenever it is offered.
  const [choice, setChoice] = useState<"own" | "join">(invite.join_organization_name ? "join" : "own");
  if (submit.isSuccess) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Mail", tone: "success" }} title="Almost there"
      body={<p role="status">{HOSTING_ACK}</p>} primary={home} />;
  }

  const org = invite.join_organization_name;
  const errors = hostingFieldErrors(submit.error);
  const set = (key: HostingFormKey, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const organizationName = <Field label="Organization name (optional)" hint="The group that runs the space, if it has one." error={errors.new_organization_name}>
    <input className="desk-input" maxLength={200} value={form.new_organization_name} onChange={(event) => set("new_organization_name", event.target.value)} />
  </Field>;
  return <CenteredCardLayout width="wide" state={{ status: "ready" }} media={{ icon: "Building2", tone: "accent" }}
    title="Host your makerspace"
    body={<div className="grid gap-3">
      <p className="font-semibold text-ink">{invite.inviter_name} invited you to host your makerspace on Space Works</p>
      {invite.invite_note ? <blockquote className="border-l-2 border-accent pl-3 text-ink">{invite.invite_note}</blockquote> : null}
      <p>Check your details below. After you send them we email you a link to confirm. Details from declined requests are deleted after 90 days.</p>
    </div>}
    primary={{ label: "Send request", pending: submit.isPending, pendingLabel: "Sending…",
      onClick: () => (document.getElementById(FORM_ID) as HTMLFormElement | null)?.requestSubmit() }}
    content={<form id={FORM_ID} className="grid gap-5" onSubmit={(event) => {
      event.preventDefault();
      if (submit.isPending) return;
      const join = Boolean(org) && choice === "join";
      submit.mutate({ ...hostingRequestBody(form, { includeOrganization: !join }), token, organization_choice: join ? "join" : "own" });
    }}>
      <HostingRequestFields value={form} onChange={set} errors={errors} showOrganizationName={false} />
      {org ? <fieldset className="grid gap-3">
        <legend className="mb-2 text-sm font-semibold text-ink">Who owns the space</legend>
        <label className="flex min-h-11 items-start gap-3 rounded-xl border border-line p-4 text-sm has-checked:border-accent has-checked:bg-accent-soft">
          <input type="radio" name="organization_choice" value="join" checked={choice === "join"} onChange={() => setChoice("join")} aria-describedby="hosting-join-help" />
          <span><span className="font-semibold text-ink">Join {org}</span>
            <span id="hosting-join-help" className="mt-1 block text-muted">Your space would be owned by {org}, and its managers could help run it. The platform team confirms the final setup.</span></span>
        </label>
        <label className="flex min-h-11 items-center gap-3 rounded-xl border border-line p-4 text-sm font-semibold text-ink has-checked:border-accent has-checked:bg-accent-soft">
          <input type="radio" name="organization_choice" value="own" checked={choice === "own"} onChange={() => setChoice("own")} />
          Create my own organization
        </label>
        {errors.organization_choice ? <p className="text-xs text-danger">{errors.organization_choice}</p> : null}
        {choice === "own" ? organizationName : null}
      </fieldset> : organizationName}
      {submit.error ? <p role="alert" className="text-sm text-danger">{hostingErrorText(submit.error, EXPIRED)}</p> : null}
      <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
    </form>} />;
}
