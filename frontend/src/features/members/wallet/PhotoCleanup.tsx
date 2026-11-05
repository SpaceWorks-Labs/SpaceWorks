// Optional background clean-up of the card photo (SPEC §6, Q-I3). It runs on this server as a
// short job; the cleaned photo is only a candidate until the holder keeps it (the original is
// then deleted) or keeps the original. Hidden when the server has no clean-up model.
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { memberRequest } from "../../../lib/api";
import { cardPath, myCardsKey, type MyCard } from "./api";

type CleanupJob = { id: number; state: "queued" | "running" | "succeeded" | "failed" | "cancelled"; error_code?: string };
const POLL_MS = 1500;
const POLL_TRIES = 60;

export async function waitForJob(id: number, wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))) {
  let job = await memberRequest<CleanupJob>(`/member/card-jobs/${id}`);
  for (let tries = 0; tries < POLL_TRIES && (job.state === "queued" || job.state === "running"); tries += 1) {
    await wait(POLL_MS);
    job = await memberRequest<CleanupJob>(`/member/card-jobs/${id}`);
  }
  return job;
}

export function PhotoCleanup({ card }: { card: MyCard }) {
  const client = useQueryClient();
  const [candidate, setCandidate] = useState<{ job: number; url: string } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const start = useMutation({ mutationFn: async () => {
    setDone(null);
    const queued = await memberRequest<CleanupJob>(`${cardPath(card)}/photo/cleanup`, { method: "POST" });
    const job = await waitForJob(queued.id);
    if (job.state !== "succeeded") throw new Error("The clean-up didn't finish. Your photo is unchanged; try again later.");
    const { url } = await memberRequest<{ url: string }>(`/member/card-jobs/${job.id}/result`);
    setCandidate({ job: job.id, url });
  } });
  const decide = useMutation({ mutationFn: async (keep: boolean) => {
    if (!candidate) return;
    await memberRequest(`${cardPath(card)}/photo/${keep ? "accept" : "discard"}`, { method: "POST",
      body: JSON.stringify({ job_id: candidate.job }) });
    setCandidate(null);
    setDone(keep ? "The cleaned photo is on your card now." : "You kept your original photo.");
    await client.invalidateQueries({ queryKey: myCardsKey });
    await client.invalidateQueries({ queryKey: ["member", "card-image"] });
    await client.invalidateQueries({ queryKey: ["member", "card-face"] });
  } });
  if (!card.photo_set || !card.photo_cleanup_available) return null;
  return <div className="grid gap-2">
    <p className="text-sm text-ink">Tidy the background: our server puts you on a plain white background. Nothing changes until you choose.</p>
    {!candidate ? <button type="button" className="desk-button-ghost min-h-11 w-fit" disabled={start.isPending}
      onClick={() => start.mutate()}>{start.isPending ? "Cleaning up…" : "Clean up the background"}</button> : null}
    {candidate ? <div className="grid gap-2">
      <img src={candidate.url} alt="Your photo with a cleaned background" className="h-40 w-auto max-w-full rounded-control border border-line bg-white object-contain" />
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button-primary min-h-11" disabled={decide.isPending} onClick={() => decide.mutate(true)}>
          Use the cleaned photo</button>
        <button type="button" className="desk-button min-h-11" disabled={decide.isPending} onClick={() => decide.mutate(false)}>
          Keep my original</button>
      </div>
      <p className="text-xs text-muted">Using the cleaned photo deletes the original.</p>
    </div> : null}
    <p role="status" aria-live="polite" className="text-sm text-success">{done ?? ""}</p>
    {start.error || decide.error ? <ErrorText message={(start.error ?? decide.error)?.message} /> : null}
  </div>;
}
