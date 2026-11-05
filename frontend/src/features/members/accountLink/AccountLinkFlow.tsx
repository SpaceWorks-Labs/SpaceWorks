import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlowLayout } from "../../../components/layouts";
import type { Action, CalloutProps } from "../../../components/ui";
import { ActionControl } from "../../../components/ui/ActionControl";
import { StructuredApiError } from "../../../lib/api";
import { cancelMerge, confirmMerge, errorCode, fetchMergePreview, linkErrorCopy, mergeMeKey, mergePreviewKey, proveMerge, proveMergeWithPasskey,
  resendMergeCodes, startMerge, type MergeIntent, type MergeMethod, type MergeResult } from "./accountLinkApi";
import { ConfirmStep, ResultCounts, ReviewStep } from "./AccountLinkReview";
import { proofReady, ProveStep, StartStep, type ProofFields } from "./AccountLinkSteps";
import { isPasskeyCancelled, passkeysSupported } from "../../auth/passkeys/webauthn";

type Step = "start" | "prove" | "review" | "confirm";
const ORDER: Step[] = ["start", "prove", "review", "confirm"];
const LABELS: Record<Step, string> = { start: "Start", prove: "Prove", review: "Review", confirm: "Confirm" };
const EMPTY: ProofFields = { password: "", otp: "", survivorCode: "", sourceCode: "" };
const ignore = () => undefined;

/** Links a second (former staff) account into the signed-in one. Proof first, then a server preview, then confirm. */
export function AccountLinkFlow({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [step, setStep] = useState<Step>("start");
  const [identifier, setIdentifier] = useState("");
  const [method, setMethod] = useState<MergeMethod>("credentials");
  const [intent, setIntent] = useState<MergeIntent | null>(null);
  const [fields, setFields] = useState<ProofFields>(EMPTY);
  const [understood, setUnderstood] = useState(false);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<MergeResult | null>(null);
  const intentId = intent?.intent_id ?? "";
  const preview = useQuery({ queryKey: mergePreviewKey(intentId), queryFn: () => fetchMergePreview(intentId), retry: false,
    // The hash confirmed must be the one the person read, so the preview never refreshes behind them.
    staleTime: Infinity, enabled: Boolean(intentId) && (step === "review" || step === "confirm") && !result });

  const fail = (failure: unknown) => {
    setError(failure);
    const code = errorCode(failure);
    if (code === "proof_expired") { setIntent(null); setFields(EMPTY); setStep("start"); }
    if (code === "preview_stale") { setUnderstood(false); setStep("review"); void client.invalidateQueries({ queryKey: mergePreviewKey(intentId) }); }
  };
  const begin = useMutation({ mutationFn: (chosen: MergeMethod) => startMerge(identifier.trim(), chosen), onMutate: () => setError(null), onError: fail,
    onSuccess: next => { setIntent(next); setMethod(next.method); setFields(EMPTY); setResent(false); setStep("prove"); } });
  const prove = useMutation({ onMutate: () => setError(null), onError: fail,
    mutationFn: () => proveMerge(intentId, method === "credentials" ? { password: fields.password, otp: fields.otp }
      : { survivor_code: fields.survivorCode, source_code: fields.sourceCode }),
    onSuccess: next => { setIntent(next); setFields(EMPTY); if (next.state === "proved") setStep("review"); else setError(new StructuredApiError(400, { code: "proof_failed" })); } });
  const passkey = useMutation({ onMutate: () => setError(null),
    onError: (failure: unknown) => { if (!isPasskeyCancelled(failure)) fail(failure); },
    mutationFn: () => proveMergeWithPasskey(intentId, fields.password),
    onSuccess: next => { setIntent(next); setFields(EMPTY); if (next.state === "proved") setStep("review"); else setError(new StructuredApiError(400, { code: "proof_failed" })); } });
  const resend = useMutation({ mutationFn: () => resendMergeCodes(intentId), onMutate: () => { setError(null); setResent(false); }, onError: fail,
    onSuccess: next => { setIntent(next); setFields(EMPTY); setResent(true); } });
  const confirm = useMutation({ mutationFn: (sha: string) => confirmMerge(intentId, sha), onMutate: () => setError(null), onError: fail,
    onSuccess: async done => {
      setResult(done);
      await Promise.all([["member"], ["staff", "me"], mergeMeKey].map(queryKey => client.invalidateQueries({ queryKey })));
    } });

  const dropIntent = () => { if (intentId) void cancelMerge(intentId).catch(ignore); setIntent(null); };
  const close = () => { if (!result) dropIntent(); onClose(); };
  const switchToCodes = () => { dropIntent(); setMethod("email_codes"); begin.mutate("email_codes"); };
  const code = errorCode(error);
  const callout: CalloutProps | undefined = error ? { size: "panel", tone: code === "preview_stale" || code === "proof_expired" ? "warn" : "danger",
    lead: linkErrorCopy(error), action: code === "factor_enrolment_required" ? { label: "Use emailed codes instead", onClick: switchToCodes } : undefined } : undefined;

  const reviewing = step === "review" || step === "confirm";
  const state = reviewing && preview.isPending ? { status: "loading" as const }
    : reviewing && preview.isError ? { status: "error" as const, error: linkErrorCopy(preview.error), onRetry: () => void preview.refetch() }
    : { status: "ready" as const };
  const index = ORDER.indexOf(step);
  const steps = ORDER.map((key, i) => ({ key, label: LABELS[key], required: true,
    state: i < index ? "done" as const : i === index ? "current" as const : "todo" as const }));
  const footers: Record<Step, { back?: Action; next: Action }> = {
    start: { next: { label: "Continue", pending: begin.isPending, pendingLabel: "Starting…", onClick: () => begin.mutate(method),
      disabled: !identifier.trim(), disabledReason: "Enter the other account's username or email." } },
    prove: { back: { label: "Back", disabled: prove.isPending, onClick: () => { dropIntent(); setError(null); setStep("start"); } },
      next: { label: "Verify", pending: prove.isPending, pendingLabel: "Checking…", onClick: () => prove.mutate(), disabled: !proofReady(method, fields),
        disabledReason: method === "credentials" ? "Enter the password and the authenticator code." : "Enter both codes." } },
    review: { next: { label: "Continue to confirm", onClick: () => { setError(null); setStep("confirm"); } } },
    confirm: { back: { label: "Back to review", disabled: confirm.isPending, onClick: () => setStep("review") },
      next: { label: "Link accounts", pending: confirm.isPending, pendingLabel: "Linking…", disabled: !understood || !preview.data,
        disabledReason: "Tick the box to confirm you understand.", onClick: () => { if (preview.data) confirm.mutate(preview.data.preview_sha256); } } },
  };

  const grace = Boolean(result?.grace_opened);
  const staff: Action | undefined = result?.roles_gained.length ? { label: "Open the staff console", href: "/admin" } : undefined;
  const back: Action = { label: "Back to your account", onClick: onClose };
  return <FlowLayout presentation="dialog" open={open} title="Link your staff account" accentTitle state={state}
    subject="Bring a second account's roles and history into the one you're signed in to."
    steps={steps} current={step} footer={footers[step]} onCancel={close} error={callout}
    leaveGuard={intent && !result ? "Your link request will be cancelled. Nothing has been linked." : undefined}
    result={result ? { tone: "success", title: "Accounts linked",
      summary: grace ? "Set up two-step sign-in within 3 days to keep using staff screens. Member features keep working."
        : "Your roles and history now live in this account. The other account no longer signs in.",
      children: <><ResultCounts result={result} />{grace && staff ? <div><ActionControl action={staff} /></div> : null}</>,
      next: grace ? { label: "Set up two-step sign-in", href: "/mfa" } : back, undo: grace ? back : staff } : undefined}
    work={step === "start" ? <StartStep identifier={identifier} method={method} onIdentifier={setIdentifier} onMethod={setMethod} />
      : step === "prove" ? <ProveStep method={method} identifier={identifier.trim()} fields={fields} onChange={setFields}
        onResend={() => resend.mutate()} resending={resend.isPending} resent={resent}
        passkey={passkeysSupported() ? { onUse: () => passkey.mutate(), pending: passkey.isPending } : undefined} />
      : preview.data ? step === "review" ? <ReviewStep preview={preview.data} />
        : <ConfirmStep preview={preview.data} understood={understood} onUnderstood={setUnderstood} /> : null} />;
}
