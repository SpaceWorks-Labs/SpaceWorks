import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { isSurfaceOff, StructuredApiError } from "../../../lib/api";
import { UnitPicker } from "./UnitPicker";
import { unitErrorText, unitKeys, unitsApi } from "./unitsApi";

/**
 * Which unit one member belongs to (`PUT memberships/<mid>/unit`). A unit-scoped staff member is
 * offered only their own subtree, and the server refuses a unit outside it (`unit_scope_forbids`).
 * Archived units take no new members. Hidden while `membership.units` is off.
 */
export function MemberUnitField({ makerspaceId, membershipId }: { makerspaceId: number; membershipId: number }) {
  const client = useQueryClient();
  const key = unitKeys.memberUnit(makerspaceId, membershipId);
  const current = useQuery({ queryKey: key, queryFn: () => unitsApi.memberUnit(makerspaceId, membershipId), retry: false });
  const [choice, setChoice] = useState<number | null | undefined>(undefined);
  const save = useMutation({
    mutationFn: (unitId: number | null) => unitsApi.setMemberUnit(makerspaceId, membershipId, unitId),
    onSuccess: data => {
      client.setQueryData(key, data); setChoice(undefined);
      void client.invalidateQueries({ queryKey: ["membership-l4", makerspaceId, "register"] });
      void client.invalidateQueries({ queryKey: ["members", makerspaceId] });
    },
  });
  if (isSurfaceOff(current.error) || (current.error instanceof StructuredApiError && current.error.status === 403)) return null;
  if (current.isPending) return <p role="status" className="text-sm text-muted">{t`Loading unit…`}</p>;
  // Until the server can read the assignment back, the picker starts empty and saving replaces it.
  const known = current.isSuccess;
  const saved = current.data?.unit?.id ?? null;
  const value = choice === undefined ? saved : choice;
  return <div className="grid gap-2">
    <UnitPicker makerspaceId={makerspaceId} value={value} label={t`Unit`} noneLabel={t`No unit`} disabled={save.isPending}
      hint={known ? undefined : t`The current unit could not be read. Choosing one here replaces it.`}
      onChange={next => { save.reset(); setChoice(next); }} />
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button min-h-11" disabled={save.isPending || (known && value === saved) || choice === undefined}
        onClick={() => save.mutate(value)}>{save.isPending ? t`Saving…` : t`Save unit`}</button>
      {save.isSuccess ? <span role="status" className="text-sm text-muted">
        {save.data.unit ? t`Now in ${save.data.unit.name}.` : t`No longer in a unit.`}</span> : null}
    </div>
    {save.error ? <ErrorText message={unitErrorText(save.error)} /> : null}
  </div>;
}
