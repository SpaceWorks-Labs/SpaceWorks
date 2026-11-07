import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { staffRequest } from "../../../lib/api";
import { ActionDialog } from "./ActionDialog";
import { useHostingDecision, type ApproveBody, type ApproveResult, type HostingRequestRow } from "./onboardingApi";
import type { Page } from "./spacesApi";

const INVITATION = { sent: "The Space Manager invitation was emailed.", skipped: "No invitation was sent.",
  unavailable: "Email is not configured, so no invitation was sent." };

/** Approve creates the space, links it to its owner organization and (by default) invites the applicant as Space Manager. */
export function ApproveRequestDialog({ request, onClose }: { request: HostingRequestRow; onClose: () => void }) {
  const [name, setName] = useState(request.space_name);
  const [slug, setSlug] = useState(request.proposed_slug);
  const [owner, setOwner] = useState<"new" | "existing">("new");
  const [orgName, setOrgName] = useState(request.new_organization_name || request.space_name);
  const [orgId, setOrgId] = useState("");
  const [invite, setInvite] = useState(true);
  const organizations = useQuery({ queryKey: ["organizations", "platform-picker"], enabled: owner === "existing",
    queryFn: () => staffRequest<Page<{ id: number; name: string }>>("/admin/organizations/", {}, "platform") });
  const approve = useHostingDecision<ApproveResult>(request.id, "approve");
  const canSubmit = name.trim().length >= 2 && (owner === "new" ? orgName.trim().length >= 2 : Boolean(orgId));
  const submit = () => {
    const body: ApproveBody = { name: name.trim(), invite_manager: invite, ...(slug.trim() ? { slug: slug.trim() } : {}),
      ...(owner === "new" ? { new_organization_name: orgName.trim() } : { organization_id: Number(orgId) }) };
    approve.mutate(body, { onSuccess: (result) => { toast(t`${result.makerspace.name} was created. ${INVITATION[result.invitation]}`); onClose(); } });
  };
  return <ActionDialog title={t`Approve and create the space`} confirmLabel={t`Approve`} pending={approve.isPending} error={approve.error}
    canSubmit={canSubmit} onCancel={onClose} onSubmit={submit}
    message={t`Creates the space for ${request.applicant_name} (${request.applicant_email}).`}>
    <Field label={t`Space name`}><input className="desk-input" value={name} maxLength={200} onChange={event => setName(event.target.value)} /></Field>
    <Field label={t`Web address`} hint={t`Lowercase letters, numbers and hyphens. Leave empty to derive it from the name.`}>
      <input className="desk-input" value={slug} maxLength={50} autoCapitalize="none" spellCheck={false} onChange={event => setSlug(event.target.value)} />
    </Field>
    <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-semibold text-ink">{t`Owner organization`}</legend>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="radio" name="owner" checked={owner === "new"} onChange={() => setOwner("new")} />{t`A new organization`}</label>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="radio" name="owner" checked={owner === "existing"} onChange={() => setOwner("existing")} />{t`An existing organization`}</label>
    </fieldset>
    {owner === "new" ? <Field label={t`New organization name`}>
      <input className="desk-input" value={orgName} maxLength={200} onChange={event => setOrgName(event.target.value)} />
    </Field> : <Field label={t`Existing organization`} hint={organizations.isError ? t`Couldn't load organizations.` : undefined}>
      <select className="desk-input" value={orgId} onChange={event => setOrgId(event.target.value)}>
        <option value="">{organizations.isLoading ? t`Loading…` : t`Choose an organization`}</option>
        {(organizations.data?.results ?? []).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
    </Field>}
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={invite} onChange={event => setInvite(event.target.checked)} />{t`Email the applicant a Space Manager invitation`}</label>
  </ActionDialog>;
}
