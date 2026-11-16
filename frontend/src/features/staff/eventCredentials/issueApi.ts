import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../../lib/api";

export type IssueGroup = "attendance" | "participants" | "awards" | "roles";
export type PlannedRow = { subject_kind: "registration" | "role_assignment"; subject_id: number; kind: string;
  award_id: number | null; result_revision_id: number | null; name: string; kind_title: string; award?: string; reason?: string };
export type IssuePlan = { event_version: number; recipients: PlannedRow[]; skipped: PlannedRow[]; counts: Record<string, number> };
export type Batch = { id: number; state: string; total: number; completed: number; failures: { id: number; error_code: string }[] };
export type IssuedRow = { id: number; recipient_name: string; kind: string; kind_title: string; award: string; status: string;
  revision: number; issued_at: string; public_verification_enabled: boolean; revocation_reason: string };

const base = (eventId: number) => `/admin/events/${eventId}/certificates/`;
const subject = (row: PlannedRow) => ({ subject_kind: row.subject_kind, subject_id: row.subject_id, kind: row.kind,
  award_id: row.award_id, result_revision_id: row.result_revision_id });

export function useIssuePlan(eventId: number) {
  return useMutation({ mutationFn: (groups: IssueGroup[]) => staffRequest<IssuePlan>(`${base(eventId)}issue-plan/`,
    { method: "POST", body: JSON.stringify({ groups }) }) });
}

export function useSample(eventId: number) {
  return useMutation({ mutationFn: (row: PlannedRow) => staffRequestBlob(`${base(eventId)}issue-plan/sample.pdf`,
    { method: "POST", body: JSON.stringify(subject(row)) }) });
}

export function useIssue(eventId: number) {
  return useMutation({ mutationFn: ({ plan, publish }: { plan: IssuePlan; publish: boolean }) => {
    const operation = crypto.randomUUID();
    return staffRequest<Batch>(`${base(eventId)}bulk/`, { method: "POST", headers: { "Idempotency-Key": operation },
      body: JSON.stringify({ operation_id: operation, expected_version: plan.event_version, all_attended: false,
        subjects: plan.recipients.map(subject), confirmed_count: plan.recipients.length, publish_event_details: publish }) });
  } });
}

export function useBatch(eventId: number, batchId: number | null) {
  return useQuery({ queryKey: ["certificate-batch", eventId, batchId], enabled: batchId !== null, retry: false,
    queryFn: () => staffRequest<Batch>(`${base(eventId)}batches/${batchId}/`),
    refetchInterval: (query) => query.state.data?.state === "completed" || query.state.error ? false : 3000 });
}

export function useIssued(eventId: number, page: number, kind: string) {
  return useQuery({ queryKey: ["events", "credentials", eventId, "issued", page, kind],
    queryFn: () => staffRequest<{ count: number; next: string | null; previous: string | null; results: IssuedRow[] }>(
      `${base(eventId)}issued/?${new URLSearchParams({ page: String(page), ...(kind ? { kind } : {}) })}`) });
}

export async function savePng(eventId: number, row: IssuedRow) {
  const blob = await staffRequestBlob(`${base(eventId)}${row.id}/png/`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = `certificate-${row.id}.png`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
