import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { formatTime } from "../../../lib/format";
import { communicationKeys } from "../eventCommunicationsApi";
import type { BroadcastCampaign, BroadcastDraft } from "./broadcastApi";

export type AutosaveState = { saving: boolean; failed: boolean; conflict: boolean; savedAt: string | null };
const DELAY_MS = 1500;
const content = (draft: Omit<BroadcastDraft, "render_schema_version">) => ({ subject: draft.subject, body: draft.body, statuses: draft.statuses,
  attendance: draft.attendance, design: draft.design, ctas: draft.ctas ?? [] });
export const draftDigest = (draft: Omit<BroadcastDraft, "render_schema_version">) => JSON.stringify(content(draft));
export const draftComplete = (draft: BroadcastDraft) => !!draft.subject.trim() && !!draft.body.trim() && draft.statuses.length > 0;

/**
 * Server-side draft autosave (X41, parity B22): a versioned PATCH of the author's own private draft. A draft
 * belongs to its author only (others get a 404), there is one per author and event, and `flush` saves now.
 */
export function useDraftAutosave(tenant: number, event: number, saved: BroadcastCampaign | null, draft: BroadcastDraft, onSaved: (row: BroadcastCampaign) => void) {
  const client = useQueryClient();
  const [state, setState] = useState<AutosaveState>({ saving: false, failed: false, conflict: false, savedAt: null });
  const version = useRef(saved?.version ?? 0);
  const last = useRef(saved ? draftDigest(saved) : "");
  const savedId = useRef(saved?.id ?? null);
  // A newly opened or reopened draft is the saved baseline; any difference from it is unsaved work.
  if (saved && saved.id !== savedId.current) { savedId.current = saved.id; last.current = draftDigest(saved); version.current = saved.version; }
  const save = useMutation({
    mutationFn: (body: { operation_id: string; expected_version: number; draft: ReturnType<typeof content> }) => staffRequest<BroadcastCampaign>(`/admin/events/${event}/broadcasts/${saved!.id}/`, { method: "PATCH", headers: { "Idempotency-Key": body.operation_id }, body: JSON.stringify(body) }),
    onSuccess: row => { version.current = row.version; setState({ saving: false, failed: false, conflict: false, savedAt: new Date().toISOString() }); onSaved(row); void client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }); },
    onError: (error: unknown) => { last.current = ""; setState(value => ({ ...value, saving: false, failed: true, conflict: (error as { status?: number })?.status === 409 })); },
  });
  useEffect(() => { if (saved && saved.version > version.current) version.current = saved.version; }, [saved]);
  const digest = draftDigest(draft);
  const dirty = digest !== last.current;
  const ready = !!saved && saved.status === "draft" && dirty && draftComplete(draft) && !state.conflict;
  const flush = () => {
    if (!ready) return;
    last.current = digest;
    setState(value => ({ ...value, saving: true, failed: false }));
    save.mutate({ operation_id: crypto.randomUUID(), expected_version: version.current, draft: content(draft) });
  };
  useEffect(() => {
    if (!ready || state.failed) return;
    const timer = setTimeout(flush, DELAY_MS);
    return () => clearTimeout(timer);
    // `flush` reads the latest render; the digest captures every content change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, digest, state.failed]);
  return { state, flush, dirty, pending: ready || save.isPending };
}

/** The quiet status line under the message, in the words staff see while they write. */
export function draftStatusText(state: AutosaveState, dirty: boolean, hasDraft: boolean) {
  if (state.conflict) return t`This draft changed in another tab. Reopen it to keep editing.`;
  if (state.saving) return t`Saving…`;
  if (state.failed && dirty) return t`Couldn't save`;
  if (dirty) return t`Unsaved changes`;
  if (hasDraft && state.savedAt) return t`Draft saved · ${formatTime(state.savedAt)}`;
  if (hasDraft) return t`Draft saved`;
  return t`Changes are saved as a draft automatically.`;
}

/** Discard the author's own draft (DELETE; only a draft can go). */
export function useDraftDiscard(tenant: number, event: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: number) => staffRequest<void>(`/admin/events/${event}/broadcasts/${campaignId}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }),
  });
}

/** Ask before the tab closes while work is unsaved. */
export function useUnsavedGuard(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [active]);
}
