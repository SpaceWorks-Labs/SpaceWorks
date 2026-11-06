import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ActionControl } from "./ActionControl";
import { Card } from "./Card";
import { EmptyState } from "./EmptyState";
import { ErrorBlock } from "./ErrorBlock";
import { Field } from "./Field";
import { Icon } from "./icon";
import QrScanner from "./QrScanner";
import { ResultPanel, type ResultPanelProps } from "./ResultPanel";
import { Skeleton } from "./Skeleton";
import { StatusPill } from "./StatusPill";
import type { Action, QueryState } from "./types";

export type ScanWorkbenchProps = {
  onFind: (value: string) => void;
  onScan?: (payload: string) => void;
  searchLabel?: string;
  helper?: string;
  findPending?: boolean;
  cameraLabel?: string;
  result?: ResultPanelProps;
  controls?: ReactNode;
  recent?: { key: string; label: string; meta?: string; tone?: "success" | "warn" | "danger"; undo?: Action }[];
  recentTitle?: string;
  state?: QueryState;
};
/** Camera access stays user-initiated and all decoding/stream cleanup stays in QrScanner. */
export function ScanWorkbench({ onFind, onScan = onFind, searchLabel = "Find a QR code or item", helper = "You can also paste a QR link.",
  findPending, cameraLabel = "Hold the QR code inside the frame", result, controls, recent = [], recentTitle = "Recent scans",
  state = { status: "ready" } }: ScanWorkbenchProps) {
  const [cameraOpen, setCameraOpen] = useState(false);
  const [value, setValue] = useState("");
  const blocked = findPending || state.status !== "ready";
  // Keyboard-wedge scanners type a code then Enter, back to back: clear after each find and hand focus back
  // once the lookup settles, so the next scan never appends to the last one.
  const input = useRef<HTMLInputElement>(null);
  const refocus = useRef(false);
  useEffect(() => { if (!blocked && refocus.current) { refocus.current = false; input.current?.focus(); } }, [blocked]);
  return <section aria-label={t`Scan workbench`} className="grid min-w-0 gap-6">
    <div className="grid min-w-0 gap-6 xl:grid-cols-2">
      <div className="grid min-w-0 content-start gap-3">
        <div className="relative grid min-h-40 place-items-center overflow-hidden rounded-xl border border-outline bg-surface p-6 text-ink md:min-h-60 md:p-8">
          <div aria-hidden="true" className="pointer-events-none absolute inset-6 rounded-xl border-2 border-dashed border-outline" />
          <div className="relative grid justify-items-center gap-3 text-center"><Icon name="Search" className="h-16 w-16" />
            <p>{t`Camera is off`}</p><p className="text-sm text-muted">{cameraLabel}</p></div>
        </div>
        <ActionControl primary action={{ label: t`Start scanning`, onClick: () => setCameraOpen(true), disabled: blocked,
          disabledReason: blocked ? "Wait until the scanner is ready." : undefined }} className="w-full" />
      </div>
      {/* Phones: a result (and its Confirm) comes before the camera card instead of below the fold. */}
      <div className={`grid min-w-0 content-start gap-4 ${result ? "max-md:order-first" : ""}`}>
        <form className="flex min-w-0 flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); if (!value.trim() || blocked) return;
          onFind(value.trim()); setValue(""); refocus.current = true; if (!findPending) input.current?.focus(); }}>
          <Field label={searchLabel} hint={helper} className="min-w-0 flex-1 basis-48"><input ref={input} className="desk-input w-full" type="search"
            value={value} onChange={event => setValue(event.target.value)} disabled={blocked} /></Field>
          <button type="submit" className="desk-button" disabled={blocked || !value.trim()} aria-busy={findPending || undefined}>{findPending ? t`Finding…` : t`Find`}</button>
        </form>
        {state.status === "loading" ? <div role="status" aria-label={t`Loading scanner`}><span className="sr-only">{t`Loading scanner`}</span><Skeleton className="h-32" /></div>
          : state.status === "error" ? <ErrorBlock error={new Error(state.error || t`Couldn't load the scanner.`)} onRetry={state.onRetry} />
          : result ? <ResultPanel {...result} /> : <EmptyState message={t`Scan a QR code or find an item to get started.`} />}
        {controls}
      </div>
    </div>
    <Card><h2 className="title-panel mb-4">{recentTitle}</h2>
      {recent.length ? <ul className="divide-y divide-line">{recent.map(item => <li key={item.key} className="flex min-w-0 flex-wrap items-center gap-3 py-3">
        <div className="min-w-0 flex-1"><StatusPill label={item.label} tone={item.tone ?? "neutral"} />
          {item.meta ? <p className="mt-2 text-sm text-muted">{item.meta}</p> : null}</div>
        {item.undo ? <ActionControl action={item.undo} /> : null}
      </li>)}</ul> : <p className="text-sm text-muted">{t`No scans yet.`}</p>}
    </Card>
    {cameraOpen ? <QrScanner onScan={payload => { setCameraOpen(false); onScan(payload); }} onClose={() => setCameraOpen(false)} /> : null}
  </section>;
}
