import { t } from "@lingui/core/macro";
import { SegmentedControl } from "../../components/ui";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { DUE_OPTIONS } from "./PaymentDueBadge";
import { PAYMENT_SUBJECTS } from "./paymentsApi";
import { areaLabel, type AreaKey } from "./areaPayments/areaPaymentsApi";

/** `eventOnly`: an area manager without finance actions reads their own-area queue, so the subject
 * picker and the finance-gated saved views are left out rather than 403ing. `areas`: the areas the
 * caller may filter by (decision 241/242), shown when there is more than one. */
export function PaymentsFilters({ list, makerspaceId, eventOnly = false, areas }: {
  list: ReturnType<typeof useUrlListState>; makerspaceId: number; eventOnly?: boolean; areas?: readonly AreaKey[];
}) {
  const areaPicker = areas && areas.length > 1 ? <label className="grid gap-1 text-sm text-muted">{t`Area`}
    <select className="desk-input" value={list.values.area ?? ""} onChange={event => list.setFilter("area", event.target.value)}>
      <option value="">{t`All areas`}</option>
      {areas.map(key => <option key={key} value={key}>{areaLabel(key)}</option>)}
    </select>
  </label> : null;
  const controls = <ListViewControls state={list} makerspaceId={makerspaceId} entity="payments" search={false} savedViews={!eventOnly}
    sorts={[["due_at", "Due date"], ["-due_at", "Due date descending"], ["-created_at", "Newest"], ["created_at", "Oldest"], ["amount", "Amount ascending"], ["-amount", "Amount descending"]]}
    activeCount={(eventOnly ? 0 : Number(Boolean(list.values.subject_type))) + Number(Boolean(list.values.area))} controls={eventOnly ? areaPicker ?? undefined :
    <>{areaPicker}<label className="grid gap-1 text-sm text-muted">{t`Subject`}<select className="desk-input" value={list.values.subject_type} onChange={event => list.setFilter("subject_type", event.target.value)}>
        <option value="">{t`All subjects`}</option>
        {PAYMENT_SUBJECTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label></>} />;
  // "Overdue" is a frequent desk filter, so the due-date control stays on the To collect toolbar.
  if (list.values.status !== "pending") return controls;
  return <div className="grid min-w-0 gap-3">
    {controls}
    <SegmentedControl label={t`Due`} value={list.values.due_state}
      options={[["", t`All due dates`], ...DUE_OPTIONS].map(([value, label]) => ({ value, label }))}
      onChange={value => list.update({ due_state: value })} />
  </div>;
}
