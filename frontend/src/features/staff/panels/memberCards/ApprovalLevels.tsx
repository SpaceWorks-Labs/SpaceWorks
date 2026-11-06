// Design approval levels for this space (#136): the space level and each organisation, for
// member and programme cards and for event cards and tickets. The most specific level wins:
// event, then programme, then organisation, then space. Programme and event levels are set on
// the programme and the event.
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorBlock, Skeleton } from "../../../../components/ui";
import { staffRequest } from "../../../../lib/api";
import { ApprovalLevelSelect, type ApprovalValue } from "../../../cards/ApprovalLevelSelect";

type Group = "membership" | "event";
type Levels = {
  groups: { group: Group; available: boolean; default: boolean; space: ApprovalValue }[];
  organisations: { id: number; name: string; membership: ApprovalValue; event: ApprovalValue }[];
};
const GROUP_LABELS: Record<Group, string> = { membership: t`Member and programme cards`, event: t`Event cards and tickets` };

export function useApprovalLevels(makerspaceId: number) {
  const client = useQueryClient();
  const key = ["card-approval-levels", makerspaceId];
  const path = `/admin/makerspaces/${makerspaceId}/card-approval-levels`;
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<Levels>(path) });
  const save = useMutation({
    mutationFn: (input: { group: Group; organization_id?: number; required: ApprovalValue }) =>
      staffRequest<Levels>(path, { method: "PUT", body: JSON.stringify(input) }),
    onSuccess: (levels) => {
      client.setQueryData(key, levels);
      void client.invalidateQueries({ queryKey: ["member-card-settings", makerspaceId] });
      void client.invalidateQueries({ queryKey: ["card-design"] });
    },
  });
  return { query, save };
}

export function ApprovalLevels({ makerspaceId }: { makerspaceId: number }) {
  const { query, save } = useApprovalLevels(makerspaceId);
  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError || !query.data) return <ErrorBlock error={query.error} resource="approval levels" onRetry={() => void query.refetch()} />;
  const groups = query.data.groups.filter((row) => row.available);
  const spaceValue = (group: Group) => {
    const row = groups.find((item) => item.group === group)!;
    return row.space ?? row.default;
  };
  return <section className="grid gap-3 rounded-control border border-line bg-panel p-3" aria-labelledby="approval-levels-title">
    <div className="grid gap-1">
      <h3 id="approval-levels-title" className="text-sm font-semibold text-ink">{t`Design approval`}</h3>
      <p className="text-xs text-muted">{t`Space Managers' own edits always publish. For everyone else, the most specific setting wins: an event, then a programme, then an organisation, then this space.`}</p>
    </div>
    {save.error ? <ErrorBlock error={save.error} /> : null}
    <div className="grid gap-3 sm:grid-cols-2">
      {groups.map((row) => <ApprovalLevelSelect key={row.group} label={t`${GROUP_LABELS[row.group]}, this space`}
        value={row.space} inherited={row.default} inheritLabel="Built-in default" disabled={save.isPending}
        onChange={(required) => save.mutate({ group: row.group, required })} />)}
    </div>
    {query.data.organisations.length && groups.length ? <div className="grid gap-2">
      <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">{t`Organisations`}</h4>
      <ul className="grid gap-2">
        {query.data.organisations.map((org) => <li key={org.id} className="grid gap-2 rounded-control border border-line p-3">
          <span className="text-sm font-semibold text-ink">{org.name}</span>
          <div className="grid gap-2 sm:grid-cols-2">
            {groups.map((row) => <ApprovalLevelSelect key={row.group} label={GROUP_LABELS[row.group]} value={org[row.group]}
              inherited={spaceValue(row.group)} inheritLabel="Follow this space" disabled={save.isPending}
              onChange={(required) => save.mutate({ group: row.group, organization_id: org.id, required })} />)}
          </div>
        </li>)}
      </ul>
    </div> : <p className="text-xs text-muted">{t`No organisation works with this space yet, so only the space level applies.`}</p>}
    <p className="sr-only" aria-live="polite">{save.isSuccess ? t`Approval setting saved.` : ""}</p>
    {groups.length === 0 ? <p className="text-xs text-muted">{t`Card designs are switched off here.`}</p> : null}
  </section>;
}
