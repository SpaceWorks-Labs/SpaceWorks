import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";

import { ActionControl, EmptyState, ErrorText, Field, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../components/ui";
import type { Tone } from "../../components/ui";
import {
  useCancelHostingInvitation,
  useCreateHostingInvitation,
  useHostingAvailability,
  useHostingInvitations,
  type HostingInvitation,
  type HostingInvitationCreated,
  type HostingScope,
} from "../hosting/hostingApi";

const PAGE_SIZE = 24;
const EMPTY = { invitee_email: "", space_name: "", note: "" };
const STATUS: Record<HostingInvitation["display_status"], { label: string; tone: Tone }> = {
  invited: { label: t`Invited`, tone: "accent" },
  pending_verification: { label: t`Confirming email`, tone: "warn" },
  submitted: { label: t`In review`, tone: "info" },
  accepted: { label: t`Accepted`, tone: "success" },
  rejected: { label: t`Not accepted`, tone: "danger" },
  withdrawn: { label: t`Withdrawn`, tone: "neutral" },
  expired: { label: t`Expired`, tone: "neutral" },
};

function cancellable(invitation: HostingInvitation) {
  return invitation.display_status !== "expired" && (invitation.status === "invited" || invitation.status === "pending_verification");
}

/** Staff invite another makerspace to managed hosting. The link is shown once, from the create response only. */
export function HostingInvitations({ scope }: { scope: HostingScope }) {
  const available = useHostingAvailability();
  const [page, setPage] = useState(1);
  const [form, setForm] = useState(EMPTY);
  const [created, setCreated] = useState<HostingInvitationCreated | null>(null);
  const invitations = useHostingInvitations(scope, page, available);
  const create = useCreateHostingInvitation(scope);
  const cancel = useCancelHostingInvitation(scope);
  if (!available) return null;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (create.isPending) return;
    create.mutate({
      invitee_email: form.invitee_email.trim(),
      ...(form.space_name.trim() ? { space_name: form.space_name.trim() } : {}),
      ...(form.note.trim() ? { note: form.note.trim() } : {}),
    }, { onSuccess: (invitation) => { setCreated(invitation); setForm(EMPTY); } });
  }
  const set = (key: keyof typeof EMPTY, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const data = invitations.data;
  return (
    <section className="rounded-xl border border-line bg-bg p-4" aria-labelledby="hosting-invitations-heading">
      <h3 className="title-section" id="hosting-invitations-heading">{t`Hosting invitations`}</h3>
      <p className="mt-1 text-sm text-muted">{t`Invite another makerspace to request hosting on Space Works. The platform team reviews every request.`}</p>
      <form className="mt-4 grid gap-4" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t`Their email`}>
            <input className="desk-input" type="email" required maxLength={254} autoComplete="off" value={form.invitee_email} onChange={(event) => set("invitee_email", event.target.value)} />
          </Field>
          <Field label={t`Space name (optional)`}>
            <input className="desk-input" maxLength={200} value={form.space_name} onChange={(event) => set("space_name", event.target.value)} />
          </Field>
        </div>
        <Field label={t`Note (optional)`} hint={`${form.note.length}/500 · Included in the invitation.`}>
          <textarea className="desk-input min-h-20" maxLength={500} value={form.note} onChange={(event) => set("note", event.target.value)} />
        </Field>
        <button className="desk-button-primary w-fit" type="submit" disabled={create.isPending}>{create.isPending ? t`Sending…` : t`Send invitation`}</button>
        {create.error ? <p className="text-sm text-danger" role="alert">{create.error.message}</p> : null}
      </form>
      {created ? <div className="mt-4 rounded-xl border border-success bg-success-soft p-4 text-success-ink" role="status">
        <p className="font-semibold">{t`Copy this link now. It won't be shown again.`}</p>
        <p className="mt-1 break-all code-text text-xs">{created.invite_url}</p>
        <ul className="mt-2 grid gap-1 text-sm">
          <li>{created.delivery_status === "sent" ? t`Email sent` : created.delivery_status === "pending" || created.delivery_status === "sending" ? t`Email queued. It is being sent now` : t`Email could not be sent — share the link yourself`}</li>
          <li>{created.join_offered ? t`They can join your organization` : t`They'll create their own organization`}</li>
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="desk-button" type="button" onClick={() => { void navigator.clipboard?.writeText(created.invite_url); }}>{t`Copy link`}</button>
          <button className="desk-button" type="button" onClick={() => setCreated(null)}>{t`Done`}</button>
        </div>
      </div> : null}

      {invitations.isLoading ? <Skeleton className="mt-5 h-24 w-full" /> : null}
      {invitations.isError ? <ErrorText resource={t`hosting invitations`} onRetry={() => { void invitations.refetch(); }} /> : null}
      {cancel.error ? <ErrorText message={cancel.error.message} /> : null}
      {data && !data.results.length ? <EmptyState message={t`No hosting invitations yet.`} /> : null}
      {data?.results.length ? <div className="mt-5 grid gap-3">{data.results.map((invitation) => {
        const status = STATUS[invitation.display_status] ?? { label: invitation.display_status, tone: "neutral" as const };
        return <ListRow key={invitation.id} title={invitation.space_name || t`Makerspace invitation`}
          identity={{ kind: "icon", icon: "Building2", tone: "accent" }}
          meta={<>{t`Sent `}<RelativeTime date={invitation.created_at} />{invitation.invite_expires_at ? <> {t` · Link expires `}<RelativeTime date={invitation.invite_expires_at} /></> : null}</>}
          right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={status.label} tone={status.tone} />
            {cancellable(invitation) ? <ActionControl action={{ label: t`Cancel invitation`, tone: "danger", disabled: cancel.isPending, disabledReason: t`Wait for the current cancellation.`,
              confirm: { title: t`Cancel this invitation?`, message: t`The link stops working. Send a new invitation if they still want to host here.`, confirmLabel: t`Cancel invitation` },
              onClick: () => cancel.mutate(invitation.id) }} /> : null}</div>} />;
      })}</div> : null}
      {data && data.count > PAGE_SIZE ? <div className="mt-3"><Pagination page={page} totalPages={Math.ceil(data.count / PAGE_SIZE)}
        onChange={setPage} count={data.count} pageSize={PAGE_SIZE} /></div> : null}
    </section>
  );
}
