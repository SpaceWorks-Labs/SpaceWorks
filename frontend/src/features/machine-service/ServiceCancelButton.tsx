import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { ConfirmDialog } from "../../components/ui";

/** Cancel with an explicit confirmation, then refetch every affected server view.
 *
 * The queue changes for everyone behind this job, so the caller lists the request
 * lists, detail/activity and machine-summary keys to invalidate; other viewers pick the
 * shortened timeline up on their normal polling cadence.
 */
export function ServiceCancelButton({ title, onCancel, invalidate, label = t`Cancel job`, staff = false }: {
  title: string;
  onCancel: () => Promise<unknown>;
  invalidate: QueryKey[];
  label?: string;
  staff?: boolean;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const cancel = useMutation({
    mutationFn: onCancel,
    onSuccess: async () => {
      setOpen(false);
      await Promise.all(invalidate.map(queryKey => queryClient.invalidateQueries({ queryKey })));
    },
  });
  const message = staff
    ? `Cancel "${title}"? Any reserved material goes back to its pool, nothing is charged, and the requester is told.`
    : `Cancel "${title}"? Any reserved material goes back to its pool and nothing is charged. This can't be undone.`;
  return <div className="grid gap-1">
    <button className="desk-button-danger-outline" type="button" disabled={cancel.isPending || cancel.isSuccess}
      onClick={() => setOpen(true)}>
      {cancel.isSuccess ? t`Cancelled` : label}
    </button>
    {cancel.error ? <p className="text-sm text-danger" role="alert">{cancel.error.message}</p> : null}
    <ConfirmDialog open={open} title={t`Cancel this job?`} message={message} tone="danger"
      confirmLabel={cancel.isPending ? t`Cancelling…` : t`Yes, cancel job`} cancelLabel={t`Keep job`} pending={cancel.isPending}
      onConfirm={() => cancel.mutate()} onCancel={() => setOpen(false)} />
  </div>;
}
