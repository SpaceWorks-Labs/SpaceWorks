import { t } from "@lingui/core/macro";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { toast, invalidateToastUndo, toastSession } from "../../../components/ui/toastStore";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import type { Makerspace } from "../panels/shared";
import { inverse, type Plan, type Step } from "./modulePlans";

const errorText = (error: unknown) => error instanceof StructuredApiError ? error.detail ?? error.message : t`Couldn't change this switch. Try again.`;

/**
 * Saving is per switch (the install and uninstall routes take one key; the feature route takes the full
 * list), so every change saves immediately and the toast offers Undo. A plan is a few ordered calls, all
 * through the audited services; a refused call stops the run and the screen reloads what actually changed.
 */
export function useModuleSwitches(makerspaceId: number) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const refresh = useCallback(() => Promise.all([
    ["modules", makerspaceId], ["makerspace-settings", makerspaceId], ["staff", "makerspaces"], ["makerspaces"], ["report-catalog"],
    ["operations-report"], ["platform-overview"], ["platform-dashboard"],
  ].map(queryKey => client.invalidateQueries({ queryKey }))), [client, makerspaceId]);

  const run = useCallback(async (steps: Step[]) => {
    const done: Step[] = [];
    try {
      for (const step of steps) {
        if (step.kind === "module") {
          await staffRequest(`/admin/makerspace/${makerspaceId}/modules/${step.action}`, { method: "POST", body: JSON.stringify({ key: step.key }) });
        } else {
          const settings = await staffRequest<Makerspace>(`/admin/makerspaces/${makerspaceId}`);
          const next = new Set(settings.enabled_features ?? []);
          step.remove?.forEach(key => next.delete(key));
          step.add?.forEach(key => next.add(key));
          await staffRequest(`/admin/makerspaces/${makerspaceId}`, { method: "PATCH", body: JSON.stringify({ enabled_features: [...next] }) });
        }
        done.push(step);
      }
    } finally { await refresh(); }
    return done;
  }, [makerspaceId, refresh]);

  const apply = useCallback(async (plan: Plan) => {
    if (!plan.steps.length) { toast(t`Nothing to change.`); return false; }
    setBusy(true); setError(""); invalidateToastUndo(`modules:${makerspaceId}`);
    const session = toastSession();
    let done: Step[] = [];
    try {
      done = await run(plan.steps);
    } catch (failure) {
      setError(errorText(failure));
      return false;
    } finally { setBusy(false); }
    setTouched(current => new Set([...current, ...plan.touched]));
    if (session === toastSession()) toast(plan.summary, { undoKey: `modules:${makerspaceId}`, undo: async () => { await run(inverse(done)); setTouched(current => { const next = new Set(current); plan.touched.forEach(key => next.delete(key)); return next; }); } });
    return true;
  }, [makerspaceId, run]);

  return { apply, busy, error, touched, clearError: () => setError("") };
}
