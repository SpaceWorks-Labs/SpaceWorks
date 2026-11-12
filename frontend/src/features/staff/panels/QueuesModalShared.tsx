import { t } from "@lingui/core/macro";
import type React from "react";
import { useEffect, useState } from "react";

import QrScanner from "../../../components/ui/QrScanner";
import { Field, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { BoxArt } from "../../../components/BoxSpinner";

export function BoxCodeField({ value, onChange, makerspaceId, pending }: { value: string; onChange: (code: string) => void; makerspaceId: number; pending: boolean }) {
  const [containers, setContainers] = useState<ContainerOption[]>([]);
  const [scanned, setScanned] = useState<{ code: string; label: string } | null>(null);
  const [scanOpen, setScanOpen] = useState(false);
  const [scanError, setScanError] = useState("");
  const [manualOpen, setManualOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    staffRequest<{ results: ContainerOption[] }>(`/admin/makerspace/${makerspaceId}/containers?page_size=1000`)
      .then((res) => {
        if (!cancelled) setContainers((res.results ?? []).filter((c) => c.is_active !== false && c.code));
      })
      .catch(() => {
        if (!cancelled) setContainers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [makerspaceId]);

  const displayLabel = containers.find((container) => container.code === value)?.label ?? (scanned && scanned.code === value ? scanned.label : "");

  const handleScan = async (payload: string) => {
    setScanOpen(false);
    const clean = payload.trim();
    if (!clean) return;
    try {
      const res = await staffRequest<{ target: { type: string; code?: string; label?: string } }>("/admin/qr/resolve", {
        method: "POST",
        body: JSON.stringify({ payload: clean }),
      });
      if (res.target.type === "box" && res.target.code) {
        onChange(res.target.code);
        setScanned({ code: res.target.code, label: res.target.label ?? "" });
        setScanError("");
      } else {
        setScanError(t`Scanned QR is not a box/container.`);
      }
    } catch {
      setScanError(t`Could not resolve the scanned QR.`);
    }
  };

  return (
    <div className="grid gap-1 text-sm">
      <span className="font-medium text-ink">{t`Container`}</span>
      <div className="flex min-w-0 flex-wrap gap-2">
        <div className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span title={value ? displayLabel || value : undefined} className={value ? "min-w-0 truncate font-medium text-ink" : "min-w-0 truncate text-muted"}>{value ? displayLabel || value : t`No container selected`}</span>
            {value ? <StatusPill label={t`Selected`} tone="success" /> : null}
          </div>
        </div>
        <button className="desk-button shrink-0" type="button" disabled={pending} onClick={() => setScanOpen(true)}>{t`Scan`}</button>
      </div>
      {containers.length ? (
        <Field label={t`Available container`}>
          <select className="desk-input" value="" disabled={pending} onChange={(event) => event.target.value && onChange(event.target.value)}>
            <option value="">{t`Choose an available container…`}</option>
            {containers.map((container) => <option key={container.id} value={container.code ?? ""}>{container.label}</option>)}
          </select>
        </Field>
      ) : null}
      <button className="desk-button-ghost justify-self-start" type="button" disabled={pending} onClick={() => setManualOpen((open) => !open)}>
        {manualOpen ? t`Hide manual code entry` : t`Enter code manually`}
      </button>
      {manualOpen ? <Field label={t`Container code`}><input className="desk-input min-w-0" value={value} disabled={pending} onChange={(event) => onChange(event.target.value)} /></Field> : null}
      {scanError ? <p className="text-xs text-danger">{scanError}</p> : null}
      {scanOpen ? <QrScanner onScan={handleScan} onClose={() => setScanOpen(false)} /> : null}
    </div>
  );
}

export function FormFooter({ formId, pending, submitLabel, tone = "default", onCancel }: { formId: string; pending: boolean; submitLabel: string; tone?: "danger" | "default"; onCancel: () => void }) {
  return (
    <div className="desk-actions flex flex-wrap justify-end gap-2">
      <button className="desk-button-ghost" type="button" disabled={pending} onClick={onCancel}>{t`Cancel`}</button>
      <button className={tone === "danger" ? "desk-button-danger" : "desk-button-success"} type="submit" form={formId} disabled={pending}>{pending ? <><BoxArt size={16} mono />{t`Working…`}</> : submitLabel}</button>
    </div>
  );
}

// The product's free-text storage location ("shelf") so staff know where to physically
// fetch or return the item during handover. Renders nothing when no shelf is recorded.
export function ShelfLine({ location }: { location?: string | null }) {
  return location ? (
    <p className="text-xs text-muted">{t`Shelf: `}<span className="font-medium text-ink">{location}</span></p>
  ) : null;
}

export function submitForm(event: React.FormEvent<HTMLFormElement>, submit: () => void) {
  event.preventDefault();
  submit();
}

type ContainerOption = { id: number; code?: string | null; label: string; is_active?: boolean };
