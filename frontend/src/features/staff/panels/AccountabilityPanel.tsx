import { t } from "@lingui/core/macro";
import { useId, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ErrorBlock, ListRow, Modal, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { invalidateInventoryViews } from "../queryInvalidation";
import { type Makerspace, useStaffGet } from "./shared";
import type { AccountabilityResponse, Offender } from "./AccountabilityTypes";
import { ProblemReportCard } from "./ProblemReportCard";
import { ListLayout } from "../../../components/layouts";
import { opsQueryState, opsStatusLabel, useOpsTabs } from "../opsPresentation";

export function AccountabilityPanel({ makerspace, isSuperadmin }: { makerspace: Makerspace; isSuperadmin: boolean }) {
  const queryClient = useQueryClient();
  const restrictionFormId = useId();
  const [restrictionTarget, setRestrictionTarget] = useState<Pick<Offender, "requester_id" | "username"> | null>(null);
  const [restrictionReason, setRestrictionReason] = useState("");
  const report = useStaffGet<AccountabilityResponse>(["accountability", makerspace.id], `/admin/makerspace/${makerspace.id}/accountability`);
  const data = report.data;
  const anonymous = data?.anonymous_accountability;
  // An empty (or unknown) `section` param means every section, as before the redesign.
  const tabs = useOpsTabs("section", [
    { key: "all", label: t`All` },
    { key: "overdue", label: t`Overdue`, count: data?.overdue.length },
    { key: "problems", label: t`Problems`, count: data?.problem_reports.length },
    { key: "offenders", label: t`Repeat offenders`, count: data?.repeat_offenders.length },
    { key: "restricted", label: t`Restricted`, count: data?.restrictions.length },
  ], "all");
  const section = tabs.active;

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["accountability", makerspace.id] });
  };
  const refreshAfterTriage = () => {
    refresh();
    invalidateInventoryViews(queryClient, makerspace.id, makerspace.slug);
    queryClient.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
  };
  const restrict = useMutation({
    mutationFn: ({ userId, reason }: { userId: number; reason: string }) =>
      staffRequest(`/admin/users/${userId}/restrict`, {
        method: "POST",
        body: JSON.stringify({ status: "restricted", reason }),
      }),
    onSuccess: refresh,
  });
  const restore = useMutation({
    mutationFn: (userId: number) => staffRequest(`/admin/users/${userId}/restore-access`, { method: "POST" }),
    onSuccess: refresh,
  });
  const closeRestrictionDialog = () => {
    setRestrictionTarget(null);
    setRestrictionReason("");
  };
  const submitRestriction = (event: FormEvent) => {
    event.preventDefault();
    const target = restrictionTarget;
    const reason = restrictionReason.trim();
    closeRestrictionDialog();
    if (target && reason) restrict.mutate({ userId: target.requester_id, reason });
  };

  const counts = { overdue: data?.overdue.length ?? 0, problems: data?.problem_reports.length ?? 0,
    offenders: data?.repeat_offenders.length ?? 0, restricted: data?.restrictions.length ?? 0 };
  const hasAnonymous = Boolean(anonymous && anonymous.total_issues > 0);
  const selectedCount = section === "all" ? counts.overdue + counts.problems + counts.offenders + counts.restricted : counts[section as keyof typeof counts];
  // In the combined view only sections with something in them are drawn, each under its own heading.
  const on = (key: keyof typeof counts) => section === "all" ? counts[key] > 0 || (key === "offenders" && hasAnonymous) : section === key;
  const heading = (label: string) => section === "all" ? <h2 className="title-section mt-2">{label}</h2> : null;
  const empty = section === "all" ? "Nothing to follow up. No overdue loans, open problems or restrictions." : { overdue: "No overdue loans. Nice.", problems: "No open problem reports.",
    offenders: "No damage or loss on record against a named person.", restricted: "No one is restricted here." }[section]!;
  const status = (value: string) => <StatusPill label={opsStatusLabel(value)} tone={value === "active" ? "success" : "danger"} />;
  return <div onClickCapture={tabs.onClickCapture}>
    <ListLayout header={{ title: t`Accountability`, subtitle: t`Late, lost or damaged — and who it's tied to.` }}
      state={opsQueryState(report, "accountability")} tabs={tabs.tabs} activeTab={section}
      stats={[
        { label: t`Overdue loans`, value: data?.overdue.length ?? 0, href: tabs.href("overdue") },
        { label: t`Open problems`, value: data?.problem_reports.length ?? 0, href: tabs.href("problems") },
        { label: t`Repeat offenders`, value: data?.repeat_offenders.length ?? 0, href: tabs.href("offenders") },
        { label: t`Restricted`, value: data?.restrictions.length ?? 0, href: tabs.href("restricted") },
      ]} isEmpty={!selectedCount && !(["all", "offenders"].includes(section) && hasAnonymous)}
      empty={{ message: empty }} body={{ kind: "rows", rows: <>
        {on("overdue") ? <>{heading("Overdue loans")}{data?.overdue.map(row => <ListRow key={row.type + "-" + row.reference_id}
          title={row.label || "(unnamed)"} identity={{ kind: "avatar", name: row.requester_username, seed: row.requester_username }}
          meta={row.requester_username + " · " + (row.type === "direct" ? "Direct handout" : "Request")}
          right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={"Overdue " + row.days_overdue + " d"} tone="danger" />
            {row.type === "request" ? <a className="desk-button" href={"/m/" + makerspace.slug + "/admin/requests?id=" + row.reference_id}>{t`Open loan`}</a> : null}</div>} />)}
          {data?.truncated.overdue ? <p className="text-sm text-muted">{t`Showing the earliest overdue loans only.`}</p> : null}</> : null}
        {on("problems") ? <>{heading("Open problems")}{data?.problem_reports.map(row => <ProblemReportCard key={row.id} row={row}
          makerspace={makerspace} onTriaged={refreshAfterTriage} />)}
          {data?.truncated.problem_reports ? <p className="text-sm text-muted">{t`Showing the oldest open reports only.`}</p> : null}</> : null}
        {on("offenders") ? <>
          {heading("Repeat offenders")}
          {anonymous && anonymous.total_issues > 0 ? <div className="rounded-xl border border-line bg-surface p-4">
            <h2 className="title-section">{t`Account-less loans`}</h2>
            <p className="mt-2 text-sm">{anonymous.total_issues} {anonymous.total_issues === 1 ? "incident" : "incidents"} · {anonymous.total_quantity} {anonymous.total_quantity === 1 ? "item" : "items"}</p>
            <p className="mt-1 text-sm text-muted">{t`${anonymous.damaged} damaged, ${anonymous.missing} missing. These have no person to rank or restrict, so they are reported as a total.`}</p>
          </div> : null}
          {data?.repeat_offenders.map(row => <ListRow key={row.requester_id} title={row.username}
            identity={{ kind: "avatar", name: row.username, seed: String(row.requester_id) }}
            meta={row.damaged + " damaged · " + row.missing + " missing · " + row.total_issues + " issues (" + row.total_quantity + " units)"}
            right={<div className="flex flex-wrap items-center gap-3">{status(row.access_status)}
              {isSuperadmin ? row.access_status === "active"
                ? <button className="desk-button" type="button" disabled={restrict.isPending} onClick={() => setRestrictionTarget({ requester_id: row.requester_id, username: row.username })}>{t`Restrict…`}</button>
                : <button className="desk-button" type="button" disabled={restore.isPending} onClick={() => restore.mutate(row.requester_id)}>{restore.isPending && restore.variables === row.requester_id ? t`Restoring…` : t`Restore access`}</button> : null}</div>} />)}
          {!data?.repeat_offenders.length ? <p className="text-sm text-muted">{empty}</p> : null}
          {data?.truncated.repeat_offenders ? <p className="text-sm text-muted">{t`Showing the top offenders only.`}</p> : null}
        </> : null}
        {on("restricted") ? <>{heading("Restricted")}{data?.restrictions.map(row => <ListRow key={row.requester_id} title={row.username}
          identity={{ kind: "avatar", name: row.username, seed: String(row.requester_id) }}
          meta={row.restriction_reason} right={<div className="flex flex-wrap items-center gap-3">{status(row.access_status)}
            {isSuperadmin ? <button className="desk-button" type="button" disabled={restore.isPending} onClick={() => restore.mutate(row.requester_id)}>{restore.isPending && restore.variables === row.requester_id ? t`Restoring…` : t`Restore access`}</button> : null}</div>} />)}</> : null}
      </> }} detail={<>
        {restrict.error ? <ErrorBlock error={restrict.error} /> : null}
        {restore.error ? <ErrorBlock error={restore.error} /> : null}
      <Modal
        open={restrictionTarget !== null}
        onClose={closeRestrictionDialog}
        title={t`Restrict requester?`}
        footer={(
          <div className="desk-actions flex flex-wrap justify-end gap-2">
            <button className="desk-button" type="button" onClick={closeRestrictionDialog}>{t`Cancel`}</button>
            {/* Submit no-ops on a blank reason, so leaving it enabled renders a dead button that
                reports nothing. Disabling states the requirement instead of failing silently. */}
            <button className="desk-button-danger" type="submit" form={restrictionFormId} disabled={!restrictionReason.trim() || restrict.isPending}>
              {restrict.isPending ? t`Restricting…` : "Restrict " + (restrictionTarget?.username ?? "requester")}
            </button>
          </div>
        )}
      >
        <form id={restrictionFormId} className="grid gap-3" onSubmit={submitRestriction}>
          <p className="text-sm text-muted">
            {t`Restrict `}{restrictionTarget?.username ?? t`this requester`} {t` from making new requests.`}</p>
          <p className="text-sm text-muted">{t`Add a reason to continue.`}</p>
          <label className="grid gap-2 text-sm font-semibold">
            <span>{t`Reason for restriction`}</span>
            <textarea
              className="desk-input min-h-24"
              required
              value={restrictionReason}
              onChange={(event) => setRestrictionReason(event.target.value)}
            />
          </label>
        </form>
      </Modal>
      </>} />
  </div>;
}
