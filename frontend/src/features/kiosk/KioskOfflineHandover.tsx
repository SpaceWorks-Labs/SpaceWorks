import { t } from "@lingui/core/macro";
import { useRef, useState, type FormEvent } from "react";
import { Callout } from "../../components/ui";
import { FlowLayout } from "../../components/layouts";
import { CameraCapture } from "../../components/ui/CameraCapture";
import { enqueueCommand } from "./offlineQueueStore";
import { normalizeEvidence } from "./offlineEvidence";
import { registerKioskSync } from "./useKioskQueue";
import type { OfflineQueue } from "./offlineQueueTypes";
import type { ReplayEnvelope } from "./kioskReplayApi";
import { KioskQueueStatus } from "./KioskQueueStatus";
import { KitChecklistCapture, useSuppliedKitChecklist } from "../inventory/KitChecklist";

export function KioskOfflineHandover({ queue, onChange, retry, acknowledge }: {
  queue: OfflineQueue; onChange: (queue: OfflineQueue) => void; retry: () => void; acknowledge: () => void;
}) {
  const [selected, setSelected] = useState(queue.works[0]?.id ?? "");
  const [kind, setKind] = useState<ReplayEnvelope["kind"]>("assign_box");
  const [box, setBox] = useState("");
  const [remark, setRemark] = useState("");
  const [assetQrs, setAssetQrs] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [camera, setCamera] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [captureSession, setCaptureSession] = useState(0);
  const captureForm = useRef<HTMLFormElement>(null);
  const loaded = queue.works.find((item) => item.id === selected);
  const work = loaded?.work;
  const allowed = queue.lease.permitted_operations;
  const choices: ReplayEnvelope["kind"][] = work?.kind === "direct_loan" ? ["direct_return"] : ["assign_box", "reviewed_issue", "reviewed_return"];
  const operation = choices.includes(kind) ? kind : choices[0];
  const returning = operation.endsWith("return");
  const kits = useSuppliedKitChecklist(operation === "assign_box" ? [] : work?.kit_components ?? [], `${selected}/${operation}/${captureSession}`);

  async function capture(event: FormEvent) {
    event.preventDefault();
    if (!loaded || !work || busy || !kits.ready) return;
    setBusy(true); setError(null);
    try {
      const image = operation === "assign_box" ? undefined : photo ? await normalizeEvidence(photo, work.evidence_max_bytes) : undefined;
      const identity = { version: 1 as const, client_command_id: crypto.randomUUID(), aggregate_id: loaded.aggregateId,
        sequence: 1, client_created_at: new Date().toISOString() };
      const evidence = image ? { evidence_type: returning ? "return" as const : "issue" as const,
        content_type: image.type, size_bytes: image.size } : undefined;
      const payload = operation === "assign_box" ? { request_id: work.id, box_code: box.trim() }
        : operation === "reviewed_issue" ? { request_id: work.id, remark: remark.trim(),
          asset_qr_payloads: assetQrs.split(/\r?\n/).map((value) => value.trim()).filter(Boolean), rejects: [] }
        : operation === "reviewed_return" ? { request_id: work.id, box_code: box.trim(), remark: remark.trim(),
          resolutions: work.lines.filter((line) => line.quantity > line.returned).map((line) => ({ item_id: line.item_id, returned: line.quantity - line.returned })) }
        : { loan_id: work.id, notes: remark.trim(), qr_payload: box.trim(), resolutions:
          work.lines.filter((line) => line.quantity > line.returned).map((line) => ({ item_id: line.item_id, returned: line.quantity - line.returned })) };
      const envelope = { ...identity, kind: operation,
        payload: operation === "assign_box" ? payload : { ...payload, kit_checklist: kits.counts },
        ...(evidence ? { evidence } : {}) } as ReplayEnvelope;
      onChange(await enqueueCommand(queue.scope, loaded.id, envelope, image));
      setPhoto(null); setBox(""); setRemark(""); setAssetQrs("");
      setCaptureSession((value) => value + 1);
      void registerKioskSync().catch(() => undefined);
      retry();
    } catch (failure) { setError(failure instanceof Error ? failure.message : t`Capture failed. Nothing was queued.`); }
    finally { setBusy(false); }
  }

  return <div className="grid gap-4">
    <Callout size="panel" tone="warn" lead="Handovers stay encrypted on this device." body={t`Continue only a loaded handover. Work is queued until the server confirms it, and syncs when you reconnect.`} action={{ label: t`Retry now`, onClick: retry }} />
    <FlowLayout presentation="kiosk" state={{ status: "ready" }} title={t`Queue a handover`} current="capture"
      steps={[{ key: "capture", label: t`Capture handover`, state: "current" }]} pending={busy}
      onCancel={() => { setPhoto(null); setBox(""); setRemark(""); setAssetQrs(""); }}
      footer={{ next: { label: t`Queue handover`, pending: busy, pendingLabel: "Encrypting capture…",
        disabled: !kits.ready || !allowed.includes(operation) || (operation !== "assign_box" && !photo),
        disabledReason: !allowed.includes(operation) ? "Choose an allowed operation." : !kits.ready ? "Check every kit part to continue."
          : operation !== "assign_box" && !photo ? "Add the evidence photo to continue." : undefined,
        onClick: () => captureForm.current?.requestSubmit() } }}
      error={error ? { size: "inline", tone: "danger", lead: error } : undefined}
      work={<form ref={captureForm} className="grid gap-3" onSubmit={capture}>
      <label className="grid gap-1 text-sm">{t`Loaded handover`}<select className="desk-input" value={selected} disabled={busy} onChange={(event) => { setSelected(event.target.value); setPhoto(null); setBox(""); setRemark(""); }}>
        {queue.works.map((item) => <option key={item.id} value={item.id}>{item.work.display_label}</option>)}
      </select></label>
      <label className="grid gap-1 text-sm">{t`Operation`}<select className="desk-input" value={operation} disabled={busy} onChange={(event) => { setKind(event.target.value as ReplayEnvelope["kind"]); setPhoto(null); }}>
        {choices.map((choice) => <option key={choice} disabled={!allowed.includes(choice)} value={choice}>{choice.replace(/_/g, " ")}</option>)}
      </select></label>
      {operation === "assign_box" || returning ? <label className="grid gap-1 text-sm">{t`Scan box or return QR`}<input className="desk-input code-text" required value={box} disabled={busy} onChange={(event) => setBox(event.target.value)} /></label> : null}
      {operation !== "assign_box" ? <>
        {operation === "reviewed_issue" ? <label className="grid gap-1 text-sm">{t`Asset QRs (one per line)`}<textarea className="desk-input code-text" disabled={busy} value={assetQrs} onChange={(event) => setAssetQrs(event.target.value)} /></label> : null}
        <label className="grid gap-1 text-sm">{t`Evidence photo`}<input key={`${selected}/${operation}/${photo ? "selected" : "empty"}`} type="file" accept="image/*" capture="environment" disabled={busy} onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} /></label>
        {navigator.mediaDevices ? <button type="button" className="desk-button-brand" disabled={busy} onClick={() => setCamera(true)}>{t`Take evidence photo`}</button> : null}
        {photo ? <p className="text-sm" role="status">{t`Photo selected; it will be normalized and encrypted with the command.`}</p> : null}
        <label className="grid gap-1 text-sm">{t`Remark`}<input className="desk-input" required={returning} disabled={busy} value={remark} onChange={(event) => setRemark(event.target.value)} /></label>
        <KitChecklistCapture checklist={kits} />
      </> : null}
      <p className="text-sm text-muted">{operation !== "assign_box" && !photo ? t`Add the evidence photo to continue.` : returning && !remark.trim() ? t`Add a return remark to continue.` : !kits.ready ? t`Check every kit part to continue.` : t`Review the handover before queuing it.`}</p>
      <button type="submit" hidden aria-hidden="true" tabIndex={-1} disabled={busy || !kits.ready || !allowed.includes(operation) || (operation !== "assign_box" && !photo)} />
    </form>} />
    <CameraCapture open={camera} onClose={() => setCamera(false)} onCapture={(file) => { setPhoto(file); setCamera(false); }} label={t`Handover evidence`} />
    <KioskQueueStatus queue={queue} retry={retry} acknowledge={acknowledge} />
  </div>;
}
