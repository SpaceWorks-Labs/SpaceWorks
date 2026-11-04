import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { getSessionGeneration } from "../../lib/api/sessionTokens";
import { completeResume, createResume, deleteResume, downloadResume, resumeStatus, saveBlob, saveDetail, uploadResume } from "./api";
import { savedDetailsKey, type ResumeAsset, type SavedCommand, type SavedField } from "./types";

type Attempt = { file: File; epoch: number; session: number; createId: string; completeId: string; uploaded: boolean; asset?: ResumeAsset; abort: AbortController };
type PreviousUpload = ResumeAsset & { filename: string };

/** Key the private component even when its caller reuses an account route. */
export function ResumeVault(props: { actorId: number; saved?: SavedField }) {
  return <OwnerResumeVault key={props.actorId} {...props} />;
}

function OwnerResumeVault({ actorId, saved }: { actorId: number; saved?: SavedField }) {
  const client = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [asset, setAsset] = useState<ResumeAsset | null>(null);
  const [retired, setRetired] = useState<PreviousUpload[]>([]);
  const [consent, setConsent] = useState(false);
  const work = useRef<Attempt | null>(null);
  const epoch = useRef(0), mounted = useRef(true);
  const saveCommand = useRef<{ assetId: number; command: SavedCommand } | null>(null);
  const deleteCommands = useRef(new Map<number, { asset: ResumeAsset; id: string }>());
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; work.current?.abort.abort(); }; }, []);
  const active = (attempt: Attempt) => mounted.current && attempt.epoch === epoch.current && attempt.session === getSessionGeneration("person") && !attempt.abort.signal.aborted;
  const guard = (attempt: Attempt) => { if (!active(attempt)) throw new DOMException("The file or account changed.", "AbortError"); };
  const savedId = saved?.value && typeof saved.value === "object" && "asset_id" in saved.value ? saved.value.asset_id : undefined;
  const assetId = asset?.asset_id || savedId;
  const statusKey = (id: number) => [...savedDetailsKey(actorId), "resume", id] as const;
  const status = useQuery({ queryKey: [...savedDetailsKey(actorId), "resume", assetId],
    queryFn: () => resumeStatus(assetId!), enabled: Boolean(assetId), gcTime: 0, retry: false,
    refetchInterval: query => ["uploading", "validating"].includes(query.state.data?.state || "") && document.visibilityState === "visible" ? 3000 : false });
  const current = status.data || asset;
  const refresh = () => client.invalidateQueries({ queryKey: savedDetailsKey(actorId) });
  const publish = async (attempt: Attempt, next: ResumeAsset) => {
    guard(attempt);
    await client.cancelQueries({ queryKey: statusKey(next.asset_id), exact: true });
    guard(attempt);
    attempt.asset = next; setAsset(next); client.setQueryData(statusKey(next.asset_id), next);
  };
  const upload = useMutation({ mutationFn: async () => {
    if (!file || file.size < 1 || file.size > 10 * 1024 ** 2 || !file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF of at most 10 MiB.");
    const attempt: Attempt = work.current ?? { file, epoch: epoch.current, session: getSessionGeneration("person"), createId: crypto.randomUUID(), completeId: crypto.randomUUID(), uploaded: false, abort: new AbortController() };
    work.current = attempt;
    guard(attempt);
    // A retry before byte completion replays create to refresh an expired presign.
    if (!attempt.asset || (!attempt.uploaded && attempt.asset.state === "uploading")) {
      const created = await createResume(attempt.file, attempt.createId);
      attempt.asset = created;
      if (!active(attempt) && mounted.current && attempt.session === getSessionGeneration("person")) setRetired(items => [...items.filter(item => item.asset_id !== created.asset_id), { ...created, filename: attempt.file.name }]);
      await publish(attempt, created);
    }
    guard(attempt);
    // Replaying a previously accepted create may already return validating/ready.
    if (attempt.asset!.state !== "uploading") { await publish(attempt, await resumeStatus(attempt.asset!.asset_id)); return; }
    if (!attempt.uploaded) {
      await uploadResume(attempt.file, attempt.asset!, attempt.abort.signal);
      guard(attempt); attempt.uploaded = true;
    }
    const completed = await completeResume(attempt.asset!, attempt.completeId);
    await publish(attempt, { ...attempt.asset!, ...completed });
    await refresh();
  } });
  const save = useMutation({ mutationFn: async () => {
    if (current?.state !== "ready" || !consent) throw new Error("Wait for the PDF check and choose whether to save it.");
    if (!saveCommand.current || saveCommand.current.assetId !== current.asset_id) saveCommand.current = { assetId: current.asset_id, command: { operation_id: crypto.randomUUID(), expected_version: saved?.version || 0 } };
    return saveDetail("resume", { asset_id: current.asset_id, sha256: current.sha256 }, saveCommand.current.command);
  }, onSuccess: () => { if (mounted.current) { saveCommand.current = null; return refresh(); } } });
  const remove = useMutation({ mutationFn: async (target: ResumeAsset) => {
    const session = getSessionGeneration("person");
    let command = deleteCommands.current.get(target.asset_id);
    if (!command) {
      const latest = await resumeStatus(target.asset_id);
      if (!mounted.current || session !== getSessionGeneration("person")) throw new DOMException("The account changed.", "AbortError");
      command = { asset: latest, id: crypto.randomUUID() }; deleteCommands.current.set(target.asset_id, command);
    }
    await deleteResume(command.asset, command.id);
    return target.asset_id;
  }, onSuccess: async id => {
    if (!mounted.current) return;
    setRetired(items => items.filter(item => item.asset_id !== id));
    if (id === assetId) { work.current?.abort.abort(); work.current = null; setAsset(null); setFile(null); setConsent(false); }
    await refresh();
  } });
  const download = useMutation({ mutationFn: async () => {
    if (!current) return;
    const session = getSessionGeneration("person"), blob = await downloadResume(current.asset_id);
    if (mounted.current && session === getSessionGeneration("person")) saveBlob(blob, "resume.pdf");
  } });
  const chooseFile = (next: File | null) => {
    epoch.current += 1; work.current?.abort.abort();
    const previous = work.current?.asset;
    if (previous && previous.asset_id !== savedId) setRetired(items => [...items.filter(item => item.asset_id !== previous.asset_id), { ...previous, filename: work.current!.file.name }]);
    work.current = null; saveCommand.current = null;
    setFile(next); setAsset(null); setConsent(false); upload.reset(); save.reset();
  };
  const error = upload.error || status.error || save.error || remove.error || download.error;
  const changing = upload.isPending || save.isPending || remove.isPending;
  return <div className="grid gap-3 rounded-card border border-line p-4">
    <Field label="Private résumé" hint="PDF only, up to 10 MiB. Uploading does not opt you in to saving or sponsor sharing.">
      <input className="desk-input" type="file" accept="application/pdf,.pdf" disabled={save.isPending || remove.isPending} onChange={e => chooseFile(e.target.files?.[0] || null)} />
    </Field>
    <button className="desk-button" disabled={!file || changing} onClick={() => upload.mutate()}>{work.current?.uploaded ? "Check or finish PDF upload" : "Upload PDF"}</button>
    {current ? <p role="status">{file && !asset ? "Previously saved résumé" : "Résumé"}: {current.state === "validating" ? "checking file safety" : current.state}</p> : null}
    {current?.state === "ready" && (!file || asset) ? <><label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={consent} disabled={changing} onChange={e => setConsent(e.target.checked)} />Save this résumé to my private details</label>
      <div className="flex flex-wrap gap-2"><button className="desk-button-primary" disabled={!consent || changing} onClick={() => save.mutate()}>Save résumé</button>
        <button className="desk-button" disabled={download.isPending || changing} onClick={() => download.mutate()}>Download PDF</button></div></> : null}
    {current && !["deleted", "deleting"].includes(current.state) ? <button className="desk-button-danger-outline" disabled={changing} onClick={() => remove.mutate(current)}>Delete uploaded résumé</button> : null}
    {retired.filter(item => item.asset_id !== assetId && item.asset_id !== savedId).map(item => <div key={item.asset_id} className="flex flex-wrap items-center gap-2">
      <p className="text-sm text-muted">Previous unsaved PDF: {item.filename}</p><button className="desk-button-danger-outline" disabled={changing} onClick={() => remove.mutate(item)}>Delete previous PDF {item.filename}</button>
    </div>)}
    <p className="text-sm text-muted">An event receives its own copy when you submit a résumé. Deleting this private copy does not delete already-submitted evidence.</p>
    {error && error.name !== "AbortError" ? <p role="alert" className="text-danger">{error.message}</p> : null}
    {save.isSuccess ? <p role="status">Résumé saved privately.</p> : null}
  </div>;
}
