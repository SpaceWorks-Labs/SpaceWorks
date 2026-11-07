import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../../components/ui";
import { memberRequest } from "../../lib/api";
import { refreshOrganizationAuthority } from "../organizations/refreshOrganizationAuthority";
import { eventErrorText } from "../staff/eventUi";

export function OrganizationLeaveCard({ organizationId, name, version, onLeft }: { organizationId: number; name: string; version: number; onLeft?: () => void }) {
  const [confirmed, setConfirmed] = useState(false);
  const operation = useRef(crypto.randomUUID());
  const client = useQueryClient();
  const leave = useMutation({ mutationFn: () => memberRequest<{ organization_id: number; state: "left"; allowed_actions: string[] }>(`/member/organizations/${organizationId}/leave/`, { method: "POST", headers: { "Idempotency-Key": operation.current }, body: JSON.stringify({ operation_id: operation.current, expected_version: version }) }),
    onSuccess: async () => { await refreshOrganizationAuthority(client); onLeft?.(); } });
  return <Card><section className="grid gap-3" aria-label={t`Leave ${name}`}><h2 className="title-section">{t`Leave ${name}`}</h2><p className="text-sm text-muted">{t`Your organization access will end immediately. A sole active owner must appoint another owner before leaving. A recent identity check may be required.`}</p>
    {leave.isSuccess ? <p role="status" className="text-sm">{t`You have left ${name}.`}</p> : <><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />{t`I understand that my organization access will end`}</label><button className="desk-button-danger-outline justify-self-start" type="button" disabled={!confirmed || leave.isPending} onClick={() => leave.mutate()}>{leave.isPending ? t`Leaving…` : t`Leave organization`}</button></>}
    {leave.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(leave.error)}</p> : null}
  </section></Card>;
}
