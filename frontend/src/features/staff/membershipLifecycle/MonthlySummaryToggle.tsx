import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi, lifecycleKeys } from "../membershipLifecycleApi";
import { Panel } from "../panels/shared";

const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : "That did not work.");

/** X33: the monthly staff summary email. The Space Manager switches it on; each person may opt out. */
export function MonthlySummaryToggle({ makerspaceId, canManageMakerspace }: { makerspaceId: number; canManageMakerspace: boolean }) {
  const client = useQueryClient();
  const status = useQuery({ queryKey: lifecycleKeys.summary(makerspaceId), queryFn: () => lifecycleApi.summary(makerspaceId) });
  const save = useMutation({ mutationFn: (input: { enabled?: boolean; opted_out?: boolean }) => lifecycleApi.setSummary(makerspaceId, input),
    onSuccess: (data) => client.setQueryData(lifecycleKeys.summary(makerspaceId), data) });
  const data = status.data;
  const failure = status.error ?? save.error;
  return <Panel title="Monthly membership summary">
    <p className="mb-3 text-sm text-muted">On the first of each month, staff who manage members get last month's joins, lapses, renewals and open requests by email.</p>
    {data ? <div className="grid gap-3">
      {canManageMakerspace ? <label className="flex min-h-11 items-center gap-2 text-sm">
        <input className="h-4 w-4" type="checkbox" checked={data.enabled} disabled={save.isPending}
          onChange={(event) => save.mutate({ enabled: event.target.checked })} />Send the summary to staff
      </label> : <p className="text-sm">{data.enabled ? "The summary is on." : "The summary is off."}</p>}
      {data.enabled ? <label className="flex min-h-11 items-center gap-2 text-sm">
        <input className="h-4 w-4" type="checkbox" checked={!data.opted_out} disabled={save.isPending}
          onChange={(event) => save.mutate({ opted_out: !event.target.checked })} />Send it to me
      </label> : null}
      {data.next_run_at && data.enabled ? <p className="text-sm text-muted">Next: {new Date(data.next_run_at).toLocaleDateString()}</p> : null}
    </div> : null}
    {failure ? <p role="alert" className="mt-2 text-sm text-danger">{errorText(failure)}</p> : null}
  </Panel>;
}
