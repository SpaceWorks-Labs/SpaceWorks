import { SegmentedControl } from "../../components/ui";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { DUE_OPTIONS } from "./PaymentDueBadge";
import { PAYMENT_SUBJECTS } from "./paymentsApi";

export function PaymentsFilters({ list, makerspaceId }: { list: ReturnType<typeof useUrlListState>; makerspaceId: number }) {
  return <>
    {list.values.status === "pending" ? <SegmentedControl label="Due" value={list.values.due_state}
      options={[["", "All due dates"], ...DUE_OPTIONS].map(([value, label]) => ({ value, label }))}
      onChange={value => list.update({ due_state: value })} /> : null}
    <label className="grid gap-1 text-sm text-muted">Subject
      <select className="desk-input" value={list.values.subject_type} onChange={event => list.setFilter("subject_type", event.target.value)}>
        <option value="">All subjects</option>
        {PAYMENT_SUBJECTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
    <ListViewControls state={list} makerspaceId={makerspaceId} entity="payments" search={false}
      sorts={[["due_at", "Due date"], ["-due_at", "Due date descending"], ["-created_at", "Newest"], ["created_at", "Oldest"], ["amount", "Amount ascending"], ["-amount", "Amount descending"]]} />
  </>;
}
