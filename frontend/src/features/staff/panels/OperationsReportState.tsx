import type React from "react";

import { Skeleton, SkeletonRows } from "../../../components/ui";

export type ReportCell = string | number | boolean | null;
export type TypedReportRow = Record<string, ReportCell | undefined>;
export type ReportRows = {
  report_key?: string;
  rows: ReportCell[][];
  typed_rows?: TypedReportRow[];
  meta?: { source?: string; grain?: string; rollup_through?: string | null };
};
export type ChartRow = { label: string; value: number };

export function reportRows(data?: ReportRows) {
  return data?.rows?.slice(1) ?? [];
}

export function reportHeaders(data?: ReportRows) {
  return (data?.rows?.[0] ?? []).map(String);
}

export function typedRows(data?: ReportRows) {
  return data?.typed_rows ?? [];
}

export function chartRows(data: ReportRows | undefined, labelKey: string, valueKey: string): ChartRow[] {
  const typed = typedRows(data);
  if (typed.length) {
    return typed.map((row) => ({ label: String(row[labelKey] ?? "Unknown"), value: Number(row[valueKey] ?? 0) }));
  }
  const header = reportHeaders(data);
  return reportRows(data).map((row) => ({
    label: String(row[header.indexOf(labelKey)] ?? "Unknown"),
    value: Number(row[header.indexOf(valueKey)] ?? 0),
  }));
}

export function DataState(props: { loading: boolean; error: unknown; empty: boolean; children: React.ReactNode }) {
  if (props.loading) return <ReportSkeleton />;
  if (props.error) return <p className="mt-3 text-sm text-danger">{props.error instanceof Error ? props.error.message : "Unable to load report."}</p>;
  if (props.empty) return <p className="mt-3 text-sm text-muted">No records.</p>;
  return <>{props.children}</>;
}

function ReportSkeleton() {
  return (
    <div className="mt-4 grid gap-3" aria-hidden="true">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="rounded-md border border-line bg-surface p-3">
            <Skeleton className="h-7 w-20" /><Skeleton className="mt-2 h-3 w-24" />
          </div>
        ))}
      </div>
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full divide-y divide-line text-left text-sm"><tbody className="divide-y divide-line bg-bg"><SkeletonRows rows={4} cols={4} /></tbody></table>
      </div>
    </div>
  );
}

export function StatCards({ stats }: { stats: [string, number | undefined][] }) {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-line bg-panel p-3">
          <p className="font-display tabular-nums text-[32px] leading-[38px] font-extrabold text-ink">{formatNumber(value ?? 0)}</p><p className="eyebrow">{label}</p>
        </div>
      ))}
    </div>
  );
}

export function formatReportCell(value: ReportCell | undefined) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (/^\d{4}-\d{2}-\d{2}T/.test(value)) return new Date(value).toLocaleString();
  return value;
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
}
