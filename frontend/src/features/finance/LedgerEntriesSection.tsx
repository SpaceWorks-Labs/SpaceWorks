import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileText, Receipt } from "lucide-react";

import { Field, Modal, Pagination, StatusPill } from "../../components/ui";
import { formatMoney } from "../staff/paymentsApi";
import { LedgerEntryForm } from "./LedgerEntryForm";
import {
  DOMAIN_LABELS, financeApi, financeError, financeKeys, invalidateFinance, words, type FinanceAccess, type LedgerEntry,
} from "./financeApi";
import { LogoLoader } from "../../components/LogoLoader";

/** Expenses and other receipts in the caller's areas: record, open a receipt, void with a reason. */
export function LedgerEntriesSection({ makerspaceId, access }: { makerspaceId: number; access: FinanceAccess }) {
  const client = useQueryClient();
  const [domain, setDomain] = useState("");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [voiding, setVoiding] = useState<LedgerEntry | null>(null);
  const [reason, setReason] = useState("");
  const params = new URLSearchParams({ page: String(page), ...(domain ? { domain } : {}) }).toString();
  const entries = useQuery({ queryKey: financeKeys.entries(makerspaceId, params), queryFn: () => financeApi.entries(makerspaceId, params) });
  const voidEntry = useMutation({
    mutationFn: () => financeApi.voidEntry(makerspaceId, voiding!.id, reason),
    onSuccess: () => { invalidateFinance(client, makerspaceId); setVoiding(null); setReason(""); },
  });
  const openReceipt = async (entry: LedgerEntry) => {
    const { url } = await financeApi.receiptUrl(makerspaceId, entry.id);
    window.open(url, "_blank", "noopener");
  };
  const domains = access.everything ? Object.keys(DOMAIN_LABELS) : access.domains;
  const canRecord = access.record_everything || access.record_domains.length > 0;
  return <div className="grid min-w-0 gap-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <Field label={t`Area`}><select className="desk-input" value={domain} onChange={event => { setDomain(event.target.value); setPage(1); }}>
        <option value="">{t`All my areas`}</option>
        {domains.map(value => <option key={value} value={value}>{DOMAIN_LABELS[value] ?? value}</option>)}</select></Field>
      {canRecord ? <button type="button" className="desk-button" onClick={() => setAdding(true)}>
        <BookOpen aria-hidden="true" size={16} />{t`Record money`}</button> : null}
    </div>
    {entries.isLoading ? <LogoLoader label={t`Loading entries…`} size={48} className="min-h-16 py-3" /> : null}
    {entries.error ? <p role="alert" className="text-sm text-danger">{financeError(entries.error)}</p> : null}
    {entries.data?.count === 0 ? <p className="text-sm text-muted">{t`No expenses or other receipts yet. Purchases, repairs and payouts recorded elsewhere appear here too.`}</p> : null}
    <ul className="grid gap-2">
      {(entries.data?.results ?? []).map(entry => <li key={entry.id} className="grid gap-1 rounded-lg border border-line bg-panel p-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="grid min-w-0 gap-1">
          <p className="font-semibold">{entry.description}</p>
          <p className="text-sm text-muted">{entry.entry_date} · {DOMAIN_LABELS[entry.domain] ?? entry.domain}
            {entry.machine_type_label ? ` · ${entry.machine_type_label}` : ""} · {words(entry.category)} · {words(entry.method)}
            {entry.counterparty ? ` · ${entry.counterparty}` : ""}</p>
          {entry.voided_at ? <p className="text-sm text-muted">{t`Void: ${entry.void_reason}`}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          <strong className={entry.voided_at ? "tabular-nums line-through" : "tabular-nums"}>
            {entry.kind === "expense" ? "−" : "+"}{formatMoney(entry.amount, entry.currency)}</strong>
          {entry.voided_at ? <StatusPill label={t`Void`} tone="neutral" /> : <StatusPill label={entry.kind === "expense" ? t`Paid out` : t`Received`} tone={entry.kind === "expense" ? "warn" : "success"} />}
          {/* Never an inline <img>: a PDF or photo opens through a short-lived signed link. */}
          {entry.has_receipt ? <button type="button" className="desk-button-ghost" onClick={() => void openReceipt(entry)}>
            {entry.receipt_kind === "pdf" ? <FileText aria-hidden="true" size={16} /> : <Receipt aria-hidden="true" size={16} />}
            {entry.receipt_kind === "pdf" ? t`Receipt (PDF)` : t`Receipt`}</button> : null}
          {!entry.voided_at && canRecord ? <button type="button" className="desk-button-ghost" onClick={() => setVoiding(entry)}>{t`Void`}</button> : null}
        </div>
      </li>)}
    </ul>
    {entries.data && entries.data.count > 24 ? <Pagination page={page} totalPages={Math.ceil(entries.data.count / 24)} count={entries.data.count} pageSize={24} onChange={setPage} /> : null}
    {adding ? <LedgerEntryForm makerspaceId={makerspaceId} access={access} onClose={() => setAdding(false)} /> : null}
    {voiding ? <Modal open onClose={() => setVoiding(null)} title={t`Void this entry`}>
      <form className="grid gap-3" onSubmit={event => { event.preventDefault(); voidEntry.mutate(); }}>
        <p className="text-sm">{t`The entry stays on record, marked void, and drops out of every total. It can't be edited.`}</p>
        <Field label={t`Why is it void?`}><input className="desk-input" required maxLength={300} value={reason} onChange={event => setReason(event.target.value)} /></Field>
        {voidEntry.error ? <p role="alert" className="text-sm text-danger">{financeError(voidEntry.error)}</p> : null}
        <div className="flex justify-end gap-2"><button type="button" className="desk-button-ghost" onClick={() => setVoiding(null)}>{t`Keep it`}</button>
          <button type="submit" className="desk-button-danger" disabled={voidEntry.isPending}>{t`Void entry`}</button></div>
      </form>
    </Modal> : null}
  </div>;
}
