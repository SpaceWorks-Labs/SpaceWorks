import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { UnitPicker } from "./UnitPicker";
import { unitErrorText, unitKeys, unitsApi } from "./unitsApi";
import { BoxArt } from "../../../components/BoxSpinner";

/** Off switch, no `manage_member_units`, or a row outside the caller's reach: the server says 404/403. */
const hidden = (error: unknown) => error instanceof StructuredApiError && [403, 404].includes(error.status);

/**
 * Confine one staff member to a unit and the units beneath it (`membership.unit_scoped_staff`). Their
 * member register, roster, join requests, renewals and reports narrow to that subtree. It narrows only
 * this space's role; organization grants and the platform administrator are never limited. Rendered
 * only when the server answers, so a space without the switch shows nothing.
 */
export function StaffUnitScopeField({ makerspaceId, membershipId, name }: { makerspaceId: number; membershipId: number; name: string }) {
  const client = useQueryClient();
  const key = unitKeys.staffScope(makerspaceId, membershipId);
  const scope = useQuery({ queryKey: key, queryFn: () => unitsApi.staffScope(makerspaceId, membershipId), retry: false });
  const [choice, setChoice] = useState<number | null | undefined>(undefined);
  const save = useMutation({
    mutationFn: (unitId: number | null) => unitsApi.setStaffScope(makerspaceId, membershipId, unitId),
    onSuccess: data => { client.setQueryData(key, data); setChoice(undefined); },
  });
  if (scope.isPending || hidden(scope.error)) return null;
  const current = scope.data?.unit?.id ?? null;
  const value = choice === undefined ? current : choice;
  return <section aria-labelledby={`unit-scope-${membershipId}`} className="grid gap-3 border-t border-line pt-4">
    <div className="grid gap-1">
      <h3 id={`unit-scope-${membershipId}`} className="title-section">{t`Unit limit`}</h3>
      <p className="text-sm text-muted">{t`Limit ${name} to one unit and everything beneath it. Their member lists, join requests, renewals and reports show only those members. Organization access is never limited.`}</p>
    </div>
    {scope.isError ? <ErrorText message={unitErrorText(scope.error)} onRetry={() => void scope.refetch()} /> : <>
      <UnitPicker makerspaceId={makerspaceId} value={value} label={t`Limited to`} noneLabel={t`The whole space (no limit)`}
        disabled={save.isPending} onChange={next => { save.reset(); setChoice(next); }} />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="desk-button min-h-11" disabled={save.isPending || value === current} onClick={() => save.mutate(value)}>
          {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save unit limit`}</button>
        {save.isSuccess ? <span role="status" className="text-sm text-muted">
          {save.data.unit ? t`${name} now works only with ${save.data.unit.name}.` : t`${name} works with the whole space again.`}</span> : null}
      </div>
      {save.error ? <ErrorText message={unitErrorText(save.error)} /> : null}
    </>}
  </section>;
}
