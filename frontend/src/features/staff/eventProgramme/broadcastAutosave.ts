import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { communicationKeys } from "../eventCommunicationsApi";
import type { BroadcastCampaign, BroadcastDraft } from "./broadcastApi";

export type AutosaveState = "idle" | "saving" | "saved" | "conflict" | "error";
const DELAY_MS = 1500;
const content = (draft: BroadcastDraft) => ({ subject: draft.subject, body: draft.body, statuses: draft.statuses, attendance: draft.attendance, design: draft.design, ctas: draft.ctas });

/** Server-side draft autosave (X41): versioned PATCH of an existing composer draft. */
export function useDraftAutosave(tenant: number, event: number, saved: BroadcastCampaign | null, draft: BroadcastDraft, onSaved: (row: BroadcastCampaign) => void) {
  const client = useQueryClient();
  const [state, setState] = useState<AutosaveState>("idle");
  const version = useRef(saved?.version ?? 0);
  const last = useRef(saved ? JSON.stringify(content({ ...saved, render_schema_version: 2 })) : "");
  const save = useMutation({
    mutationFn: (body: { operation_id: string; expected_version: number; draft: ReturnType<typeof content> }) => staffRequest<BroadcastCampaign>(`/admin/events/${event}/broadcasts/${saved!.id}/`, { method: "PATCH", headers: { "Idempotency-Key": body.operation_id }, body: JSON.stringify(body) }),
    onSuccess: row => { version.current = row.version; setState("saved"); onSaved(row); void client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }); },
    onError: (error: unknown) => setState((error as { status?: number })?.status === 409 ? "conflict" : "error"),
  });
  useEffect(() => { if (saved && saved.version > version.current) version.current = saved.version; }, [saved]);
  const digest = JSON.stringify(content(draft));
  const ready = !!saved && saved.status === "draft" && digest !== last.current && !!draft.subject.trim() && !!draft.body.trim() && draft.statuses.length > 0 && state !== "conflict";
  const flush = () => {
    if (!ready) return;
    last.current = digest;
    setState("saving");
    save.mutate({ operation_id: crypto.randomUUID(), expected_version: version.current, draft: content(draft) });
  };
  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(flush, DELAY_MS);
    return () => clearTimeout(timer);
    // `flush` reads the latest render; the digest captures every content change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, digest]);
  return { state, flush, pending: ready || save.isPending };
}

export const AUTOSAVE_TEXT: Record<AutosaveState, string> = {
  idle: "",
  saving: "Saving draft…",
  saved: "Draft saved",
  conflict: "This draft changed in another tab. Reopen it to keep editing.",
  error: "Autosave failed. Your changes are still here; try Save draft.",
};
