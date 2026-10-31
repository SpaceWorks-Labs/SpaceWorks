import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi, lifecycleKeys } from "../membershipLifecycleApi";
import { Panel } from "../panels/shared";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : "That did not work.");

/** The space's financial year (#71). Finance setting: only the Space Manager changes it. */
export function FinancialYearSetting({ makerspaceId, canEdit }: { makerspaceId: number; canEdit: boolean }) {
  const client = useQueryClient();
  const year = useQuery({ queryKey: lifecycleKeys.financialYear(makerspaceId), queryFn: () => lifecycleApi.financialYear(makerspaceId) });
  const save = useMutation({ mutationFn: (month: number) => lifecycleApi.setFinancialYear(makerspaceId, month),
    onSuccess: (data) => client.setQueryData(lifecycleKeys.financialYear(makerspaceId), data) });
  const data = year.data;
  return <Panel title="Financial year">
    <p className="mb-3 text-sm text-muted">Financial-year plans end when the year ends, and reports offer the year as a filter. Changing it never moves terms already sold.</p>
    {data ? <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-sm">Starts in
        <select className="desk-input max-w-full" value={data.financial_year_start_month} disabled={!canEdit || save.isPending}
          onChange={(event) => save.mutate(Number(event.target.value))}>
          {MONTHS.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}
        </select>
      </label>
      <p className="text-sm text-ink">This year: FY {data.current_label} ({new Date(data.current_start).toLocaleDateString()} – {new Date(data.current_end).toLocaleDateString()})</p>
    </div> : null}
    {year.error ?? save.error ? <p role="alert" className="mt-2 text-sm text-danger">{errorText(year.error ?? save.error)}</p> : null}
  </Panel>;
}
