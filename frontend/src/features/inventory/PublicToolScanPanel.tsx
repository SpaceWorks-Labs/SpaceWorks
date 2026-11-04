import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, QrCode } from "lucide-react";

import { SegmentedControl } from "../../components/ui";
import QrScanner from "../../components/ui/QrScanner";
import type { PublicToolLoan } from "../../types/inventory";
import { invalidatePublicInventory } from "../staff/queryInvalidation";
import { publicToolCheckout, publicToolReturn } from "./api";
import { PublicEvidenceUpload } from "./PublicEvidenceUpload";
import { ContactFields } from "./ContactFields";
import { useToolContact } from "./useToolContact";

type PublicToolScanPanelProps = {
  makerspaceSlug: string;
  // "contact" where the makerspace has no member accounts: no account, confirmed email (#91).
  requestAccess?: "contact";
};

type Mode = "checkout" | "return";

function LoanResult({ loan }: { loan: PublicToolLoan }) {
  return (
    <div className="rounded-xl border border-success bg-success px-3 py-2 text-on-success dark:bg-success-soft dark:text-success-ink">
      <h3 className="title-section break-words capitalize text-on-success dark:text-success-ink">
        {loan.status.replace(/_/g, " ")}: {loan.items.map((item) => item.product_name).join(", ") || "Tool loan"}
      </h3>
      <p className="mt-1 break-all code-text text-xs">{loan.public_token}</p>
      <div className="mt-2 space-y-1">
        {loan.items.map((item) => (
          <div className="flex justify-between gap-3 text-sm" key={item.product_name}>
            <span className="min-w-0 break-words">{item.product_name}</span>
            <span className="shrink-0 tabular-nums">x{item.quantity}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** One numbered step. Every step is full width: this panel can be a 300px column beside the catalogue. */
function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="grid min-w-0 gap-3 border-t border-line pt-4">
      <h3 className="flex items-center gap-2 title-section">
        <span aria-hidden="true" className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold tabular-nums text-ink">{n}</span>
        {title}
      </h3>
      {children}
    </section>
  );
}

export function PublicToolScanPanel({ makerspaceSlug, requestAccess }: PublicToolScanPanelProps) {
  const queryClient = useQueryClient();
  const contact = useToolContact(makerspaceSlug, requestAccess === "contact");
  const [mode, setMode] = useState<Mode>("checkout");
  const [scannedToken, setScannedToken] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [issueEvidenceId, setIssueEvidenceId] = useState<number | null>(null);
  const [returnEvidenceId, setReturnEvidenceId] = useState<number | null>(null);
  const [returnRemark, setReturnRemark] = useState("");
  const [reportProblem, setReportProblem] = useState(false);
  const [problemNote, setProblemNote] = useState("");
  const [uploadKey, setUploadKey] = useState(0);
  const effectivePayload = scannedToken.trim();
  const checkout = useMutation({
    mutationFn: () =>
      publicToolCheckout(makerspaceSlug, {
        payload: effectivePayload,
        evidence_id: issueEvidenceId as number,
        ...contact.body(issueEvidenceId),
      }),
    onSuccess: () => {
      invalidatePublicInventory(queryClient, makerspaceSlug);
      contact.afterHandover();
      setIssueEvidenceId(null);
      setUploadKey((key) => key + 1);
    },
  });
  const returnTool = useMutation({
    mutationFn: () =>
      publicToolReturn(makerspaceSlug, {
        payload: effectivePayload,
        evidence_id: returnEvidenceId as number,
        remark: returnRemark.trim(),
        report_problem: reportProblem,
        problem_note: reportProblem ? problemNote.trim() : "",
        ...contact.body(returnEvidenceId),
      }),
    onSuccess: () => {
      invalidatePublicInventory(queryClient, makerspaceSlug);
      contact.afterHandover();
      setReturnEvidenceId(null);
      setReturnRemark("");
      setReportProblem(false);
      setProblemNote("");
      setUploadKey((key) => key + 1);
    },
  });
  const checkoutDisabled =
    !effectivePayload ||
    issueEvidenceId === null ||
    !contact.ready;
  const returnDisabled =
    !effectivePayload ||
    returnEvidenceId === null ||
    !returnRemark.trim() ||
    (reportProblem && !problemNote.trim()) ||
    !contact.ready;
  const error = checkout.error?.message ?? returnTool.error?.message;
  const result = checkout.data ?? returnTool.data;
  const returning = mode === "return";
  const pending = returning ? returnTool.isPending : checkout.isPending;
  const missing = !effectivePayload ? "Scan the tool's QR label first."
    : returning ? (returnEvidenceId === null ? "Add a return photo." : !returnRemark.trim() ? "Add return condition notes."
      : reportProblem && !problemNote.trim() ? "Describe the problem for staff." : "")
      : issueEvidenceId === null ? "Add a photo of the tool." : "";
  const contactMissing = missing || contact.ready ? "" : "Give your name, phone and email, and type the emailed code.";

  // Check out and Return are one choice, not two side-by-side forms: side by side they wrapped one
  // word per line in the narrow request column. Both photo steps stay mounted (just hidden) so an
  // uploaded photo survives switching back and forth.
  return (
    <div className="grid min-w-0 gap-4">
      <div>
        <h2 className="title-panel">Check out or return a tool</h2>
        <p className="mt-1 text-sm leading-6 text-muted">
          Scan the tool's QR label, add a photo, then confirm.
        </p>
      </div>
      <div className="[&>[role=radiogroup]]:flex [&>[role=radiogroup]]:w-full [&_[role=radio]]:flex-1">
        <SegmentedControl label="Scan action" value={mode} options={[{ value: "checkout", label: "Check out" }, { value: "return", label: "Return" }]}
          onChange={(value) => setMode(value as Mode)} />
      </div>

      {contact.details ? (
        <Step n={1} title="Your details (no account needed)">
          <ContactFields contact={contact.details} />
        </Step>
      ) : null}

      <Step n={contact.details ? 2 : 1} title="Scan the tool's QR">
        {scannedToken ? (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-success bg-success-soft px-3 py-1 text-success-ink">
            <span className="inline-flex items-center gap-2 text-sm font-semibold"><CircleCheck aria-hidden="true" size={18} />Tool scanned</span>
            <button type="button" className="min-h-11 px-2 text-sm underline underline-offset-4" onClick={() => setScannedToken("")}>
              Clear scan
            </button>
          </div>
        ) : (
          <button className="desk-button w-full" type="button" onClick={() => setScannerOpen(true)}>
            <QrCode aria-hidden="true" size={18} />Scan QR with camera
          </button>
        )}
      </Step>

      <Step n={contact.details ? 3 : 2} title={returning ? "Return photo and notes" : "Photo of the tool"}>
        <div hidden={returning}>
          <PublicEvidenceUpload
            key={`issue-${uploadKey}`}
            slug={makerspaceSlug}
            evidenceType="issue"
            disabled={checkout.isPending}
            contactEmail={contact.uploadEmail}
            onUploaded={(id, grant) => { contact.remember(id, grant); setIssueEvidenceId(id); }}
          />
        </div>
        <div hidden={!returning} className="grid gap-4">
          <PublicEvidenceUpload
            key={`return-${uploadKey}`}
            slug={makerspaceSlug}
            evidenceType="return"
            disabled={returnTool.isPending}
            contactEmail={contact.uploadEmail}
            onUploaded={(id, grant) => { contact.remember(id, grant); setReturnEvidenceId(id); }}
          />
          <label className="grid gap-1">
            <span className="text-sm font-semibold text-ink">Return condition notes</span>
            <textarea
              className="desk-input min-h-24 w-full resize-y"
              placeholder="Clean, working, all parts back"
              value={returnRemark}
              onChange={(event) => setReturnRemark(event.target.value)}
            />
          </label>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-ink">
            <input
              className="h-5 w-5 shrink-0 accent-brand"
              type="checkbox"
              checked={reportProblem}
              onChange={(event) => setReportProblem(event.target.checked)}
            />
            <span className="min-w-0">Report a problem with this tool</span>
          </label>
          {reportProblem ? (
            <label className="grid gap-1">
              <span className="text-sm font-semibold text-ink">What's wrong? (staff will review)</span>
              <textarea
                className="desk-input min-h-20 w-full resize-y"
                value={problemNote}
                onChange={(event) => setProblemNote(event.target.value)}
              />
            </label>
          ) : null}
        </div>
      </Step>

      <div className="grid gap-2 border-t border-line pt-4">
        <button
          className="desk-button-brand w-full disabled:cursor-not-allowed"
          disabled={(returning ? returnDisabled : checkoutDisabled) || pending}
          type="button"
          onClick={() => (returning ? returnTool.mutate() : checkout.mutate())}
        >
          {returning ? (returnTool.isPending ? "Returning..." : "Return") : checkout.isPending ? "Checking out..." : "Check out"}
        </button>
        {missing || contactMissing ? <p className="text-sm text-muted">{missing || contactMissing}</p> : null}
      </div>
      {error ? (
        <p role="alert" className="break-words rounded-lg border border-danger/40 bg-panel px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {result ? <LoanResult loan={result} /> : null}
      {scannerOpen ? (
        <QrScanner
          onClose={() => setScannerOpen(false)}
          onScan={(scanned) => {
            setScannedToken(scanned);
            setScannerOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
