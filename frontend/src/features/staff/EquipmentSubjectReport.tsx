import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useContext, useId, useState } from "react";

import { staffRequest, staffRequestBlob } from "../../lib/api";
import { capabilityOn } from "../../lib/features";
import { StaffListContext } from "./StaffListContext";
import { ReportTable, type ReportRows } from "./panels/OperationsReportsParts";

type Subject = { tenant: number; kind: "event" | "booking"; id: number };
type Report = "equipment" | "loan-timeline" | "consumables";

export function EquipmentSubjectReport(props: Subject) {
  const { actorId, actions, isSuperadmin, makerspace } = useContext(StaffListContext);
  const modules = makerspace?.enabled_modules;
  const domain = props.kind === "event" ? "events" : "bookings";
  if (!actorId || makerspace?.id !== props.tenant || !modules ||
      !["reports", domain].every(module => modules.includes(module)) ||
      !(isSuperadmin || actions?.includes("view_inventory") && actions.includes("view_audit"))) {
    return null;
  }
  // The containing workspace has already resolved this exact resource for viewing.
  // The report endpoint independently rechecks its resource and loan authority.
  const reports: Report[] = [];
  // Per-loan metrics, then the same loans' lifecycle milestones in time order.
  if (modules.includes("request_workflow")) reports.push("equipment", "loan-timeline");
  // Activity-attributed consumable use; stock itself stays in inventory.
  if (capabilityOn(makerspace, "inventory.consumables")) reports.push("consumables");
  return <>{reports.map(report => <EquipmentReport report={report}
    key={JSON.stringify([report, actorId, props.tenant, props.kind, props.id])}
    {...props} actorId={actorId} />)}</>;
}

function copy(report: Report) {
  if (report === "loan-timeline") return {
    show: t`View loan timeline`, hide: t`Hide loan timeline`,
    loading: t`Loading loan timeline…`, unavailable: t`The loan timeline is unavailable for your access.`,
    download: t`Download loan timeline CSV`, failed: t`The loan timeline could not be downloaded.`,
  };
  return report === "equipment" ? {
    show: t`View equipment report`, hide: t`Hide equipment report`,
    loading: t`Loading equipment report…`, unavailable: t`The equipment report is unavailable for your access.`,
    download: t`Download equipment CSV`, failed: t`The equipment report could not be downloaded.`,
  } : {
    show: t`View consumables report`, hide: t`Hide consumables report`,
    loading: t`Loading consumables report…`, unavailable: t`The consumables report is unavailable for your access.`,
    download: t`Download consumables CSV`, failed: t`The consumables report could not be downloaded.`,
  };
}

function EquipmentReport({ tenant, kind, id, actorId, report }: Subject & { actorId: number; report: Report }) {
  const [open, setOpen] = useState(false);
  const key = `${kind}-${report}`;
  const text = copy(report);
  const params = new URLSearchParams({ subject_kind: kind, subject_id: String(id) });
  const base = `/admin/makerspace/${tenant}`;
  const preview = useQuery({
    queryKey: [`${report}-subject-report`, actorId, tenant, kind, id],
    enabled: open, retry: false, gcTime: 0,
    queryFn: ({ signal }) => staffRequest<ReportRows>(`${base}/analytics/${key}?${params}`, { signal }),
  });
  const download = useMutation({
    mutationFn: () => staffRequestBlob(`${base}/reports/${key}/export?${params}&format=csv`),
  });
  function exportCsv() {
    download.mutate(undefined, { onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${key}.csv`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } });
  }
  const panelId = useId();
  return <section className="grid gap-2" data-replay-block>
    <button className="desk-button w-fit" type="button" aria-expanded={open} aria-controls={panelId}
      onClick={() => setOpen(value => !value)}>{open ? text.hide : text.show}</button>
    <div id={panelId} className="grid min-w-0 gap-2" hidden={!open}>{open ? <>
      {preview.isPending ? <p role="status">{text.loading}</p> : null}
      {preview.isError ? <p role="alert">{text.unavailable}</p> : null}
      {!preview.isError && !preview.isFetching && preview.data ? <>
        <ReportTable data={preview.data} />
        <button className="desk-button w-fit" type="button" disabled={download.isPending}
          onClick={exportCsv}>{text.download}</button>
      </> : null}
      {download.isError ? <p role="alert">{text.failed}</p> : null}
    </> : null}</div>
  </section>;
}
