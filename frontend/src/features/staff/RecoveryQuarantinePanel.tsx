import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { CenteredCardLayout } from "../../components/layouts";

export type RecoveryState = {
  mode: "normal" | "quiesced" | "quarantined";
  quarantine_reason: string;
  quarantined_at: string | null;
  residual_risk: string;
};

export function RecoveryQuarantinePanel({ state, onAcknowledged }: { state: RecoveryState; onAcknowledged: (state: RecoveryState) => void }) {
  const [confirmed, setConfirmed] = useState(false);
  const acknowledge = useMutation({
    mutationFn: () => staffRequest<RecoveryState>("/recovery", {
      method: "POST",
      body: JSON.stringify({ acknowledgement: state.residual_risk }),
    }),
    onSuccess: onAcknowledged,
  });
  return <CenteredCardLayout state={{ status: "ready" }} width={480}
    media={{ icon: "TriangleAlert", tone: "danger" }} eyebrow={t`Recovery quarantine`}
    title={t`Staff access is paused`} body={state.quarantine_reason}
    primary={{ label: t`Lift quarantine`, tone: "danger", pending: acknowledge.isPending, pendingLabel: t`Acknowledging…`,
      disabled: !confirmed, disabledReason: t`Review and accept the residual risk first.`, onClick: () => acknowledge.mutate() }}
    content={<div className="grid gap-4">
      <div className="rounded-xl border border-danger-line bg-panel p-4 text-sm text-danger">
        <p className="font-semibold">{t`Residual risk`}</p><p className="mt-2">{state.residual_risk}</p>
      </div>
      <label className="flex min-h-11 cursor-pointer items-start gap-3 text-sm text-ink">
        <input className="mt-1" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
        {t`I reviewed the restore report where one exists and accept this exact residual risk.`}</label>
      {acknowledge.error ? <p className="text-sm text-danger" role="alert">{acknowledge.error.message}</p> : null}
    </div>} />;
}
