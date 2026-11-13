import { plural, t } from "@lingui/core/macro";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ClipboardPaste, Plus } from "lucide-react";

import { Field } from "../../components/ui";
import { SETTLEMENT_METHODS, invalidatePaymentViews, settlementMethodLabel } from "../staff/paymentsApi";
import { CollectionSheetGrid } from "./CollectionSheetGrid";
import { MAX_SHEET_ROWS, collectionApi, sheetErrorText, type CollectionSheetResponse } from "./collectionApi";
import { localToday, parsePasted, sheetProblems, toInput, type SheetRow } from "./collectionSheetRows";
import { invalidateFinance } from "./financeApi";
import { BoxArt } from "../../components/BoxSpinner";

const open = (row: SheetRow) => !row.result || row.result.outcome === "failed";

/**
 * Parity O-B3 collection sheet (`billing.collection_sheet`): a treasurer back from a meeting records every
 * cash/UPI/cheque payment in one go. Each row is its own offline settlement on the server, so a bad row never
 * blocks the rest, and with the two-person check on, every row still waits for a second person.
 */
export function CollectionSheet({ makerspaceId, makerChecker }: { makerspaceId: number; makerChecker: boolean }) {
  const client = useQueryClient();
  const today = localToday();
  const counter = useRef(0);
  const nextKey = () => (counter.current += 1);
  const [defaults, setDefaults] = useState({ method: "cash", date: today });
  const [rows, setRows] = useState<SheetRow[]>(() => [{ key: nextKey(), payment: "", method: "cash", reference: "", date: today }]);
  const [pasted, setPasted] = useState("");
  const [notice, setNotice] = useState("");
  const problems = useMemo(() => sheetProblems(rows, today), [rows, today]);
  const pending = rows.filter(open);
  const blocked = rows.some((row, index) => open(row) && problems[index]);
  const add = (extra: SheetRow[]) => {
    // Blank rows are replaced, not kept above what was pasted.
    const keep = rows.filter((row) => row.payment.trim() || row.reference.trim() || row.result);
    const room = Math.max(0, MAX_SHEET_ROWS - keep.length);
    setRows([...keep, ...extra.slice(0, room)]);
    setNotice(extra.length > room ? t`A sheet holds ${MAX_SHEET_ROWS} rows; only the first ${room} pasted rows were added.`
      : extra.length ? "" : t`Nothing to add: the pasted text has no rows that start with a charge number.`);
  };
  const blankRow = (): SheetRow => ({ key: nextKey(), payment: "", method: defaults.method, reference: "", date: defaults.date });
  const change = (key: number, patch: Partial<SheetRow>) =>
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch, result: undefined } : row)));
  const record = useMutation({
    mutationFn: (sent: SheetRow[]) => collectionApi.recordSheet(makerspaceId, sent.map((row) => toInput(row, today))),
    onSuccess: (data: CollectionSheetResponse, sent) => {
      const byKey = new Map(sent.map((row, index) => [row.key, data.results.find((result) => result.index === index)]));
      setRows((current) => current.map((row) => (byKey.has(row.key) ? { ...row, result: byKey.get(row.key) } : row)));
      invalidatePaymentViews(client, makerspaceId);
      invalidateFinance(client, makerspaceId);
    },
  });
  const summary = record.data?.summary;
  return <section className="grid min-w-0 gap-4" aria-labelledby="collection-sheet-heading">
    <header className="grid gap-1">
      <h3 id="collection-sheet-heading" className="title-section">{t`Collection sheet`}</h3>
      <p className="max-w-prose text-sm text-muted">{t`Record up to ${MAX_SHEET_ROWS} offline payments in one go, for example after a meeting where members paid in cash or by UPI. Each row settles one pending charge and issues its receipt, exactly as recording it on its own would. Rows succeed or fail separately.`}</p>
    </header>
    {makerChecker ? <p className="max-w-prose rounded-lg border border-line bg-surface p-3 text-sm text-ink" data-testid="maker-checker-note">
      <strong>{t`Two-person check is on.`}</strong>{" "}
      {t`Every row is filed for a second person to confirm under Offline payments. Nothing on this sheet counts as paid until they do, and you can't confirm rows you recorded yourself.`}
    </p> : null}
    <div className="grid gap-3 sm:grid-cols-[minmax(0,12rem)_minmax(0,12rem)_minmax(0,1fr)] sm:items-end">
      <Field label={t`Method for new rows`}><select className="desk-input max-w-full" value={defaults.method}
        onChange={(event) => setDefaults({ ...defaults, method: event.target.value })}>
        {SETTLEMENT_METHODS.map(([code]) => <option key={code} value={code}>{settlementMethodLabel(code)}</option>)}
      </select></Field>
      <Field label={t`Received on, for new rows`}><input type="date" className="desk-input" max={today} value={defaults.date}
        onChange={(event) => setDefaults({ ...defaults, date: event.target.value })} /></Field>
    </div>
    <details className="rounded-xl border border-line bg-panel p-3">
      <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold">
        <ClipboardPaste aria-hidden="true" size={16} />{t`Paste from a spreadsheet`}</summary>
      <div className="mt-2 grid gap-2">
        <Field label={t`Copied cells`} hint={t`Columns in order: charge number, method, reference, received date (2026-11-10 or 10/11/2026). Empty method or date cells take the values above; a header row is skipped.`}>
          <textarea className="desk-input code-text" rows={5} value={pasted} onChange={(event) => setPasted(event.target.value)} />
        </Field>
        <div><button type="button" className="desk-button" disabled={!pasted.trim()} onClick={() => {
          add(parsePasted(pasted, defaults, nextKey)); setPasted("");
        }}>{t`Add pasted rows`}</button></div>
      </div>
    </details>
    {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
    <CollectionSheetGrid rows={rows} problems={problems} today={today} disabled={record.isPending} onChange={change}
      onRemove={(key) => setRows((current) => current.filter((row) => row.key !== key))} />
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button" disabled={rows.length >= MAX_SHEET_ROWS || record.isPending}
        onClick={() => setRows([...rows, blankRow()])}><Plus aria-hidden="true" size={16} />{t`Add a row`}</button>
      {rows.some((row) => !open(row)) ? <button type="button" className="desk-button-ghost"
        onClick={() => setRows((current) => current.filter(open))}>{t`Clear recorded rows`}</button> : null}
      <span className="grow" />
      <span className="text-sm text-muted tabular-nums">{t`${pending.length} to record`}</span>
      <button type="button" className="desk-button-primary" disabled={!pending.length || blocked || record.isPending}
        onClick={() => record.mutate(pending)}>
        {record.isPending ? <><BoxArt size={16} mono />{t`Recording…`}</> : makerChecker
          ? plural(pending.length, { one: "File # payment for confirmation", other: "File # payments for confirmation" })
          : plural(pending.length, { one: "Record # payment", other: "Record # payments" })}
      </button>
    </div>
    {blocked ? <p className="text-sm text-danger">{t`Fix the rows marked above before recording.`}</p> : null}
    {record.error ? <p role="alert" className="text-sm text-danger">{sheetErrorText(record.error)}</p> : null}
    {summary ? <p role="status" className="text-sm text-ink">
      {t`Last sheet: ${summary.recorded} recorded, ${summary.awaiting_confirmation} waiting for a second person, ${summary.failed} not recorded.`}
      {summary.failed ? ` ${t`Fix or remove the rows marked "Not recorded" and record again.`}` : ""}
    </p> : null}
  </section>;
}
