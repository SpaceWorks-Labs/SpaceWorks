import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { tenantPublicRequest } from "../../lib/api";
import type { TypeIntake } from "../inventory/MachineIntakeForm";
import { fetchPublicConsumablePools } from "../printing/publicApi";
import { fetchJobTypes, jobKeys, submitJob } from "./api";
import { emptyDraft, submitBody, type JobDraft } from "./jobDraft";
import { fileKey, JobUploadError, uploadJobFiles, type FileErrors, type JobFile } from "./jobUploads";
import { preselectType } from "./JobTypeStep";

export const JOB_STEPS = ["type", "files", "details", "confirm"] as const;
export type JobStep = typeof JOB_STEPS[number];

/** All server and draft state of the "Request a job" flow; the page only lays it out. */
export function useJobRequest(slug: string, features: string[], search: URLSearchParams, onSubmitted: (jobId: number) => void) {
  const queryClient = useQueryClient();
  const types = useQuery({ queryKey: jobKeys.types(slug), queryFn: () => fetchJobTypes(slug), enabled: Boolean(slug), retry: false });
  const [queueId, setQueueId] = useState<number | null>(null);
  const [step, setStep] = useState<JobStep>("type");
  const [models, setModels] = useState<File[]>([]);
  const [screenshots, setScreenshots] = useState<File[]>([]);
  const [fileErrors, setFileErrors] = useState<FileErrors>({});
  const [draft, setDraft] = useState<JobDraft>(emptyDraft);
  const [progress, setProgress] = useState("");
  // Files already staged for this type: a retry after a refusal (say, "check in first") re-uses them.
  const staged = useRef(new Map<string, number>());

  useEffect(() => {
    if (!types.data || queueId !== null) return;
    const chosen = preselectType(types.data, search);
    if (!chosen) return;
    setQueueId(chosen.queue_id);
    if (search.has("type") || search.has("queue")) setStep("files");
  }, [types.data]); // preselect once, when the list arrives

  const type = types.data?.find(row => row.queue_id === queueId);
  const intakeOn = features.includes("machines.structured_intake") || features.includes("machines.material_catalogue");
  const intake = useQuery({ queryKey: ["machine-intake", slug, type?.machine_type_id],
    queryFn: () => tenantPublicRequest<TypeIntake>(slug, `/public/${encodeURIComponent(slug)}/machine-types/${type!.machine_type_id}/intake`),
    enabled: Boolean(type) && intakeOn, retry: false });
  const pools = useQuery({ queryKey: ["public-printer-consumable-pools", slug], queryFn: () => fetchPublicConsumablePools(slug),
    enabled: Boolean(type?.is_printer), retry: false });

  const submit = useMutation({
    mutationFn: async () => {
      if (!type) throw new Error("Choose a machine type first.");
      const all: JobFile[] = [...models.map(file => ({ file, kind: "model" as const })), ...screenshots.map(file => ({ file, kind: "screenshot" as const }))];
      const pending = all.filter(item => !staged.current.has(fileKey(item.file)));
      const ids = await uploadJobFiles(slug, type.queue_id, pending, setProgress);
      pending.forEach((item, index) => staged.current.set(fileKey(item.file), ids[index]));
      const fileIds = all.map(item => staged.current.get(fileKey(item.file))!);
      return submitJob(slug, submitBody(type, draft, fileIds, intake.data, pools.data));
    },
    onSuccess: job => {
      void queryClient.invalidateQueries({ queryKey: jobKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["public-printer-consumable-pools", slug] });
      onSubmitted(job.id);
    },
    onError: error => {
      if (error instanceof JobUploadError) { setFileErrors(error.errors); setStep("files"); }
    },
  });

  function chooseType(next: number) {
    if (next === queueId) return;
    staged.current.clear();
    setFileErrors({});
    setDraft(current => ({ ...current, intake: {}, material: "", color: "", poolId: "" }));
    setQueueId(next);
  }
  function changeFiles(next: { models?: File[]; screenshots?: File[] }) {
    if (next.models) setModels(next.models);
    if (next.screenshots) setScreenshots(next.screenshots);
    setFileErrors({});
  }
  const update = (patch: Partial<JobDraft>) => setDraft(current => ({ ...current, ...patch }));

  return { types, type, step, setStep, chooseType, models, screenshots, changeFiles, fileErrors, draft, update,
    intake, pools, submit, progress };
}
