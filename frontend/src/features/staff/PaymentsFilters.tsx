import { SegmentedControl } from "../../components/ui";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { DUE_OPTIONS } from "./PaymentDueBadge";
import { PAYMENT_SUBJECTS } from "./paymentsApi";

/** `eventOnly`: an Event Manager without finance actions sees event registrations only, so
 * the subject picker and the finance-gated saved views are left out rather than 403ing. */
export function PaymentsFilters({ list, makerspaceId, eventOnly = false }: { list: ReturnType<typeof useUrlListState>; makerspaceId: number; eventOnly?: boolean }) {
  const controls = <ListViewControls state={list} makerspaceId={makerspaceId} entity="payments" search={false} savedViews={!eventOnly}
    sorts={[["due_at", "Due date"], ["-due_at", "Due date descending"], ["-created_at", "Newest"], ["created_at", "Oldest"], ["amount", "Amount ascending"], ["-amount", "Amount descending"]]}
    activeCount={eventOnly ? 0 : Number(Boolean(list.values.subject_type))} controls={eventOnly ? undefined :
    <label className="grid gap-1 text-sm text-muted">Subject
      <select className="desk-input" value={list.values.subject_type} onChange={event => list.setFilter("subject_type", event.target.value)}>
        <option value="">All subjects</option>
        {PAYMENT_SUBJECTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>} />;
  // "Overdue" is a frequent desk filter, so the due-date control stays on the To collect toolbar.
  if (list.values.status !== "pending") return controls;
  return <div className="grid min-w-0 gap-3">
    {controls}
    <SegmentedControl label="Due" value={list.values.due_state}
      options={[["", "All due dates"], ...DUE_OPTIONS].map(([value, label]) => ({ value, label }))}
      onChange={value => list.update({ due_state: value })} />
  </div>;
}
