import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Modal } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";
import { staffRequest } from "../../../../lib/api";
import { ChargeSettle } from "../../areaPayments/ChargeSettle";
import { JobActionFields } from "./JobActionFields";
import { initialJobValues, jobActionBody, type JobFormValues } from "./jobActionBody";
import { ACTION_ERROR_HELP } from "./jobLabels";
import { errorCode, type StaffJob } from "./machineJobsApi";

/**
 * Audit row MC3: the pickup desk's hand-over, with the same fields as the Machine Manager's board --
 * the member's pickup code (typed or scanned) and who collected it. Pay-before-pickup refusals say
 * the charge is due (never "may have been handed over already") and, when the desk may record the
 * cash, offer it right here.
 */
export function HandoverCollectDialog({ job, makerspaceId, onDone, onClose }: {
  job: MachineServiceRequest; makerspaceId: number; onDone: () => void; onClose: () => void;
}) {
  const [values, setValues] = useState<JobFormValues>(() => initialJobValues(job as unknown as StaffJob));
  const collect = useMutation({
    mutationFn: () => staffRequest(`/admin/machine-service/requests/${job.id}/collect`,
      { method: "POST", body: JSON.stringify(jobActionBody("collect", values, { hasPool: false, printer: false })) }),
    onSuccess: onDone,
  });
  const code = errorCode(collect.error);
  return <Modal open title={t`Hand over: ${job.title}`} onClose={onClose}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); collect.mutate(); }}>
      <JobActionFields action="collect" values={values} set={patch => setValues(current => ({ ...current, ...patch }))}
        machines={[]} pools={[]} unitLabel="" hasPool={false} showOverride={false} />
      {collect.error ? <p role="alert" className="text-sm text-danger">{code === "pickup_code"
        ? t`That pickup code does not match this job. Check it with the member and try again.`
        : (code && ACTION_ERROR_HELP[code]) ?? collect.error.message}</p> : null}
      {code === "payment_due" ? <ChargeSettle makerspaceId={makerspaceId} charge={job.payment}
        invalidateKeys={[["machine-service-handover", makerspaceId]]} /> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={collect.isPending}>
          {collect.isPending ? t`Saving…` : t`Mark collected`}</button>
      </div>
    </form>
  </Modal>;
}
