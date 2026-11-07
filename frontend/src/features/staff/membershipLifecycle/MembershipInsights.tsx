import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { DashboardLayout } from "../../../components/layouts/DashboardLayout";
import { lifecycleApi, lifecycleKeys, reportRecords } from "../membershipLifecycleApi";

type Row = Record<string, unknown>;
const num = (value: unknown) => Number(value ?? 0) || 0;
const sum = (rows: Row[], key: string) => rows.reduce((total, row) => total + num(row[key]), 0);
const pct = (part: number, whole: number) => (whole ? `${Math.round((part * 100) / whole)}%` : "—");

function useReport(makerspaceId: number, key: string, params: Record<string, string> | null) {
  return useQuery({
    queryKey: ["membership-l4", makerspaceId, "report", key, params?.start, params?.end],
    queryFn: () => lifecycleApi.report(makerspaceId, key, params ?? {}), enabled: Boolean(params),
  });
}

/** G19 + X34: renewal, collection, bridge and funnel tiles; each tile drills into the register. */
export function MembershipInsights({ makerspaceId }: { makerspaceId: number }) {
  const fy = useQuery({ queryKey: lifecycleKeys.financialYear(makerspaceId), queryFn: () => lifecycleApi.financialYear(makerspaceId) });
  const [preset, setPreset] = useState("");
  const range = fy.data?.presets.find((row) => row.key === preset) ?? fy.data?.presets[0];
  const params = range ? { start: range.start, end: range.end, grain: "month" } : null;
  const bridge = useReport(makerspaceId, "membership-bridge", params);
  const renewals = useReport(makerspaceId, "membership-renewals", params);
  const funnel = useReport(makerspaceId, "membership-applications-funnel", params);
  const always = fy.data ? {} : null;
  const calendar = useReport(makerspaceId, "membership-expiry-calendar", always);
  const breakdown = useReport(makerspaceId, "membership-breakdown", always);
  const winBack = useReport(makerspaceId, "membership-win-back", always);
  const calendarRows = reportRecords(calendar.data);
  const breakdownRows = reportRecords(breakdown.data);
  const winBackRows = reportRecords(winBack.data);
  const bridgeRows = reportRecords(bridge.data);
  const renewalRows = reportRecords(renewals.data);
  const funnelRows = reportRecords(funnel.data);
  const due = sum(renewalRows, "due");
  const firstDue = sum(renewalRows, "first_year_due");
  const raised = sum(renewalRows, "charges_raised");
  const waits = funnelRows.map((row) => row.median_hours_to_approve).filter((value) => value !== null && value !== undefined).map(num);
  const loading = fy.isLoading || bridge.isLoading || renewals.isLoading;
  const failed = fy.isError || bridge.isError || renewals.isError || funnel.isError;
  const drill = (standing: string) => `?section=register${standing ? `&standing=${standing}` : ""}`;
  return <DashboardLayout state={{ status: loading ? "loading" : failed ? "error" : "ready", error: t`Couldn't load membership insights.` }}
    header={{ eyebrow: range ? range.label : t`Membership`, title: t`Membership insights`, headingLevel: 2,
      meta: fy.data ? <label className="grid gap-1 text-sm">{t`Financial year`}<select className="desk-input max-w-full" value={preset || range?.key || ""} onChange={(event) => setPreset(event.target.value)}>
          {fy.data.presets.map((row) => <option key={row.key} value={row.key}>{row.label}</option>)}
        </select></label> : undefined }}
    stats={[
      { label: t`Members at the end`, value: num(bridgeRows.at(-1)?.end), href: drill("active") },
      { label: t`Renewal rate`, value: pct(sum(renewalRows, "renewed"), due), href: drill("ending_soon") },
      { label: t`First-year renewal`, value: pct(sum(renewalRows, "first_year_renewed"), firstDue), href: drill("ending_soon") },
      { label: t`Collection rate`, value: pct(sum(renewalRows, "charges_collected"), raised), href: drill("grace") },
      { label: t`Joined`, value: sum(bridgeRows, "joined"), href: drill("active") },
      { label: t`Came back`, value: sum(bridgeRows, "came_back"), href: drill("active") },
      { label: t`Lapsed`, value: sum(bridgeRows, "lapsed"), tone: "attention", href: drill("lapsed") },
      { label: t`Revoked`, value: sum(bridgeRows, "revoked"), href: drill("") },
    ]}
    main={[
      { title: t`Membership bridge`, empty: { message: t`No membership activity in this year.` }, isEmpty: !bridgeRows.length,
        content: <p className="text-sm text-ink">{t`Start ${num(bridgeRows[0]?.start)} + joined ${sum(bridgeRows, "joined")} + came back ${sum(bridgeRows, "came_back")}− lapsed ${sum(bridgeRows, "lapsed")} − revoked ${sum(bridgeRows, "revoked")} = end ${num(bridgeRows.at(-1)?.end)}`}</p> },
      { title: t`Renewals: forecast and actual`, empty: { message: t`No terms ended in this year.` }, isEmpty: !renewalRows.length,
        content: <ul className="grid gap-1 text-sm">{renewalRows.map((row) => <li key={`${row.period}-${row.currency}`}>
          {t`${String(row.period)}: forecast ${String(row.forecast_amount)} · collected ${String(row.actual_amount)} ${String(row.currency).toUpperCase()}`}</li>)}</ul> },
      { title: t`Applications`, empty: { message: t`No join requests in this year.` }, isEmpty: !funnelRows.length,
        content: <p className="text-sm text-ink">{t`Submitted ${sum(funnelRows, "submitted")}, approved ${sum(funnelRows, "approved")}, rejected ${sum(funnelRows, "rejected")}.`}{waits.length ? t` Median wait about ${Math.round(waits.reduce((a, b) => a + b, 0) / waits.length)} hours.` : ""}</p> },
      { title: t`Expiring in the next 13 weeks`, empty: { message: t`No terms end in the next 13 weeks.` },
        isEmpty: !calendarRows.some((row) => num(row.terms_ending)),
        content: <ul className="grid gap-1 text-sm">{calendarRows.filter((row) => num(row.terms_ending)).map((row) =>
          <li key={`${row.week_start}-${row.currency}`}>{t`Week of ${String(row.week_start)}: ${num(row.terms_ending)} ending`}</li>)}</ul> },
      { title: t`Breakdowns`, empty: { message: t`No active members yet.` }, isEmpty: !breakdownRows.length,
        content: <ul className="grid gap-1 text-sm">{breakdownRows.map((row) =>
          <li key={`${row.dimension}-${row.value}`}>{String(row.dimension).replace("_", " ")}: {String(row.value)} — {num(row.members)}</li>)}</ul> },
      { title: t`Win-back list`, empty: { message: t`Nobody lapsed in the last 180 days.` }, isEmpty: !winBackRows.length,
        action: { label: t`Open lapsed members`, href: drill("lapsed") },
        content: <ul className="grid gap-1 text-sm">{winBackRows.slice(0, 10).map((row) =>
          <li key={String(row.membership_id)}>{String(row.name || row.email)} · {String(row.plan || "")}</li>)}</ul> },
    ]} />;
}
