import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Field, SegmentedControl } from "../../components/ui";
import { downloadOverviewCsv, overviewReady, type OverviewPreset, type OverviewQuery } from "./platformOverviewApi";
import { BoxArt } from "../../components/BoxSpinner";

const PRESETS: { value: OverviewPreset; label: string }[] = [
  { value: "this_month", label: t`This month` }, { value: "this_year", label: t`This year` },
  { value: "all_time", label: t`All time` }, { value: "custom", label: t`Custom` },
];

type Props = {
  query: OverviewQuery; onChange: (next: OverviewQuery) => void;
  ready: boolean; excludedCount: number | null; onRefresh: () => void; refreshing: boolean;
};

/** Period presets, the excluded-spaces toggle, refresh and the CSV export. */
export function PlatformOverviewControls({ query, onChange, ready, excludedCount, onRefresh, refreshing }: Props) {
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState("");
  const exportCsv = async () => {
    setExporting(true); setNotice("");
    try {
      setNotice(await downloadOverviewCsv(query) ? t`CSV downloaded. The export was recorded in the audit log.`
        : t`Still computing. Try the export again in a few seconds.`);
    } catch {
      setNotice(t`The export failed. Try again.`);
    } finally { setExporting(false); }
  };
  const invalidCustom = query.preset === "custom" && Boolean(query.start && query.end) && !overviewReady(query);
  return <div className="grid gap-4 rounded-xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-end gap-4">
      <SegmentedControl label={t`Period`} value={query.preset} options={PRESETS}
        onChange={value => onChange({ ...query, preset: value as OverviewPreset })} />
      {query.preset === "custom" ? <>
        <Field label={t`From`}><input className="desk-input min-h-11" type="date" value={query.start}
          onChange={event => onChange({ ...query, start: event.target.value })} /></Field>
        <Field label={t`To`} error={invalidCustom ? "The end date must be on or after the start date." : undefined}>
          <input className="desk-input min-h-11" type="date" value={query.end}
            onChange={event => onChange({ ...query, end: event.target.value })} /></Field>
      </> : null}
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <label className="inline-flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5" checked={query.includeExcluded}
          onChange={event => onChange({ ...query, includeExcluded: event.target.checked })} />
        {t`Include archived, not-serving and directory-hidden spaces${excludedCount ? ` (${excludedCount})` : ""}`}
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button min-h-11" onClick={onRefresh} disabled={refreshing || !overviewReady(query)}>
          <RefreshCw aria-hidden="true" size={18} />{refreshing ? <><BoxArt size={16} mono />{t`Recomputing…`}</> : t`Recompute`}</button>
        <button type="button" className="desk-button-primary min-h-11" onClick={() => void exportCsv()} disabled={!ready || exporting}>
          <Download aria-hidden="true" size={18} />{exporting ? <><BoxArt size={16} mono />{t`Exporting…`}</> : t`Export CSV`}</button>
      </div>
    </div>
    {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
  </div>;
}
