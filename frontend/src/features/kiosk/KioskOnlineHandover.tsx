import { t } from "@lingui/core/macro";
import { useRef, useState, type FormEvent } from "react";
import { ListRow, ResultPanel, StatusPill } from "../../components/ui";
import { FlowLayout } from "../../components/layouts";

import { EvidenceUpload } from "../staff/panels/EvidenceUpload";
import { KitChecklistCapture, useSuppliedKitChecklist } from "../inventory/KitChecklist";
import {
  loadWorkPackage,
  prepareEvidence,
  runOnlineCommand,
  type KioskLease,
  type KioskWorkPackage,
} from "./kioskApi";

type Props = { token: string; lease: KioskLease; makerspaceId: number;
  onWorkLoaded?: (work: KioskWorkPackage) => Promise<void> };

// Online reviewed-request handover: load the minimal work package, then assign a box,
// issue or return through the lease-checked command route. Evidence goes straight to
// object storage via the kiosk presign; the server promotes it inside the workflow.
export function KioskOnlineHandover({ token, lease, makerspaceId, onWorkLoaded }: Props) {
  const [loadingWork, setLoadingWork] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [requestId, setRequestId] = useState("");
  const [work, setWork] = useState<KioskWorkPackage | null>(null);
  const [boxCode, setBoxCode] = useState("");
  const [remark, setRemark] = useState("");
  const [evidenceId, setEvidenceId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [captureSession, setCaptureSession] = useState(0);
  const actionForm = useRef<HTMLFormElement>(null);
  const kits = useSuppliedKitChecklist(work?.kit_components ?? [], `${work?.id}/${work?.status}/${captureSession}`);
  const allowed = new Set(lease.permitted_operations);
  const presign = (body: object) => prepareEvidence(token, lease.lease_token, body);

  async function load(id: number) {
    setLoadingWork(true); setError(null);
    try {
      const loaded = await loadWorkPackage(token, lease.lease_token, "reviewed_request", id);
      setWork(loaded);
      setCaptureSession((value) => value + 1);
      await onWorkLoaded?.(loaded);
    }
    catch { setWork(null); setError(t`That request is not available to this Station.`); }
    finally { setLoadingWork(false); }
  }

  function submitLoad(event: FormEvent) {
    event.preventDefault();
    if (loadingWork || running) return;
    setMessage(null);
    void load(Number(requestId));
  }

  async function run(kind: string, payload: object, done: string) {
    if (!work || running) return;
    setRunning(kind); setError(null);
    try {
      await runOnlineCommand(token, lease.lease_token, kind, { request_id: work.id, ...payload });
      setMessage(done); setRemark(""); setBoxCode(""); setEvidenceId(null);
      await load(work.id);
    } catch { setError(t`The handover was refused. Check the box, photo and remark, then try again.`); }
    finally { setRunning(null); }
  }

  const resolutions = (work?.lines ?? []).filter((line) => line.quantity > line.returned).map((line) => ({
    item_id: line.item_id, returned: Math.max(0, line.quantity - line.returned),
  }));
  const canIssue = work?.status === "accepted" && Boolean(work.box) && allowed.has("reviewed_issue");
  const canReturn = (work?.status === "issued" || work?.status === "partially_returned") && allowed.has("reviewed_return");
  const cancel = () => { setWork(null); setEvidenceId(null); setBoxCode(""); setRemark(""); };

  return <div className="grid gap-4">
    <form className="flex flex-wrap items-end gap-3" onSubmit={submitLoad}>
      <label className="grid min-w-0 flex-1 basis-48 gap-1 text-sm">{t`Request number`}<input className="desk-input w-full tabular-nums" inputMode="numeric" required value={requestId} onChange={(event) => setRequestId(event.target.value.replace(/\D/g, ""))} /></label>
      <button className="desk-button-brand" type="submit" disabled={!requestId || loadingWork || Boolean(running)}>{loadingWork ? t`Loading…` : t`Load request`}</button>
    </form>
    {work ? <section className="grid gap-3" aria-label={work.display_label}>
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="title-panel">{work.display_label}</h2><StatusPill label={work.status.replace(/_/g, " ")} tone="accent" /></div>
      <p className="text-sm text-muted">{work.person_display || t`Requester`}{work.box ? t` · box ${work.box}` : ""}</p>
      <div className="grid gap-3">{work.lines.map(line => <ListRow key={line.item_id} title={line.label} right={<span className="text-sm tabular-nums">{line.returned} / {line.quantity} returned</span>} />)}</div>
      {work.status === "accepted" && !work.box && allowed.has("assign_box") ? <FlowLayout presentation="kiosk"
        state={{ status: "ready" }} title={t`Assign a box`} current="box" steps={[{ key: "box", label: t`Box`, state: "current" }]}
        pending={loadingWork || Boolean(running)}
        onCancel={cancel} footer={{ next: { label: t`Assign box`, pending: Boolean(running), pendingLabel: "Assigning…",
          onClick: () => actionForm.current?.requestSubmit() } }} work={<form ref={actionForm} className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); void run("assign_box", { box_code: boxCode.trim() }, "Box assigned."); }}>
        <label className="grid min-w-0 flex-1 basis-48 gap-1 text-sm">{t`Box code`}<input className="desk-input w-full tabular-nums" required value={boxCode} onChange={(event) => setBoxCode(event.target.value)} /></label>
        <button type="submit" hidden aria-hidden="true" tabIndex={-1} disabled={Boolean(running)} />
      </form>} /> : null}
      {canIssue || canReturn ? <FlowLayout presentation="kiosk" state={{ status: "ready" }} title={canIssue ? t`Issue items` : t`Return items`}
        pending={loadingWork || Boolean(running)}
        current="evidence" steps={[{ key: "evidence", label: t`Photo and remarks`, state: "current" }]}
        onCancel={cancel} footer={{ next: { label: canIssue ? t`Issue items` : t`Return all items`, pending: Boolean(running),
          pendingLabel: canIssue ? "Issuing…" : "Returning…", disabled: evidenceId === null || !kits.ready,
          disabledReason: evidenceId === null ? "Add the evidence photo to continue." : !kits.ready ? "Check every kit part to continue." : undefined,
          onClick: () => actionForm.current?.requestSubmit() } }} work={<form ref={actionForm} className="grid gap-3" onSubmit={(event) => {
        event.preventDefault();
        if (evidenceId === null || !kits.ready) return;
        if (canIssue) void run("reviewed_issue", { evidence_id: evidenceId, remark, asset_qr_payloads: [], rejects: [], kit_checklist: kits.counts }, "Issued.");
        else void run("reviewed_return", { evidence_id: evidenceId, remark, box_code: boxCode.trim(), resolutions, kit_checklist: kits.counts }, "Returned.");
      }}>
        <EvidenceUpload makerspaceId={makerspaceId} evidenceType={canIssue ? "issue" : "return"} label={canIssue ? t`Issue photo` : t`Return photo`} presign={presign} onUploaded={setEvidenceId} />
        {canReturn ? <label className="grid gap-1 text-sm">{t`Scan the box`}<input className="desk-input tabular-nums" required value={boxCode} onChange={(event) => setBoxCode(event.target.value)} /></label> : null}
        <label className="grid gap-1 text-sm">{t`Remark`}<input className="desk-input" required={canReturn} value={remark} onChange={(event) => setRemark(event.target.value)} /></label>
        <KitChecklistCapture checklist={kits} />
        <p className="text-sm text-muted">{evidenceId === null ? t`Add the ${canIssue ? "issue" : "return"} photo${canReturn ? " and a return remark" : ""} to continue.` : !kits.ready ? t`Check every kit part to continue.` : t`Review the details before confirming this handover.`}</p>
        <button type="submit" hidden aria-hidden="true" tabIndex={-1} disabled={evidenceId === null || !kits.ready || Boolean(running)} />
      </form>} /> : null}
    </section> : null}
    {message ? <ResultPanel tone="success" title={message} summary={t`The handover is recorded.`} next={{ label: t`Next`, onClick: () => setMessage(null) }} /> : null}
    {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
  </div>;
}
