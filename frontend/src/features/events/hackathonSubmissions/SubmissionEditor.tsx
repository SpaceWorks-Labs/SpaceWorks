import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { ActionControl, Callout, Field, Spinner } from "../../../components/ui";
import { useSubmission, useSubmissionCommand } from "./api";
import { ProgrammeCharges } from "./ProgrammeCharges";
import { LinkEditor } from "./LinkEditor";
import { UploadEditor } from "./UploadEditor";
import { ProjectFormFields } from "./ProjectFormFields";
import { AssetList } from "./AssetList";
import { StageAnswerFields, StageChecklist, StageTracker } from "./StageTracker";
import { parts, submissionErrorMessage } from "./stageRules";
import type { Project, SubmissionScope, UploadSpec } from "./types";

const blank: Project = { title: "", tagline: "", problem: "", description: "", challenges: "", tech_tags: [],
  ai_declaration: { used: false, details: "" }, reuse_declaration: { used: false, details: "" },
  form_answers: {}, track_ids: [], prize_ids: [], asset_ids: [], public_asset_ids: [], links: [], public_requested: false };

/** G mounts this inside AppShell. Server state stays in TanStack Query; local
 * fields are a draft and never overwrite a newer server version implicitly. */
export function SubmissionEditor({ scope, uploadOrigins, formats, tracks = [], prizes = [], formFields }: {
  scope: SubmissionScope; uploadOrigins: readonly string[]; formats: readonly (UploadSpec & { label: string })[];
  tracks?: readonly { id: number; label: string }[]; prizes?: readonly { id: number; label: string }[];
  formFields?: (answers: Record<string, unknown>, change: (answers: Record<string, unknown>) => void) => ReactNode;
}) {
  const query = useSubmission(scope), mutation = useSubmissionCommand(scope);
  const [project, setProject] = useState<Project>(blank);
  const [dirty, setDirty] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [filesReady, setFilesReady] = useState(false);
  const version = useRef<number | null>(null);
  const operation = useRef(crypto.randomUUID());
  useEffect(() => {
    if (!query.data || dirty) return;
    setProject({ ...blank, ...query.data.project,
      ai_declaration: { ...blank.ai_declaration, ...query.data.project.ai_declaration },
      reuse_declaration: { ...blank.reuse_declaration, ...query.data.project.reuse_declaration } });
    version.current = query.data.version;
  }, [query.data, dirty]);
  const change = (patch: Partial<Project>) => { setProject(value => ({ ...value, ...patch })); setDirty(true); operation.current = crypto.randomUUID(); };
  const active = query.data?.requirements?.stages?.find(stage => stage.id === query.data?.requirements?.active_stage_id);
  async function command(action: "save" | "submit" | "withdraw") {
    if (version.current === null) return;
    try {
      const result = await mutation.mutateAsync({ action, version: version.current, stageId: active?.id,
        project: action === "save" ? Object.fromEntries(Object.entries(project).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(query.data?.project[key as keyof Project]))) : undefined, operationId: operation.current });
      version.current = result.version; operation.current = crypto.randomUUID(); setDirty(false);
    } catch { /* Mutation error stays visible and the operation ID survives retry. */ }
  }
  if (query.isLoading) return <div role="status"><Spinner />{t`Loading project…`}</div>;
  if (query.isError) return <Callout size="panel" tone="danger" lead="Could not load your project."
    action={{ label: t`Retry`, onClick: () => void query.refetch() }} />;
  const requirements = query.data?.requirements;
  const stages = requirements?.stages ?? [];
  const show = parts(active); // #177: the active stage decides whether files, links or both are taken.
  const availableTracks = requirements?.tracks ?? tracks;
  const availablePrizes = requirements?.prizes ?? prizes;
  const locked = !["draft", "submitted"].includes(query.data?.state ?? "draft") || !query.data?.allowed_actions.includes("save");
  const form = <div className="grid gap-6">
    <p className="text-sm text-muted">{t`Build your project draft, then submit a frozen version for judging. Files stay private until you choose gallery sharing and the organizer publishes it.`}</p>
    {query.data?.snapshot_id ? <p role="status" className="rounded-xl border border-line bg-success-soft p-3 text-sm text-success-ink">{t`Frozen submission receipt: ${query.data.snapshot_id}. Judging uses this submitted version.`}</p> : null}
    {stages.length ? <StageTracker stages={stages} activeId={active?.id ?? null} timezone={requirements?.timezone ?? "UTC"} /> : null}
    {requirements ? <p className="text-sm text-muted">{stages.length ? "" : t`Submit by `} {stages.length ? "" : `${new Date(requirements.deadline).toLocaleString(formatLocale())}. `}{requirements.budget.remaining_bytes === null ? t`Storage is metered by your host.` : t`${Math.floor(requirements.budget.remaining_bytes / 1024 / 1024)} MiB remaining; ${Math.ceil(requirements.budget.reserved_bytes / 1024 / 1024)} MiB reserved.`}</p> : null}
    {query.data?.id ? <ProgrammeCharges scope={scope} isLeader={Boolean(query.data.allowed_actions.includes("submit"))} /> : null}
    {dirty ? <p role="status" className="text-sm font-semibold text-ink">{t`You have unsaved changes.`}</p> : null}
    {mutation.isError ? <Callout size="panel" tone="danger" lead="Your changes were not saved."
      body={submissionErrorMessage(mutation.error, active)} action={{ label: t`Reload server version`, onClick: () => { setDirty(false); void query.refetch(); } }} /> : null}
    <fieldset disabled={locked || mutation.isPending} className="grid gap-4">
      <Field label={t`Project title`}><input className="desk-input min-h-11" maxLength={200} value={project.title} onChange={e => change({ title: e.target.value })} /></Field>
      <Field label={t`Tagline`}><input className="desk-input min-h-11" maxLength={300} value={project.tagline} onChange={e => change({ tagline: e.target.value })} /></Field>
      {(["problem", "description", "challenges"] as const).map(field => <Field key={field} label={field === "problem" ? t`Problem you are solving` : field === "description" ? t`How it works` : t`Challenges and learning`}>
        <textarea className="desk-input min-h-32" maxLength={field === "description" ? 30000 : 10000} value={project[field]} onChange={e => change({ [field]: e.target.value })} /></Field>)}
      <Field label={t`Technologies`} hint={t`Separate up to 30 tags with commas.`}><input className="desk-input min-h-11" value={project.tech_tags.join(", ")}
        onChange={e => change({ tech_tags: e.target.value.split(",").map(v => v.trim()).filter(Boolean) })} /></Field>
      {([["track_ids", availableTracks, "Tracks"], ["prize_ids", availablePrizes, "Prizes"]] as const).map(([field, choices, label]) => choices.length ?
        <fieldset key={field} className="grid gap-2"><legend className="font-semibold text-ink">{label}</legend>
          {choices.map(choice => <label key={choice.id} className="flex min-h-11 items-center gap-3 text-sm">
            <input type="checkbox" checked={project[field].includes(choice.id)} onChange={event => change({
              [field]: event.target.checked ? [...project[field], choice.id] : project[field].filter(id => id !== choice.id),
            })} />{choice.label}</label>)}</fieldset> : null)}
      {requirements ? <ProjectFormFields requirements={requirements} project={project} change={answers => change({ form_answers: answers })} /> : formFields?.(project.form_answers, answers => change({ form_answers: answers }))}
      {active ? <StageAnswerFields stage={active} project={project} onChange={answers => change({ form_answers: answers })} /> : null}
      {(["ai_declaration", "reuse_declaration"] as const).map(field => <div key={field} className="grid gap-3">
        <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={project[field].used}
          onChange={e => change({ [field]: { ...project[field], used: e.target.checked } })} />{field === "ai_declaration" ? t`We used AI tools` : t`We reused existing code or designs`}</label>
        <Field label={field === "ai_declaration" ? t`AI-use details` : t`Reused work and attribution`}><textarea className="desk-input min-h-24" maxLength={5000}
          value={project[field].details} onChange={e => change({ [field]: { ...project[field], details: e.target.value } })} /></Field>
      </div>)}
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={project.public_requested}
        onChange={e => change({ public_requested: e.target.checked })} />{t`Allow our project description in the public gallery`}</label>
    </fieldset>
    {show.optional ? <p className="text-sm text-muted">{t`Nothing to upload for this stage; a deck or link is optional.`}</p> : null}
    {show.links || project.links.length ? <LinkEditor value={project.links} disabled={locked || mutation.isPending} onChange={links => change({ links })} /> : null}
    {show.files ? <UploadEditor scope={scope} allowedOrigins={uploadOrigins} options={formats} onPendingChange={setUploading} disabled={locked || mutation.isPending || !query.data?.id}
      onUploaded={asset => change({ asset_ids: [...new Set([...project.asset_ids, asset.asset_id])] })} /> : null}
    {!query.data?.id ? <p className="text-sm text-muted">{t`Save your project draft to start uploading files.`}</p> : null}
    <AssetList scope={scope} assetIds={project.asset_ids} publicIds={project.public_asset_ids} onReadinessChange={setFilesReady} disabled={locked || mutation.isPending || uploading}
      onRemove={id => change({ asset_ids: project.asset_ids.filter(v => v !== id), public_asset_ids: project.public_asset_ids.filter(v => v !== id) })}
      onConsent={(id, checked) => change({ public_asset_ids: checked ? [...new Set([...project.public_asset_ids, id])] : project.public_asset_ids.filter(v => v !== id) })} />
    {active ? <StageChecklist stage={active} project={project} /> : null}
    <div className="flex flex-wrap gap-3"><ActionControl action={{ label: active ? t`Submit ${active.name}` : t`Submit project`, disabled: dirty || locked || Boolean(active?.blocked) || uploading || (project.asset_ids.length > 0 && !filesReady) || !project.title.trim() || !query.data?.allowed_actions.includes("submit"),
      disabledReason: uploading ? "Wait for the upload to finish." : !filesReady && project.asset_ids.length ? "Wait for every file to pass validation." : dirty ? "Save your draft before submitting." : undefined, pending: mutation.isPending, onClick: () => void command("submit"),
      confirm: { title: t`Submit this version?`, message: t`This captures your current project, team and ready files for judging.` } }} />
      <ActionControl action={{ label: t`Withdraw submission`, tone: "danger", disabled: uploading || !query.data?.allowed_actions.includes("withdraw"), pending: mutation.isPending,
        onClick: () => void command("withdraw"), confirm: { title: t`Withdraw this submission?`, message: t`Your project will no longer be eligible for judging or public display.` } }} /></div>
  </div>;
  return <FormPageLayout state={{ status: "ready" }} header={{ title: t`Your maker project` }} form={form}
    submit={{ label: t`Save draft`, pending: mutation.isPending, disabled: !dirty || locked || uploading, onClick: () => void command("save") }} />;
}
