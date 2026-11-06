import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../../../components/layouts";
import { Callout, ListRow, RelativeTime, StatusPill } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import type { MachineServiceRequest } from "../../../../generated/api";
import { staffRequest } from "../../../../lib/api";
import { useStaffGet } from "../shared";

type Props = { makerspaceId: number; enabled: boolean };
const requester = (row: MachineServiceRequest) => row.requester_name || row.requester?.username || "Unknown requester";
const paymentInfo = (payment: MachineServiceRequest["payment"]) => {
  if (!payment) return null;
  const paid = ["paid_online", "paid_offline", "waived"].includes(payment.status ?? "");
  return { paid, label: payment.status === "waived" ? t`Waived` : `${paid ? "Paid" : "Unpaid"} ${payment.currency.toUpperCase()} ${payment.amount}`.trim() };
};

/** The API remains the authority for collection permission and makerspace scope. */
export function HandoverConsole({ makerspaceId, enabled }: Props) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const queryKey = ["machine-service-handover", makerspaceId];
  const waiting = useStaffGet<MachineServiceRequest[]>(queryKey,
    `/admin/makerspaces/${makerspaceId}/machine-service/requests?status=completed`, enabled);
  const collect = useMutation({
    mutationFn: (id: number) => staffRequest(`/admin/machine-service/requests/${id}/collect`, { method: "POST", body: "{}" }),
    onSuccess: (_result, id) => {
      const row = waiting.data?.find(value => value.id === id);
      toast(t`Handed to ${row ? requester(row) : "the requester"}.`);
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  if (!enabled) return null;
  const rows = waiting.data ?? [];
  const shown = rows.filter(row => requester(row).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  return <ListLayout standalone={false}
    header={{ title: t`Ready to collect`, subtitle: t`Finished jobs waiting for their owners.` }}
    state={{ status: waiting.isLoading ? "loading" : waiting.isError ? "error" : "ready", error: t`Couldn't load finished jobs. Try again.`, onRetry: () => void waiting.refetch() }}
    stats={[{ label: t`Waiting`, value: rows.length }, { label: t`Unpaid`, value: rows.filter(row => paymentInfo(row.payment)?.paid === false).length }]}
    filters={{ search: { label: t`Search by requester`, value: search, onChange: setSearch } }}
    isEmpty={!shown.length} empty={{ message: t`Nothing waiting. Finished jobs show up here for handover.` }}
    filteredEmpty={{ message: t`No jobs match this requester. Try another name.`, action: { label: t`Clear search`, onClick: () => setSearch("") } }}
    body={{ kind: "rows", rows: shown.map(row => {
      const payment = paymentInfo(row.payment);
      return <ListRow key={row.id} title={row.title}
        identity={{ kind: "avatar", name: requester(row), seed: String(row.requester?.id ?? requester(row)) }}
        meta={<span className="grid gap-2"><span>{requester(row)}{row.machine?.name ? ` · ${row.machine.name}` : ""}{row.completed_at ? <> {t` · finished `}<RelativeTime date={row.completed_at} exact /></> : null}</span>
          {payment ? <StatusPill label={payment.label} tone={payment.paid ? "success" : "warn"} /> : null}</span>}
        right={<button type="button" className="desk-button" disabled={collect.isPending} onClick={() => collect.mutate(row.id)}>{t`Hand over`}</button>} />;
    }) }}
    detail={collect.isError ? <Callout size="inline" tone="danger" lead="Couldn't mark that job collected. It may have been handed over already." /> : undefined}
  />;
}
