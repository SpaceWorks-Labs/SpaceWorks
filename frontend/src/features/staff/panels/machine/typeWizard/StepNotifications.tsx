import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LogoLoader } from "../../../../../components/LogoLoader";
import { Badge } from "../../../../../components/ui";
import { staffRequest } from "../../../../../lib/api";
import { notificationEventLabel } from "../../../../notifications/notificationEventLabels";
import { RecipientTarget, type Draft } from "../../../NotificationRecipientEvent";
import { EMPTY_SCOPE, type RecipientRulesResponse } from "../../../notificationDestinationTypes";
import { bodyWithAdded, bodyWithout, eventRules, forType, offeredEvents, ruleLabel, type MACHINE_EVENTS } from "./typeNotificationRules";
import type { StepProps } from "./wizardTypes";

const FEATURES = (): Record<string, string> => ({ stock: t`Stock`, devices: t`Devices`, maintenance: t`Maintenance` });
const blank = (): Draft => ({ kind: "role", role_id: null, user_id: null, scope: EMPTY_SCOPE });
const ready = (draft: Draft) => draft.kind === "role" ? draft.role_id !== null : draft.kind === "user" ? draft.user_id !== null : true;

function EventRow({ item, data, typeId, suggested, save, pending }: {
  item: typeof MACHINE_EVENTS[number]; data: RecipientRulesResponse; typeId: number; suggested: boolean;
  save: (body: ReturnType<typeof bodyWithout>) => void; pending: boolean;
}) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const mine = eventRules(data, item.feature, item.event).filter(rule => forType(rule, typeId));
  const labels = { role: t`A role`, user: t`A named member`, members: t`All members`, requester: t`The person it is about` };
  return <li className="grid gap-2 rounded-lg border border-line p-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><strong className="min-w-0 break-words">{notificationEventLabel(item.event)}</strong>
      <span className="flex flex-wrap gap-1"><Badge tone="neutral">{FEATURES()[item.feature] ?? item.feature}</Badge>{suggested ? <Badge tone="info">{t`Suggested by the template`}</Badge> : null}</span></div>
    {mine.length ? <ul className="grid gap-1">{mine.map(rule => <li key={rule.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <span className="min-w-0 break-words">{ruleLabel(rule, data, labels)}</span>
      <button type="button" className="desk-button-danger min-h-11" disabled={pending} onClick={() => save(bodyWithout(data, item.feature, item.event, rule.id))}>{t`Remove`}</button></li>)}</ul>
      : <p className="text-sm text-muted">{t`No rule is narrowed to this machine type. The space-wide recipients still apply.`}</p>}
    {draft ? <div className="grid gap-2 rounded-md border border-line bg-bg p-3">
      <RecipientTarget data={data} index={0} rule={draft} rules={[draft]} update={next => setDraft(next[0] ?? blank())} />
      <div className="flex flex-wrap gap-2"><button type="button" className="desk-button-primary min-h-11" disabled={!ready(draft) || pending}
        onClick={() => save(bodyWithAdded(data, item.feature, item.event, typeId, { kind: draft.kind, role_id: draft.role_id, user_id: draft.user_id }))}>{t`Add for this type`}</button>
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => setDraft(null)}>{t`Cancel`}</button></div></div>
      : <div><button type="button" className="desk-button min-h-11" onClick={() => setDraft(blank())}>{t`Add a recipient`}</button></div>}
  </li>;
}

/** Step 10: who hears about this type's machine events, as recipient rules narrowed to the type (the existing per-event routing, no store of its own). */
export function StepNotifications({ ctx }: StepProps) {
  const typeId = ctx.machineType!.id;
  const client = useQueryClient();
  const path = `/admin/makerspace/${ctx.makerspaceId}/notification-recipient-rules`;
  const data = useQuery({ queryKey: ["notification-recipient-rules", ctx.makerspaceId], retry: false, queryFn: () => staffRequest<RecipientRulesResponse>(path) });
  const flags = ctx.prefill?.notifications ?? ctx.spec?.notifications;
  const save = useMutation({ mutationFn: (body: ReturnType<typeof bodyWithout>) => staffRequest<RecipientRulesResponse>(path, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["notification-recipient-rules", ctx.makerspaceId] }) });
  if (data.isLoading) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  if (data.isError || !data.data) return <p role="alert" className="text-sm text-danger">{data.error?.message}</p>;
  const events = offeredEvents(data.data);
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Choose who is told about machine events for this type. A rule added here is narrowed to this machine type; events with no rule keep their space-wide recipients.`}</p>
    {events.length ? <ul className="grid gap-2">{events.map(item => <EventRow key={`${item.feature}.${item.event}`} item={item} data={data.data} typeId={typeId}
      suggested={Boolean(item.suggestedBy && flags?.[item.suggestedBy])} save={body => save.mutate(body)} pending={save.isPending} />)}</ul>
      : <p className="text-sm text-muted">{t`None of the machine events can be routed here. The modules they belong to may be off.`}</p>}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
  </div>;
}
