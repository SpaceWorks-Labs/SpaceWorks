import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { AuthUserPayload } from "../../../generated/api";
import { ErrorBlock } from "../../../components/ui";
import type { StaffEvent } from "../eventsApi";
import type { eventAccess } from "../eventStaffPermissions";
import { sessionScope } from "./sessionScope";
import { ClaimReceiptPreview } from "./ClaimReceiptPreview";
import { StageFormsManager, StageFormBuilder, StageAssignments, StageActivation, StageMilestones, StageResponseDetail } from "../eventStageForms";
import { ReimbursementRequests, ReimbursementClaims, ClaimReview, ReimbursementProgramme } from "../eventReimbursements";

type StageView = { kind: "list" } | { kind: "builder"; id?: number } | { kind: "activate"; id: number }
  | { kind: "assignments" } | { kind: "shortlist" } | { kind: "response"; id: number; finance: boolean };
type SupportView = { kind: "requests" } | { kind: "claims" } | { kind: "claim"; id: number } | { kind: "programme" };

/**
 * Stage forms (Events core) and travel support (the event_reimbursements add-on) inside the
 * event drawer. The actions offered here only shape the screen: every list and command is
 * authorized again by the API for this exact event, and finance views need VIEW_FINANCE.
 */
export function EventAddonPanel({ event, makerspaceId, section, access }: {
  event: StaffEvent; makerspaceId: number; section: "stage-forms" | "reimbursements"; access: ReturnType<typeof eventAccess>;
}) {
  const account = useQuery({ queryKey: ["event-addon-actor", ...sessionScope()], queryFn: () => staffRequest<AuthUserPayload>("/auth/me"),
    gcTime: 0, retry: false });
  if (account.error) return <ErrorBlock error={account.error} />;
  if (!account.data) return <p role="status">{t`Loading your event access…`}</p>;
  const scope = { actorId: account.data.id, makerspaceId, eventId: event.id };
  return section === "stage-forms" ? <StagePanel scope={scope} event={event} access={access} /> : <SupportPanel scope={scope} />;
}

type Scope = { actorId: number; makerspaceId: number; eventId: number };

function Back({ onClick, label }: { onClick: () => void; label: string }) {
  return <button type="button" className="desk-button mb-4 justify-self-start" onClick={onClick}>{label}</button>;
}

function StagePanel({ scope, event, access }: { scope: Scope; event: StaffEvent; access: ReturnType<typeof eventAccess> }) {
  const [view, setView] = useState<StageView>({ kind: "list" });
  const list = () => setView({ kind: "list" });
  const authoring = access.edit ? ["stage_create"] : [];
  if (view.kind === "builder") return <div className="grid gap-2"><Back onClick={list} label={t`All stage forms`} />
    <StageFormBuilder scope={scope} stageFormId={view.id} allowedActions={authoring} onCreated={id => setView({ kind: "builder", id })} />
    {view.id ? <button type="button" className="desk-button justify-self-start" onClick={() => setView({ kind: "activate", id: view.id! })}>{t`Activate for participants`}</button> : null}</div>;
  if (view.kind === "activate") return <div className="grid gap-2"><Back onClick={() => setView({ kind: "builder", id: view.id })} label={t`Back to stage form`} />
    <StageActivation scope={scope} stageFormId={view.id} /></div>;
  if (view.kind === "assignments") return <div className="grid gap-2"><Back onClick={list} label={t`All stage forms`} />
    <StageAssignments scope={scope} onResponse={(id, finance) => setView({ kind: "response", id, finance })} /></div>;
  if (view.kind === "response") return <div className="grid gap-2"><Back onClick={() => setView({ kind: "assignments" })} label={t`All assignments`} />
    <StageResponseDetail scope={scope} responseId={view.id} finance={view.finance} /></div>;
  // The shortlist command is compare-and-set on the event's own version.
  const eventVersion = (event as StaffEvent & { version?: number }).version;
  if (view.kind === "shortlist") return <div className="grid gap-2"><Back onClick={list} label={t`All stage forms`} />
    {eventVersion === undefined ? <p role="alert">{t`Reload the event before publishing a shortlist.`}</p> : <StageMilestones scope={scope} eventVersion={eventVersion}
      allowedActions={access.registrations || access.applications ? ["stage_shortlist"] : []} />}</div>;
  return <div className="grid gap-4">
    <StageFormsManager scope={scope} allowedActions={authoring} onCreate={() => setView({ kind: "builder" })}
      onEdit={id => setView({ kind: "builder", id })} onAssignments={() => setView({ kind: "assignments" })} />
    {access.registrations || access.applications
      ? <button type="button" className="desk-button justify-self-start" onClick={() => setView({ kind: "shortlist" })}>{t`Publish shortlist`}</button> : null}
  </div>;
}

function SupportPanel({ scope }: { scope: Scope }) {
  const [view, setView] = useState<SupportView>({ kind: "requests" });
  const [receipt, setReceipt] = useState<number | null>(null);
  const tabs: { key: SupportView["kind"]; label: string }[] = [
    { key: "requests", label: t`Requests` }, { key: "claims", label: t`Claims` }, { key: "programme", label: t`Programme and budget` },
  ];
  return <div className="grid gap-4">
    <div className="flex flex-wrap gap-2" role="group" aria-label={t`Travel support views`}>
      {tabs.map(tab => <button key={tab.key} type="button" className="desk-button" aria-pressed={view.kind === tab.key || (tab.key === "claims" && view.kind === "claim")}
        onClick={() => setView({ kind: tab.key } as SupportView)}>{tab.label}</button>)}
    </div>
    {view.kind === "requests" ? <ReimbursementRequests scope={scope} /> : null}
    {view.kind === "claims" ? <ReimbursementClaims scope={scope} onOpen={id => setView({ kind: "claim", id })} /> : null}
    {view.kind === "claim" ? <ClaimReview scope={scope} claimId={view.id} onReceipt={setReceipt} /> : null}
    {view.kind === "claim" && receipt !== null
      ? <ClaimReceiptPreview key={receipt} scope={scope} assetId={receipt} onClose={() => setReceipt(null)} /> : null}
    {view.kind === "programme" ? <ReimbursementProgramme scope={scope} /> : null}
  </div>;
}
