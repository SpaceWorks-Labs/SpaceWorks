import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../../../components/layouts";
import { ConfirmDialog, ListRow, OverflowMenu, RelativeTime, StatusPill } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import type { MachineServiceRequest } from "../../../../generated/api";
import { staffRequest } from "../../../../lib/api";
import { ChargeSettle } from "../../areaPayments/ChargeSettle";
import { useStaffGet } from "../shared";
import { HandoverCollectDialog } from "./HandoverCollectDialog";

type Props = { makerspaceId: number; enabled: boolean };
/** `job_policy.UNCOLLECTED_AFTER_DAYS`: from day 14 a finished job may be marked Not collected. */
const UNCOLLECTED_AFTER_MS = 14 * 86_400_000;
const requester = (row: MachineServiceRequest) => row.requester_name || row.requester?.username || t`Unknown requester`;
const paymentInfo = (payment: MachineServiceRequest["payment"]) => {
  if (!payment) return null;
  const paid = ["paid_online", "paid_offline", "waived"].includes(payment.status ?? "");
  return { paid, label: payment.status === "waived" ? t`Waived` : (paid ? t`Paid ${payment.currency.toUpperCase()} ${payment.amount}` : t`Unpaid ${payment.currency.toUpperCase()} ${payment.amount}`).trim() };
};

/** The API remains the authority for collection permission and makerspace scope. */
export function HandoverConsole({ makerspaceId, enabled }: Props) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [collecting, setCollecting] = useState<MachineServiceRequest | null>(null);
  const [uncollected, setUncollected] = useState<MachineServiceRequest | null>(null);
  const queryKey = ["machine-service-handover", makerspaceId];
  const waiting = useStaffGet<MachineServiceRequest[]>(queryKey,
    `/admin/makerspaces/${makerspaceId}/machine-service/requests?status=completed`, enabled);
  const refresh = () => { void queryClient.invalidateQueries({ queryKey }); };
  const markUncollected = useMutation({
    mutationFn: (id: number) => staffRequest(`/admin/machine-service/requests/${id}/uncollected`, { method: "POST", body: "{}" }),
    onSuccess: () => { setUncollected(null); toast(t`Marked not collected. The member has been told.`); refresh(); },
  });
  if (!enabled) return null;
  const rows = waiting.data ?? [];
  const shown = rows.filter(row => requester(row).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  const now = Date.now();
  return <ListLayout standalone={false}
    header={{ title: t`Ready to collect`, subtitle: t`Finished jobs waiting for their owners.` }}
    state={{ status: waiting.isLoading ? "loading" : waiting.isError ? "error" : "ready", error: t`Couldn't load finished jobs. Try again.`, onRetry: () => void waiting.refetch() }}
    stats={[{ label: t`Waiting`, value: rows.length }, { label: t`Unpaid`, value: rows.filter(row => paymentInfo(row.payment)?.paid === false).length }]}
    filters={{ search: { label: t`Search by requester`, value: search, onChange: setSearch } }}
    isEmpty={!shown.length} empty={{ message: t`Nothing waiting. Finished jobs show up here for handover.` }}
    filteredEmpty={{ message: t`No jobs match this requester. Try another name.`, action: { label: t`Clear search`, onClick: () => setSearch("") } }}
    body={{ kind: "rows", rows: shown.map(row => {
      const payment = paymentInfo(row.payment);
      const late = row.completed_at ? now - Date.parse(row.completed_at) >= UNCOLLECTED_AFTER_MS : false;
      return <ListRow key={row.id} title={row.title}
        identity={{ kind: "avatar", name: requester(row), seed: String(row.requester?.id ?? requester(row)) }}
        meta={<span className="grid gap-2"><span>{requester(row)}{row.machine?.name ? ` · ${row.machine.name}` : ""}{row.completed_at ? <> {t` · finished `}<RelativeTime date={row.completed_at} exact /></> : null}</span>
          {payment ? <StatusPill label={payment.label} tone={payment.paid ? "success" : "warn"} /> : null}
          <ChargeSettle makerspaceId={makerspaceId} charge={row.payment} invalidateKeys={[queryKey]} /></span>}
        right={<span className="flex flex-wrap items-center gap-2">
          <button type="button" className="desk-button" onClick={() => setCollecting(row)}>{t`Hand over`}</button>
          {late ? <OverflowMenu label={t`More for ${row.title}`} actions={[{ label: t`Mark not collected`, tone: "danger", onClick: () => setUncollected(row) }]} /> : null}
        </span>} />;
    }) }}
    detail={<>
      {markUncollected.error ? <p role="alert" className="text-sm text-danger">{markUncollected.error.message}</p> : null}
      {collecting ? <HandoverCollectDialog job={collecting} makerspaceId={makerspaceId} onClose={() => setCollecting(null)}
        onDone={() => { toast(t`Handed to ${requester(collecting)}.`); setCollecting(null); refresh(); }} /> : null}
      <ConfirmDialog open={uncollected !== null} title={t`Mark not collected?`} tone="danger" confirmLabel={t`Mark not collected`}
        pending={markUncollected.isPending}
        message={t`The member did not pick this job up within 14 days. It leaves the pickup shelf and the member is told.`}
        onCancel={() => { setUncollected(null); markUncollected.reset(); }} onConfirm={() => { if (uncollected) markUncollected.mutate(uncollected.id); }} />
    </>}
  />;
}
